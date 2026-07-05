import os
import subprocess
import sys
from typing import List, Dict, Any, Optional

def format_timestamp(seconds: float) -> str:
    """
    Converts float seconds (e.g., 12.34) to SRT timestamp format: HH:MM:SS,mmm
    """
    # Safeguard negative values
    if seconds < 0:
        seconds = 0.0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{msecs:03}"

def write_srt_file(segments: List[Dict[str, Any]], output_path: str) -> None:
    """
    Saves subtitle segments to an SRT file.
    """
    print(f"[*] Writing subtitles to SRT file: {output_path}...")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments, start=1):
            start_ts = format_timestamp(seg["start"])
            end_ts = format_timestamp(seg["end"])
            text = seg["text"]
            
            f.write(f"{idx}\n")
            f.write(f"{start_ts} --> {end_ts}\n")
            f.write(f"{text}\n\n")
            
    print(f"[+] SRT file successfully written: {output_path}")

def format_ass_timestamp(seconds: float) -> str:
    """
    Converts float seconds to ASS format: H:MM:SS.cc (centiseconds)
    """
    if seconds < 0:
        seconds = 0.0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    csecs = int(round((seconds - int(seconds)) * 100))
    if csecs == 100:
        csecs = 99
    return f"{hrs}:{mins:02}:{secs:02}.{csecs:02}"

def write_ass_file(segments: List[Dict[str, Any]], output_path: str) -> None:
    """
    Saves subtitle segments into an Advanced Substation Alpha (.ass) file
    with stylized, professional typography (outlines, colors, shadow, centering).
    """
    print(f"[*] Creating highly styled ASS subtitles file: {output_path}...")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    header = """[Script Info]
Title: Styled Translated Video Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H60000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        for seg in segments:
            start_ts = format_ass_timestamp(seg["start"])
            end_ts = format_ass_timestamp(seg["end"])
            # In ASS files, newlines are expressed as '\N'
            text = seg["text"].replace("\n", "\\N")
            f.write(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}\n")

    print(f"[+] Styled ASS file written to: {output_path}")

def embed_subtitles(video_path: str, srt_path: str, output_video_path: str, embed_mode: str) -> None:
    """
    Embeds subtitles into the video file using FFmpeg.
    Supports ASS-based style burning to ensure subtitles are always beautifully formatted and highly legible.
    """
    from extract_audio import find_ffmpeg_binary
    ffmpeg_path = find_ffmpeg_binary("ffmpeg")
    if not ffmpeg_path:
        raise FileNotFoundError("ffmpeg binary was not found during embed execution.")

    print(f"[*] Embedding subtitles in mode '{embed_mode}'...")
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source video not found: {video_path}")
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"Subtitle file not found: {srt_path}")
        
    os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)

    if embed_mode == "soft":
        # Soft embedding: Copy video/audio streams and insert SRT metadata
        command = [
            ffmpeg_path, "-y",
            "-i", video_path,
            "-i", srt_path,
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", "mov_text",
            "-metadata:s:s:0", "language=eng",
            output_video_path
        ]
    elif embed_mode == "burn":
        # Check if we should burn a stylized ASS file instead of standard SRT
        sub_file_to_use = srt_path
        if srt_path.endswith(".srt"):
            ass_path = srt_path.replace(".srt", ".ass")
            if os.path.exists(ass_path):
                sub_file_to_use = ass_path

        # Hard-burn subtitles with video re-encoding
        absolute_sub_path = os.path.abspath(sub_file_to_use).replace("\\", "/").replace(":", "\\:")
        command = [
            ffmpeg_path, "-y",
            "-i", video_path,
            "-vf", f"subtitles='{absolute_sub_path}'",
            "-c:a", "copy",
            output_video_path
        ]
    else:
        raise ValueError(f"Invalid embed mode: {embed_mode}. Choose 'soft' or 'burn'.")

    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(f"[+] Subtitled video successfully produced: {output_video_path}")
    except subprocess.CalledProcessError as e:
        print(f"[-] ffmpeg error output: {e.stderr.decode('utf-8', errors='ignore')}", file=sys.stderr)
        raise RuntimeError(f"FFmpeg failed to embed subtitles with exit code {e.returncode}") from e
