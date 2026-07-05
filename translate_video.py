#!/usr/bin/env python3
import os
import sys
import argparse

# Pipeline diagnostics and Stage 1 Verification
from extract_audio import verify_ffmpeg_installation, validate_video_file, extract_audio
from transcribe import transcribe_audio
from translate import translate_segments
from format_subtitles import format_subtitles
from write_srt import write_srt_file, write_ass_file, embed_subtitles
from dubbing import generate_voiceover_audio, combine_video_and_voiceover
from dual_subtitles import generate_dual_subtitles

def main():
    parser = argparse.ArgumentParser(
        description="Production-Grade Video Subtitle Translator - Speech transcription, translation, smart formatting, styled ASS rendering, dual-subtitles, and AI dubbing voiceover."
    )
    parser.add_argument(
        "input_video",
        type=str,
        help="Path to the input video file (e.g., video.mp4)"
    )
    parser.add_argument(
        "--target-lang",
        type=str,
        required=True,
        help="Target language code for subtitles/dubbing (e.g., 'es', 'fr', 'ja', 'de')"
    )
    parser.add_argument(
        "--source-lang",
        type=str,
        default=None,
        help="Source language code of video speech (e.g., 'en'). Omit to auto-detect."
    )
    parser.add_argument(
        "--model",
        type=str,
        default="small",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size to use for transcription (default: 'small')"
    )
    parser.add_argument(
        "--embed",
        type=str,
        choices=["soft", "burn"],
        default=None,
        help="Embed subtitles into a copy of the video: 'soft' (soft subtitle track) or 'burn' (hardburned frames)"
    )
    parser.add_argument(
        "--denoise",
        action="store_true",
        help="Apply highpass and lowpass filters to the video's audio track before transcribing to eliminate noise."
    )
    parser.add_argument(
        "--dual-subs",
        action="store_true",
        help="Generate a dual-language subtitle file combining both the translated text and the original transcription."
    )
    parser.add_argument(
        "--dub",
        action="store_true",
        help="Perform AI voiceover dubbing in the target language. Synthesizes translated speech and replaces/mixes it with video."
    )
    parser.add_argument(
        "--mute-original-audio",
        action="store_true",
        help="Mute original audio completely in the dubbing process, instead of blending it as background ambiance."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="Directory to write output files (default: './output')"
    )
    
    args = parser.parse_args()

    # Pre-execution environment diagnosis
    try:
        verify_ffmpeg_installation()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    # Validate input video file format and verify audio stream exists
    try:
        video_metadata = validate_video_file(args.input_video)
    except Exception as e:
        print(f"[-] Validation Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Base names and temporary file paths
    video_base_name = os.path.splitext(os.path.basename(args.input_video))[0]
    temp_audio_path = os.path.join(args.output_dir, f"{video_base_name}_temp_audio.wav")
    output_srt_path = os.path.join(args.output_dir, f"{video_base_name}.srt")
    output_ass_path = os.path.join(args.output_dir, f"{video_base_name}.ass")
    output_video_path = os.path.join(args.output_dir, f"{video_base_name}_subtitled.mp4")
    output_dub_audio_path = os.path.join(args.output_dir, f"{video_base_name}_dubbed.wav")
    output_dub_video_path = os.path.join(args.output_dir, f"{video_base_name}_dubbed.mp4")

    try:
        print("="*60)
        print("    Production-Grade Video Subtitle Translator & Dubber    ")
        print("="*60)
        print(f"Input Video:     {args.input_video}")
        print(f"Target Lang:     {args.target_lang}")
        print(f"Source Lang:     {args.source_lang or 'Auto-detect'}")
        print(f"Whisper Model:   {args.model}")
        print(f"Apply Denoising: {args.denoise}")
        print(f"Dual Subtitles:  {args.dual_subs}")
        print(f"AI Dubbing:      {args.dub}")
        print(f"Embed Mode:      {args.embed or 'None'}")
        print(f"Output Dir:      {args.output_dir}")
        print("-"*60)

        # Stage 1: Extract Audio (with optional background noise filter pass)
        extract_audio(args.input_video, temp_audio_path, apply_denoise=args.denoise)
        print("-"*60)

        # Stage 2: Transcribe (ASR)
        raw_segments = transcribe_audio(
            audio_path=temp_audio_path,
            model_size=args.model,
            source_lang=args.source_lang
        )
        print("-"*60)

        # Stage 3: Translate (Concurrently with ThreadPools and Backoff retries)
        translated_segments = translate_segments(
            segments=raw_segments,
            target_lang=args.target_lang,
            source_lang=args.source_lang or "auto"
        )
        print("-"*60)

        # Stage 4: Format for Readability (Smart Sentence Boundary, Pacing timecodes, layouts)
        formatted_translated_segments = format_subtitles(
            segments=translated_segments
        )
        print("-"*60)

        # Handle Dual Subtitles if requested
        if args.dual_subs:
            formatted_raw_segments = format_subtitles(segments=raw_segments)
            final_segments_to_write = generate_dual_subtitles(
                original_segments=formatted_raw_segments,
                translated_segments=formatted_translated_segments
            )
        else:
            final_segments_to_write = formatted_translated_segments

        # Stage 5: Write Subtitle File (SRT and Styled ASS)
        write_srt_file(final_segments_to_write, output_srt_path)
        write_ass_file(final_segments_to_write, output_ass_path)
        print("-"*60)

        # Optional: Embed Subtitles into Video
        if args.embed:
            embed_subtitles(
                video_path=args.input_video,
                srt_path=output_srt_path,
                output_video_path=output_video_path,
                embed_mode=args.embed
            )
            print("-"*60)

        # Optional: AI Voiceover Dubbing
        if args.dub:
            print("[*] Launching Dubbing & TTS Generation Phase...")
            generate_voiceover_audio(
                segments=formatted_translated_segments,
                target_lang=args.target_lang,
                output_audio_path=output_dub_audio_path
            )
            combine_video_and_voiceover(
                video_path=args.input_video,
                voiceover_path=output_dub_audio_path,
                output_video_path=output_dub_video_path,
                mute_original_audio=args.mute_original_audio
            )
            print("-"*60)

        print("\n[+] Pipeline completed successfully!")
        print(f"[+] Output Subtitles (SRT):  {output_srt_path}")
        print(f"[+] Styled Subtitles (ASS):  {output_ass_path}")
        if args.embed:
            print(f"[+] Subtitled Video:         {output_video_path}")
        if args.dub:
            print(f"[+] Dubbed Video:            {output_dub_video_path}")
        print("="*60)

    except Exception as e:
        print(f"\n[-] Error running pipeline: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Cleanup temporary audio file
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
                print("[*] Cleaned up temporary audio file.")
            except Exception as e:
                print(f"[-] Warning: Failed to clean up temporary audio: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
