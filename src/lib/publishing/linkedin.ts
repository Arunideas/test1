// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// share via the LinkedIn UGC Posts API. If an image is provided, it is converted
// to PNG, uploaded through LinkedIn's assets API, and attached to the post.
// Otherwise it runs in simulation mode so the whole publish/schedule/retry flow
// works end-to-end offline.

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

export interface LinkedInImageInput {
  id?: string;
  data: string;
  altText?: string;
}

export interface PublishPayload {
  text: string;
  visibility: "PUBLIC" | "CONNECTIONS";
  image?: LinkedInImageInput | null;
}

function urnToUrl(urn: string): string {
  // urn:li:share:123 or urn:li:ugcPost:123 -> feed permalink
  return `https://www.linkedin.com/feed/update/${encodeURIComponent(urn)}`;
}

function parseDataUri(value: string): { mime: string; buffer: Buffer } | null {
  const match = value.match(/^data:([^;,]+)(;base64)?,(.*)$/s);
  if (!match) return null;

  const [, mime, base64, body] = match;
  return {
    mime,
    buffer: Buffer.from(
      base64 ? body : decodeURIComponent(body),
      base64 ? "base64" : "utf8"
    ),
  };
}

async function imageToPngBuffer(image: LinkedInImageInput): Promise<Buffer> {
  const data = image.data.trim();

  if (data.startsWith("<svg")) {
    return sharp(Buffer.from(data, "utf8")).png().toBuffer();
  }

  const dataUri = parseDataUri(data);
  if (dataUri) {
    return sharp(dataUri.buffer).png().toBuffer();
  }

  if (/^https?:\/\//i.test(data)) {
    const res = await fetch(data);
    if (!res.ok) {
      throw new Error(`Image fetch failed ${res.status}`);
    }
    return sharp(Buffer.from(await res.arrayBuffer())).png().toBuffer();
  }

  return sharp(Buffer.from(data, "utf8")).png().toBuffer();
}

async function registerImageUpload(
  authorUrn: string
): Promise<{ uploadUrl: string; asset: string }> {
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
  const uploadUrl =
    value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]?.uploadUrl;
  const asset = value?.asset;

  if (!uploadUrl || !asset) {
    throw new Error("LinkedIn image register response missing uploadUrl or asset");
  }

  return { uploadUrl, asset };
}

async function uploadImage(uploadUrl: string, image: LinkedInImageInput): Promise<void> {
  const buffer = await imageToPngBuffer(image);
  const res = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.LINKEDIN_ACCESS_TOKEN}`,
      "Content-Type": "image/png",
    },
    body: buffer,
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
      imageAttached: Boolean(payload.image),
    };
  }

  try {
    if (!status.authorUrn) {
      return {
        ok: false,
        error: "LINKEDIN_AUTHOR_URN is required for live publishing",
        simulated: false,
        imageAttached: false,
      };
    }

    let imageAsset: string | null = null;
    if (payload.image) {
      const upload = await registerImageUpload(status.authorUrn);
      await uploadImage(upload.uploadUrl, payload.image);
      imageAsset = upload.asset;
    }

    const shareContent: Record<string, unknown> = {
      shareCommentary: { text: payload.text },
      shareMediaCategory: imageAsset ? "IMAGE" : "NONE",
    };

    if (imageAsset) {
      shareContent.media = [
        {
          status: "READY",
          media: imageAsset,
          title: { text: "World of Interns post image" },
          description: payload.image?.altText
            ? { text: payload.image.altText.slice(0, 4000) }
            : undefined,
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
