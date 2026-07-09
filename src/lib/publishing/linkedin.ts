// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. If an image is provided, the client first
// registers and uploads a feed image asset, then attaches it to the post.
// Otherwise it runs in simulation mode so the whole publish/schedule/retry flow
// works end-to-end offline.

import sharp from "sharp";

const API_BASE = process.env.LINKEDIN_API_BASE || "https://api.linkedin.com/v2";

export interface LinkedInStatus {
  connected: boolean;
  authorUrn: string | null;
  simulated: boolean;
}

export function linkedInStatus(): LinkedInStatus {
  const connected = Boolean(
    process.env.LINKEDIN_ACCESS_TOKEN && process.env.LINKEDIN_AUTHOR_URN
  );
  return {
    connected,
    authorUrn: process.env.LINKEDIN_AUTHOR_URN || null,
    simulated: !connected,
  };
}

export interface PublishResult {
  ok: boolean;
  postUrl?: string;
  postUrn?: string;
  error?: string;
  simulated: boolean;
  imageAttached?: boolean;
}

export interface LinkedInImagePayload {
  svg: string;
  altText?: string;
}

export interface PublishPayload {
  text: string;
  visibility: "PUBLIC" | "CONNECTIONS";
  image?: LinkedInImagePayload | null;
}

function urnToUrl(urn: string): string {
  // urn:li:share:123 or urn:li:ugcPost:123 -> feed permalink
  return `https://www.linkedin.com/feed/update/${encodeURIComponent(urn)}`;
}

function parseDataUri(dataUri: string): { mimeType: string; data: Buffer } | null {
  const match = dataUri.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;

  const [, mimeType, base64, payload] = match;
  const data = base64
    ? Buffer.from(payload, "base64")
    : Buffer.from(decodeURIComponent(payload), "utf8");
  return { mimeType, data };
}

async function imageToUpload(image: LinkedInImagePayload): Promise<{
  buffer: Buffer;
  contentType: string;
}> {
  const source = image.svg.trim();
  const parsed = source.startsWith("data:") ? parseDataUri(source) : null;
  const mimeType = parsed?.mimeType ?? "image/svg+xml";
  const data = parsed?.data ?? Buffer.from(source, "utf8");

  if (mimeType === "image/png" || mimeType === "image/jpeg" || mimeType === "image/gif") {
    return { buffer: data, contentType: mimeType };
  }

  // LinkedIn feed images should be common raster formats. Convert local SVGs,
  // OpenAI WebP output, and other supported formats to PNG before upload.
  const buffer = await sharp(data).png().toBuffer();
  return { buffer, contentType: "image/png" };
}

async function registerImageUpload(authorUrn: string): Promise<{
  asset: string;
  uploadUrl: string;
}> {
  const res = await fetch(`${API_BASE}/assets?action=registerUpload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": "application/json",
      "X-Restli-Protocol-Version": "2.0.0",
    },
    body: JSON.stringify({
      registerUploadRequest: {
        recipes: ["urn:li:digitalmediaRecipe:feedshare-image"],
        owner: authorUrn,
        serviceRelationships: [
          {
            relationshipType: "OWNER",
            identifier: "urn:li:userGeneratedContent",
          },
        ],
      },
    }),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`LinkedIn image registration ${res.status}: ${errText.slice(0, 300)}`);
  }

  const data = await res.json();
  const value = data?.value;
  const uploadUrl =
    value?.uploadMechanism?.["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]
      ?.uploadUrl;
  const asset = value?.asset;

  if (!asset || !uploadUrl) {
    throw new Error("LinkedIn image registration response did not include upload details.");
  }

  return { asset, uploadUrl };
}

async function uploadImage(uploadUrl: string, buffer: Buffer, contentType: string): Promise<void> {
  const res = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": contentType,
    },
    body: buffer,
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`LinkedIn image upload ${res.status}: ${errText.slice(0, 300)}`);
  }
}

export async function publishToLinkedIn(
  payload: PublishPayload
): Promise<PublishResult> {
  const status = linkedInStatus();

  if (status.simulated) {
    // Deterministic-ish simulated urn so the UI has a link to show.
    const fake = `urn:li:share:sim${Date.now()}`;
    return {
      ok: true,
      postUrn: fake,
      postUrl: urnToUrl(fake),
      simulated: true,
      imageAttached: Boolean(payload.image),
    };
  }

  try {
    let media:
      | Array<{
          status: "READY";
          description?: { text: string };
          media: string;
          title?: { text: string };
        }>
      | undefined;

    if (payload.image) {
      const { asset, uploadUrl } = await registerImageUpload(status.authorUrn!);
      const upload = await imageToUpload(payload.image);
      await uploadImage(uploadUrl, upload.buffer, upload.contentType);
      media = [
        {
          status: "READY",
          description: payload.image.altText ? { text: payload.image.altText } : undefined,
          media: asset,
          title: { text: "World of Interns post image" },
        },
      ];
    }

    const body = {
      author: status.authorUrn,
      lifecycleState: "PUBLISHED",
      specificContent: {
        "com.linkedin.ugc.ShareContent": {
          shareCommentary: { text: payload.text },
          shareMediaCategory: media ? "IMAGE" : "NONE",
          ...(media ? { media } : {}),
        },
      },
      visibility: {
        "com.linkedin.ugc.MemberNetworkVisibility": payload.visibility,
      },
    };

    const res = await fetch(`${API_BASE}/ugcPosts`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      return {
        ok: false,
        error: `LinkedIn API ${res.status}: ${errText.slice(0, 300)}`,
        simulated: false,
      };
    }

    const data = await res.json().catch(() => ({}));
    const urn: string = data?.id || res.headers.get("x-restli-id") || "";
    return {
      ok: true,
      postUrn: urn,
      postUrl: urn ? urnToUrl(urn) : undefined,
      simulated: false,
      imageAttached: Boolean(media),
    };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Network error",
      simulated: false,
    };
  }
}
