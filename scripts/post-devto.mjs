#!/usr/bin/env node
/**
 * Post article from Zenn markdown (with frontmatter) to dev.to via API
 * Usage: node scripts/post-devto.mjs articles/safecode-arena-devto.md
 */

import fs from "fs";
import path from "path";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

async function getDevtoApiKey() {
  try {
    const { stdout } = await execAsync(
      "gopass show -o devto/api-key 2>/dev/null",
    );
    return stdout.trim();
  } catch {
    const key = process.env.DEVTO_API_KEY;
    if (!key) throw new Error("DEVTO_API_KEY not found in env or gopass");
    return key;
  }
}

async function parseMarkdown(filePath) {
  const content = fs.readFileSync(filePath, "utf-8");
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);

  if (!match) throw new Error("Invalid frontmatter format");

  const frontmatterStr = match[1];
  const body = match[2].trim();

  // Parse YAML-like frontmatter
  const frontmatter = {};
  frontmatterStr.split("\n").forEach((line) => {
    const [key, ...valueParts] = line.split(":");
    if (key && valueParts.length) {
      const value = valueParts
        .join(":")
        .trim()
        .replace(/^["']|["']$/g, "");
      if (key === "topics") {
        frontmatter[key] = value
          .replace(/[\[\]]/g, "")
          .split(",")
          .map((t) => t.trim());
      } else {
        frontmatter[key] = value;
      }
    }
  });

  return { frontmatter, body };
}

async function postToDevto(filePath, publish = false) {
  const { frontmatter, body } = await parseMarkdown(filePath);
  const apiKey = await getDevtoApiKey();

  // Dev.to API format
  const payload = {
    article: {
      title: frontmatter.title,
      body_markdown: body,
      published: publish, // draft by default
      tags: (frontmatter.topics || []).slice(0, 4), // dev.to allows max 4 tags
      description: `AI code verification with ${frontmatter.topics?.[0] || "Rust"}`,
      cover_image_url: null, // optional
    },
  };

  console.log(`📤 Posting to dev.to (draft=${!publish})...`);
  console.log(`   Title: ${payload.article.title}`);
  console.log(`   Tags: ${payload.article.tags.join(", ")}`);

  const response = await fetch("https://dev.to/api/articles", {
    method: "POST",
    headers: {
      "api-key": apiKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(
      `Dev.to API error (${response.status}): ${JSON.stringify(error)}`,
    );
  }

  const result = await response.json();
  console.log(`✅ Posted successfully!`);
  console.log(`   URL: https://dev.to/${result.user.username}/${result.slug}`);
  console.log(`   ID: ${result.id}`);

  return result;
}

// CLI
const filePath = process.argv[2];
const publish = process.argv.includes("--publish");

if (!filePath) {
  console.error("Usage: node scripts/post-devto.mjs <file> [--publish]");
  process.exit(1);
}

postToDevto(filePath, publish).catch((err) => {
  console.error("❌ Error:", err.message);
  process.exit(1);
});
