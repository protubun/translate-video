import re
from typing import List, Dict, Any

def split_sentence_boundaries(text: str) -> List[str]:
    """
    Splits text along logical sentence/clause boundaries (., !, ?, ;, or commas)
    rather than splitting sentences in half randomly, ensuring natural linguistic structure.
    """
    # Regex splits at sentence-ending punctuations while preserving them
    sentences = re.split(r'(?<=[.!?;\u3002\uff01\uff1f])\s+', text)
    refined_parts = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        # If the split sentence is still exceptionally long, we can break at commas or conjunctions
        if len(s) > 80:
            subsections = re.split(r'(?<=[,，])\s+', s)
            refined_parts.extend([sub.strip() for sub in subsections if sub.strip()])
        else:
            refined_parts.append(s)
    return refined_parts

def format_subtitles(
    segments: List[Dict[str, Any]],
    max_chars_per_line: int = 40,
    max_lines: int = 2,
    reading_speed_cap: float = 17.0  # characters per second
) -> List[Dict[str, Any]]:
    """
    Reformats and re-chunks subtitle segments with:
    1. Smart Sentence-Boundary parsing.
    2. Intelligent time-pacing (timing is distributed proportionally to word lengths).
    3. Respect for line width, lines per card, and reading speed capabilities.
    """
    print(f"[*] Re-chunking {len(segments)} segments for optimal readability & pacing...")
    formatted_segments = []

    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue

        start = seg["start"]
        end = seg["end"]
        duration = end - start

        # 1. Break text into logical sentence-boundary parts
        clauses = split_sentence_boundaries(text)
        
        # Build individual line cards matching boundaries
        lines = []
        for clause in clauses:
            words = clause.split()
            current_line = []
            current_length = 0
            
            for word in words:
                added_len = len(word) + (1 if current_line else 0)
                if current_length + added_len <= max_chars_per_line:
                    current_line.append(word)
                    current_length += added_len
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
                    current_length = len(word)
            if current_line:
                lines.append(" ".join(current_line))

        if not lines:
            continue

        # 2. Re-group formatted lines into final subtitle cards (respecting max_lines)
        cards = []
        for i in range(0, len(lines), max_lines):
            cards.append(lines[i : i + max_lines])

        total_cards = len(cards)
        if total_cards == 1:
            formatted_segments.append({
                "start": start,
                "end": end,
                "text": "\n".join(cards[0])
            })
        else:
            # 3. Intelligent Subtitle Synchronization:
            # Calculate total character weight across all cards to distribute timing proportionally.
            card_texts = ["\n".join(card) for card in cards]
            total_chars = sum(len(ct) for ct in card_texts)

            current_start = start
            for idx, card_text in enumerate(card_texts):
                if total_chars > 0:
                    weight = len(card_text) / total_chars
                else:
                    weight = 1.0 / total_cards
                
                card_duration = duration * weight
                card_end = current_start + card_duration

                # Enforce reading speed compliance cap
                card_chars = len(card_text)
                if card_duration > 0:
                    cps = card_chars / card_duration
                    if cps > reading_speed_cap:
                        # Slightly stretch the duration if there is space to match reading pacing
                        adjusted_duration = card_chars / reading_speed_cap
                        card_end = min(end, current_start + adjusted_duration)

                formatted_segments.append({
                    "start": round(current_start, 3),
                    "end": round(card_end, 3),
                    "text": card_text
                })
                current_start = card_end

    print(f"[+] Re-chunking completed. Total produced subtitle entries: {len(formatted_segments)}")
    return formatted_segments
