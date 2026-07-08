import { NextResponse } from "next/server";
import { updateEntry } from "@/lib/planning/service";
import type { CalendarStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function PATCH(
  req: Request,
  { params }: { params: { id: string } }
) {
  const body = (await req.json()) as {
    status?: CalendarStatus;
    note?: string;
    topicId?: string;
  };
  const entry = await updateEntry(params.id, body);
  if (!entry) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json({ entry });
}
