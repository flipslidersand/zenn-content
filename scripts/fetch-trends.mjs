#!/usr/bin/env node

import { openDb } from "./db.mjs";

const SOURCES = {
  hackernews: {
    url: "https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=30&numericFilters=created_at_i>",
    category: (title) => categorize(title),
  },
  devto: {
    url: "https://dev.to/api/articles?top=7&per_page=30",
    category: (tags) => categorizeByTags(tags),
  },
};

const CATEGORY_KEYWORDS = {
  "AI/ML": [
    "ai", "ml", "llm", "gpt", "claude", "machine learning", "deep learning",
    "neural", "openai", "anthropic", "vector", "embedding",
    "ai ", "人工知能", "機械学習", "生成ai", "chatgpt", "自動化", "モデル",
  ],
  Security: [
    "security", "vulnerability", "exploit", "cve", "auth", "encryption",
    "hack", "breach", "zero-day",
    "セキュリティ", "脆弱性", "認証", "暗号", "リスク", "攻撃", "不正アクセス",
  ],
  Infrastructure: [
    "kubernetes", "docker", "k8s", "terraform", "aws", "gcp", "azure",
    "devops", "ci/cd", "cloud", "infra",
    "インフラ", "クラウド", "サーバー", "デプロイ", "コンテナ", "ローカル",
  ],
  Tech: [
    "javascript", "typescript", "python", "rust", "go", "golang", "node",
    "react", "api", "database", "sql", "git", "os", "windows", "linux",
    "pc", "office", "プログラミング", "開発", "コード", "エンジニア", "技術",
    "ツール", "ライブラリ", "フレームワーク", "性能", "roi",
  ],
  キャリア: [
    "career", "job", "hiring", "interview", "salary", "remote work",
    "developer", "engineer",
    "転職", "採用", "キャリア", "面接", "給与", "リモート", "フリーランス",
    "コスト", "依頼", "ゴール", "ヘルプ",
  ],
  スタートアップ: [
    "startup", "funding", "vc", "saas", "product", "launch", "founder",
    "スタートアップ", "起業", "事業", "プロダクト",
  ],
  "経済・市場": [
    "market", "economy", "finance", "stock", "investment", "crypto", "gdp",
    "経済", "市場", "投資", "グローバル", "労働", "規範",
  ],
  エンタメ: [
    "game", "gaming", "movie", "music", "art", "design", "creative",
    "エンタメ", "ゲーム", "映画", "音楽", "デザイン",
  ],
  ライフスタイル: [
    "health", "productivity", "habit", "sleep", "fitness", "life",
    "習慣", "生産性", "健康", "ライフスタイル", "会議室", "ミーティング",
  ],
  "社会・文化": [
    "society", "culture", "education", "environment", "politics", "social",
    "社会", "文化", "教育", "組織", "変化", "意識", "恥", "実行",
    "仕事", "業務", "チーム", "コミュニケーション", "オンサイト", "非同期",
  ],
};

export function categorize(text) {
  const lower = text.toLowerCase();
  for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
    if (keywords.some((k) => lower.includes(k))) return category;
  }
  return "Tech";
}

function categorizeByTags(tags = []) {
  const tagStr = tags.join(" ").toLowerCase();
  return categorize(tagStr);
}

async function fetchHackerNews() {
  const since = Math.floor(Date.now() / 1000) - 7 * 24 * 60 * 60;
  const res = await fetch(`${SOURCES.hackernews.url}${since}`);
  const data = await res.json();

  return (data.hits || [])
    .filter((h) => h.title && h.points > 10)
    .map((h) => ({
      source: "hackernews",
      keyword: h.title,
      category: categorize(h.title),
    }));
}

async function fetchDevTo() {
  const res = await fetch(SOURCES.devto.url);
  const articles = await res.json();

  return (articles || [])
    .filter((a) => a.title)
    .map((a) => ({
      source: "devto",
      keyword: a.title,
      category: categorizeByTags(a.tag_list || []),
    }));
}

export async function fetchAndStore() {
  const db = openDb();
  const insert = db.prepare(`
    INSERT OR IGNORE INTO keywords (source, keyword, category)
    VALUES (@source, @keyword, @category)
  `);

  const [hnItems, devtoItems] = await Promise.all([
    fetchHackerNews(),
    fetchDevTo(),
  ]);
  const all = [...hnItems, ...devtoItems];

  const insertMany = db.transaction((items) => {
    for (const item of items) insert.run(item);
  });

  insertMany(all);
  db.close();

  return all.length;
}

// CLI entry
import { fileURLToPath } from 'url';
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const count = await fetchAndStore();
  process.stdout.write(`Fetched ${count} keywords\n`);
}
