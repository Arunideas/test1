// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. If an image is supplied, the client
// uploads it as feed image media first. Otherwise it runs in simulation mode so
// the whole publish/schedule/retry flow works end-to-end offline.

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
  altText: string;
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

interface UploadableImage {
  bytes: Buffer;
  contentType: "image/png" | "image/jpeg";
}

async function imageToUploadable(image: LinkedInImagePayload): Promise<UploadableImage> {
  const source = image.data.trim();
  if (source.startsWith("<svg")) {
    return {
      bytes: await sharp(Buffer.from(source, "utf8")).png().toBuffer(),
      contentType: "image/png",
    };
  }

  const dataUri = source.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (dataUri) {
    const [, mime, isBase64, payload] = dataUri;
    const raw = isBase64
      ? Buffer.from(payload, "base64")
      : Buffer.from(decodeURIComponent(payload), "utf8");
    if (mime === "image/png") return { bytes: raw, contentType: "image/png" };
    if (mime === "image/jpeg" || mime === "image/jpg") {
      return { bytes: raw, contentType: "image/jpeg" };
    }
    if (mime === "image/svg+xml") {
      return { bytes: await sharp(raw).png().toBuffer(), contentType: "image/png" };
    }
  }

  if (/^https?:\/\//i.test(source)) {
    const res = await fetch(source);
    if (!res.ok) throw new Error(`Image fetch failed: ${res.status}`);
    const contentType = res.headers.get("content-type") || "";
    const raw = Buffer.from(await res.arrayBuffer());
    if (contentType.includes("image/png")) return { bytes: raw, contentType: "image/png" };
    if (contentType.includes("image/jpeg") || contentType.includes("image/jpg")) {
      return { bytes: raw, contentType: "image/jpeg" };
    }
    if (contentType.includes("image/svg+xml")) {
      return { bytes: await sharp(raw).png().toBuffer(), contentType: "image/png" };
    }
  }

  throw new Error("Unsupported LinkedIn image format");
}

async function registerAndUploadImage(image: LinkedInImagePayload): Promise<string> {
  const authorUrn = process.env.LINKEDIN_AUTHOR_URN;
  if (!authorUrn) throw new Error("LINKEDIN_AUTHOR_URN is required for image upload");

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
    throw new Error(`LinkedIn image registration ${registerRes.status}: ${errText.slice(0, 300)}`);
  }

  const registered = await registerRes.json();
  const asset: string | undefined = registered?.value?.asset;
  const uploadUrl: string | undefined =
    registered?.value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]?.uploadUrl;

  if (!asset || !uploadUrl) {
    throw new Error("LinkedIn image registration response missing asset or upload URL");
  }

  const uploadable = await imageToUploadable(image);
  const uploadRes = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": uploadable.contentType,
    },
    body: uploadable.bytes,
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
    const imageAsset = payload.image ? await registerAndUploadImage(payload.image) : null;
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
    };
  }
}
