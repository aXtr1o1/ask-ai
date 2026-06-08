"""
app/services/spot_vector_store.py
─────────────────────────────────────────────────────────────────────────────
In-memory TF-IDF semantic vector store for space booking spot search.

Key design decisions:
  - Per-client scoped (keyed by user_name / client_name)
  - Server-lifetime: loaded once on first GET_SPOTS call, reused forever
  - Session-independent: any session for the same client hits the same index
  - char_wb n-grams (2-4): handles typos, partial words, mixed-case
  - Empty query → returns ALL spots (for "show all" use cases)
  - Zero-score fallback → returns top-K alphabetically (never empty)

Usage:
    from app.services.spot_vector_store import spot_store

    if not spot_store.is_loaded(client_name):
        spot_store.load(client_name, raw_spots_list)

    results = spot_store.search(client_name, "reef mal", top_k=15)
    spot_store.clear(client_name)   # force reload after data refresh
"""

import logging
import numpy as np
from typing import Optional

logger = logging.getLogger("spot_vector_store")
if not logger.handlers:
    import logging as _logging
    _h = _logging.StreamHandler()
    _h.setFormatter(_logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)

# The 4 fields used to build the searchable text corpus per spot
_SEARCH_FIELDS = ("SpotCode", "SpotName", "BuildingName", "FloorName")


class SpotVectorStore:
    """
    Singleton in-memory TF-IDF vector store for spots.

    Internal structure per client:
        {
          "vectorizer": TfidfVectorizer (fitted),
          "matrix":     sparse CSR matrix  (n_spots × n_features),
          "spots":      list[dict]          (original raw records),
        }
    """

    def __init__(self):
        # client_name → store entry dict
        self._store: dict = {}

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def is_loaded(self, client_name: str) -> bool:
        """Return True if a TF-IDF index already exists for this client."""
        return client_name in self._store

    def get_all(self, client_name: str) -> list:
        """Return all raw spot records for a client (used for buildings-only mode)."""
        entry = self._store.get(client_name)
        return entry["spots"] if entry else []


    def load(self, client_name: str, raw_spots: list) -> None:
        """
        Build and cache the TF-IDF index from a list of raw spot records.

        Each spot is represented as a single concatenated string of all 4 fields:
            "WRMF-SCR WASH ROOMS (M/F) Security control room Reef Mall GF Level"

        char_wb analyzer with ngram_range=(2,4) makes the search robust to:
          - Typos  ("washrm"  → "WASH ROOMS")
          - Partial input ("Reef"  → "Reef Mall")
          - Case differences (case-folded internally by TF-IDF)
        """
        if not raw_spots:
            logger.warning(f"⚠️ load() called with empty spot list for '{client_name}' — skipped")
            return

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            # Build one text string per spot from all 4 searchable fields
            texts = []
            for spot in raw_spots:
                parts = [str(spot.get(field, "") or "") for field in _SEARCH_FIELDS]
                texts.append(" ".join(parts))

            # ── TF-IDF vectorizer config ───────────────────────────────────
            # analyzer='char_wb'   → character-level n-grams (word boundary aware)
            # ngram_range=(2,4)    → bigrams to 4-grams: "re", "ref", "reef", etc.
            # sublinear_tf=True    → log-scale TF to reduce dominance of repeated terms
            # min_df=1             → include all terms (small vocabulary is fine)
            vectorizer = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 4),
                sublinear_tf=True,
                min_df=1,
            )
            matrix = vectorizer.fit_transform(texts)

            self._store[client_name] = {
                "vectorizer": vectorizer,
                "matrix":     matrix,
                "spots":      raw_spots,
            }
            logger.info(
                "✅ Vector store loaded | client='%s' | spots=%d | features=%d",
                client_name, len(raw_spots), matrix.shape[1],
            )

        except ImportError:
            logger.error(
                "❌ scikit-learn is not installed. "
                "Run: pip install scikit-learn  — falling back to no index."
            )
        except Exception as e:
            logger.error(
                "❌ Failed to build vector store for '%s': %s", client_name, e, exc_info=True
            )

    def search(
        self,
        client_name: str,
        query: Optional[str],
        top_k: int = 15,
    ) -> list:
        """
        Return the top-K spots most similar to `query`.

        Behaviour:
          - Empty / None query  →  return ALL spots (no filtering)
          - Zero cosine scores  →  fallback: return first top_k spots alphabetically
          - Store not loaded    →  return [] with a warning
        """
        if client_name not in self._store:
            logger.warning("⚠️ search() called but store not loaded for '%s'", client_name)
            return []

        entry     = self._store[client_name]
        all_spots = entry["spots"]

        # ── Empty query: return ALL spots (user wants to browse everything) ──
        if not query or not str(query).strip():
            logger.info(
                "📋 No search_term — returning all %d spots for '%s'",
                len(all_spots), client_name,
            )
            return all_spots

        try:
            from sklearn.metrics.pairwise import cosine_similarity

            query_vec = entry["vectorizer"].transform([str(query)])
            scores    = cosine_similarity(query_vec, entry["matrix"]).flatten()

            # Sort by score descending
            ranked_indices = np.argsort(scores)[::-1]

            # Keep only results with a positive score
            matched = [i for i in ranked_indices[:top_k] if scores[i] > 0.0]

            if matched:
                results = [all_spots[i] for i in matched]
                logger.info(
                    "🔍 Vector search | client='%s' | query='%s' | hits=%d | top_score=%.3f",
                    client_name, query, len(results), scores[ranked_indices[0]],
                )
            else:
                # Nothing matched at all — return first top_k as graceful fallback
                results = all_spots[:top_k]
                logger.warning(
                    "⚠️ Zero matches for query='%s' on client='%s' — returning first %d spots",
                    query, client_name, top_k,
                )

            return results

        except Exception as e:
            logger.error(
                "❌ Vector search error for '%s': %s", client_name, e, exc_info=True
            )
            # Safe fallback
            return all_spots[:top_k]

    def get_unique_buildings(self, client_name: str) -> list:
        """
        Return a list of unique BuildingName strings for this client.
        Used when the user asks 'show me buildings' with no search term.
        Each entry is a dict with only BuildingName so the frontend renders it as a title card.
        """
        if client_name not in self._store:
            return []
        all_spots = self._store[client_name]["spots"]
        seen = set()
        buildings = []
        for spot in all_spots:
            b = spot.get("BuildingName", "").strip()
            if b and b not in seen:
                seen.add(b)
                buildings.append({"BuildingName": b})
        return buildings

    def clear(self, client_name: str) -> None:
        """
        Evict a client's index from memory.
        The next GET_SPOTS call will re-fetch from the API and rebuild.
        """
        if client_name in self._store:
            del self._store[client_name]
            logger.info("🗑️ Vector store cleared for '%s' — will rebuild on next call", client_name)
        else:
            logger.debug("clear() called but '%s' was not in store — no-op", client_name)

    def loaded_clients(self) -> list:
        """Return list of client names currently indexed (useful for diagnostics)."""
        return list(self._store.keys())


# ─────────────────────────────────────────────────────────────
# Module-level singleton — import this everywhere
# ─────────────────────────────────────────────────────────────
spot_store = SpotVectorStore()
