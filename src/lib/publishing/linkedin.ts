// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. Otherwise it runs in simulation mode so
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

export interface PublishImage {
  data: string;
  altText?: string;
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

function parseDataUri(data: string): { mime: string; buffer: Buffer } | null {
  const match = data.match(/^data:([^;,]+);base64,(.+)$/);
  if (!match) return null;
  return {
    mime: match[1],
    buffer: Buffer.from(match[2], "base64"),
  };
}

async function imageToPngBuffer(image: PublishImage): Promise<Buffer> {
  const parsed = parseDataUri(image.data);
  const raw = parsed?.buffer ?? Buffer.from(image.data, "utf8");

  if (parsed?.mime === "image/png") {
    return raw;
  }

  return sharp(raw, { failOn: "none" })
    .resize(1200, 1200, {
      fit: "inside",
      withoutEnlargement: true,
    })
    .flatten({ background: "#f3efe7" })
    .png()
    .toBuffer();
}

async function registerAndUploadImage(
  token: string,
  authorUrn: string,
  image: PublishImage
): Promise<{ asset: string } | { error: string }> {
  const png = await imageToPngBuffer(image);
  const registerRes = await fetch(`${API_BASE}/assets?action=registerUpload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
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

  if (!registerRes.ok) {
    const errText = await registerRes.text().catch(() => "");
    return {
      error: `LinkedIn image registration ${registerRes.status}: ${errText.slice(0, 300)}`,
    };
  }

  const data = await registerRes.json().catch(() => ({}));
  const value = data?.value;
  const upload =
    value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ];
  const uploadUrl: string | undefined = upload?.uploadUrl;
  const asset: string | undefined = value?.asset;

  if (!uploadUrl || !asset) {
    return {
      error: "LinkedIn image registration did not return an upload URL and asset URN",
    };
  }

  const uploadRes = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "image/png",
      "Content-Length": String(png.byteLength),
    },
    body: png,
  });

  if (!uploadRes.ok) {
    const errText = await uploadRes.text().catch(() => "");
    return {
      error: `LinkedIn image upload ${uploadRes.status}: ${errText.slice(0, 300)}`,
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
    const token = process.env.LINKEDIN_ACCESS_TOKEN as string;
    const image = payload.image
      ? await registerAndUploadImage(
          token,
          status.authorUrn as string,
          payload.image
        )
      : null;

    if (image && "error" in image) {
      return {
        ok: false,
        error: image.error,
        simulated: false,
        imageAttached: false,
      };
    }

    const shareContent: Record<string, unknown> = {
      shareCommentary: { text: payload.text },
      shareMediaCategory: image ? "IMAGE" : "NONE",
    };

    if (image) {
      shareContent.media = [
        {
          status: "READY",
          media: image.asset,
          title: { text: "World of Interns" },
          description: {
            text: (payload.image?.altText || "World of Interns post image").slice(
              0,
              200
            ),
          },
        },
      ];
    }

    const body = {
      author: status.authorUrn,
      lifecycleState: "PUBLISHED",
      specificContent: {
        "com.linkedin.ugc.ShareContent": shareContent,
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
      imageAttached: Boolean(image),
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
