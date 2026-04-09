#!/usr/bin/env python3
"""从视频帧中提取主要颜色，输出 JSON"""
import sys, os, glob, json, subprocess, tempfile, re
from PIL import Image
from collections import Counter
from datetime import datetime, timezone

def extract_video_id(url):
    m = re.search(r'(?:v=|youtu\.be/)([\w-]{11})', url)
    return m.group(1) if m else url.replace('/', '_').replace(':', '_')

def analyze(url, n_colors=12, interval=2, all_frames=False):
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
        vf_filter = "fps=1/0" if all_frames else f"fps=1/{interval}"
        ffmpeg_cmd = [
            "ffmpeg", "-i", video_path,
            "-hide_banner", "-loglevel", "error"
        ]
        if all_frames:
            # 逐帧提取
            ffmpeg_cmd += [os.path.join(tmpdir, "frame_%06d.png")]
        else:
            ffmpeg_cmd += ["-vf", f"fps=1/{interval}", os.path.join(tmpdir, "frame_%04d.png")]
        subprocess.run(ffmpeg_cmd, check=True)

        # 分析颜色
        all_pixels = Counter()
        frames = sorted(glob.glob(os.path.join(tmpdir, "frame_*.png")))
        print(f"📸 共 {len(frames)} 帧" + (" (逐帧)" if all_frames else f" (每{interval}秒)"), file=sys.stderr)

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
    import argparse
    parser = argparse.ArgumentParser(description="从 YouTube 视频提取主要颜色")
    parser.add_argument("url", help="YouTube 视频 URL")
    parser.add_argument("-n", "--n-colors", type=int, default=12, help="提取颜色数量 (默认 12)")
    parser.add_argument("-i", "--interval", type=int, default=2, help="采样间隔秒数 (默认 2)")
    parser.add_argument("--all-frames", action="store_true", help="逐帧分析（慢但精确）")
    args = parser.parse_args()

    result = analyze(args.url, args.n_colors, args.interval, args.all_frames)
    print(json.dumps(result, ensure_ascii=False, indent=2))
