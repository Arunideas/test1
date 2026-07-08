import { newId, readDb, updateDb } from "../db";
import { keywordsFromTopic, pickHashtags } from "../content/hashtags";
import { analyzeText } from "../voice/styleEngine";
import { AiRequiredError } from "../service";
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
  const brand = db.brandStyle;

  if (!hasOpenAI()) {
    throw new AiRequiredError(
      "AI writing is required. Set OPENAI_API_KEY to generate campaigns."
    );
  }
  const body = await generatePostWithLLM({
    brand,
    systemHint: service.goal,
    topic: service.topic,
    audience: service.postAudience,
  });
  if (!body) {
    throw new AiRequiredError(
      "AI generation failed. Check OPENAI_API_KEY, model access, and try again."
    );
  }

  const analysis = analyzeText(body, brand);
  return {
    id: newId("asset"),
    kind,
    title: ASSET_TITLES[kind],
    body,
    hashtags: pickHashtags(brand, keywordsFromTopic(service.topic), service.topic),
    scores: analysis.scores,
    warnings: analysis.warnings,
    engine: "openai",
  };
}

async function buildOutreachAsset(
  kind: CampaignAssetKind,
  service: GrowthService,
  scaffold: DraftAsset
): Promise<CampaignAsset> {
  // Outreach copy is written by AI only. The scaffold supplies the subject,
  // title, and placeholders — the body comes from the model.
  if (!hasOpenAI()) {
    throw new AiRequiredError(
      "AI writing is required. Set OPENAI_API_KEY to generate outreach."
    );
  }
  const body = await generateTextWithLLM(
    outreachSystemPrompt(ASSET_TITLES[kind], service),
    `Service: ${service.name}. Goal: ${service.goal}.`
  );
  if (!body) {
    throw new AiRequiredError(
      "AI generation failed. Check OPENAI_API_KEY, model access, and try again."
    );
  }
  return {
    id: newId("asset"),
    kind,
    title: scaffold.title,
    subject: scaffold.subject,
    body,
    meta: scaffold.meta,
    engine: "openai",
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
