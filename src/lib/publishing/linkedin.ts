// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// text or image share via the LinkedIn UGC Posts API. Otherwise it runs in
// simulation mode so the whole publish/schedule/retry flow works end-to-end
// offline.

import sharp from "sharp";

const API_BASE = process.env.LINKEDIN_API_BASE || "https://api.linkedin.com/v2";
const PNG_MIME = "image/png";

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
  imageAttached: boolean;
}

export interface PublishImage {
  data: string;
  altText?: string | null;
}

export interface PublishPayload {
  text: string;
  visibility: "PUBLIC" | "CONNECTIONS";
  image?: PublishImage | null;
}

function urnToUrl(urn: string): string {
  // urn:li:share:123 or urn:li:ugcPost:123 -> feed permalink
  return `https://www.linkedin.com/feed/update/${encodeURIComponent(urn)}`;
}

function authHeaders(): Record<string, string> {
  return {
    Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
    "X-Restli-Protocol-Version": "2.0.0",
  };
}

function parseDataUri(input: string): { mime: string; buffer: Buffer } | null {
  const match = input.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;
  const [, mime, base64, payload] = match;
  const data = base64
    ? Buffer.from(payload, "base64")
    : Buffer.from(decodeURIComponent(payload), "utf8");
  return { mime, buffer: data };
}

async function imageDataToBuffer(data: string): Promise<Buffer> {
  const trimmed = data.trim();
  const dataUri = parseDataUri(trimmed);
  if (dataUri) return dataUri.buffer;

  if (/^https?:\/\//i.test(trimmed)) {
    const res = await fetch(trimmed);
    if (!res.ok) throw new Error(`Image fetch failed ${res.status}`);
    return Buffer.from(await res.arrayBuffer());
  }

  return Buffer.from(trimmed, "utf8");
}

async function imageDataToPng(data: string): Promise<Buffer> {
  const source = await imageDataToBuffer(data);
  return sharp(source, { limitInputPixels: 1200 * 1200 * 8 })
    .resize(1200, 1200, { fit: "inside", withoutEnlargement: true })
    .png()
    .toBuffer();
}

async function registerImageUpload(owner: string): Promise<{
  asset: string;
  uploadUrl: string;
}> {
  const res = await fetch(`${API_BASE}/assets?action=registerUpload`, {
    method: "POST",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      registerUploadRequest: {
        recipes: ["urn:li:digitalmediaRecipe:feedshare-image"],
        owner,
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
    throw new Error(`LinkedIn image register ${res.status}: ${errText.slice(0, 300)}`);
  }

  const data = (await res.json()) as {
    value?: {
      asset?: string;
      uploadMechanism?: {
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"?: {
          uploadUrl?: string;
        };
      };
    };
  };
  const asset = data.value?.asset;
  const uploadUrl =
    data.value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]?.uploadUrl;

  if (!asset || !uploadUrl) {
    throw new Error("LinkedIn image register response missing asset or upload URL");
  }

  return { asset, uploadUrl };
}

async function uploadImage(uploadUrl: string, png: Buffer): Promise<void> {
  const res = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": PNG_MIME,
      "Content-Length": String(png.length),
    },
    body: png,
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
  const imageAttached = Boolean(payload.image?.data);

  if (status.simulated) {
    // Deterministic-ish simulated urn so the UI has a link to show.
    const fake = `urn:li:share:sim${Date.now()}`;
    return {
      ok: true,
      postUrn: fake,
      postUrl: urnToUrl(fake),
      simulated: true,
      imageAttached,
    };
  }

  try {
    let media:
      | Array<{
          status: "READY";
          media: string;
          title?: { text: string };
          description?: { text: string };
        }>
      | undefined;

    if (payload.image?.data && status.authorUrn) {
      const png = await imageDataToPng(payload.image.data);
      const upload = await registerImageUpload(status.authorUrn);
      await uploadImage(upload.uploadUrl, png);
      const altText = payload.image.altText?.trim();
      media = [
        {
          status: "READY",
          media: upload.asset,
          ...(altText
            ? {
                title: { text: "World of Interns post image" },
                description: { text: altText },
              }
            : {}),
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
        ...authHeaders(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      return {
        ok: false,
        error: `LinkedIn API ${res.status}: ${errText.slice(0, 300)}`,
        simulated: false,
        imageAttached,
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
      imageAttached,
    };
  }
}
