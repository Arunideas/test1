import type { GrowthService } from "./services";

export interface DraftAsset {
  title: string;
  subject?: string;
  body: string;
  meta?: { placeholders?: string[] };
}

const PLACEHOLDERS = ["First name", "Company", "Role", "Your name"];

function offerOf(s: GrowthService): string {
  return s.offer ?? "help your team hire and assess interns faster";
}

function proofOf(s: GrowthService): string {
  return s.proof ?? "candidates are assessed for the actual task before you see them";
}

export function hrEmail(s: GrowthService): DraftAsset {
  const subject = subjectFor(s);
  const body = [
    "Hi [First name],",
    "",
    `I'm with World of Interns. We help teams like [Company] get ${offerOf(s)}.`,
    "",
    "Most hiring slows down for one reason: too many raw resumes, not enough time to read them.",
    `On our side, ${proofOf(s)}.`,
    "",
    "If a [Role] intern is on your list this quarter, I can share a short, pre-assessed shortlist to look at. No commitment.",
    "",
    "Would a quick 15-minute call next week be useful?",
    "",
    "Thanks,",
    "[Your name]",
    "World of Interns",
  ].join("\n");
  return { title: "HR outreach email", subject, body, meta: { placeholders: PLACEHOLDERS } };
}

export function linkedinMessage(s: GrowthService): DraftAsset {
  const connect = `Hi [First name], I help teams hire ${offerOf(
    s
  )}. Since [Company] is likely hiring interns, thought it was worth connecting. No pitch — happy to share what is working for similar teams.`;
  const firstMessage = [
    "Thanks for connecting, [First name].",
    "",
    `Quick context: we ${offerOf(s)}. ${capitalize(proofOf(s))}.`,
    "",
    "If it is useful, I can send a short example shortlist for a [Role] intern — no obligation. Worth a look?",
  ].join("\n");
  const body = [
    "Connection note (under 300 characters):",
    connect,
    "",
    "First message after they accept:",
    firstMessage,
  ].join("\n");
  return {
    title: "LinkedIn message",
    body,
    meta: { placeholders: PLACEHOLDERS },
  };
}

export function followUp(s: GrowthService): DraftAsset {
  const subject = `Re: ${subjectFor(s)}`;
  const body = [
    "Hi [First name],",
    "",
    "Following up on my last note — no worries if the timing is off.",
    "",
    `One thing that tends to help: ${proofOf(s)}. It saves the first-round screening time entirely.`,
    "",
    "If hiring a [Role] intern is still on the list, I can send a sample shortlist this week. Want me to?",
    "",
    "Thanks,",
    "[Your name]",
  ].join("\n");
  return { title: "Follow-up email", subject, body, meta: { placeholders: PLACEHOLDERS } };
}

export function proposal(s: GrowthService): DraftAsset {
  const title = `${s.name} proposal — [Company]`;
  const body = [
    `# ${s.name} proposal for [Company]`,
    "",
    "## The problem",
    "Hiring interns takes weeks: sourcing, screening, and coordinating rounds. Most of that time goes into reading resumes that never fit.",
    "",
    "## What we propose",
    `We ${offerOf(s)}. You review a short, ranked shortlist instead of raw applications.`,
    "",
    "## How it works",
    "1. We agree on the role and the one task the intern will own.",
    "2. We assess candidates for that task, not a generic aptitude test.",
    "3. You get a ranked shortlist with assessment evidence.",
    "4. You interview only the top few and decide.",
    "",
    "## What you get",
    "- A pre-assessed shortlist for the role",
    "- Assessment evidence for each candidate",
    "- A faster loop, typically within 10 days",
    "",
    "## Next step",
    "A 15-minute call to confirm the role and timeline. If it does not fit, no obligation.",
    "",
    "[Your name] · World of Interns",
  ].join("\n");
  return { title, body, meta: { placeholders: ["Company", "Your name"] } };
}

function subjectFor(s: GrowthService): string {
  switch (s.id) {
    case "hire_interns_10_days":
      return "Pre-assessed interns for [Role], ready in ~10 days";
    case "campus_hiring":
      return "A lighter campus hiring drive for [Company]";
    case "employer_branding":
      return "Helping [Company] attract the right interns";
    case "assessment_platform":
      return "Role-based assessments for [Company]'s intern hiring";
    case "recruitment_automation":
      return "Automating first-round screening at [Company]";
    default:
      return `Intern hiring at [Company]`;
  }
}

function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/** LLM system prompt for outreach — kept honest and non-pushy. */
export function outreachSystemPrompt(kind: string, s: GrowthService): string {
  return [
    `Write a ${kind} for World of Interns reaching out to a hiring manager.`,
    `Offer: ${offerOf(s)}. Proof point: ${proofOf(s)}.`,
    "Tone: honest, practical, calm, brief. No hype, no buzzwords, no false urgency.",
    "Use placeholders [First name], [Company], [Role], [Your name].",
    "End with a soft, low-pressure ask. Keep it under 130 words.",
    "Return only the message text.",
  ].join("\n");
}
