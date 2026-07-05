import os
import shutil
import subprocess
import sys
from typing import Optional, Tuple

def find_ffmpeg_binary(binary_name: str = "ffmpeg") -> Optional[str]:
    """
    Attempts to locate a system-wide or project-local ffmpeg/ffprobe binary.
    Checks the PATH, /home/user, and other typical paths.
    """
    # 1. Check if it's directly in PATH
    path_res = shutil.which(binary_name)
    if path_res:
        return path_res

    # 2. Check workspace directories specifically
    possible_paths = [
        os.path.join("/home/user", binary_name),
        os.path.join(os.getcwd(), binary_name)
    ]
    for p in possible_paths:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p

    return None

def verify_ffmpeg_installation() -> Tuple[str, str]:
    """
    Verifies that ffmpeg and ffprobe are available and functional.
    Returns a tuple of paths: (ffmpeg_path, ffprobe_path)
    Raises RuntimeError with install instructions if either is missing.
    """
    ffmpeg_path = find_ffmpeg_binary("ffmpeg")
    ffprobe_path = find_ffmpeg_binary("ffprobe")

    if not ffmpeg_path or not ffprobe_path:
        error_msg = (
            "\n" + "="*70 + "\n"
            " ERROR: FFmpeg or FFprobe dependencies were not found on this system.\n"
            " " + "="*70 + "\n"
            " Both binaries must be installed to run this pipeline.\n\n"
            " How to Install FFmpeg:\n"
            " - Ubuntu/Debian:  sudo apt update && sudo apt install ffmpeg\n"
            " - macOS (Homebrew): brew install ffmpeg\n"
            " - Windows (Choco):   choco install ffmpeg\n"
            " - Manual Static Binaries: Download from https://johnvansickle.com/ffmpeg/ (Linux)\n"
            "   or https://www.gyan.dev/ffmpeg/builds/ (Windows) and add to your system PATH.\n"
            " " + "="*70 + "\n"
        )
        raise RuntimeError(error_msg)

    # Simple sanity check execution
    try:
        subprocess.run([ffmpeg_path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception as e:
        raise RuntimeError(f"FFmpeg binary at {ffmpeg_path} exists but is not functional: {e}")

    return ffmpeg_path, ffprobe_path

def validate_video_file(video_path: str) -> dict:
    """
    Validates that the input file is a readable video using ffprobe.
    Returns metadata dict containing:
      - 'duration': float (seconds)
      - 'has_audio': bool
      - 'has_video': bool
    """
    print(f"[*] Validating input video file: {video_path}...")
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Input file not found: {video_path}")

    _, ffprobe_path = verify_ffmpeg_installation()

    # Query stream info in JSON/flat format
    command = [
        ffprobe_path, "-v", "error",
        "-show_entries", "format=duration:stream=codec_type",
        "-of", "default=noprint_wrappers=1",
        video_path
    ]

    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        output = result.stdout
    except subprocess.CalledProcessError as e:
        err_out = e.stderr or e.stdout
        raise ValueError(f"Input file could not be analyzed by ffprobe. Is it a valid video format? Error details: {err_out}")

    duration = 0.0
    has_audio = False
    has_video = False

    for line in output.splitlines():
        if "=" in line:
            key, val = line.strip().split("=", 1)
            if key == "duration":
                try:
                    duration = float(val)
                except ValueError:
                    pass
            elif key == "codec_type":
                if val == "video":
                    has_video = True
                elif val == "audio":
                    has_audio = True

    if not has_video:
        print("[!] Warning: Input file does not contain a video stream.")
    if not has_audio:
        raise ValueError("Input file contains no audio streams. Transcription is impossible.")

    print(f"[+] Video is valid. Duration: {duration:.2f} seconds. (Audio: Yes, Video: {has_video})")
    return {
        "duration": duration,
        "has_audio": has_audio,
        "has_video": has_video
    }

def extract_audio(video_path: str, output_audio_path: str, apply_denoise: bool = False) -> str:
    """
    Extracts audio from video_path and saves it as a 16kHz mono WAV file.
    Optionally applies a background noise reduction pass using FFmpeg's lowpass/highpass filters.
    """
    print(f"[*] Extracting audio from {video_path}...")
    ffmpeg_path, _ = verify_ffmpeg_installation()

    # Core conversion flags
    command = [
        ffmpeg_path, "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1"
    ]

    if apply_denoise:
        # Apply gentle highpass (removes low-end hums < 80Hz) and lowpass (removes high-end hisses > 8000Hz)
        print("[*] Applying background noise reduction (bandpass speech filters: 80Hz-8000Hz)...")
        command.extend(["-af", "highpass=f=80,lowpass=f=8000"])

    command.append(output_audio_path)

    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(f"[+] Audio successfully extracted to {output_audio_path}")
    except subprocess.CalledProcessError as e:
        print(f"[-] ffmpeg error output: {e.stderr.decode('utf-8', errors='ignore')}", file=sys.stderr)
        raise RuntimeError(f"FFmpeg failed with exit code {e.returncode}") from e

    return output_audio_path
