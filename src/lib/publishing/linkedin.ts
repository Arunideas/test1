// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. Otherwise it runs in simulation mode so
// the whole publish/schedule/retry flow works end-to-end offline.

import sharp from "sharp";
import { readDb } from "../db";
import type { GeneratedImage } from "../types";

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

export interface PublishPayload {
  text: string;
  visibility: "PUBLIC" | "CONNECTIONS";
  imageId?: string | null;
}

function urnToUrl(urn: string): string {
  // urn:li:share:123 or urn:li:ugcPost:123 -> feed permalink
  return `https://www.linkedin.com/feed/update/${encodeURIComponent(urn)}`;
}

function parseDataUri(dataUri: string): Buffer | null {
  const match = dataUri.match(/^data:([^;,]+)?(;base64)?,(.*)$/s);
  if (!match) return null;
  const encoded = match[3] ?? "";
  return match[2]
    ? Buffer.from(encoded, "base64")
    : Buffer.from(decodeURIComponent(encoded), "utf8");
}

async function sourceToBuffer(source: string): Promise<Buffer> {
  const trimmed = source.trim();
  if (trimmed.startsWith("data:")) {
    const parsed = parseDataUri(trimmed);
    if (!parsed) throw new Error("Invalid generated image data URI");
    return parsed;
  }

  if (/^https?:\/\//i.test(trimmed)) {
    const res = await fetch(trimmed);
    if (!res.ok) {
      throw new Error(`Image fetch failed with ${res.status}`);
    }
    return Buffer.from(await res.arrayBuffer());
  }

  return Buffer.from(trimmed, "utf8");
}

async function generatedImageToPng(image: GeneratedImage): Promise<Buffer> {
  const input = await sourceToBuffer(image.svg);
  return sharp(input, { animated: false, failOn: "none" })
    .flatten({ background: "#ffffff" })
    .png()
    .toBuffer();
}

async function resolveGeneratedImage(imageId: string): Promise<GeneratedImage> {
  const db = await readDb();
  const image = db.images.find((i) => i.id === imageId);
  if (!image) throw new Error(`Generated image not found: ${imageId}`);
  return image;
}

async function uploadLinkedInImage(
  image: GeneratedImage,
  authorUrn: string,
  accessToken: string
): Promise<string> {
  const registerBody = {
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
  };

  const registerRes = await fetch(`${API_BASE}/assets?action=registerUpload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
      "X-Restli-Protocol-Version": "2.0.0",
    },
    body: JSON.stringify(registerBody),
  });

  if (!registerRes.ok) {
    const errText = await registerRes.text().catch(() => "");
    throw new Error(`LinkedIn image register ${registerRes.status}: ${errText.slice(0, 300)}`);
  }

  const data = await registerRes.json();
  const value = data?.value;
  const uploadUrl =
    value?.uploadMechanism?.["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]
      ?.uploadUrl;
  const asset: string | undefined = value?.asset;
  if (!uploadUrl || !asset) {
    throw new Error("LinkedIn image register response did not include an upload URL and asset");
  }

  const png = await generatedImageToPng(image);
  const uploadRes = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "image/png",
    },
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
      imageAttached: Boolean(payload.imageId),
    };
  }

  try {
    const accessToken = process.env.LINKEDIN_ACCESS_TOKEN;
    let imageAsset: string | null = null;
    if (payload.imageId) {
      if (!accessToken || !status.authorUrn) {
        return {
          ok: false,
          error: "LinkedIn credentials are required to upload an image",
          simulated: false,
          imageAttached: false,
        };
      }
      const image = await resolveGeneratedImage(payload.imageId);
      imageAsset = await uploadLinkedInImage(image, status.authorUrn, accessToken);
    }

    const body = {
      author: status.authorUrn,
      lifecycleState: "PUBLISHED",
      specificContent: {
        "com.linkedin.ugc.ShareContent": {
          shareCommentary: { text: payload.text },
          shareMediaCategory: imageAsset ? "IMAGE" : "NONE",
          ...(imageAsset
            ? {
                media: [
                  {
                    status: "READY",
                    media: imageAsset,
                    title: { text: "World of Interns post image" },
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
      };
    }

    const data = await res.json().catch(() => ({}));
    const urn: string = data?.id || res.headers.get("x-restli-id") || "";
    return {
      ok: true,
      postUrn: urn,
      postUrl: urn ? urnToUrl(urn) : undefined,
      simulated: false,
      imageAttached: Boolean(imageAsset),
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
