// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. If an image is supplied, it is converted
// to an opaque PNG, uploaded as a feed image asset, and attached to the post.
// Otherwise the client runs in simulation mode so the whole publish/schedule/
// retry flow works end-to-end offline.

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
  data: string;
  altText?: string | null;
  title?: string | null;
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

async function dataToBuffer(data: string): Promise<Buffer> {
  const trimmed = data.trim();

  if (trimmed.startsWith("data:")) {
    const comma = trimmed.indexOf(",");
    if (comma === -1) throw new Error("Invalid image data URI");
    const metadata = trimmed.slice(0, comma);
    const payload = trimmed.slice(comma + 1);
    return metadata.endsWith(";base64")
      ? Buffer.from(payload, "base64")
      : Buffer.from(decodeURIComponent(payload), "utf8");
  }

  if (/^https?:\/\//i.test(trimmed)) {
    const res = await fetch(trimmed);
    if (!res.ok) {
      throw new Error(`Image fetch failed ${res.status}: ${await res.text().catch(() => "")}`);
    }
    return Buffer.from(await res.arrayBuffer());
  }

  if (trimmed.startsWith("<svg")) {
    return Buffer.from(trimmed, "utf8");
  }

  throw new Error("Unsupported image data format");
}

async function toPngBytes(image: LinkedInImagePayload): Promise<Buffer> {
  const input = await dataToBuffer(image.data);
  return sharp(input)
    .flatten({ background: "#ffffff" })
    .png()
    .toBuffer();
}

async function registerAndUploadImage(
  image: LinkedInImagePayload,
  authorUrn: string
): Promise<{ asset: string }> {
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

  const register = await fetch(`${API_BASE}/assets?action=registerUpload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": "application/json",
      "X-Restli-Protocol-Version": "2.0.0",
    },
    body: JSON.stringify(registerBody),
  });

  if (!register.ok) {
    const errText = await register.text().catch(() => "");
    throw new Error(`LinkedIn image register ${register.status}: ${errText.slice(0, 300)}`);
  }

  const data = await register.json();
  const value = data?.value;
  const asset: string | undefined = value?.asset;
  const uploadUrl: string | undefined =
    value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]?.uploadUrl;

  if (!asset || !uploadUrl) {
    throw new Error("LinkedIn image register response did not include an upload URL");
  }

  const bytes = await toPngBytes(image);
  const upload = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": "application/octet-stream",
    },
    body: bytes,
  });

  if (!upload.ok) {
    const errText = await upload.text().catch(() => "");
    throw new Error(`LinkedIn image upload ${upload.status}: ${errText.slice(0, 300)}`);
  }

  return { asset };
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
    const uploadedImage =
      payload.image && status.authorUrn
        ? await registerAndUploadImage(payload.image, status.authorUrn)
        : null;

    const body = {
      author: status.authorUrn,
      lifecycleState: "PUBLISHED",
      specificContent: {
        "com.linkedin.ugc.ShareContent": {
          shareCommentary: { text: payload.text },
          shareMediaCategory: uploadedImage ? "IMAGE" : "NONE",
          ...(uploadedImage
            ? {
                media: [
                  {
                    status: "READY",
                    description: payload.image?.altText
                      ? { text: payload.image.altText }
                      : undefined,
                    media: uploadedImage.asset,
                    title: { text: payload.image?.title || "World of Interns" },
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
      imageAttached: Boolean(uploadedImage),
    };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Network error",
      simulated: false,
    };
  }
}
