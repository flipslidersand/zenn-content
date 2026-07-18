#!/usr/bin/env node
/**
 * 記事パフォーマンス比較: 予測 vs 実測
 * 使用: node scripts/perf.mjs
 */
import { readFileSync, readdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { parse } from "yaml";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function loadPredictions() {
  const raw = readFileSync(join(ROOT, "stats/predictions.yml"), "utf8");
  return parse(raw);
}

function loadLatestSnapshot() {
  const dir = join(ROOT, "stats");
  const files = readdirSync(dir)
    .filter((f) => /^\d{4}-\d{2}-\d{2}\.yml$/.test(f))
    .sort();
  if (files.length === 0) return null;
  const latest = files[files.length - 1];
  const raw = readFileSync(join(dir, latest), "utf8");
  return { date: latest.replace(".yml", ""), data: parse(raw) };
}

async function fetchLive() {
  const res = await fetch(
    "https://zenn.dev/api/articles?username=flipslidersand&order=liked",
  );
  const json = await res.json();
  return json.articles ?? [];
}

function daysSince(dateStr) {
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000);
}

function verdict(actual, low, high) {
  if (actual >= high) return "🔥上振れ";
  if (actual >= low) return "✅範囲内";
  if (actual >= low * 0.5) return "⚠️下振れ";
  return "❌大外れ";
}

const predictions = loadPredictions();
const snapshot = loadLatestSnapshot();
const live = await fetchLive();

const liveMap = Object.fromEntries(live.map((a) => [a.slug, a]));

console.log("# 記事パフォーマンス比較\n");
console.log(`実測: ライブ API（${new Date().toISOString().slice(0, 10)}）`);
if (snapshot) console.log(`前回スナップショット: ${snapshot.date}`);
console.log();

const rows = [];
for (const [slug, pred] of Object.entries(predictions)) {
  const art = liveMap[slug];
  if (!art) continue;
  const days = daysSince(pred.published);
  const likes = art.liked_count ?? 0;
  const target = days <= 7 ? "7d" : "30d";
  const low = pred[`predicted_likes_${target}_low`];
  const high = pred[`predicted_likes_${target}_high`];
  rows.push({ slug, days, likes, low, high, pred, art });
}

rows.sort((a, b) => new Date(a.pred.published) - new Date(b.pred.published));

console.log("| 公開日 | slug | 経過日 | 実測👍 | 予測範囲 | 判定 | タイプ |");
console.log("|--------|------|--------|--------|----------|------|--------|");

for (const r of rows) {
  const range = `${r.low}〜${r.high}`;
  const v = verdict(r.likes, r.low, r.high);
  console.log(
    `| ${r.pred.published} | ${r.slug.slice(0, 28)} | ${r.days}d | ${r.likes} | ${range} | ${v} | ${r.pred.type} |`,
  );
}

console.log("\n## 傾向分析");
const techRows = rows.filter((r) => r.pred.type === "tech");
const ideaRows = rows.filter((r) => r.pred.type === "idea");
const techAvg =
  techRows.length > 0
    ? (techRows.reduce((s, r) => s + r.likes, 0) / techRows.length).toFixed(1)
    : "N/A";
const ideaAvg =
  ideaRows.length > 0
    ? (ideaRows.reduce((s, r) => s + r.likes, 0) / ideaRows.length).toFixed(1)
    : "N/A";
console.log(`- tech 平均: ${techAvg} likes（${techRows.length}本）`);
console.log(`- idea 平均: ${ideaAvg} likes（${ideaRows.length}本）`);

const hits = rows.filter((r) => r.likes >= r.low);
console.log(`- 予測範囲内以上: ${hits.length}/${rows.length}本`);
