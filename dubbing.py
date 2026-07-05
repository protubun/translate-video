import os
import sys
import subprocess
from typing import List, Dict, Any

def generate_voiceover_audio(
    segments: List[Dict[str, Any]],
    target_lang: str,
    output_audio_path: str
) -> str:
    """
    Synthesizes translated segments into spoken voiceover audio using Google Text-to-Speech (gTTS).
    Automatically strings them together into a single voice track with silent padding to match timestamps.
    """
    print(f"[*] Starting voiceover text-to-speech synthesis (Language='{target_lang}')...")
    
    try:
        from gtts import gTTS
    except ImportError as e:
        raise ImportError("gTTS is not installed. Please run `pip install -r requirements.txt`.") from e

    # We will build synthesized chunks and arrange them using ffmpeg
    from extract_audio import find_ffmpeg_binary
    ffmpeg_path = find_ffmpeg_binary("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg is required to assemble synthesized voiceover audio files.")

    # Create temporary scratch directory
    temp_dir = "./output/tts_scratch"
    os.makedirs(temp_dir, exist_ok=True)

    concat_list_path = os.path.join(temp_dir, "concat_list.txt")
    print(f"[*] Generating {len(segments)} spoken chunks...")

    # We need to construct a sequence of silent durations and spoken segments.
    # To keep this robust and light, we synthesize the voice for each segment,
    # measure its length, and use an FFmpeg filter or sequential concatenation.
    tts_files = []
    
    current_timeline_seconds = 0.0

    for idx, seg in enumerate(segments):
        start = seg["start"]
        text = seg["text"].strip()
        if not text:
            continue

        # 1. Pad silent gaps between segments
        silence_duration = start - current_timeline_seconds
        if silence_duration > 0.05:
            # Generate temporary silent WAV
            silence_file = os.path.join(temp_dir, f"silence_{idx}.wav")
            silence_cmd = [
                ffmpeg_path, "-y", "-f", "lavfi", "-i",
                f"anullsrc=r=16000:cl=mono", "-t", f"{silence_duration:.3f}",
                silence_file
            ]
            subprocess.run(silence_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            tts_files.append(silence_file)
            current_timeline_seconds += silence_duration

        # 2. Synthesize audio file for translated segment
        chunk_mp3 = os.path.join(temp_dir, f"speech_raw_{idx}.mp3")
        chunk_wav = os.path.join(temp_dir, f"speech_norm_{idx}.wav")
        
        try:
            tts = gTTS(text=text, lang=target_lang, slow=False)
            tts.save(chunk_mp3)

            # Transcode MP3 to 16kHz mono WAV matching project configurations
            transcode_cmd = [
                ffmpeg_path, "-y", "-i", chunk_mp3,
                "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                chunk_wav
            ]
            subprocess.run(transcode_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            
            # Determine actual generated speech duration
            duration_cmd = [
                find_ffmpeg_binary("ffprobe"), "-v", "error", "-show_entries",
                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", chunk_wav
            ]
            proc = subprocess.run(duration_cmd, stdout=subprocess.PIPE, text=True, check=True)
            actual_duration = float(proc.stdout.strip())

            # Speed stretch or compress the audio track dynamically if it doesn't fit target timestamp boundaries!
            target_duration = seg["end"] - start
            if target_duration > 0.1 and abs(actual_duration - target_duration) > 0.2:
                tempo = actual_duration / target_duration
                # FFmpeg atempo supports speed factors between 0.5 and 2.0
                tempo = max(0.5, min(2.0, tempo))
                stretched_wav = os.path.join(temp_dir, f"speech_stretched_{idx}.wav")
                
                stretch_cmd = [
                    ffmpeg_path, "-y", "-i", chunk_wav,
                    "-filter:a", f"atempo={tempo:.2f}",
                    stretched_wav
                ]
                subprocess.run(stretch_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                tts_files.append(stretched_wav)
                current_timeline_seconds += target_duration
            else:
                tts_files.append(chunk_wav)
                current_timeline_seconds += actual_duration

        except Exception as e:
            print(f"[-] Warning: Failed to synthesize speech for segment {idx+1}: {e}", file=sys.stderr)
            # Create a placeholder silent audio so pacing is not disrupted
            target_duration = max(0.1, seg["end"] - start)
            err_silence = os.path.join(temp_dir, f"err_silence_{idx}.wav")
            subprocess.run([
                ffmpeg_path, "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                "-t", f"{target_duration:.3f}", err_silence
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            tts_files.append(err_silence)
            current_timeline_seconds += target_duration

    # Concat all speech & silent segments using FFmpeg's concat protocol
    if not tts_files:
        print("[!] No verbal voiceover segments translated. Skipping voice synthesis.")
        return ""

    with open(concat_list_path, "w", encoding="utf-8") as list_f:
        for filepath in tts_files:
            # Escape paths for ffmpeg concat
            escaped_path = os.path.abspath(filepath).replace("\\", "/")
            list_f.write(f"file '{escaped_path}'\n")

    print("[*] Mixing synthesized segments together into full timeline audio track...")
    concat_cmd = [
        ffmpeg_path, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c", "pcm_s16le",
        output_audio_path
    ]
    subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    print(f"[+] Full voiceover audio compiled successfully: {output_audio_path}")

    # Clean up scratch files
    for filepath in tts_files:
        try:
            os.remove(filepath)
            # Clean original raw mp3 files
            mp3_path = filepath.replace("_norm_", "_raw_").replace(".wav", ".mp3")
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
        except Exception:
            pass
    try:
        os.remove(concat_list_path)
        os.rmdir(temp_dir)
    except Exception:
        pass

    return output_audio_path

def combine_video_and_voiceover(
    video_path: str,
    voiceover_path: str,
    output_video_path: str,
    mute_original_audio: bool = False
) -> None:
    """
    Muxes the generated voiceover audio onto the original video file using FFmpeg.
    If mute_original_audio is True, the original audio channel is completely silenced.
    If False, the voiceover is downmixed (layered) over the original channel (e.g., as background ambient sound).
    """
    from extract_audio import find_ffmpeg_binary
    ffmpeg_path = find_ffmpeg_binary("ffmpeg")
    if not ffmpeg_path:
        raise FileNotFoundError("ffmpeg binary was not found during video/voiceover mix.")

    print(f"[*] Muxing voiceover track onto video {video_path}...")
    
    if mute_original_audio:
        # Completely replace the original video's audio stream with the voiceover
        command = [
            ffmpeg_path, "-y",
            "-i", video_path,
            "-i", voiceover_path,
            "-map", "0:v:0", # Get video from input
            "-map", "1:a:0", # Get audio from voiceover
            "-c:v", "copy",
            "-shortest",
            output_video_path
        ]
    else:
        # Downmix voiceover (stream 1) with original audio (stream 0) so background ambiance/music remains audible.
        command = [
            ffmpeg_path, "-y",
            "-i", video_path,
            "-i", voiceover_path,
            "-filter_complex", "[0:a]volume=0.3[bg];[1:a]volume=1.0[voice];[bg][voice]amix=inputs=2:duration=first[a]",
            "-map", "0:v:0",
            "-map", "[a]",
            "-c:v", "copy",
            output_video_path
        ]

    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(f"[+] Subtitled Video with Voiceover compiled: {output_video_path}")
    except subprocess.CalledProcessError as e:
        print(f"[-] ffmpeg mixing error: {e.stderr.decode('utf-8', errors='ignore')}", file=sys.stderr)
        raise RuntimeError(f"FFmpeg failed to mix video and voiceover with exit code {e.returncode}")
