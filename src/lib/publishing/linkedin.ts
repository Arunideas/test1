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

export interface LinkedInImagePayload {
  source: string;
  altText?: string | null;
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

function decodeDataUri(dataUri: string): Buffer {
  const match = dataUri.match(/^data:([^;,]+)?((?:;[^,]+)*),(.*)$/s);
  if (!match) throw new Error("Invalid image data URI");
  const [, , params = "", data = ""] = match;
  if (params.includes(";base64")) return Buffer.from(data, "base64");
  return Buffer.from(decodeURIComponent(data), "utf8");
}

async function loadImageBytes(source: string): Promise<Buffer> {
  const trimmed = source.trim();
  if (trimmed.startsWith("<svg")) return Buffer.from(trimmed, "utf8");
  if (trimmed.startsWith("data:image/")) return decodeDataUri(trimmed);
  if (/^https?:\/\//i.test(trimmed)) {
    const res = await fetch(trimmed);
    if (!res.ok) throw new Error(`Image fetch failed (${res.status})`);
    return Buffer.from(await res.arrayBuffer());
  }
  throw new Error("Unsupported image source");
}

async function imageToPngBytes(image: LinkedInImagePayload): Promise<Buffer> {
  const input = await loadImageBytes(image.source);
  return sharp(input, { density: 144 })
    .resize(1200, 1200, {
      fit: "contain",
      background: "#ffffff",
    })
    .flatten({ background: "#ffffff" })
    .png()
    .toBuffer();
}

async function registerLinkedInImageUpload(owner: string): Promise<{
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
    throw new Error(`LinkedIn image registration ${res.status}: ${errText.slice(0, 300)}`);
  }

  const data = await res.json();
  const value = data?.value;
  const upload =
    value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ];
  const asset: string | undefined = value?.asset;
  const uploadUrl: string | undefined = upload?.uploadUrl;
  if (!asset || !uploadUrl) throw new Error("LinkedIn image registration response was incomplete");
  return { asset, uploadUrl };
}

async function uploadLinkedInImage(image: LinkedInImagePayload, owner: string): Promise<string> {
  const png = await imageToPngBytes(image);
  const { asset, uploadUrl } = await registerLinkedInImageUpload(owner);
  const res = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": "image/png",
    },
    body: png,
  });
  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`LinkedIn image upload ${res.status}: ${errText.slice(0, 300)}`);
  }
  return asset;
}

export async function publishToLinkedIn(
  payload: PublishPayload
): Promise<PublishResult> {
  const status = linkedInStatus();
  const hasImage = Boolean(payload.image?.source);

  if (status.simulated) {
    // Deterministic-ish simulated urn so the UI has a link to show.
    const fake = `urn:li:share:sim${Date.now()}`;
    return {
      ok: true,
      postUrn: fake,
      postUrl: urnToUrl(fake),
      simulated: true,
      imageAttached: hasImage,
    };
  }

  try {
    const mediaAsset = payload.image
      ? await uploadLinkedInImage(payload.image, status.authorUrn as string)
      : null;
    const body = {
      author: status.authorUrn,
      lifecycleState: "PUBLISHED",
      specificContent: {
        "com.linkedin.ugc.ShareContent": {
          shareCommentary: { text: payload.text },
          shareMediaCategory: mediaAsset ? "IMAGE" : "NONE",
          ...(mediaAsset
            ? {
                media: [
                  {
                    status: "READY",
                    media: mediaAsset,
                    title: {
                      text: payload.image?.altText || "World of Interns post image",
                    },
                  },
                ],
              }
            : {}),
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
        imageAttached: false,
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
      imageAttached: false,
    };
  }
}
