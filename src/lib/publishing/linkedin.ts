import sharp from "sharp";

// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// text or image share via the LinkedIn UGC Posts API. Otherwise it runs in
// simulation mode so the whole publish/schedule/retry flow works end-to-end
// offline.

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

export interface PublishImagePayload {
  data: string;
  altText: string;
}

export interface PublishPayload {
  text: string;
  visibility: "PUBLIC" | "CONNECTIONS";
  image?: PublishImagePayload | null;
}

function urnToUrl(urn: string): string {
  // urn:li:share:123 or urn:li:ugcPost:123 -> feed permalink
  return `https://www.linkedin.com/feed/update/${encodeURIComponent(urn)}`;
}

function decodeImageData(data: string): { bytes: Buffer; contentType: string } {
  const match = data.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) {
    return {
      bytes: Buffer.from(data, "utf8"),
      contentType: data.trimStart().startsWith("<svg")
        ? "image/svg+xml"
        : "application/octet-stream",
    };
  }

  const [, contentType, base64, body] = match;
  return {
    bytes: Buffer.from(base64 ? body : decodeURIComponent(body), base64 ? "base64" : "utf8"),
    contentType,
  };
}

async function toLinkedInPng(data: string): Promise<Buffer> {
  const { bytes } = decodeImageData(data);
  return sharp(bytes)
    .resize({
      width: 1200,
      height: 1200,
      fit: "inside",
      withoutEnlargement: true,
    })
    .png()
    .toBuffer();
}

interface RegisteredImageUpload {
  asset: string;
  uploadUrl: string;
  headers: Record<string, string>;
}

async function registerImageUpload(
  authorUrn: string
): Promise<RegisteredImageUpload> {
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
    throw new Error(`LinkedIn image register ${res.status}: ${errText.slice(0, 300)}`);
  }

  const data = await res.json();
  const value = data?.value;
  const request =
    value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ];
  if (!value?.asset || !request?.uploadUrl) {
    throw new Error("LinkedIn image register response did not include an upload URL");
  }

  return {
    asset: value.asset,
    uploadUrl: request.uploadUrl,
    headers: request.headers ?? {},
  };
}

async function uploadImage(
  authorUrn: string,
  image: PublishImagePayload
): Promise<string> {
  const upload = await registerImageUpload(authorUrn);
  const png = await toLinkedInPng(image.data);
  const res = await fetch(upload.uploadUrl, {
    method: "PUT",
    headers: {
      ...upload.headers,
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": "image/png",
    },
    body: png,
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`LinkedIn image upload ${res.status}: ${errText.slice(0, 300)}`);
  }

  return upload.asset;
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
    const imageAsset = payload.image
      ? await uploadImage(status.authorUrn as string, payload.image)
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
                    description: { text: payload.image?.altText ?? "" },
                    media: imageAsset,
                    title: {
                      text: (payload.image?.altText || "World of Interns image").slice(0, 70),
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
