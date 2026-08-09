// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. Otherwise it runs in simulation mode so
// the whole publish/schedule/retry flow works end-to-end offline.

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

export interface PublishImage {
  data: string;
  altText?: string;
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

function bearerHeaders(extra?: Record<string, string>): HeadersInit {
  return {
    Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
    ...extra,
  };
}

function parseDataUri(data: string): { mime: string; bytes: Buffer } | null {
  const match = data.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;
  const [, mime, base64, body] = match;
  const bytes = base64
    ? Buffer.from(body, "base64")
    : Buffer.from(decodeURIComponent(body), "utf8");
  return { mime, bytes };
}

async function imageToPngBuffer(image: PublishImage): Promise<Buffer> {
  const data = image.data.trim();

  if (data.startsWith("<svg")) {
    return sharp(Buffer.from(data), { density: 144 })
      .resize({ width: 1200, height: 1200, fit: "inside", withoutEnlargement: true })
      .png()
      .toBuffer();
  }

  const parsed = parseDataUri(data);
  if (parsed) {
    return sharp(parsed.bytes, { density: parsed.mime === "image/svg+xml" ? 144 : undefined })
      .resize({ width: 1200, height: 1200, fit: "inside", withoutEnlargement: true })
      .png()
      .toBuffer();
  }

  if (/^https?:\/\//i.test(data)) {
    const res = await fetch(data);
    if (!res.ok) {
      throw new Error(`Image fetch failed: ${res.status}`);
    }
    const bytes = Buffer.from(await res.arrayBuffer());
    return sharp(bytes)
      .resize({ width: 1200, height: 1200, fit: "inside", withoutEnlargement: true })
      .png()
      .toBuffer();
  }

  throw new Error("Unsupported LinkedIn image data");
}

async function uploadImage(image: PublishImage, owner: string): Promise<string> {
  const registerRes = await fetch(`${API_BASE}/assets?action=registerUpload`, {
    method: "POST",
    headers: bearerHeaders({
      "Content-Type": "application/json",
      "X-Restli-Protocol-Version": "2.0.0",
    }),
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
        supportedUploadMechanism: ["SYNCHRONOUS_UPLOAD"],
      },
    }),
  });

  if (!registerRes.ok) {
    const errText = await registerRes.text().catch(() => "");
    throw new Error(`LinkedIn image registration ${registerRes.status}: ${errText.slice(0, 300)}`);
  }

  const registerData = await registerRes.json();
  const value = registerData?.value;
  const uploadMechanism =
    value?.uploadMechanism?.["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"];
  const uploadUrl: string | undefined = uploadMechanism?.uploadUrl;
  const asset: string | undefined = value?.asset;

  if (!uploadUrl || !asset) {
    throw new Error("LinkedIn image registration response missing upload URL or asset");
  }

  const png = await imageToPngBuffer(image);
  const uploadRes = await fetch(uploadUrl, {
    method: "PUT",
    headers: bearerHeaders({
      "Content-Type": "image/png",
    }),
    body: png,
  });

  if (!uploadRes.ok) {
    const errText = await uploadRes.text().catch(() => "");
    throw new Error(`LinkedIn image upload ${uploadRes.status}: ${errText.slice(0, 300)}`);
  }

  return asset;
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
      imageAttached: Boolean(payload.image?.data),
    };
  }

  try {
    let mediaAsset: string | null = null;
    if (payload.image?.data && status.authorUrn) {
      mediaAsset = await uploadImage(payload.image, status.authorUrn);
    }

    const shareContent: Record<string, unknown> = {
      shareCommentary: { text: payload.text },
      shareMediaCategory: mediaAsset ? "IMAGE" : "NONE",
    };

    if (mediaAsset) {
      shareContent.media = [
        {
          status: "READY",
          description: { text: payload.image?.altText || "World of Interns post image" },
          media: mediaAsset,
          title: { text: payload.image?.altText || "World of Interns" },
        },
      ];
    }

    const body = {
      author: status.authorUrn,
      lifecycleState: "PUBLISHED",
      specificContent: {
        "com.linkedin.ugc.ShareContent": shareContent,
      },
      visibility: {
        "com.linkedin.ugc.MemberNetworkVisibility": payload.visibility,
      },
    };

    const res = await fetch(`${API_BASE}/ugcPosts`, {
      method: "POST",
      headers: {
        ...bearerHeaders(),
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
      imageAttached: Boolean(mediaAsset),
    };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Network error",
      simulated: false,
    };
  }
}
