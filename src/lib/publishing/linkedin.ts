// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. If an image is provided, it registers and
// uploads the image first, then attaches it to the share. Otherwise it runs in
// simulation mode so the whole publish/schedule/retry flow works end-to-end offline.

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
}

export interface PublishPayload {
  text: string;
  visibility: "PUBLIC" | "CONNECTIONS";
  image?: {
    data: string;
    altText?: string | null;
  } | null;
}

interface PreparedImage {
  bytes: Buffer;
  contentType: "image/png" | "image/jpeg" | "image/gif";
}

function urnToUrl(urn: string): string {
  // urn:li:share:123 or urn:li:ugcPost:123 -> feed permalink
  return `https://www.linkedin.com/feed/update/${encodeURIComponent(urn)}`;
}

function parseDataUri(data: string): { mime: string; bytes: Buffer } | null {
  const match = data.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;
  const [, mime, isBase64, payload] = match;
  return {
    mime,
    bytes: Buffer.from(decodeURIComponent(payload), isBase64 ? "base64" : "utf8"),
  };
}

async function svgToPng(svg: string | Buffer): Promise<Buffer> {
  const sharp = (await import("sharp")).default;
  return sharp(Buffer.isBuffer(svg) ? svg : Buffer.from(svg, "utf8")).png().toBuffer();
}

async function prepareImage(data: string): Promise<PreparedImage> {
  const parsed = parseDataUri(data);
  if (parsed) {
    if (parsed.mime === "image/png") {
      return { bytes: parsed.bytes, contentType: "image/png" };
    }
    if (parsed.mime === "image/jpeg" || parsed.mime === "image/jpg") {
      return { bytes: parsed.bytes, contentType: "image/jpeg" };
    }
    if (parsed.mime === "image/gif") {
      return { bytes: parsed.bytes, contentType: "image/gif" };
    }
    if (parsed.mime === "image/svg+xml") {
      return { bytes: await svgToPng(parsed.bytes), contentType: "image/png" };
    }
  }

  if (data.trim().startsWith("<svg")) {
    return { bytes: await svgToPng(data), contentType: "image/png" };
  }

  throw new Error("Unsupported image format for LinkedIn upload");
}

async function registerImageUpload(authorUrn: string): Promise<{
  asset: string;
  uploadUrl: string;
}> {
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
    throw new Error(`LinkedIn upload registration ${res.status}: ${errText.slice(0, 300)}`);
  }

  const data = await res.json();
  const value = data?.value;
  const upload =
    value?.uploadMechanism?.["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"];
  if (!value?.asset || !upload?.uploadUrl) {
    throw new Error("LinkedIn upload registration returned an invalid response");
  }
  return { asset: value.asset, uploadUrl: upload.uploadUrl };
}

async function uploadImage(
  uploadUrl: string,
  image: PreparedImage
): Promise<void> {
  const res = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": image.contentType,
    },
    body: new Uint8Array(image.bytes),
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

  if (status.simulated) {
    // Deterministic-ish simulated urn so the UI has a link to show.
    const fake = `urn:li:share:sim${Date.now()}`;
    return {
      ok: true,
      postUrn: fake,
      postUrl: urnToUrl(fake),
      simulated: true,
    };
  }

  try {
    const media = [];
    if (payload.image?.data && status.authorUrn) {
      const prepared = await prepareImage(payload.image.data);
      const upload = await registerImageUpload(status.authorUrn);
      await uploadImage(upload.uploadUrl, prepared);
      media.push({
        status: "READY",
        media: upload.asset,
        title: {
          text: payload.image.altText || "World of Interns LinkedIn image",
        },
      });
    }

    const body = {
      author: status.authorUrn,
      lifecycleState: "PUBLISHED",
      specificContent: {
        "com.linkedin.ugc.ShareContent": {
          shareCommentary: { text: payload.text },
          shareMediaCategory: media.length ? "IMAGE" : "NONE",
          ...(media.length ? { media } : {}),
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
    };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Network error",
      simulated: false,
    };
  }
}
