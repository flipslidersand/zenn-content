#!/usr/bin/env node

import { execSync } from "child_process";
import path from "path";
import { fileURLToPath } from "url";
import { fetchAndStore } from "./fetch-trends.mjs";
import { generateDraftsForToday } from "./generate-draft.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_DIR = path.join(__dirname, "..");

async function gitCommitPush(files) {
  if (files.length === 0) return;
  execSync(`git -C ${REPO_DIR} add drafts/`);
  execSync(
    `git -C ${REPO_DIR} commit -m "draft: auto-generate ${files.length} drafts [automated]"`,
  );
  execSync(`git -C ${REPO_DIR} push origin HEAD`);
}

async function purgeOldKeywords() {
  const { openDb } = await import("./db.mjs");
  const db = openDb();
  const result = db
    .prepare(
      `
    DELETE FROM keywords WHERE fetched_at < datetime('now', '-30 days')
  `,
    )
    .run();
  db.close();
  return result.changes;
}

async function main() {
  const mode = process.argv[2] || "daily";

  if (mode === "daily") {
    // 1. Fetch new keywords
    const fetched = await fetchAndStore();
    process.stdout.write(`Fetched: ${fetched} keywords\n`);

    // 2. Generate drafts for today's category
    const files = await generateDraftsForToday();
    process.stdout.write(`Generated: ${files.length} drafts\n`);

    // 3. Commit & push
    await gitCommitPush(files);
  }

  if (mode === "purge") {
    const deleted = await purgeOldKeywords();
    process.stdout.write(`Purged: ${deleted} old keywords\n`);
  }
}

main();
