import re

def get_singular_form(word: str) -> str:
    """Dynamically converts a word to its singular form."""
    if not word or len(word) <= 2:
        return word
    w_low = word.lower()
    
    # categories -> category
    if w_low.endswith("ies"):
        return word[:-3] + ("y" if word[-1].islower() else "Y")
        
    # benches -> bench, boxes -> box, bushes -> bush
    if w_low.endswith("es") and any(w_low.endswith(x) for x in ["shes", "ches", "xes", "zes"]):
        return word[:-2]
        
    # aprons -> apron, rooms -> room (but not glass -> glas)
    if w_low.endswith("s") and not w_low.endswith("ss"):
        return word[:-1]
        
    return word

def generate_fallback_candidates(original_val: str, is_keyword_mapping: bool = False) -> list:
    """Generates unique fallback search candidates, handling dashes, prefixes, and singular conversions."""
    if not original_val:
        return []
    candidates = []
    val = " ".join(original_val.strip().split())
    no_dash = val.replace("-", " ")
    with_dash = val.replace(" ", "-")
    
    for text_val in [val, no_dash, with_dash]:
        cleaned = " ".join(text_val.split())
        candidates.append(cleaned)
        sing = get_singular_form(cleaned)
        if sing != cleaned:
            candidates.append(sing)
            
        words = cleaned.split()
        if len(words) > 2:
            w2 = " ".join(words[:2])
            candidates.append(w2)
            sing_w2 = get_singular_form(w2)
            if sing_w2 != w2:
                candidates.append(sing_w2)
        if len(words) > 1:
            w0, w1 = words[0], words[1]
            is_generic_prefix = w1.isdigit() or len(w1) == 1
            if not is_generic_prefix:
                candidates.append(w0)
                sing_w0 = get_singular_form(w0)
                if sing_w0 != w0:
                    candidates.append(sing_w0)
                    
    seen = {original_val} if not is_keyword_mapping else set()
    unique_candidates = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique_candidates.append(c)
    return unique_candidates
