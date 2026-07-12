---
title: "48GBマシンのフリーズ犯人は自分の実装だった — メモリスパイク診断の実例"
published: true
---

MP-i1630（Linux, 48GB RAM）で7月8日から使用中に何度もシステムがフリーズする事象が発生しました。電源ボタン強制再起動が必要になる完全フリーズで、最初はNVIDIAドライバやコンポジタの不具合と疑っていました。しかし、journalctl のboot履歴を丹念に追うと、真犯人は自分たちのバッチプロセスにあったことが判明。その診断プロセスと得た知見を共有します。

## 事象の整理

**タイムライン:**
- 7/08 00:18〜22:34: 短時間boot 10連続（10〜20分で何度も強制再起動）
- 7/09 06:01〜06:56: 2連続
- 7/09 21:04〜22:44: 3連続（メモリ圧迫ログ頻発）
- **7/09 22:45以降: ゼロ再発（7/11現在も安定）**

**事象の特徴:**
```
journalctl から抽出:
 7月 09 22:34:02 systemd-journald: Under memory pressure, flushing caches.
 7月 09 22:34:04 systemd-journald: Under memory pressure, flushing caches.
 7月 09 22:34:06 systemd-journald: Under memory pressure, flushing caches.
libinput: your system is too slow
```

スワップなし、OOM killer ログなし、なのにシステム全体が応答不能に。

## 最初の仮説と棄却

**仮説1: NVIDIA ドライバ / Mutter（ウィンドウコンポジタ）**
- 根拠: GNOME Shell 全体がフリーズしており、GPU関連を疑った
- 棄却理由: Firefox のみならず、複数アプリ使用時も再発しており、ブラウザ非依存と判明

**仮説2: 常駐k8s/ArgoCDスタックの圧迫**
- 常時稼働コンテナ: dev-control-plane (kube-apiserver/etcd) + Grafana/Prometheus/Qdrant 一式
- 根拠: 高負荷状態が常在しているのではないか
- 棄却理由: docker stats で実測すると `dev-control-plane 2.2GB / qdrant 0.7GB / その他 <0.3GB` で合計 ~3.5GB。48GB搭載機での3.5GB は圧迫には遠い

## 真犯人の発見

**Boot 履歴から発見:**
```bash
journalctl --list-boots --no-pager | grep "07-0[89]"
```

この出力に全15回の短時間bootが記録されており、全て **7/08〜7/09 早朝** に集中していました。

**時刻との照合:**
- 7/09 06:01〜06:28: knowledge pipeline 実行中（Qdrant 投入タスク）
- **07:28 に 1回目の "Under memory pressure" ログ**

この時刻が一致したのがきっかけです。

**メモリ使用量の履歴を確認:**
- Rust クローラーの実装に全タスクを `asyncio.create_task()` で同時 spawn していた
- 1000記事×複数タスク = メモリ爆発（RSS 11.5GB 観測）
- 続く push フェーズで torch 勾配が蓄積、RSS 17GB ピーク観測

**結論:**
```
48GB 搭載 → 17GB スパイク = 65% 使用率
→ ページキャッシュ枯渇（スワップなし）
→ スケジューリング遅延
→ ユーザー入力タイムアウト → 入力遅延警告
→ コンポジタ タイムアウト → UI フリーズ
```

メモリリークではなく、**一時的なメモリスパイク** が原因でした。

## 実装の修正と再発ゼロ

バッチのメモリ制御を修正しました：
- Rust クローラーの並列度を制限（全同時 spawn → sequential batch）
- torch 勾配キャッシュをクリア（計算ステップごと）

修正後、7/09 22:45 以降、**2.5日間フリーズ再発ゼロ**。

## 診断手法の実用性

このプロセスで有用だった手法をまとめます。

### 1. journalctl の boot 履歴で全再起動をマッピング
```bash
journalctl --list-boots --no-pager | grep "YYYY-MM-DD"
# 出力:
#  IDX  BOOT_ID                           FIRST               LAST
#   -5  xxx                               2026-07-09 06:01    06:28
#   -4  yyy                               2026-07-09 06:28    06:56
```

短時間 boot が連続している = ハード障害ではなくソフト問題の可能性が高い。

### 2. Per-boot メモリ圧迫イベント集計
```bash
for b in -5 -4 -3 -2 -1 0; do
  journalctl -b $b --no-pager | grep -c "Under memory pressure"
done
```

正常な boot では 0、問題 boot では数〜十数件。この差が明確。

### 3. shutdown の cleanness を確認
```bash
journalctl -b -5 --no-pager | tail -50 | grep -c "Reached target.*Shutdown"
```

- 0 = 強制再起動の可能性
- 1以上 = 正常 shutdown

### 4. タイムラインの照合
イベントログ（memory pressure）の時刻とアプリケーションログ（バッチ処理開始）を照合。一致 → 原因特定。

## PSI（Pressure Stall Information）の活用

現在は以下の monitoring を導入しました：

```bash
cat /proc/pressure/memory
# some avg10=0.00 avg60=0.00 avg300=0.00 total=29
# full avg10=0.00 avg60=0.00 avg300=0.00 total=28

cat /proc/pressure/cpu
# some avg10=0.33 avg60=0.27 avg300=0.44 total=16034362
```

- `memory some`: メモリを待つプロセスが**ある**状態の割合
- `memory full`: メモリを待つプロセスが**すべて**待ってる状態（ほぼフリーズ）
- `cpu some`: CPU を待つプロセスがある状態

systemd timer で 1分ごとに PSI を読んで Discord に通知するようにしました。次回フリーズの予兆が検知できます。

## 教訓

**メモリ不足に見えるが、実は「バッチプロセスのスパイク」である場合がある。**

OOM killer が出ていない、swap が未使用、という条件では特に注意が必要です。systemd-journald の「Under memory pressure」ログとアプリケーションログの時刻照合が、最初の切り分けポイントになります。

diagnostics を正確に行わないと、ドライバのせいにしたり、常駐スタック全体を疑ったり、的外れな対策をしてしまいます。今回も「NVIDIA 最新ドライバに更新」「Wayland 切り替え検証」を検討していました。

実装品質とシステム監視の両方が、こういう突発事象の早期解決には不可欠です。
