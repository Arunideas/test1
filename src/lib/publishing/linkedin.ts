// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. Image posts first register and upload a
// PNG asset, then attach it to the UGC post. Otherwise the client runs in
// simulation mode so the whole publish/schedule/retry flow works end-to-end.

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

export interface PublishPayload {
  text: string;
  visibility: "PUBLIC" | "CONNECTIONS";
  image?: {
    data: string;
    altText?: string;
    title?: string;
  } | null;
}

function urnToUrl(urn: string): string {
  // urn:li:share:123 or urn:li:ugcPost:123 -> feed permalink
  return `https://www.linkedin.com/feed/update/${encodeURIComponent(urn)}`;
}

function dataUriToBuffer(dataUri: string): Buffer | null {
  const match = dataUri.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;

  const [, , isBase64, data] = match;
  return isBase64
    ? Buffer.from(data, "base64")
    : Buffer.from(decodeURIComponent(data), "utf8");
}

async function imageDataToPng(data: string): Promise<Buffer> {
  const trimmed = data.trim();
  const dataUriBuffer = dataUriToBuffer(trimmed);
  const input = dataUriBuffer ?? Buffer.from(trimmed, "utf8");

  return sharp(input, { limitInputPixels: 20_000_000 })
    .resize(1200, 1200, { fit: "inside", withoutEnlargement: true })
    .png()
    .toBuffer();
}

async function uploadImageAsset(
  image: NonNullable<PublishPayload["image"]>,
  ownerUrn: string
): Promise<{ ok: true; asset: string } | { ok: false; error: string }> {
  const token = process.env.LINKEDIN_ACCESS_TOKEN;
  const registerBody = {
    registerUploadRequest: {
      recipes: ["urn:li:digitalmediaRecipe:feedshare-image"],
      owner: ownerUrn,
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
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-Restli-Protocol-Version": "2.0.0",
    },
    body: JSON.stringify(registerBody),
  });

  if (!registerRes.ok) {
    const errText = await registerRes.text().catch(() => "");
    return {
      ok: false,
      error: `LinkedIn image registration ${registerRes.status}: ${errText.slice(0, 300)}`,
    };
  }

  const registered = await registerRes.json().catch(() => ({}));
  const value = registered?.value;
  const uploadUrl =
    value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]?.uploadUrl;
  const asset = value?.asset;

  if (!uploadUrl || !asset) {
    return {
      ok: false,
      error: "LinkedIn image registration did not return an upload URL and asset URN",
    };
  }

  const png = await imageDataToPng(image.data);
  const uploadRes = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "image/png",
    },
    body: png,
  });

  if (!uploadRes.ok) {
    const errText = await uploadRes.text().catch(() => "");
    return {
      ok: false,
      error: `LinkedIn image upload ${uploadRes.status}: ${errText.slice(0, 300)}`,
    };
  }

  return { ok: true, asset };
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
    const uploadedImage = payload.image
      ? await uploadImageAsset(payload.image, status.authorUrn!)
      : null;

    if (uploadedImage && !uploadedImage.ok) {
      return {
        ok: false,
        error: uploadedImage.error,
        simulated: false,
      };
    }

    const media =
      uploadedImage?.ok && uploadedImage.asset
        ? [
            {
              status: "READY",
              description: {
                text:
                  payload.image?.altText ||
                  "World of Interns LinkedIn post image",
              },
              media: uploadedImage.asset,
              title: {
                text: payload.image?.title || "World of Interns",
              },
            },
          ]
        : undefined;

    const body = {
      author: status.authorUrn,
      lifecycleState: "PUBLISHED",
      specificContent: {
        "com.linkedin.ugc.ShareContent": {
          shareCommentary: { text: payload.text },
          shareMediaCategory: media ? "IMAGE" : "NONE",
          ...(media ? { media } : {}),
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
      imageAttached: Boolean(media),
    };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Network error",
      simulated: false,
    };
  }
}
