import { NextResponse } from "next/server";
import { buildCampaign, listCampaigns } from "@/lib/growth/campaign";

export const dynamic = "force-dynamic";

export async function GET() {
  const campaigns = await listCampaigns();
  return NextResponse.json({ campaigns });
}

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as { serviceId?: string };
    if (!body?.serviceId) {
      return NextResponse.json({ error: "serviceId is required" }, { status: 400 });
    }
    const campaign = await buildCampaign(body.serviceId);
    if (!campaign) {
      return NextResponse.json({ error: "Unknown service" }, { status: 404 });
    }
    return NextResponse.json({ campaign });
  } catch (err) {
    console.error("campaign error", err);
    return NextResponse.json({ error: "Failed to build campaign" }, { status: 500 });
  }
}
