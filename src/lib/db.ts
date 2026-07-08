import { promises as fs } from "fs";
import path from "path";
import type { Database } from "./types";
import { buildSeedDatabase } from "./seed";

const DATA_DIR = path.join(process.cwd(), "data");
const DB_FILE = path.join(DATA_DIR, "db.json");

// Simple in-process write queue so concurrent API requests don't clobber the file.
let writeChain: Promise<unknown> = Promise.resolve();
let cache: Database | null = null;

async function ensureFile(): Promise<void> {
  await fs.mkdir(DATA_DIR, { recursive: true });
  try {
    await fs.access(DB_FILE);
  } catch {
    const seed = buildSeedDatabase();
    await fs.writeFile(DB_FILE, JSON.stringify(seed, null, 2), "utf8");
  }
}

export async function readDb(): Promise<Database> {
  if (cache) return cache;
  await ensureFile();
  const raw = await fs.readFile(DB_FILE, "utf8");
  const parsed = JSON.parse(raw) as Database;
  // Merge in any new seed collections (keeps backend fields current across upgrades).
  const seed = buildSeedDatabase();
  const merged: Database = {
    categories: parsed.categories?.length ? parsed.categories : seed.categories,
    topics: parsed.topics?.length ? parsed.topics : seed.topics,
    brandStyle: parsed.brandStyle ?? seed.brandStyle,
    prompts: parsed.prompts?.length ? parsed.prompts : seed.prompts,
    imageTemplates: parsed.imageTemplates?.length
      ? parsed.imageTemplates
      : seed.imageTemplates,
    images: parsed.images ?? [],
    posts: parsed.posts ?? [],
    calendar: parsed.calendar ?? [],
    performance: parsed.performance ?? [],
    config: parsed.config ?? seed.config,
    campaigns: parsed.campaigns ?? [],
  };
  cache = merged;
  return merged;
}

async function persist(db: Database): Promise<void> {
  await ensureFile();
  await fs.writeFile(DB_FILE, JSON.stringify(db, null, 2), "utf8");
}

/**
 * Read-modify-write helper. The mutator receives the current db, mutates it,
 * and optionally returns a value. Writes are serialized to avoid races.
 */
export async function updateDb<T>(
  mutator: (db: Database) => T | Promise<T>
): Promise<T> {
  const run = async (): Promise<T> => {
    const db = await readDb();
    const result = await mutator(db);
    cache = db;
    await persist(db);
    return result;
  };
  const p = writeChain.then(run, run);
  // keep the chain alive but swallow errors so one failure doesn't break the queue
  writeChain = p.then(
    () => undefined,
    () => undefined
  );
  return p;
}

export function newId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}
