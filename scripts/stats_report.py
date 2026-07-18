#!/usr/bin/env python3
"""
週次統計レポート生成
stdin: Zenn API JSON (articles?username=...)
stdout: Markdown テーブル（Issue 本文用）
使用: curl -s "..." | python3 scripts/stats_report.py
"""
import json
import sys
import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent


def load_predictions():
    p = ROOT / "stats" / "predictions.yml"
    if not p.exists():
        return {}
    try:
        import yaml

        return yaml.safe_load(p.read_text()) or {}
    except ImportError:
        # yaml 未インストール時は簡易パーサー
        result = {}
        current = None
        for line in p.read_text().splitlines():
            if line.startswith("#") or not line.strip():
                continue
            if not line.startswith(" "):
                current = line.rstrip(":")
                result[current] = {}
            elif current and ":" in line:
                k, v = line.strip().split(":", 1)
                v = v.strip().strip('"')
                try:
                    result[current][k] = int(v)
                except ValueError:
                    result[current][k] = v
        return result


def verdict(likes, low, high):
    if likes >= high:
        return "🔥上振れ"
    if likes >= low:
        return "✅範囲内"
    if likes >= low * 0.5:
        return "⚠️下振れ"
    return "❌大外れ"


def main():
    data = json.load(sys.stdin)
    articles = sorted(data.get("articles", []), key=lambda a: a["published_at"])
    preds = load_predictions()
    today = datetime.date.today()

    total_likes = sum(a.get("liked_count", 0) for a in articles)
    print(f"記事数: {len(articles)}  累計いいね: {total_likes}")
    print()
    print("| 公開日 | タイトル | 経過日 | 👍実測 | 予測範囲 | 判定 |")
    print("|--------|----------|--------|--------|----------|------|")

    for a in articles:
        slug = a["slug"]
        likes = a.get("liked_count", 0)
        pub = a["published_at"][:10]
        days = (today - datetime.date.fromisoformat(pub)).days
        pred = preds.get(slug, {})
        target = "7d" if days <= 7 else "30d"
        low = pred.get(f"predicted_likes_{target}_low")
        high = pred.get(f"predicted_likes_{target}_high")
        if low is None or high is None:
            rng, v = "未設定", "—"
        else:
            rng = f"{low}〜{high}"
            v = verdict(likes, low, high)
        title = a["title"][:22]
        print(f"| {pub} | {title} | {days}d | {likes} | {rng} | {v} |")

    # タイプ別集計
    tech = [a for a in articles if preds.get(a["slug"], {}).get("type") == "tech"]
    idea = [a for a in articles if preds.get(a["slug"], {}).get("type") == "idea"]
    if tech or idea:
        print()
        if tech:
            avg = sum(a.get("liked_count", 0) for a in tech) / len(tech)
            print(f"**tech 平均**: {avg:.1f} likes（{len(tech)}本）")
        if idea:
            avg = sum(a.get("liked_count", 0) for a in idea) / len(idea)
            print(f"**idea 平均**: {avg:.1f} likes（{len(idea)}本）")


if __name__ == "__main__":
    main()
