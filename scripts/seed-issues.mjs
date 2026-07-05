#!/usr/bin/env node

import { execSync } from 'child_process';
import { openDb } from './db.mjs';
import { categorize } from './fetch-trends.mjs';

const REPO = 'flipslidersand/dev-nodee-infrastructure';

const issues = JSON.parse(
  execSync(`gh issue list -R ${REPO} --json number,title --limit 100`, {
    encoding: 'utf8',
  }),
).filter((i) => i.number >= 192 && i.number <= 211);

const db = openDb();

const upsert = db.prepare(`
  INSERT INTO keywords (source, keyword, category)
  VALUES (@source, @keyword, @category)
  ON CONFLICT(source, keyword) DO UPDATE SET category = excluded.category
`);

const upsertMany = db.transaction((items) => {
  for (const { source, keyword, category } of items)
    upsert.run({ source, keyword, category });
});

// "Zenn: " プレフィックスは Issue 管理用のラベルであり記事テーマではない。
// 残すと LLM が「Zenn プラットフォームについての記事」と誤解する。
const items = issues.map((i) => {
  const keyword = i.title.replace(/^Zenn:\s*/, '');
  return {
    source: 'zenn-issue',
    keyword,
    category: categorize(keyword),
    number: i.number,
  };
});

upsertMany(items);
db.close();

for (const item of items) {
  process.stdout.write(`#${item.number} [${item.category}] ${item.keyword}\n`);
}
process.stdout.write(`\nTotal: ${items.length} keywords\n`);
