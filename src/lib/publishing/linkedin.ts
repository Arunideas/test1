// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. If an image is supplied, it is converted
// to PNG and uploaded as LinkedIn feed image media first. Otherwise it runs in
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

function dataToBuffer(data: string): { buffer: Buffer; mimeType: string } {
  const trimmed = data.trim();
  const match = trimmed.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (match) {
    return {
      buffer: match[2]
        ? Buffer.from(match[3], "base64")
        : Buffer.from(decodeURIComponent(match[3]), "utf8"),
      mimeType: match[1],
    };
  }

  const mimeType = trimmed.startsWith("<svg") || trimmed.startsWith("<?xml")
    ? "image/svg+xml"
    : "application/octet-stream";
  return { buffer: Buffer.from(trimmed, "utf8"), mimeType };
}

async function toLinkedInPng(data: string): Promise<Buffer> {
  const { buffer, mimeType } = dataToBuffer(data);
  const sharp = (await import("sharp")).default;
  return sharp(buffer, mimeType === "image/svg+xml" ? { density: 144 } : undefined)
    .resize({
      width: 1200,
      height: 1200,
      fit: "inside",
      withoutEnlargement: true,
    })
    .png()
    .toBuffer();
}

async function uploadImage(image: NonNullable<PublishPayload["image"]>): Promise<string> {
  const status = linkedInStatus();
  const registerBody = {
    registerUploadRequest: {
      recipes: ["urn:li:digitalmediaRecipe:feedshare-image"],
      owner: status.authorUrn,
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

  const registerData = await registerRes.json();
  const upload =
    registerData?.value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ];
  const uploadUrl: string | undefined = upload?.uploadUrl;
  const asset: string | undefined = registerData?.value?.asset;
  if (!uploadUrl || !asset) {
    throw new Error("LinkedIn image registration did not return an upload URL and asset URN");
  }

  const png = await toLinkedInPng(image.data);
  const uploadRes = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": "image/png",
    },
    body: png,
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
      imageAttached: Boolean(payload.image?.data),
    };
  }

  try {
    const asset = payload.image?.data ? await uploadImage(payload.image) : null;
    const body = {
      author: status.authorUrn,
      lifecycleState: "PUBLISHED",
      specificContent: {
        "com.linkedin.ugc.ShareContent": {
          shareCommentary: { text: payload.text },
          shareMediaCategory: asset ? "IMAGE" : "NONE",
          ...(asset
            ? {
                media: [
                  {
                    status: "READY",
                    description: payload.image?.altText
                      ? { text: payload.image.altText }
                      : undefined,
                    media: asset,
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
      imageAttached: Boolean(asset),
    };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Network error",
      simulated: false,
    };
  }
}
