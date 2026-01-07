import os
import sys
import time
import ctypes
import subprocess
from pathlib import Path

# ================== USER CONFIG ==================
VIDEO_PATH = "input.mp4"
OUT_DIR = "highlights"
FFMPEG_BIN = "ffmpeg"   # set full path if not in PATH, e.g. r"C:\ffmpeg\bin\ffmpeg.exe"

FAST_COPY = True        # True = -c copy (nhanh, có thể lệch keyframe vài frame)
ROLL_ENABLED = True
PRE_ROLL_SEC = 0.30
POST_ROLL_SEC = 0.20
STEP = 0.10             # bước chỉnh pre/post bằng hotkey

# Hotkeys
KEY_IN = "i"
KEY_OUT = "o"
KEY_UNDO = "u"
KEY_PRINT = "p"
KEY_EXPORT = "e"
KEY_QUIT = "q"
KEY_QUIT_CTRL = "ctrl+q"  # NEW

KEY_TOGGLE_ROLL = "r"
KEY_PRE_DOWN = "["
KEY_PRE_UP = "]"
KEY_POST_DOWN = "-"
KEY_POST_UP = "="
# ==================================================

def is_64bit_python() -> bool:
    return sys.maxsize > 2**32

def find_vlc_dir() -> str | None:
    # Prefer 64-bit VLC, then 32-bit VLC
    candidates = [
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC",
    ]
    for d in candidates:
        if Path(d, "libvlc.dll").exists() and Path(d, "libvlccore.dll").exists():
            return d
    return None

def setup_vlc_dll(vlc_dir: str):
    vlc_dir = str(Path(vlc_dir))
    vlc_dll = str(Path(vlc_dir) / "libvlc.dll")
    vlc_core = str(Path(vlc_dir) / "libvlccore.dll")

    # Make Windows search VLC dir for dependencies
    os.add_dll_directory(vlc_dir)
    os.environ["PATH"] = vlc_dir + os.pathsep + os.environ.get("PATH", "")

    # Force load to validate architecture match early
    ctypes.CDLL(vlc_core)
    ctypes.CDLL(vlc_dll)

def bootstrap_vlc() -> tuple[str, str]:
    vlc_dir = find_vlc_dir()
    if not vlc_dir:
        print("❌ Không tìm thấy VLC (libvlc.dll).")
        print("✅ Hãy cài VLC Desktop (khuyên dùng 64-bit).")
        sys.exit(1)

    if is_64bit_python() and "Program Files (x86)" in vlc_dir:
        print("❌ Python đang là 64-bit nhưng VLC là 32-bit (Program Files (x86)).")
        print("✅ Hãy gỡ VLC hiện tại và cài VLC 64-bit tại: C:\\Program Files\\VideoLAN\\VLC")
        sys.exit(1)

    try:
        setup_vlc_dll(vlc_dir)
    except OSError as e:
        print("❌ Không load được libVLC:", e)
        print("✅ Khuyến nghị: Python 64-bit + VLC 64-bit.")
        sys.exit(1)

    plugin_dir = str(Path(vlc_dir) / "plugins")
    return vlc_dir, plugin_dir

VLC_DIR, VLC_PLUGIN_DIR = bootstrap_vlc()

# Import after bootstrap
import vlc
import keyboard

def fmt_tc(sec: float) -> str:
    sec = max(0.0, sec)
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec) % 60
    m = (int(sec) // 60) % 60
    h = int(sec) // 3600
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def ensure_inputs():
    if not Path(VIDEO_PATH).exists():
        raise FileNotFoundError(f"Không thấy file: {VIDEO_PATH} (đặt cùng thư mục script).")
    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

def safe_run(cmd: list[str]):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr

def get_duration_ffprobe(video_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        video_path
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    return float(out)

def export_highlights(highlights: list[tuple[float, float]]):
    ensure_inputs()
    if not highlights:
        print("Không có highlight nào để export.")
        return

    print(f"\n=== EXPORT {len(highlights)} highlight(s) ===")
    for idx, (s, e) in enumerate(highlights, 1):
        if e <= s:
            print(f"Skip HL_{idx:03d}: OUT <= IN")
            continue

        out_path = str(Path(OUT_DIR) / f"HL_{idx:03d}.mp4")

        if FAST_COPY:
            # fast but may snap to keyframes slightly
            cmd = [
                FFMPEG_BIN, "-y",
                "-ss", f"{s:.3f}",
                "-to", f"{e:.3f}",
                "-i", VIDEO_PATH,
                "-c", "copy",
                out_path
            ]
        else:
            # accurate but slower
            cmd = [
                FFMPEG_BIN, "-y",
                "-ss", f"{s:.3f}",
                "-to", f"{e:.3f}",
                "-i", VIDEO_PATH,
                "-c:v", "libx264",
                "-c:a", "aac",
                out_path
            ]

        rc, _, err = safe_run(cmd)
        if rc == 0:
            print(f"OK  {Path(out_path).name}  [{fmt_tc(s)} -> {fmt_tc(e)}]  dur={(e - s):.3f}s")
        else:
            print(f"FAIL {Path(out_path).name}\n{err}")

    # Save CSV reference
    csv_path = Path(OUT_DIR) / "highlights.csv"
    lines = ["index,in_sec,out_sec,duration_sec,in_tc,out_tc"]
    for i, (s, e) in enumerate(highlights, 1):
        lines.append(f"{i},{s:.3f},{e:.3f},{(e - s):.3f},{fmt_tc(s)},{fmt_tc(e)}")
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {csv_path}")

def main():
    global ROLL_ENABLED, PRE_ROLL_SEC, POST_ROLL_SEC

    ensure_inputs()
    duration = get_duration_ffprobe(VIDEO_PATH)

    instance = vlc.Instance([f"--plugin-path={VLC_PLUGIN_DIR}"])
    media = instance.media_new(VIDEO_PATH)
    player = instance.media_player_new()
    player.set_media(media)

    def status_roll() -> str:
        return f"ROLL={'ON' if ROLL_ENABLED else 'OFF'} | pre={PRE_ROLL_SEC:.2f}s | post={POST_ROLL_SEC:.2f}s"

    def get_time_sec() -> float:
        ms = player.get_time()
        return 0.0 if ms is None or ms < 0 else ms / 1000.0

    def compute_in(now: float) -> float:
        if not ROLL_ENABLED:
            return clamp(now, 0.0, duration)
        return clamp(now - PRE_ROLL_SEC, 0.0, duration)

    def compute_out(now: float) -> float:
        if not ROLL_ENABLED:
            return clamp(now, 0.0, duration)
        return clamp(now + POST_ROLL_SEC, 0.0, duration)

    in_point = None
    highlights: list[tuple[float, float]] = []

    print("=== VLC Hotkey Highlight Cutter (Windows) ===")
    print(f"Using VLC: {VLC_DIR}")
    print(f"Video: {VIDEO_PATH} | Duration: {duration:.3f}s")
    print("Hotkeys:")
    print(f"  I = IN (pre-roll) | O = OUT (post-roll) + save")
    print(f"  U = Undo | P = Print | E = Export")
    print(f"  Q = Quit | Ctrl+Q = Quit (NEW)")
    print("Roll tuning:")
    print(f"  R toggle roll | [ ] pre-roll -/+{STEP:.2f}s | - = post-roll -/+{STEP:.2f}s")
    print(f"Current: {status_roll()}")
    print("\nNOTE: hotkey global (bấm khi VLC đang phát vẫn nhận).")

    player.play()
    time.sleep(0.4)

    def on_in():
        nonlocal_in = None  # dummy to avoid confusion; real var is outer scope `in_point`
        del nonlocal_in
        nonlocal in_point
        now = get_time_sec()
        in_point = compute_in(now)
        tag = " (rolled)" if ROLL_ENABLED else ""
        print(f"IN  = {fmt_tc(in_point)}{tag} | now={fmt_tc(now)} | {status_roll()}")

    def on_out():
        nonlocal in_point, highlights
        now = get_time_sec()
        out_point = compute_out(now)

        if in_point is None:
            print("OUT ignored: chưa set IN (bấm I trước).")
            return
        if out_point <= in_point:
            print(f"OUT ignored: OUT ({fmt_tc(out_point)}) <= IN ({fmt_tc(in_point)})")
            return

        highlights.append((in_point, out_point))
        tag = " (rolled)" if ROLL_ENABLED else ""
        print(f"SAVED HL_{len(highlights):03d}: [{fmt_tc(in_point)} -> {fmt_tc(out_point)}] dur={(out_point - in_point):.3f}s{tag} | now={fmt_tc(now)}")
        in_point = None

    def on_undo():
        nonlocal in_point, highlights
        if highlights:
            s, e = highlights.pop()
            print(f"UNDO last: [{fmt_tc(s)} -> {fmt_tc(e)}]")
        else:
            print("UNDO: không có highlight nào.")
        in_point = None

    def on_print():
        if not highlights:
            print("No highlights yet.")
            return
        print("\n=== HIGHLIGHTS ===")
        for i, (s, e) in enumerate(highlights, 1):
            print(f"HL_{i:03d}: {fmt_tc(s)} -> {fmt_tc(e)}  dur={(e - s):.3f}s")
        print(f"=== {status_roll()} ===\n")

    def on_export():
        export_highlights(highlights)

    def on_toggle_roll():
        nonlocal in_point
        ROLL_ENABLED_local = globals()["ROLL_ENABLED"]
        globals()["ROLL_ENABLED"] = not ROLL_ENABLED_local
        in_point = None
        print(f"Toggle -> {status_roll()}")

    def on_pre_down():
        globals()["PRE_ROLL_SEC"] = max(0.0, globals()["PRE_ROLL_SEC"] - STEP)
        print(status_roll())

    def on_pre_up():
        globals()["PRE_ROLL_SEC"] = globals()["PRE_ROLL_SEC"] + STEP
        print(status_roll())

    def on_post_down():
        globals()["POST_ROLL_SEC"] = max(0.0, globals()["POST_ROLL_SEC"] - STEP)
        print(status_roll())

    def on_post_up():
        globals()["POST_ROLL_SEC"] = globals()["POST_ROLL_SEC"] + STEP
        print(status_roll())

    def on_quit():
        print("Quitting...")
        try:
            player.stop()
        except Exception:
            pass
        os._exit(0)

    # Register hotkeys
    keyboard.add_hotkey(KEY_IN, on_in)
    keyboard.add_hotkey(KEY_OUT, on_out)
    keyboard.add_hotkey(KEY_UNDO, on_undo)
    keyboard.add_hotkey(KEY_PRINT, on_print)
    keyboard.add_hotkey(KEY_EXPORT, on_export)

    keyboard.add_hotkey(KEY_TOGGLE_ROLL, on_toggle_roll)
    keyboard.add_hotkey(KEY_PRE_DOWN, on_pre_down)
    keyboard.add_hotkey(KEY_PRE_UP, on_pre_up)
    keyboard.add_hotkey(KEY_POST_DOWN, on_post_down)
    keyboard.add_hotkey(KEY_POST_UP, on_post_up)

    keyboard.add_hotkey(KEY_QUIT, on_quit)
    keyboard.add_hotkey(KEY_QUIT_CTRL, on_quit)  # Ctrl+Q (NEW)

    # Keep alive
    try:
        while True:
            time.sleep(0.2)
            state = player.get_state()
            if state in (vlc.State.Ended, vlc.State.Error):
                print(f"Player state: {state}. Press E to export, Q/Ctrl+Q to quit.")
                time.sleep(1.0)
    except KeyboardInterrupt:
        on_quit()

if __name__ == "__main__":
    main()
