import { NextResponse } from "next/server";
import { approveJob, cancelJob, retryJob } from "@/lib/publishing/service";

export const dynamic = "force-dynamic";

export async function POST(
  req: Request,
  { params }: { params: { id: string } }
) {
  const body = (await req.json().catch(() => ({}))) as {
    action?: "approve" | "cancel" | "retry";
  };
  let job;
  switch (body.action) {
    case "approve":
      job = await approveJob(params.id);
      break;
    case "cancel":
      job = await cancelJob(params.id);
      break;
    case "retry":
      job = await retryJob(params.id);
      break;
    default:
      return NextResponse.json({ error: "Unknown action" }, { status: 400 });
  }
  if (!job) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json({ job });
}
