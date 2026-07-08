import { NextResponse } from "next/server";
import { checkDuplicate } from "@/lib/planning/service";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = (await req.json()) as { topic?: string };
  if (!body?.topic) {
    return NextResponse.json({ error: "topic is required" }, { status: 400 });
  }
  const result = await checkDuplicate(body.topic);
  return NextResponse.json(result);
}
