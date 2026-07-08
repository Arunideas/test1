import { NextResponse } from "next/server";
import { deleteCampaign, getCampaign } from "@/lib/growth/campaign";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const campaign = await getCampaign(params.id);
  if (!campaign) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json({ campaign });
}

export async function DELETE(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const ok = await deleteCampaign(params.id);
  return NextResponse.json({ ok });
}
