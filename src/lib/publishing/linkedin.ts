// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. If an image is provided, it first uploads
// the image as LinkedIn media and attaches it to the share. Otherwise it runs in
// simulation mode so the whole publish/schedule/retry flow works end-to-end
// offline.

import sharp from "sharp";
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
  image?: GeneratedImage | null;
}

function urnToUrl(urn: string): string {
  // urn:li:share:123 or urn:li:ugcPost:123 -> feed permalink
  return `https://www.linkedin.com/feed/update/${encodeURIComponent(urn)}`;
}

function parseDataUri(input: string): { mime: string; data: Buffer } | null {
  const match = input.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;
  const [, mime, base64, data] = match;
  return {
    mime,
    data: Buffer.from(data, base64 ? "base64" : "utf8"),
  };
}

async function toUploadableImage(
  image: GeneratedImage
): Promise<{ bytes: Buffer; contentType: string }> {
  const source = parseDataUri(image.svg);
  const contentType = source?.mime || "image/svg+xml";
  const bytes = source?.data || Buffer.from(image.svg, "utf8");

  if (contentType === "image/png" || contentType === "image/jpeg" || contentType === "image/gif") {
    return { bytes, contentType };
  }

  if (contentType === "image/svg+xml") {
    return {
      bytes: await sharp(bytes).png().toBuffer(),
      contentType: "image/png",
    };
  }

  throw new Error(`Unsupported image type for LinkedIn upload: ${contentType}`);
}

async function uploadLinkedInImage(image: GeneratedImage): Promise<string> {
  const owner = process.env.LINKEDIN_AUTHOR_URN;
  if (!owner) throw new Error("LINKEDIN_AUTHOR_URN is required for image upload");

  const registerBody = {
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
  };

  const registerRes = await fetch(`${API_BASE}/assets?action=registerUpload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
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
    value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]?.uploadUrl;
  const asset: string | undefined = value?.asset;
  if (!uploadUrl || !asset) {
    throw new Error("LinkedIn image register response did not include uploadUrl and asset");
  }

  const upload = await toUploadableImage(image);
  const uploadRes = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": upload.contentType,
      "Content-Length": String(upload.bytes.length),
    },
    body: upload.bytes,
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
      imageAttached: Boolean(payload.image),
    };
  }

  try {
    const imageAsset = payload.image ? await uploadLinkedInImage(payload.image) : null;
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
                    description: { text: payload.image?.altText || "World of Interns post image" },
                    media: imageAsset,
                    title: { text: "World of Interns" },
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
