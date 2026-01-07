import subprocess
import re
from pathlib import Path
import argparse

# =========================
# Defaults (you can override by CLI arguments)
FPS = 30                  # fixed 30fps template
REEL = "WHITE"            # <= 8 chars (EDL convention)
DEFAULT_SCENE_THRESHOLD = 0.10   # more sensitive than 0.20/0.30
DEFAULT_DEDUPE_WINDOW = 0.05     # small merge window; set 0.0 to disable merge
# =========================

TIME_RE = re.compile(r"pts_time:([0-9]+\.[0-9]+)")

def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)

def require_tools():
    for tool in ("ffmpeg", "ffprobe"):
        p = run([tool, "-version"])
        if p.returncode != 0:
            raise RuntimeError(
                f"Không tìm thấy '{tool}' trong PATH.\n"
                f"Hãy cài FFmpeg và đảm bảo gõ được: {tool} -version\n"
            )

def ffprobe_size_duration(video_path: str) -> tuple[int, int, float]:
    """
    Return (width, height, duration_seconds).
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration",
        "-of", "default=nw=1",
        video_path
    ]
    try:
        out = subprocess.check_output(cmd, text=True).strip().splitlines()
    except subprocess.CalledProcessError as e:
        raise RuntimeError("ffprobe lỗi. Kiểm tra file video có đọc được không.") from e

    info = {}
    for line in out:
        if "=" in line:
            k, v = line.split("=", 1)
            info[k.strip()] = v.strip()

    if "width" not in info or "height" not in info or "duration" not in info:
        raise RuntimeError("ffprobe không trả về đủ thông tin width/height/duration.")

    return int(info["width"]), int(info["height"]), float(info["duration"])

def detect_cuts_ffmpeg_raw(video_path: str, scene_threshold: float) -> list[float]:
    """
    Use FFmpeg scene detection to get raw cut timestamps (seconds).
    """
    cmd = [
        "ffmpeg", "-hide_banner", "-i", video_path,
        "-vf", f"select='gt(scene,{scene_threshold})',showinfo",
        "-f", "null", "-"
    ]
    p = run(cmd)

    # FFmpeg logs are in stderr
    cuts = []
    for line in p.stderr.splitlines():
        m = TIME_RE.search(line)
        if m:
            cuts.append(float(m.group(1)))

    cuts.sort()
    return cuts

def dedupe_cuts(cuts: list[float], dedupe_window_sec: float) -> list[float]:
    """
    Merge cuts too close. Set dedupe_window_sec=0 to disable.
    """
    if dedupe_window_sec <= 0:
        # Still normalize rounding a bit to avoid duplicates from parsing noise
        return sorted(set(round(t, 3) for t in cuts))

    merged = []
    for t in cuts:
        if not merged or (t - merged[-1]) >= dedupe_window_sec:
            merged.append(t)

    # normalize
    return [round(t, 3) for t in merged]

def to_segments(cuts: list[float], duration: float) -> list[tuple[float, float]]:
    """
    Convert cut points into segments: [(start_sec, end_sec), ...]
    """
    points = [0.0] + cuts + [duration]
    segs = []
    for a, b in zip(points, points[1:]):
        if b > a:
            segs.append((a, b))
    return segs

def sec_to_frames(t: float) -> int:
    return int(round(t * FPS))

def frames_to_tc(frames: int) -> str:
    """
    Convert frames to NON-DROP timecode HH:MM:SS:FF using FPS=30.
    """
    ff = frames % FPS
    total_seconds = frames // FPS
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

def make_white_master(out_path: str, duration: float, width: int, height: int):
    """
    Create a white MP4 clip with exact duration, size, FPS.
    """
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=white:s={width}x{height}:r={FPS}",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        out_path
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError("FFmpeg tạo white_master thất bại:\n" + p.stderr)

def export_edl(segs: list[tuple[float, float]], edl_path: str, reel: str):
    """
    Export CMX3600 EDL that cuts WHITE master into segment events.
    """
    lines = []
    lines.append("TITLE: WHITE_TEMPLATE_30FPS")
    lines.append("FCM: NON-DROP FRAME")
    lines.append("")

    for i, (s, e) in enumerate(segs, 1):
        rec_in_f = sec_to_frames(s)
        rec_out_f = sec_to_frames(e)

        rec_in_tc = frames_to_tc(rec_in_f)
        rec_out_tc = frames_to_tc(rec_out_f)

        # Source TC == Record TC (we're cutting the same white master timeline)
        lines.append(
            f"{i:03d}  {reel:<8} V     C        "
            f"{rec_in_tc} {rec_out_tc} {rec_in_tc} {rec_out_tc}"
        )
        lines.append(f"* FROM CLIP NAME: {reel}")
        lines.append("")

    Path(edl_path).write_text("\n".join(lines), encoding="utf-8")

def export_csv(segs: list[tuple[float, float]], out_csv: str):
    lines = ["index,start_sec,end_sec,duration_sec,start_tc,end_tc"]
    for i, (s, e) in enumerate(segs, 1):
        s_tc = frames_to_tc(sec_to_frames(s))
        e_tc = frames_to_tc(sec_to_frames(e))
        lines.append(f"{i},{s:.3f},{e:.3f},{(e-s):.3f},{s_tc},{e_tc}")
    Path(out_csv).write_text("\n".join(lines), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(
        description="Detect scene cuts from input video, then generate white_master.mp4 + timeline.edl (30fps)."
    )
    parser.add_argument("-i", "--input", default="input.mp4", help="Input sample video path (default: input.mp4)")
    parser.add_argument("-t", "--threshold", type=float, default=DEFAULT_SCENE_THRESHOLD,
                        help=f"Scene threshold (default: {DEFAULT_SCENE_THRESHOLD}). Lower => more cuts.")
    parser.add_argument("-d", "--dedupe", type=float, default=DEFAULT_DEDUPE_WINDOW,
                        help=f"Dedupe window in seconds (default: {DEFAULT_DEDUPE_WINDOW}). Set 0 to disable.")
    parser.add_argument("--reel", default=REEL, help=f"EDL reel name <=8 chars (default: {REEL})")
    parser.add_argument("--no-white", action="store_true", help="Do not generate white_master.mp4 (EDL/CSV only)")
    args = parser.parse_args()

    require_tools()

    input_video = args.input
    if not Path(input_video).exists():
        raise FileNotFoundError(
            f"Không thấy '{input_video}'.\n"
            f"Hãy đổi tên video mẫu thành input.mp4 hoặc chạy: python scene_blank_30fps_fixed.py -i your.mp4"
        )

    if len(args.reel) > 8:
        raise ValueError("REEL name phải <= 8 ký tự (chuẩn EDL). Ví dụ: WHITE")

    width, height, duration = ffprobe_size_duration(input_video)

    raw_cuts = detect_cuts_ffmpeg_raw(input_video, args.threshold)
    cuts = dedupe_cuts(raw_cuts, args.dedupe)
    segs = to_segments(cuts, duration)

    print("=== INFO ===")
    print(f"Video: {input_video}")
    print(f"Size: {width}x{height}")
    print(f"Duration: {duration:.3f}s")
    print(f"Template FPS: {FPS}")
    print(f"Scene threshold: {args.threshold}")
    print(f"Dedupe window: {args.dedupe} sec")
    print(f"Raw cuts found: {len(raw_cuts)}")
    print(f"Cuts after dedupe: {len(cuts)}")
    print(f"Segments: {len(segs)}")

    print("\n=== OUTPUT ===")
    if not args.no_white:
        make_white_master("white_master.mp4", duration, width, height)
        print(" - white_master.mp4")

    export_edl(segs, "timeline.edl", args.reel)
    export_csv(segs, "segments.csv")
    print(" - timeline.edl")
    print(" - segments.csv")

    print("\nGợi ý tuning nhanh:")
    print(" - Nếu vẫn thiếu cut: giảm threshold (ví dụ 0.08, 0.06)")
    print(" - Nếu cut gần nhau bị gộp: set dedupe=0 hoặc 0.02")
    print("Ví dụ:")
    print("  python scene_blank_30fps_fixed.py -i input.mp4 -t 0.08 -d 0")
    print("  python scene_blank_30fps_fixed.py -i input.mp4 -t 0.06 -d 0.02")

if __name__ == "__main__":
    main()
