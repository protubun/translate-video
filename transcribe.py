import os
from typing import List, Dict, Any, Optional

def transcribe_audio(
    audio_path: str,
    model_size: str = "small",
    source_lang: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Transcribes a 16kHz mono WAV file using faster-whisper.
    Applies automatic GPU/CPU precision loading matching hardware characteristics.
    """
    print(f"[*] Transcribing audio {audio_path} using model '{model_size}'...")
    
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ImportError("faster-whisper is not installed. Please run `pip install -r requirements.txt`.") from e

    # Determine optimal compute and device details
    import torch
    if torch.cuda.is_available():
        device = "cuda"
        # Support lower precision float16 on compatible CUDA GPUs for high ASR acceleration
        compute_type = "float16"
        print("[+] CUDA-capable GPU found! Activating accelerated GPU transcription (float16).")
    else:
        device = "cpu"
        compute_type = "int8"
        print("[*] No CUDA GPU detected. Running on CPU (int8 precision optimization).")
    
    print(f"[*] Loading model '{model_size}' (caching to disk for future executions)...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    print("[*] Transcribing... (Whisper automatically handles voice activity segments)")
    segments, info = model.transcribe(
        audio_path,
        language=source_lang,
        beam_size=5,
        vad_filter=True, # Built-in voice activity detection (VAD) filter
        vad_parameters=dict(min_silence_duration_ms=500) # Only pass segments with human speech
    )
    
    detected_lang = info.language
    probability = info.language_probability
    print(f"[+] Detected language: '{detected_lang}' with probability {probability:.2f}")

    results = []
    for segment in segments:
        text = segment.text.strip()
        # Smart Punctuation/Stutter Cleanup: strip empty utterances, leading trails or duplicate stutter pauses
        if not text or text.lower() in ["uh", "um", "ah", "er", "uh-huh"]:
            continue
            
        results.append({
            "start": round(segment.start, 3),
            "end": round(segment.end, 3),
            "text": text
        })
        print(f"  [{segment.start:06.2f}s -> {segment.end:06.2f}s] {text}")

    print(f"[+] Transcription finished. Generated {len(results)} valid speech segments.")
    return results
