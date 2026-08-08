import sharp from "sharp";

// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API, including an image when one is attached.
// Otherwise it runs in simulation mode so the whole publish/schedule/retry flow
// works end-to-end offline.

const API_BASE = process.env.LINKEDIN_API_BASE || "https://api.linkedin.com/v2";
const RESTLI_HEADERS = {
  "X-Restli-Protocol-Version": "2.0.0",
};

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

function authHeaders(contentType?: string): Record<string, string> {
  return {
    Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
    ...(contentType ? { "Content-Type": contentType } : {}),
    ...RESTLI_HEADERS,
  };
}

function decodeDataUri(data: string): Buffer | null {
  const match = data.match(/^data:([^;,]+)?(;base64)?,(.*)$/s);
  if (!match) return null;
  const isBase64 = Boolean(match[2]);
  const payload = match[3] ?? "";
  return isBase64
    ? Buffer.from(payload, "base64")
    : Buffer.from(decodeURIComponent(payload), "utf8");
}

async function loadImageBytes(data: string): Promise<Buffer> {
  const trimmed = data.trim();
  const dataUri = decodeDataUri(trimmed);
  if (dataUri) return dataUri;

  if (trimmed.startsWith("<svg")) {
    return Buffer.from(trimmed, "utf8");
  }

  return Buffer.from(trimmed, "base64");
}

async function imageToPng(image: PublishImage): Promise<Buffer> {
  const input = await loadImageBytes(image.data);
  return sharp(input, { limitInputPixels: false })
    .rotate()
    .resize({
      width: 1200,
      height: 1200,
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
  const body = {
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

  const res = await fetch(`${API_BASE}/assets?action=registerUpload`, {
    method: "POST",
    headers: authHeaders("application/json"),
    body: JSON.stringify(body),
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
    throw new Error("LinkedIn image registration response was missing upload details");
  }

  return { uploadUrl, asset };
}

async function uploadImage(uploadUrl: string, png: Buffer): Promise<void> {
  const res = await fetch(uploadUrl, {
    method: "PUT",
    headers: authHeaders("image/png"),
    body: png,
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`LinkedIn image upload ${res.status}: ${errText.slice(0, 300)}`);
  }
}

function buildPostBody(payload: PublishPayload, authorUrn: string, asset?: string) {
  const hasImage = Boolean(asset);
  return {
    author: authorUrn,
    lifecycleState: "PUBLISHED",
    specificContent: {
      "com.linkedin.ugc.ShareContent": {
        shareCommentary: { text: payload.text },
        shareMediaCategory: hasImage ? "IMAGE" : "NONE",
        ...(hasImage
          ? {
              media: [
                {
                  status: "READY",
                  media: asset,
                  title: { text: "World of Interns" },
                  description: {
                    text:
                      payload.image?.altText ||
                      "World of Interns educational LinkedIn post image",
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
    let asset: string | undefined;
    if (payload.image && status.authorUrn) {
      const png = await imageToPng(payload.image);
      const upload = await registerImageUpload(status.authorUrn);
      await uploadImage(upload.uploadUrl, png);
      asset = upload.asset;
    }

    const res = await fetch(`${API_BASE}/ugcPosts`, {
      method: "POST",
      headers: authHeaders("application/json"),
      body: JSON.stringify(buildPostBody(payload, status.authorUrn ?? "", asset)),
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
      imageAttached: Boolean(asset),
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
