#!/usr/bin/env bash
# 本地分析 YouTube 视频颜色，结果推送到 gh-pages
# 用法: ./scripts/analyze_and_deploy.sh <youtube_url> [颜色数量]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

URL="${1:?用法: $0 <youtube_url> [颜色数量] [--all-frames]}"
N_COLORS="${2:-12}"

# 检查是否有 --all-frames 参数
ALL_FRAMES=""
for arg in "$@"; do
  if [ "$arg" = "--all-frames" ]; then
    ALL_FRAMES="--all-frames"
    echo "⚠️  逐帧分析模式，会比较慢喵~"
  fi
done

echo "🎨 本地分析中..."
RESULT=$(python3 "$SCRIPT_DIR/analyze.py" "$URL" -n "$N_COLORS" $ALL_FRAMES)
VIDEO_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['video_id'])")

echo "📤 推送结果到 gh-pages..."
cd "$REPO_DIR"

# 保存当前分支
CURRENT_BRANCH=$(git branch --show-current)

# 切到 gh-pages
git stash --include-untracked -q 2>/dev/null || true
git checkout gh-pages -q

mkdir -p results
echo "$RESULT" > "results/${VIDEO_ID}.json"

# 更新 index
python3 -c "
import json, glob, os
items = []
for f in sorted(glob.glob('results/*.json'), key=os.path.getmtime, reverse=True):
    if f.endswith('index.json'): continue
    with open(f) as fh:
        d = json.load(fh)
        items.append({'video_id': d['video_id'], 'title': d['title'], 'url': d['url'], 'analyzed_at': d['analyzed_at'], 'top_color': d['colors'][0]['hex'] if d['colors'] else '#000'})
with open('results/index.json', 'w') as fh:
    json.dump(items, fh, ensure_ascii=False, indent=2)
"

git add results/
git commit -m "Add analysis: ${VIDEO_ID}" -q
git push origin gh-pages -q

# 回到原分支
git checkout "$CURRENT_BRANCH" -q
git stash pop -q 2>/dev/null || true

echo "✅ 完成! 访问 https://$(git remote get-url origin | sed 's|.*github.com[:/]||;s|\.git$||' | sed 's|/|.github.io/|') 查看结果"
