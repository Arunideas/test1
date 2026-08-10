// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// text/image share via the LinkedIn UGC Posts API. Otherwise it runs in
// simulation mode so the whole publish/schedule/retry flow works end-to-end
// offline.

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

function parseDataUri(data: string): { mediaType: string; buffer: Buffer } | null {
  const match = data.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;
  const [, mediaType, isBase64, payload] = match;
  return {
    mediaType,
    buffer: Buffer.from(
      isBase64 ? payload : decodeURIComponent(payload),
      isBase64 ? "base64" : "utf8"
    ),
  };
}

async function imageToLinkedInPng(image: PublishImage): Promise<Buffer> {
  const trimmed = image.data.trim();
  const parsed = parseDataUri(trimmed);
  const input = parsed?.buffer ?? Buffer.from(trimmed, "utf8");

  // LinkedIn feed images are safest as PNG/JPEG bytes. Local images are SVG,
  // and OpenAI images may arrive as data URIs, so normalize every attachment.
  return sharp(input, parsed ? { failOn: "none" } : undefined)
    .resize(1200, 1200, { fit: "inside", withoutEnlargement: true })
    .png()
    .toBuffer();
}

async function uploadImageToLinkedIn(
  image: PublishImage,
  authorUrn: string
): Promise<{ asset: string; altText?: string | null }> {
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

  const registered = await registerRes.json();
  const value = registered?.value;
  const asset: string | undefined = value?.asset;
  const uploadUrl: string | undefined =
    value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]?.uploadUrl;

  if (!asset || !uploadUrl) {
    throw new Error("LinkedIn image register response did not include upload details");
  }

  const bytes = await imageToLinkedInPng(image);
  const uploadRes = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": "image/png",
    },
    body: bytes,
  });

  if (!uploadRes.ok) {
    const errText = await uploadRes.text().catch(() => "");
    throw new Error(`LinkedIn image upload ${uploadRes.status}: ${errText.slice(0, 300)}`);
  }

  return { asset, altText: image.altText };
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
    const uploaded = payload.image
      ? await uploadImageToLinkedIn(payload.image, status.authorUrn as string)
      : null;
    const body = {
      author: status.authorUrn,
      lifecycleState: "PUBLISHED",
      specificContent: {
        "com.linkedin.ugc.ShareContent": {
          shareCommentary: { text: payload.text },
          shareMediaCategory: uploaded ? "IMAGE" : "NONE",
          ...(uploaded
            ? {
                media: [
                  {
                    status: "READY",
                    description: uploaded.altText
                      ? { text: uploaded.altText }
                      : undefined,
                    media: uploaded.asset,
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
      imageAttached: Boolean(uploaded),
    };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Network error",
      simulated: false,
    };
  }
}
