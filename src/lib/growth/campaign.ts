import { newId, readDb, updateDb } from "../db";
import { generateDraft, scoreDraft } from "../content/generator";
import {
  generatePostWithLLM,
  generateTextWithLLM,
  hasOpenAI,
} from "../llm/openai";
import type {
  Campaign,
  CampaignAsset,
  CampaignAssetKind,
} from "../types";
import {
  companySpotlight,
  poll,
  quiz,
  studentSpotlight,
} from "./community";
import {
  DraftAsset,
  followUp,
  hrEmail,
  linkedinMessage,
  outreachSystemPrompt,
  proposal,
} from "./outreach";
import { getService, GrowthService } from "./services";

const ASSET_TITLES: Record<CampaignAssetKind, string> = {
  linkedin_post: "LinkedIn post",
  hr_email: "HR outreach email",
  linkedin_message: "LinkedIn message",
  follow_up: "Follow-up email",
  proposal: "Proposal",
  poll: "Poll",
  quiz: "Weekly quiz",
  student_spotlight: "Student spotlight",
  company_spotlight: "Company spotlight",
  recruiter_insight: "Recruiter insight",
};

async function buildPostAsset(
  kind: CampaignAssetKind,
  service: GrowthService,
  db: Awaited<ReturnType<typeof readDb>>
): Promise<CampaignAsset> {
  const category =
    db.categories.find((c) => c.id === service.categoryId) || db.categories[0];
  const brand = db.brandStyle;

  const rule = generateDraft(
    service.contentTypeId,
    service.topic,
    category,
    service.postAudience,
    brand,
    service.topic.toLowerCase().split(/\s+/).filter((w) => w.length > 4).slice(0, 3)
  );

  let body = rule.body;
  let engine: CampaignAsset["engine"] = "rule-based";
  const llm = await generatePostWithLLM({
    brand,
    systemHint: service.goal,
    topic: service.topic,
    audience: service.postAudience,
  });
  if (llm) {
    body = llm;
    engine = "openai";
  }

  const analysis = scoreDraft(body, brand);
  return {
    id: newId("asset"),
    kind,
    title: ASSET_TITLES[kind],
    body,
    hashtags: rule.hashtags,
    scores: analysis.scores,
    warnings: analysis.warnings,
    engine,
  };
}

async function buildOutreachAsset(
  kind: CampaignAssetKind,
  service: GrowthService,
  rule: DraftAsset
): Promise<CampaignAsset> {
  let body = rule.body;
  let engine: CampaignAsset["engine"] = "rule-based";
  if (hasOpenAI() && kind !== "linkedin_message") {
    const llm = await generateTextWithLLM(
      outreachSystemPrompt(ASSET_TITLES[kind], service),
      `Service: ${service.name}. Goal: ${service.goal}.`
    );
    if (llm) {
      body = llm;
      engine = "openai";
    }
  }
  return {
    id: newId("asset"),
    kind,
    title: rule.title,
    subject: rule.subject,
    body,
    meta: rule.meta,
    engine,
  };
}

function communityAsset(kind: CampaignAssetKind, service: GrowthService): CampaignAsset {
  let a;
  switch (kind) {
    case "poll":
      a = poll(service);
      break;
    case "quiz":
      a = quiz(service);
      break;
    case "student_spotlight":
      a = studentSpotlight();
      break;
    case "company_spotlight":
      a = companySpotlight();
      break;
    default:
      a = poll(service);
  }
  return {
    id: newId("asset"),
    kind,
    title: a.title,
    body: a.body,
    hashtags: a.hashtags,
    meta: a.meta,
    engine: "rule-based",
  };
}

export async function buildCampaign(serviceId: string): Promise<Campaign | null> {
  const service = getService(serviceId);
  if (!service) return null;
  const db = await readDb();

  const assets: CampaignAsset[] = [];
  for (const kind of service.assetKinds) {
    switch (kind) {
      case "linkedin_post":
      case "recruiter_insight":
        assets.push(await buildPostAsset(kind, service, db));
        break;
      case "hr_email":
        assets.push(await buildOutreachAsset(kind, service, hrEmail(service)));
        break;
      case "follow_up":
        assets.push(await buildOutreachAsset(kind, service, followUp(service)));
        break;
      case "proposal":
        assets.push(await buildOutreachAsset(kind, service, proposal(service)));
        break;
      case "linkedin_message":
        assets.push(await buildOutreachAsset(kind, service, linkedinMessage(service)));
        break;
      case "poll":
      case "quiz":
      case "student_spotlight":
      case "company_spotlight":
        assets.push(communityAsset(kind, service));
        break;
    }
  }

  const campaign: Campaign = {
    id: newId("camp"),
    name: `${service.name} campaign`,
    audience: service.audience,
    serviceId: service.id,
    serviceName: service.name,
    goal: service.goal,
    assets,
    createdAt: new Date().toISOString(),
    status: "ready",
  };

  await updateDb((d) => {
    d.campaigns.unshift(campaign);
  });
  return campaign;
}

export async function listCampaigns(): Promise<Campaign[]> {
  const db = await readDb();
  return db.campaigns;
}

export async function getCampaign(id: string): Promise<Campaign | null> {
  const db = await readDb();
  return db.campaigns.find((c) => c.id === id) ?? null;
}

export async function deleteCampaign(id: string): Promise<boolean> {
  return updateDb((d) => {
    const idx = d.campaigns.findIndex((c) => c.id === id);
    if (idx === -1) return false;
    d.campaigns.splice(idx, 1);
    return true;
  });
}
