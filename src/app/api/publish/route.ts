import { NextResponse } from "next/server";
import { schedulePublish } from "@/lib/publishing/service";
import type { PublishMode } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as {
      postId?: string;
      mode?: PublishMode;
      scheduledAt?: string;
      visibility?: "PUBLIC" | "CONNECTIONS";
      calendarEntryId?: string;
    };
    if (!body?.postId) {
      return NextResponse.json({ error: "postId is required" }, { status: 400 });
    }
    const job = await schedulePublish({
      postId: body.postId,
      mode: body.mode ?? "immediate",
      scheduledAt: body.scheduledAt,
      visibility: body.visibility,
      calendarEntryId: body.calendarEntryId,
    });
    if (!job) return NextResponse.json({ error: "Post not found" }, { status: 404 });
    return NextResponse.json({ job });
  } catch (err) {
    console.error("publish error", err);
    return NextResponse.json({ error: "Failed to schedule publish" }, { status: 500 });
  }
}
