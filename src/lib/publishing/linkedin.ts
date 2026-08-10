// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. If an image is provided, it first
// registers and uploads a feed image asset. Otherwise it runs in simulation
// mode so the whole publish/schedule/retry flow works end-to-end offline.
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

function parseDataUri(value: string): Buffer | null {
  const match = value.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;

  const [, , isBase64, body] = match;
  return Buffer.from(decodeURIComponent(body), isBase64 ? "base64" : "utf8");
}

async function imageToPngBytes(image: PublishImage): Promise<Buffer> {
  const source = image.data.trim();
  let bytes: Buffer;

  if (/^https?:\/\//i.test(source)) {
    const res = await fetch(source);
    if (!res.ok) {
      throw new Error(`Image fetch ${res.status}: ${(await res.text()).slice(0, 200)}`);
    }
    bytes = Buffer.from(await res.arrayBuffer());
  } else {
    bytes =
      parseDataUri(source) ??
      Buffer.from(source, source.startsWith("<") ? "utf8" : "base64");
  }

  return sharp(bytes, { limitInputPixels: false })
    .resize({ width: 1200, height: 1200, fit: "inside", withoutEnlargement: true })
    .png()
    .toBuffer();
}

async function uploadLinkedInImage(
  image: PublishImage,
  authorUrn: string
): Promise<{ asset: string } | { error: string }> {
  const token = process.env.LINKEDIN_ACCESS_TOKEN;
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
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-Restli-Protocol-Version": "2.0.0",
    },
    body: JSON.stringify(registerBody),
  });

  if (!register.ok) {
    const errText = await register.text().catch(() => "");
    return {
      error: `LinkedIn image register ${register.status}: ${errText.slice(0, 300)}`,
    };
  }

  const data = await register.json().catch(() => ({}));
  const value = data?.value;
  const uploadUrl =
    value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]?.uploadUrl;
  const asset = value?.asset;

  if (!uploadUrl || !asset) {
    return { error: "LinkedIn image register response missing uploadUrl or asset" };
  }

  const png = await imageToPngBytes(image);
  const upload = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "image/png",
    },
    body: new Uint8Array(png),
  });

  if (!upload.ok) {
    const errText = await upload.text().catch(() => "");
    return {
      error: `LinkedIn image upload ${upload.status}: ${errText.slice(0, 300)}`,
    };
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
    let media:
      | Array<{
          status: "READY";
          description?: { text: string };
          media: string;
          title?: { text: string };
        }>
      | undefined;

    if (payload.image) {
      const uploaded = await uploadLinkedInImage(payload.image, status.authorUrn!);
      if ("error" in uploaded) {
        return { ok: false, error: uploaded.error, simulated: false };
      }
      media = [
        {
          status: "READY",
          description: payload.image.altText
            ? { text: payload.image.altText }
            : undefined,
          media: uploaded.asset,
          title: { text: "World of Interns" },
        },
      ];
    }

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
