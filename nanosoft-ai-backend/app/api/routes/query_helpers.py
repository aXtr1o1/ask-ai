import re

def get_singular_form(word: str) -> str:
    """Dynamically converts a word to its singular form."""
    if not word or len(word) <= 2:
        return word
    w_low = word.lower()
    if w_low.endswith("ies"):
        return word[:-3] + ("y" if word[-1].islower() else "Y")
    if w_low.endswith("es") and any(w_low.endswith(x) for x in ["shes", "ches", "xes", "zes"]):
        return word[:-2]
    return word[:-1] if w_low.endswith("s") and not w_low.endswith("ss") else word

def generate_fallback_candidates(original_val: str, is_keyword_mapping: bool = False) -> list:
    """Generates unique fallback search candidates, handling dashes, prefixes, and singular conversions."""
    if not original_val:
        return []
    val = " ".join(original_val.strip().split())
    candidates = []
    for text_val in [val, val.replace("-", " "), val.replace(" ", "-")]:
        cleaned = " ".join(text_val.split())
        candidates.extend([cleaned, get_singular_form(cleaned)])
        words = cleaned.split()
        if len(words) > 2:
            w2 = " ".join(words[:2])
            candidates.extend([w2, get_singular_form(w2)])
        if len(words) > 1 and not (words[1].isdigit() or len(words[1]) == 1):
            candidates.extend([words[0], get_singular_form(words[0])])
            
    seen = {original_val} if not is_keyword_mapping else set()
    return [c for c in candidates if c and c not in seen and not seen.add(c)]
