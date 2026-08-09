// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. If image data is supplied, it registers
// and uploads a feed image before creating the post. Otherwise it runs in
// simulation mode so the whole publish/schedule/retry flow works end-to-end
// offline.

import sharp from "sharp";

const API_BASE = process.env.LINKEDIN_API_BASE || "https://api.linkedin.com/v2";
const MAX_IMAGE_SIZE = 1200;

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

function decodeDataUri(dataUri: string): { mediaType: string; bytes: Buffer } | null {
  const match = dataUri.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;

  const mediaType = match[1];
  const isBase64 = Boolean(match[2]);
  const payload = match[3];
  const bytes = isBase64
    ? Buffer.from(payload, "base64")
    : Buffer.from(decodeURIComponent(payload), "utf8");

  return { mediaType, bytes };
}

async function toLinkedInPng(data: string): Promise<Buffer> {
  const trimmed = data.trim();
  const decoded = trimmed.startsWith("data:") ? decodeDataUri(trimmed) : null;
  const input = decoded?.bytes ?? Buffer.from(trimmed, "utf8");

  return sharp(input, { limitInputPixels: false })
    .resize({
      width: MAX_IMAGE_SIZE,
      height: MAX_IMAGE_SIZE,
      fit: "inside",
      withoutEnlargement: true,
    })
    .png()
    .toBuffer();
}

async function registerImageUpload(authorUrn: string): Promise<{
  uploadUrl: string;
  asset: string;
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

  if (!uploadUrl || !asset) {
    throw new Error("LinkedIn image registration response was missing uploadUrl or asset");
  }

  return { uploadUrl, asset };
}

async function uploadImageBytes(uploadUrl: string, bytes: Buffer): Promise<void> {
  const res = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": "image/png",
    },
    body: bytes,
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
      imageAttached: Boolean(payload.image?.data),
    };
  }

  try {
    let mediaAsset: string | null = null;
    if (payload.image?.data && status.authorUrn) {
      const png = await toLinkedInPng(payload.image.data);
      const upload = await registerImageUpload(status.authorUrn);
      await uploadImageBytes(upload.uploadUrl, png);
      mediaAsset = upload.asset;
    }

    const shareContent = mediaAsset
      ? {
          shareCommentary: { text: payload.text },
          shareMediaCategory: "IMAGE",
          media: [
            {
              status: "READY",
              media: mediaAsset,
              title: { text: "World of Interns" },
              description: {
                text:
                  payload.image?.altText?.slice(0, 4086) ||
                  "World of Interns LinkedIn post image",
              },
            },
          ],
        }
      : {
          shareCommentary: { text: payload.text },
          shareMediaCategory: "NONE",
        };

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
