import os
import subprocess
import zipfile
import re


def get_video_duration(input_file):
    """Get video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_file
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def cut_video(input_file, output_folder, clips_count, duration, progress_callback=None):
    """
    Cut video into clips. Calls progress_callback(percent: int) during processing.
    """
    os.makedirs(output_folder, exist_ok=True)
    clips = []

    total_duration = get_video_duration(input_file)
    total_work = clips_count * duration  # total seconds to encode

    encoded_so_far = 0  # seconds encoded across all clips

    for i in range(clips_count):
        start = i * duration
        out_file = os.path.join(output_folder, f"clip_{i+1}.mp4")

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", input_file,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-progress", "pipe:2",   # ← key: structured progress to stderr
            "-nostats",
            out_file
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True
        )

        clip_encoded = 0.0

        for line in process.stderr:
            line = line.strip()

            # FFmpeg -progress outputs "out_time=HH:MM:SS.mmm"
            if line.startswith("out_time="):
                time_str = line.split("=", 1)[1].strip()
                clip_encoded = _parse_time(time_str)

                if total_work > 0 and progress_callback:
                    total_encoded = encoded_so_far + clip_encoded
                    percent = int(min(total_encoded / total_work * 95, 95))
                    progress_callback(percent)

            elif line.startswith("progress=end"):
                break

        process.wait()
        encoded_so_far += duration  # mark this clip as fully done

        if os.path.exists(out_file):
            clips.append(out_file)

    # Signal 100% after zip (caller should do this)
    return clips


def _parse_time(time_str):
    """Parse HH:MM:SS.mmm or seconds string → float seconds."""
    try:
        if ":" in time_str:
            parts = time_str.split(":")
            h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
            return h * 3600 + m * 60 + s
        else:
            return float(time_str)
    except Exception:
        return 0.0


def make_zip(files, output_zip):
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if os.path.exists(f):
                z.write(f, os.path.basename(f))
    return output_zip