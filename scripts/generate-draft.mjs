#!/usr/bin/env node

import { execSync } from "child_process";
import { writeFileSync, mkdirSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { openDb } from "./db.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DRAFTS_DIR = path.join(__dirname, "../drafts");

const MODEL = process.env.GEMINI_MODEL || "gemini-2.5-flash-lite";
const VERTEX_PROJECT = process.env.VERTEX_PROJECT || "";
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || "";

const DAY_CATEGORY = {
  1: "Tech",
  2: "AI/ML",
  3: ["Security", "Infrastructure"],
  4: ["キャリア", "スタートアップ"],
  5: "経済・市場",
  6: ["エンタメ", "ライフスタイル"],
  0: "社会・文化",
};

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-")
    .substring(0, 50)
    .replace(/-+$/, "");
}

function buildPrompt(keyword, category) {
  return `キーワード: "${keyword}"
カテゴリ: ${category}

このキーワードについて、以下の構造で周辺情報をまとめてください（各セクション簡潔に）:

## 背景
なぜ今このキーワードが注目されているか（2-3文）

## 関連キーワード
- キーワード1
- キーワード2
- キーワード3

## 参考リソース
- リソース1
- リソース2
- リソース3

## 記事構成案
- セクション1
- セクション2
- セクション3`;
}

async function callGemini(prompt) {
  const body = JSON.stringify({
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: { temperature: 0.3, maxOutputTokens: 1024 },
  });

  let url, headers;
  if (GEMINI_API_KEY) {
    url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`;
    headers = {
      "Content-Type": "application/json",
      "x-goog-api-key": GEMINI_API_KEY,
    };
  } else if (VERTEX_PROJECT) {
    const region = process.env.VERTEX_REGION || "us-central1";
    const token = execSync("gcloud auth print-access-token", {
      encoding: "utf8",
    }).trim();
    url = `https://${region}-aiplatform.googleapis.com/v1/projects/${VERTEX_PROJECT}/locations/${region}/publishers/google/models/${MODEL}:generateContent`;
    headers = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  } else {
    throw new Error("GEMINI_API_KEY または VERTEX_PROJECT が未設定");
  }

  const res = await fetch(url, { method: "POST", headers, body });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(
      `Gemini API error ${res.status}: ${data?.error?.message || JSON.stringify(data).slice(0, 300)}`,
    );
  }
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) {
    throw new Error(`Gemini 応答が空: ${JSON.stringify(data).slice(0, 300)}`);
  }
  return text;
}

export async function generateDraftsForToday() {
  const db = openDb();
  mkdirSync(DRAFTS_DIR, { recursive: true });

  const dow = new Date().getDay();
  const categories = DAY_CATEGORY[dow];
  const categoryList = Array.isArray(categories) ? categories : [categories];
  const placeholders = categoryList.map(() => "?").join(",");

  const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
  const keywords = db
    .prepare(
      `
    SELECT * FROM keywords
    WHERE category IN (${placeholders})
      AND used = 0
      AND fetched_at >= ?
    ORDER BY fetched_at DESC
    LIMIT 5
  `,
    )
    .all(...categoryList, since);

  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const generatedFiles = [];

  let failed = 0;
  for (const kw of keywords) {
    let background;
    try {
      background = await callGemini(buildPrompt(kw.keyword, kw.category));
    } catch (err) {
      process.stderr.write(
        `SKIP keyword#${kw.id} "${kw.keyword}": ${err.message}\n`,
      );
      failed++;
      continue; // used=0 のまま残す → 次回リトライ
    }
    const base = slugify(kw.keyword);
    const slug = base ? `${base}-kw${kw.id}` : `kw${kw.id}`; // 日本語タイトルは slug が空になるため id で一意化
    const filename = `${date}-${slug}.md`;
    const filepath = path.join(DRAFTS_DIR, filename);

    writeFileSync(
      filepath,
      `---
title: "${kw.keyword}"
emoji: "📝"
type: "idea"
published: false
---

${background}
`,
    );

    db.prepare("UPDATE keywords SET used = 1 WHERE id = ?").run(kw.id);
    const theme = db
      .prepare(
        `
      INSERT INTO themes (keyword_id, title, slug, status)
      VALUES (?, ?, ?, 'drafted')
    `,
      )
      .run(kw.id, kw.keyword, slug);
    db.prepare("INSERT INTO drafts (theme_id, filepath) VALUES (?, ?)").run(
      theme.lastInsertRowid,
      filepath,
    );

    generatedFiles.push(filename);
    await new Promise((r) => setTimeout(r, 500));
  }

  db.close();
  if (failed > 0 && generatedFiles.length === 0) {
    throw new Error(`全 ${failed} 件の生成に失敗`);
  }
  return generatedFiles;
}

// CLI entry
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const files = await generateDraftsForToday();
  process.stdout.write(`Generated ${files.length} drafts\n`);
}
