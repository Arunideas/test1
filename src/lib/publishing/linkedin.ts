// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and a LinkedIn author URN are set, this posts a real
// share via the LinkedIn UGC Posts API. If an image is provided, it registers and
// uploads feed image media first. Otherwise it runs in simulation mode so the
// whole publish/schedule/retry flow works end-to-end offline.

import sharp from "sharp";

const API_BASE = process.env.LINKEDIN_API_BASE || "https://api.linkedin.com/v2";

export interface LinkedInStatus {
  connected: boolean;
  authorUrn: string | null;
  simulated: boolean;
}

function linkedInAuthorUrn(): string | null {
  if (process.env.LINKEDIN_AUTHOR_URN) return process.env.LINKEDIN_AUTHOR_URN;
  if (process.env.LINKEDIN_ORGANIZATION_URN) return process.env.LINKEDIN_ORGANIZATION_URN;
  if (process.env.LINKEDIN_ORGANIZATION_ID) {
    return `urn:li:organization:${process.env.LINKEDIN_ORGANIZATION_ID}`;
  }
  if (process.env.LINKEDIN_MEMBER_ID) return `urn:li:person:${process.env.LINKEDIN_MEMBER_ID}`;
  return null;
}

export function linkedInStatus(): LinkedInStatus {
  const authorUrn = linkedInAuthorUrn();
  const connected = Boolean(process.env.LINKEDIN_ACCESS_TOKEN && authorUrn);
  return {
    connected,
    authorUrn,
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
  image?: {
    data: string;
    altText?: string | null;
  } | null;
}

function urnToUrl(urn: string): string {
  // urn:li:share:123 or urn:li:ugcPost:123 -> feed permalink
  return `https://www.linkedin.com/feed/update/${encodeURIComponent(urn)}`;
}

function parseDataUri(dataUri: string): { contentType: string; bytes: Buffer } | null {
  const match = dataUri.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;
  const [, contentType, base64Flag, data] = match;
  return {
    contentType,
    bytes: base64Flag
      ? Buffer.from(data, "base64")
      : Buffer.from(decodeURIComponent(data), "utf8"),
  };
}

async function imageToPngBuffer(data: string): Promise<Buffer> {
  const trimmed = data.trim();
  let input: Buffer;

  if (trimmed.startsWith("<svg")) {
    input = Buffer.from(trimmed, "utf8");
  } else if (trimmed.startsWith("data:")) {
    const parsed = parseDataUri(trimmed);
    if (!parsed) throw new Error("Unsupported image data URI");
    input = parsed.bytes;
  } else if (/^https?:\/\//i.test(trimmed)) {
    const res = await fetch(trimmed);
    if (!res.ok) throw new Error(`Image fetch ${res.status}: ${await res.text().catch(() => "")}`);
    input = Buffer.from(await res.arrayBuffer());
  } else {
    throw new Error("Unsupported image format");
  }

  return sharp(input).png().toBuffer();
}

async function registerImageUpload(owner: string): Promise<{ asset: string; uploadUrl: string }> {
  const res = await fetch(`${API_BASE}/assets?action=registerUpload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": "application/json",
      "X-Restli-Protocol-Version": "2.0.0",
    },
    body: JSON.stringify({
      registerUploadRequest: {
        owner,
        recipes: ["urn:li:digitalmediaRecipe:feedshare-image"],
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

  const data = await res.json();
  const value = data?.value;
  const uploadUrl =
    value?.uploadMechanism?.["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]
      ?.uploadUrl;
  const asset = value?.asset;
  if (!uploadUrl || !asset) throw new Error("LinkedIn image register response was incomplete");
  return { asset, uploadUrl };
}

async function uploadImage(uploadUrl: string, bytes: Buffer): Promise<void> {
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
  const hasImage = Boolean(payload.image?.data);

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
    let imageAsset: string | null = null;
    if (payload.image?.data && status.authorUrn) {
      const png = await imageToPngBuffer(payload.image.data);
      const upload = await registerImageUpload(status.authorUrn);
      await uploadImage(upload.uploadUrl, png);
      imageAsset = upload.asset;
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
                    description: {
                      text: payload.image?.altText || "World of Interns post image",
                    },
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
