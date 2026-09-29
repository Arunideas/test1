// LinkedIn publishing client.
//
// When LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are set, this posts a real
// text share via the LinkedIn UGC Posts API. Otherwise it runs in simulation
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

function decodeDataUri(input: string): { mediaType: string; bytes: Buffer } | null {
  const match = input.match(/^data:([^;,]+)?(;base64)?,(.*)$/s);
  if (!match) return null;
  const mediaType = match[1] || "application/octet-stream";
  const isBase64 = Boolean(match[2]);
  const payload = match[3] || "";
  return {
    mediaType,
    bytes: isBase64
      ? Buffer.from(payload, "base64")
      : Buffer.from(decodeURIComponent(payload), "utf8"),
  };
}

async function imageToPngBytes(source: string): Promise<Buffer> {
  const trimmed = source.trim();
  const dataUri = decodeDataUri(trimmed);

  if (dataUri) {
    if (dataUri.mediaType === "image/png") return dataUri.bytes;
    return sharp(dataUri.bytes).png().toBuffer();
  }

  if (/^https?:\/\//i.test(trimmed)) {
    const res = await fetch(trimmed);
    if (!res.ok) {
      throw new Error(`Image fetch failed ${res.status}`);
    }
    return sharp(Buffer.from(await res.arrayBuffer())).png().toBuffer();
  }

  return sharp(Buffer.from(trimmed, "utf8")).png().toBuffer();
}

async function uploadImageToLinkedIn(
  image: NonNullable<PublishPayload["image"]>,
  authorUrn: string
): Promise<{ asset: string } | { error: string }> {
  const png = await imageToPngBytes(image.data);
  const registerRes = await fetch(`${API_BASE}/assets?action=registerUpload`, {
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

  if (!registerRes.ok) {
    const errText = await registerRes.text().catch(() => "");
    return {
      error: `LinkedIn image register ${registerRes.status}: ${errText.slice(0, 300)}`,
    };
  }

  const uploadData = await registerRes.json().catch(() => null);
  const value = uploadData?.value;
  const uploadUrl =
    value?.uploadMechanism?.[
      "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]?.uploadUrl;
  const asset: string | undefined = value?.asset;
  if (!uploadUrl || !asset) {
    return { error: "LinkedIn image register response missing upload URL or asset URN" };
  }

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
      imageAttached: Boolean(payload.image?.data),
    };
  }

  try {
    let media:
      | Array<{
          status: "READY";
          media: string;
          title: { text: string };
          description?: { text: string };
        }>
      | undefined;

    if (payload.image?.data) {
      const upload = await uploadImageToLinkedIn(payload.image, status.authorUrn!);
      if ("error" in upload) {
        return { ok: false, error: upload.error, simulated: false, imageAttached: false };
      }
      media = [
        {
          status: "READY",
          media: upload.asset,
          title: { text: "World of Interns" },
          ...(payload.image.altText
            ? { description: { text: payload.image.altText.slice(0, 200) } }
            : {}),
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
      imageAttached: false,
    };
  }
}
