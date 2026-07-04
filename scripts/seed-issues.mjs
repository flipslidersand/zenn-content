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
  for (const item of items) upsert.run(item);
});

const items = issues.map((i) => ({
  source: 'zenn-issue',
  keyword: i.title,
  category: categorize(i.title),
}));

upsertMany(items);
db.close();

for (const item of items) {
  process.stdout.write(`#${issues.find(i => i.title === item.keyword)?.number} [${item.category}] ${item.keyword}\n`);
}
process.stdout.write(`\nTotal: ${items.length} keywords\n`);
