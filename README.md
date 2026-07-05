# Video Subtitle Translator & Dubber

A production-grade, modular command-line pipeline that takes a video file, transcribes its speech, translates the transcript into over 130 target languages, formats subtitles professionally, and outputs synced subtitles (`.srt`, styled `.ass`) or fully dubbed voiceover videos.

It supports both a **free, fully local** transcription mode and high-performance **parallel, rate-limit resilient** cloud translation.

---

## How it works

The program is a linear pipeline of six modular stages. Each stage reads the output of the one before it, meaning any backend (e.g., ASR, translation, or TTS synthesizer) can be swapped independently.

```
                  video.mp4
                     │
                     ▼
[1] Extract & Denoise Audio ─────► audio.wav
   │  (FFmpeg bandpass speech filters)
   ▼
[2] Transcribe (ASR with VAD) ──► list of {start, end, text} segments
   │  (faster-whisper, with Silero-VAD filtering to skip silences)
   ▼
[3] Translate (Concurrent/Retry) ► same segments, text replaced with translation
   │  (deep-translator, ThreadPool parallel execution & exponential backoff)
   ▼
[4] Format & Time Pacing ────────► segments re-chunked on logical sentence-boundaries
   │                                & durations adjusted proportionally to word lengths
   ▼
[5] Write Subtitles ─────────────► subtitles.srt + custom styled subtitles.ass
   │
   ▼
[6] Mux Subtitles & Voiceover ───► subtitled.mp4 and/or dubbed.mp4
      (FFmpeg soft-embed or stylized ASS frame burn-in / gTTS voiceover dubbing)
```

---

## Production Improvements Added

1. **Automated FFmpeg Dependency Check & Diagnostics:** Verifies system paths and locally compiled files during startup. Returns precise installation instructions for your specific platform if missing.
2. **Video & Stream Validation:** Uses `ffprobe` to pre-validate container metadata, verify duration, and ensure active audio streams exist before invoking models.
3. **Linguistic Sentence-Boundary Re-chunking:** Splits text smartly on punctuation clauses (`.`, `!`, `?`, `;`, or `,`) rather than chopping sentences in half arbitrarily, preserving linguistic flow.
4. **Intelligent Time Pacing:** Distributes durations among split subtitle cards proportionally based on actual character weights, making transitions match natural speech speed.
5. **Parallel Concurrent Translation:** Replaces slow loops with a thread-pool executor that translates segments in parallel.
6. **Exponential Backoff and Jitter Retries:** Handles network dropouts and Google Translate rate limits by retrying failed requests using a randomized geometric scale.
7. **Speech Pre-Denoising Filters:** Applies customizable highpass (80Hz) and lowpass (8000Hz) filters via FFmpeg to optimize speech clarity for ASR.
8. **Automatic GPU/CPU Selective Precision:** Detects CUDA availability automatically, choosing optimal runtimes (`float16` for GPUs, optimized `int8` quantization for CPUs).
9. **Dual-Language Subtitles:** Generates stacked translations (original language directly under target translations) for language learners.
10. **Custom Styled ASS Burning:** Generates Advanced Substation Alpha files with customizable outlines, shadows, and fonts, burned onto the video frames securely.
11. **AI Voiceover Dubbing (TTS):** Generates synthesized target translation audio tracks using Google Text-to-Speech (gTTS), speed-stretches files automatically to fit temporal gaps, and layers them over background ambiance or mutes the original audio track.

---

## Installation

```bash
git clone <this-repo>
cd translate-video
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt`:
```
ffmpeg-python
faster-whisper
deep-translator
gTTS
```

*Note: Statically compiled `ffmpeg` and `ffprobe` binaries are pre-packaged in the root folder of this project for instant use.*

---

## Usage

```bash
python translate_video.py video.mp4 --target-lang es
```

### Advanced Features Examples

* **Burn-in beautiful custom-styled subtitles:**
  ```bash
  python translate_video.py video.mp4 --target-lang fr --embed burn
  ```
* **Generate stacked dual-language subtitles (English & French combined):**
  ```bash
  python translate_video.py video.mp4 --target-lang es --dual-subs
  ```
* **Denoise audio first, translate, and synthesize an AI Spanish Voiceover mixed with background music:**
  ```bash
  python translate_video.py video.mp4 --target-lang es --denoise --dub
  ```
* **Fully replace original audio with clean Spanish Voiceover only:**
  ```bash
  python translate_video.py video.mp4 --target-lang es --dub --mute-original-audio
  ```

### CLI Arguments:
| Flag | Description | Default |
|---|---|---|
| `input_video` | Path to source video file | *Required* |
| `--target-lang` | Target language code (e.g. `es`, `fr`, `ja`, `bg`) | *Required* |
| `--source-lang` | Source language code; omit to auto-detect | auto-detect |
| `--model` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large-v3` | `small` |
| `--embed` | Embed subtitles into copy of video: `soft` or `burn` | None |
| `--denoise` | Filter ambient background noise to boost ASR accuracy | Disabled |
| `--dual-subs` | Stack original speech transcript under translation | Disabled |
| `--dub` | Synthesize target-language AI Voiceover & mix with video | Disabled |
| `--mute-original-audio` | Mute native video track entirely during voiceover dub | Blended |
| `--output-dir` | Folder path to output processed media assets | `./output` |

---

## Extension Modules

- `translate_video.py`: Orchestrator and entry-point.
- `extract_audio.py`: Audio extraction, `ffprobe` stream validation, and pre-processing denoiser filters.
- `transcribe.py`: GPU accelerated Whisper speech-to-text with VAD filtering.
- `translate.py`: Concurrent thread-pool translator with exponential backoff retries.
- `format_subtitles.py`: Smart punctuation boundary splitter and character-weight time pacing.
- `write_srt.py`: Writes standard `.srt` format, creates styled `.ass` vectors, and handles FFmpeg soft/hard burning.
- `dubbing.py`: Automated TTS sound compilation, speed stretching to fit timestamps, and audio-mixing protocols.
- `dual_subtitles.py`: Structural combining arrays for stacked dual subtitles.

## License

MIT
