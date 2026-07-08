import { NextResponse } from "next/server";
import { ensureScheduler } from "@/lib/publishing/service";
import { runDailyPipeline } from "@/lib/publishing/pipeline";

export const dynamic = "force-dynamic";

// Optional shared-secret guard. If CRON_SECRET is set, requests must include it
// via `?secret=...` or the `x-cron-secret` header.
function authorized(req: Request): boolean {
  const secret = process.env.CRON_SECRET;
  if (!secret) return true;
  const url = new URL(req.url);
  const provided = url.searchParams.get("secret") || req.headers.get("x-cron-secret");
  return provided === secret;
}

async function handle(req: Request) {
  if (!authorized(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  ensureScheduler();
  const url = new URL(req.url);
  const num = (k: string) => {
    const v = url.searchParams.get(k);
    return v == null ? undefined : Number(v);
  };
  const result = await runDailyPipeline({
    days: num("days"),
    horizonDays: num("horizonDays"),
    timeOfDay: url.searchParams.get("timeOfDay") || undefined,
    planIfEmpty: url.searchParams.get("planIfEmpty") !== "false",
    generate: url.searchParams.get("generate") !== "false",
  });
  return NextResponse.json(result);
}

export async function POST(req: Request) {
  return handle(req);
}

// GET is allowed too so simple cron services (that only do GET) can call it.
export async function GET(req: Request) {
  return handle(req);
}
