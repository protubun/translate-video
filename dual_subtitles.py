import sys
from typing import List, Dict, Any

def generate_dual_subtitles(
    original_segments: List[Dict[str, Any]],
    translated_segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Combines original and translated segments to form a single dual-language subtitle track.
    Renders the translated subtitle prominently on top, with the original transcribed
    source subtitle styled compactly underneath.
    """
    print(f"[*] Merging transcribed and translated segments into dual-language format...")
    
    dual_segments = []
    
    # We map segments based on proximity or index match
    for idx, trans_seg in enumerate(translated_segments):
        start = trans_seg["start"]
        end = trans_seg["end"]
        translated_text = trans_seg["text"]

        # Safely acquire original language subtitle text
        orig_text = ""
        if idx < len(original_segments):
            orig_text = original_segments[idx]["text"]
        else:
            # Fallback scan for timestamps proximity
            for orig_seg in original_segments:
                if abs(orig_seg["start"] - start) < 1.0:
                    orig_text = orig_seg["text"]
                    break

        if orig_text:
            # Combine them: Translated on line 1, Original source in parentheses/brackets on line 2
            combined_text = f"{translated_text}\n({orig_text})"
        else:
            combined_text = translated_text

        dual_segments.append({
            "start": start,
            "end": end,
            "text": combined_text
        })

    print(f"[+] Successfully generated {len(dual_segments)} dual-language subtitle segments.")
    return dual_segments
