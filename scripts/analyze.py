#!/usr/bin/env python3
"""从视频帧中提取主要颜色，输出 JSON"""
import sys, os, glob, json, subprocess, tempfile, re
from PIL import Image
from collections import Counter
from datetime import datetime, timezone

def extract_video_id(url):
    m = re.search(r'(?:v=|youtu\.be/)([\w-]{11})', url)
    return m.group(1) if m else url.replace('/', '_').replace(':', '_')

def analyze(url, n_colors=12, interval=2):
    video_id = extract_video_id(url)

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video.mp4")

        # 下载
        subprocess.run([
            "yt-dlp", "-f", "worst[ext=mp4]",
            "-o", video_path, "--no-playlist", "-q", url
        ], check=True)

        # 获取视频标题
        title_result = subprocess.run([
            "yt-dlp", "--get-title", "--no-playlist", url
        ], capture_output=True, text=True)
        title = title_result.stdout.strip() or video_id

        # 采样帧
        subprocess.run([
            "ffmpeg", "-i", video_path,
            "-vf", f"fps=1/{interval}",
            os.path.join(tmpdir, "frame_%04d.png"),
            "-hide_banner", "-loglevel", "error"
        ], check=True)

        # 分析颜色
        all_pixels = Counter()
        frames = sorted(glob.glob(os.path.join(tmpdir, "frame_*.png")))

        for fp in frames:
            img = Image.open(fp).convert("RGB")
            img = img.resize((80, 45), Image.LANCZOS)
            pixels = list(img.getdata())
            for r, g, b in pixels:
                qr, qg, qb = (r // 8) * 8, (g // 8) * 8, (b // 8) * 8
                all_pixels[(qr, qg, qb)] += 1

        # 生成缩略图（取中间帧）
        thumbnail_data = None
        if frames:
            mid = frames[len(frames) // 2]
            thumb = Image.open(mid).convert("RGB")
            thumb.thumbnail((320, 180))
            import base64, io
            buf = io.BytesIO()
            thumb.save(buf, format="JPEG", quality=60)
            thumbnail_data = base64.b64encode(buf.getvalue()).decode()

        total = sum(all_pixels.values())
        top = all_pixels.most_common(n_colors)

        colors = []
        for (r, g, b), count in top:
            colors.append({
                "hex": f"#{r:02X}{g:02X}{b:02X}",
                "rgb": [r, g, b],
                "percentage": round(count / total * 100, 2)
            })

        return {
            "video_id": video_id,
            "title": title,
            "url": url,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "frames_sampled": len(frames),
            "thumbnail": thumbnail_data,
            "colors": colors
        }

if __name__ == "__main__":
    url = sys.argv[1]
    n_colors = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    result = analyze(url, n_colors)

    # 输出到 stdout
    print(json.dumps(result, ensure_ascii=False, indent=2))
