// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. If image data is supplied, the image is
// uploaded first and attached to the post. Otherwise it runs in simulation mode
// so the whole publish/schedule/retry flow works end-to-end offline.

const API_BASE = process.env.LINKEDIN_API_BASE || "https://api.linkedin.com/v2";
const UPLOAD_MECHANISM =
  "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest";
const LINKEDIN_IMAGE_MIME_TYPES = new Set([
  "image/gif",
  "image/jpeg",
  "image/png",
]);

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
  title?: string;
}

export interface PublishPayload {
  text: string;
  visibility: "PUBLIC" | "CONNECTIONS";
  image?: PublishImage;
}

function urnToUrl(urn: string): string {
  // urn:li:share:123 or urn:li:ugcPost:123 -> feed permalink
  return `https://www.linkedin.com/feed/update/${encodeURIComponent(urn)}`;
}

function parseDataUri(data: string): { mimeType: string; buffer: Buffer } | null {
  const match = data.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;
  const [, mimeType, base64, payload] = match;
  return {
    mimeType: mimeType.toLowerCase(),
    buffer: Buffer.from(
      decodeURIComponent(payload),
      base64 ? "base64" : "utf8"
    ),
  };
}

async function loadImageData(data: string): Promise<{ mimeType: string; buffer: Buffer }> {
  const trimmed = data.trim();
  const parsed = parseDataUri(trimmed);
  if (parsed) return parsed;

  if (/^https?:\/\//i.test(trimmed)) {
    const res = await fetch(trimmed);
    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`Image download ${res.status}: ${errText.slice(0, 300)}`);
    }
    const mimeType = (res.headers.get("content-type") || "application/octet-stream")
      .split(";")[0]
      .toLowerCase();
    return {
      mimeType,
      buffer: Buffer.from(await res.arrayBuffer()),
    };
  }

  if (trimmed.startsWith("<svg")) {
    return { mimeType: "image/svg+xml", buffer: Buffer.from(trimmed, "utf8") };
  }

  throw new Error("Unsupported image data. Expected SVG, data URI, or URL.");
}

async function prepareImageForLinkedIn(
  image: PublishImage
): Promise<{ mimeType: string; buffer: Buffer }> {
  const loaded = await loadImageData(image.data);
  if (LINKEDIN_IMAGE_MIME_TYPES.has(loaded.mimeType)) return loaded;

  if (loaded.mimeType === "image/svg+xml") {
    const sharp = (await import("sharp")).default;
    return {
      mimeType: "image/png",
      buffer: await sharp(loaded.buffer)
        .resize(1200, 1200, {
          fit: "contain",
          background: "#f3efe7",
          withoutEnlargement: true,
        })
        .png()
        .toBuffer(),
    };
  }

  throw new Error(`Unsupported LinkedIn image MIME type: ${loaded.mimeType}`);
}

async function uploadImageToLinkedIn(
  image: PublishImage,
  authorUrn: string
): Promise<string> {
  const prepared = await prepareImageForLinkedIn(image);
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
    throw new Error(
      `LinkedIn image upload registration ${registerRes.status}: ${errText.slice(0, 300)}`
    );
  }

  const registered = await registerRes.json();
  const asset: string | undefined = registered?.value?.asset;
  const uploadUrl: string | undefined =
    registered?.value?.uploadMechanism?.[UPLOAD_MECHANISM]?.uploadUrl;

  if (!asset || !uploadUrl) {
    throw new Error("LinkedIn image upload registration did not return an asset and upload URL.");
  }

  const uploadRes = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": prepared.mimeType,
    },
    body: prepared.buffer as unknown as BodyInit,
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
    const imageAsset = payload.image
      ? await uploadImageToLinkedIn(payload.image, status.authorUrn as string)
      : null;
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
                    title: {
                      text: payload.image?.title || "World of Interns",
                    },
                    description: payload.image?.altText
                      ? { text: payload.image.altText }
                      : undefined,
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
    };
  }
}
