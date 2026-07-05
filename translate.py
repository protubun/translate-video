import sys
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

def translate_single_text_with_retry(
    translator,
    text: str,
    max_retries: int = 5,
    initial_backoff: float = 1.0
) -> str:
    """
    Translates a single segment of text with an Exponential Backoff and Jitter retry mechanism
    to prevent network issues or API rate-limiting crashes.
    """
    text = text.strip()
    if not text:
        return ""

    backoff = initial_backoff
    for attempt in range(max_retries):
        try:
            return translator.translate(text)
        except Exception as e:
            # Check if it's the last attempt before failing
            if attempt == max_retries - 1:
                print(f"[-] Final attempt failed to translate: '{text}'. Error: {e}", file=sys.stderr)
                return text  # Fallback to the original text rather than crashing
            
            # Add randomized jitter to avoid thunderous herd problem on rate limits
            sleep_time = backoff + random.uniform(0, 0.5 * backoff)
            print(f"[!] Warning: Translation failed (Attempt {attempt+1}/{max_retries}). Retrying in {sleep_time:.2f}s... Error: {e}")
            time.sleep(sleep_time)
            backoff *= 2.0  # Double the backoff duration

    return text

def translate_segments(
    segments: List[Dict[str, Any]],
    target_lang: str,
    source_lang: str = "auto",
    max_workers: int = 4
) -> List[Dict[str, Any]]:
    """
    Translates list of segment strings concurrently using a ThreadPoolExecutor.
    Significantly increases translation performance for large collections of segments.
    """
    print(f"[*] Translating {len(segments)} segments to '{target_lang}' (source='{source_lang}')...")
    
    try:
        from deep_translator import GoogleTranslator
    except ImportError as e:
        raise ImportError("deep-translator is not installed. Please run `pip install -r requirements.txt`.") from e

    # Create Translator instance (Thread-safe instance initialization)
    translator = GoogleTranslator(source=source_lang, target=target_lang)

    # Initialize container with placeholders to preserve exact ordering
    translated_segments = [None] * len(segments)

    def process_segment(index: int, seg: Dict[str, Any]):
        translated_text = translate_single_text_with_retry(translator, seg["text"])
        return index, {
            "start": seg["start"],
            "end": seg["end"],
            "text": translated_text
        }

    # Parallelize the translation calls
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_segment, i, seg): i for i, seg in enumerate(segments)}
        for future in as_completed(futures):
            idx, res_segment = future.result()
            translated_segments[idx] = res_segment
            print(f"  [+] Seg {idx+1}/{len(segments)} Translated: '{segments[idx]['text']}' -> '{res_segment['text']}'")

    print("[+] Parallel translation complete.")
    return translated_segments
