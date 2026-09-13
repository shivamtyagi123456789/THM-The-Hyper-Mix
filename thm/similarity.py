"""
Similarity engine — the core of True Hyper Mixing (PRD Section 6).

WHAT THIS IS FOR
----------------
Given the track playing now (A), score every other track (B) by how close it is
perceptually, and explain which dimensions drove the score.

The product's whole reason for existing is the failure it must not repeat:
a love song followed by a gangster song. Nothing here uses a hard threshold on
"vibe" — that would empty the queue. Instead every dimension returns a graded
0..1 similarity, and the total is a weighted mean over whatever dimensions are
actually present for both tracks.

WHAT MAKES IT "HYPER" MIXING RATHER THAN NEAREST-NEIGHBOUR
----------------------------------------------------------
Three things the PRD calls for that a plain nearest-neighbour search cannot do:

  1. PER-DIMENSION ELASTICITY. There is no single notion of "close". 8 BPM
     apart is inaudible; a theme change from romance to violence is a cliff.
     Each dimension therefore carries its own tolerance, expressed as the
     distance at which similarity falls to 0.5.

  2. DIRECTIONAL DRIFT (FR-3.9 arc control). The user's own description of
     the ideal transition — "same vibe but the beat is slightly more pumpy" —
     is a *directed* move, not a symmetric one. Passing `arc` makes a slightly
     faster/louder neighbour score BETTER than an identical one, which no
     symmetric distance metric can express.

  3. PROVENANCE-AWARE WEIGHTING. Some features are measured, some are inferred
     (see db.FEATURE_PROVENANCE). Inferred ones are discounted rather than
     trusted equally, so a guess about "valence" cannot outvote a measured
     tempo.

DESIGN NOTE ON WHY THEMES USE COSINE, NOT EQUALITY
--------------------------------------------------
Theme is multi-label (PRD F1). "romance 0.9 + heartbreak 0.6" and "romance 0.9"
are similar; "romance" and "aggression" are not. Exact-match would throw away
that gradation, so theme_scores is treated as a sparse vector and compared by
cosine. This is the single most important dimension for the love-song/
gangster-song failure, so it is weighted accordingly.
"""

import math

# ---------------------------------------------------------------------------
# Provenance discount
# ---------------------------------------------------------------------------
# A feature we inferred (e.g. "valence" from mode + tempo + brightness) is
# worth less than one we measured. 0.5 rather than 0 because it is still real
# evidence — just weaker.
PROVENANCE_DISCOUNT = 0.5

# ---------------------------------------------------------------------------
# Dimension specification
# ---------------------------------------------------------------------------
# kind:
#   "scalar"  — numeric, compared with a tolerance (half-credit distance)
#   "cosine"  — vector, compared by cosine similarity
#   "dict"    — {label: score}, compared by cosine over the label space
#   "key"     — musical key, compared on the circle of fifths
#   "mode"    — major/minor
#   "exact"   — categorical, all-or-nothing
#
# weight: relative importance. Doubled for dims that bear on the product's
#         headline failure (theme, emotion, energy) — see the weighting note.

def _d(name, source, kind, weight, tolerance=None, provenance="measured"):
    return {"name": name, "source": source, "kind": kind, "weight": weight,
            "tolerance": tolerance, "provenance": provenance}


DIMENSIONS = [
    # --- Family F: lyrical / thematic -------------------------------------
    # The heaviest weights in the table, deliberately. The failure the product
    # exists to prevent is thematic, so theme and emotion must dominate the
    # composite; everything else is texture.
    _d("theme",           "theme_scores",        "dict",  3.0),
    _d("emotion",         "primary_emotion",     "exact", 3.0),
    _d("sentiment",       "sentiment_score",     "scalar", 1.0, 0.45),
    _d("perspective",     "perspective",         "exact", 0.6),
    _d("lyrical_density", "lyrical_density",     "scalar", 1.7, 18.0),

    # --- Family A: temporal / rhythmic ------------------------------------
    # Tempo is the dimension a listener notices first, and the one the arc
    # control acts on.
    _d("tempo",           "tempo_bpm",           "scalar", 2.3, 15.0),
    _d("beat_strength",   "beat_strength",       "scalar", 1.7, 0.16),
    _d("onset_rate",      "onset_rate",          "scalar", 1.0, 1.6),
    _d("rhythm_complex",  "rhythm_complexity",   "scalar", 0.8, 0.22),

    # --- Family G: perceptual composites ----------------------------------
    _d("energy",          "energy_level",        "scalar", 2.7, 0.16),
    _d("valence",         "valence_audio",       "scalar", 1.7, 0.22,
       provenance="approximated"),
    _d("arousal",         "arousal",             "scalar", 1.7, 0.16),
    _d("danceability",    "danceability",        "scalar", 1.0, 0.22,
       provenance="approximated"),

    # --- Family E: instrumentation / production ---------------------------
    # "Same instruments" is a strong, audible continuity cue — the difference
    # between an acoustic ballad and a trap track is mostly here.
    _d("percussive",      "percussive_strength", "scalar", 1.7, 0.2),
    _d("harmonic_ratio",  "harmonic_ratio",      "scalar", 1.0, 0.2),
    _d("acoustic",        "acoustic_score",      "scalar", 1.0, 0.26,
       provenance="approximated"),
    _d("vocal_presence",  "vocal_presence",      "scalar", 1.0, 0.26,
       provenance="approximated"),

    # --- Family C: spectral / timbre --------------------------------------
    # MFCC dominates timbre: it is the closest thing to a "sound colour"
    # fingerprint, so it carries more weight than the individual descriptors.
    _d("mfcc",            "mfcc",                "cosine", 2.0),
    _d("spectral_centroid", "spectral_centroid", "scalar", 1.0, 650.0),
    _d("band_balance",    "band_balance",        "cosine", 1.0),
    _d("spectral_rolloff", "spectral_rolloff",   "scalar", 0.8, 1200.0),
    _d("spectral_bandwidth", "spectral_bandwidth", "scalar", 0.8, 750.0),
    _d("zcr",             "zero_crossing_rate",  "scalar", 0.8, 0.055),
    _d("spectral_contrast", "spectral_contrast", "cosine", 0.8),

    # --- Family B: harmonic / tonal ---------------------------------------
    _d("chroma",          "chroma",              "cosine", 1.7),
    _d("key",             "key_note",            "key",    1.0),
    _d("mode",            "scale_mode",          "mode",   1.0),

    # --- Family D: loudness / dynamics ------------------------------------
    # Deliberately light. The PRD treats loudness levelling as an independent
    # hard requirement (Section 7), not a similarity axis — once every track is
    # normalised to a target LUFS, raw loudness differences stop being
    # perceptually meaningful, so this must not drive selection.
    _d("lufs",            "loudness_lufs",       "scalar", 0.6, 4.0),
    _d("rms",             "rms_energy",          "scalar", 1.0, 0.055),
    _d("dynamic_range",   "dynamic_range",       "scalar", 1.0, 4.0),
    _d("peak_to_loudness", "peak_to_loudness",   "scalar", 0.5, 3.0),
    _d("envelope",        "energy_envelope",     "cosine", 1.0),
]

DIMENSIONS_BY_NAME = {d["name"]: d for d in DIMENSIONS}

# Arc presets (FR-3.9). The value is the *target* signed difference for that
# dimension: a neighbour this much above the current track scores best.
# Tempo and energy only — drift on theme or instrumentation is exactly the
# "vibe break" the product is meant to prevent.
ARC_PRESETS = {
    "steady":       {"tempo": 0.0,  "energy": 0.0},
    "rising":       {"tempo": 4.0,  "energy": 0.06},
    "decelerating": {"tempo": -4.0, "energy": -0.06},
}

# How much thematic drift is tolerated even under an arc. Mood stays locked
# while energy moves; this is the "arc, not break" distinction from the PRD.
MAX_THEME_DRIFT = 0.6

# What an unclassifiable track is worth as a neighbour.
#
# "No theme" has two very different causes and the theme lock must not treat
# them alike:
#
#   no lyrics at all      — an instrumental. Nothing to conflict with, so it
#                           is genuinely safe and passes at full weight.
#   lyrics, no label      — the lexicon saw words but could not agree on a
#                           theme. This is not safety, it is ignorance, and
#                           the library proves it costs: "BLOOD IS BETTER THAN
#                           TEARS" and "Russian Bandana" both sit one hit below
#                           the floor with aggression terms firing, and both
#                           would otherwise queue next to a love song.
#
# A heavy penalty rather than exclusion, because FR-3.10 forbids anything that
# can empty the queue: this makes such a track very unlikely to win without
# making it impossible.
UNCLASSIFIED_THEME_PENALTY = 0.5

# A track with no words and no recognisable voice is an instrumental. A track
# with no words but a clear voice is one whose lyrics we simply failed to find
# — "no lyrics found" is not the same claim as "no lyrics". This floor is what
# separates the two, and it is measured: in the real library the 18 tracks with
# word_count == 0 have vocal_presence 0.65..1.00, i.e. not one of them is an
# actual instrumental. Treating them as safe is how "Hamla" — a Sez on the Beat
# diss track — queued next to romantic anchors.
VOCAL_PRESENCE_FLOOR = 0.5

# ---------------------------------------------------------------------------
# Per-dimension similarity primitives
# ---------------------------------------------------------------------------


def scalar_sim(a, b, tolerance, drift=0.0):
    """
    Graded similarity between two numbers.

    `tolerance` is the distance at which similarity falls to 0.5 — an
    intuitive, per-dimension elasticity. `drift` shifts the target: with
    drift=4, a b that is 4 BPM above a scores 1.0, which is how the arc
    control rewards a deliberate slight lift rather than mere sameness.
    """
    if a is None or b is None:
        return None
    d = abs((b - a) - drift)
    # exp(-(d/tol)^2 * ln2) == 0.5 exactly at d == tolerance.
    return math.exp(-((d / tolerance) ** 2) * math.log(2))


def cosine_sim(vec_a, vec_b):
    """Cosine similarity of two vectors, clamped to 0..1 (negatives are 'no')."""
    if not vec_a or not vec_b:
        return None
    if len(vec_a) != len(vec_b):
        n = min(len(vec_a), len(vec_b))
        vec_a, vec_b = vec_a[:n], vec_b[:n]
    dot = sum(x * y for x, y in zip(vec_a, vec_b))
    na = math.sqrt(sum(x * x for x in vec_a))
    nb = math.sqrt(sum(y * y for y in vec_b))
    if na == 0 or nb == 0:
        return None
    return max(0.0, min(1.0, dot / (na * nb)))


def dict_cosine(dict_a, dict_b):
    """
    Cosine over a sparse label->score space.

    Used for multi-label theme vectors. Returns None if either side is empty,
    so an unknown track simply doesn't contribute rather than scoring 0 and
    dragging the composite down unfairly.
    """
    if not dict_a or not dict_b:
        return None
    keys = set(dict_a) | set(dict_b)
    dot = sum(dict_a.get(k, 0.0) * dict_b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in dict_a.values()))
    nb = math.sqrt(sum(v * v for v in dict_b.values()))
    if na == 0 or nb == 0:
        return None
    return max(0.0, min(1.0, dot / (na * nb)))


# Circle of fifths — keys a fifth apart share most of their notes and mix
# cleanly; tritone-related keys do not. Ordering by fifths is what makes this
# musically correct rather than alphabetical.
_FIFTHS = ["C", "G", "D", "A", "E", "B", "F#", "C#", "G#", "D#", "A#", "F"]

# Enhancearmonic equivalents, so "Db" and "C#" are recognised as the same key.
_KEY_ALIASES = {
    "DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#",
    "C#": "C#", "D#": "D#", "F#": "F#", "G#": "G#", "A#": "A#",
}


def _normalise_key(key):
    if not key:
        return None
    k = str(key).strip().upper().replace("MAJOR", "").replace("MINOR", "").strip()
    k = k.replace("♯", "#").replace("♭", "b").replace("B", "b") if k.endswith("b") else k
    k = k.upper()
    return _KEY_ALIASES.get(k, k if k in _FIFTHS else None)


def key_sim(key_a, key_b):
    """Similarity on the circle of fifths: same key 1.0, tritone ~0.0."""
    a, b = _normalise_key(key_a), _normalise_key(key_b)
    if a is None or b is None:
        return None
    ia, ib = _FIFTHS.index(a), _FIFTHS.index(b)
    steps = abs(ia - ib)
    steps = min(steps, 12 - steps)          # circular
    # 0 steps -> 1.0, 6 steps (tritone) -> 0.0, linear between.
    return max(0.0, 1.0 - steps / 6.0)


def mode_sim(mode_a, mode_b):
    """
    Major vs minor. Same mode is a clean continuation; a mode change is a real
    emotional shift, so it scores low but not zero — it is not a veto.
    """
    if not mode_a or not mode_b:
        return None
    a, b = str(mode_a).lower()[:3], str(mode_b).lower()[:3]
    if a not in ("maj", "min") or b not in ("maj", "min"):
        return None
    return 1.0 if a == b else 0.35


def exact_sim(a, b):
    """Categorical match. Returns None (not 0) when either side is unknown."""
    if a is None or b is None:
        return None
    if isinstance(a, str) and a in ("unknown", "neutral", ""):
        return None
    return 1.0 if a == b else 0.0


# ---------------------------------------------------------------------------
# Per-dimension dispatch
# ---------------------------------------------------------------------------

def dimension_similarity(dim, a, b, drift=0.0):
    """Similarity for one dimension between two library dicts, or None."""
    kind = dim["kind"]
    src = dim["source"]
    x, y = a.get(src), b.get(src)

    if kind == "scalar":
        return scalar_sim(x, y, dim["tolerance"], drift)
    if kind == "cosine":
        return cosine_sim(x, y)
    if kind == "dict":
        sim = dict_cosine(x, y)
        # A theme we could not read is not a theme that agrees. dict_cosine
        # returns None for an unclassifiable track so it "doesn't contribute",
        # which is right for a genuine instrumental and wrong for a track whose
        # words we read and failed to label: scoring it None hands the
        # full 3.0 theme weight a free pass to the mean, so an unknown track
        # banks weight-3.0 at whatever the audio says. Returning 0.0 for the
        # unknown side instead is NOT the fix either — it would punish a real
        # instrumental, which has no thematic content to clash with.
        #
        # The caller resolves this per-candidate via is_unclassified; here we
        # only need to stop returning None for the case that reaches us.
        if sim is None and is_unclassified(a) != is_unclassified(b):
            return 0.0
        return sim
    if kind == "key":
        return key_sim(x, y)
    if kind == "mode":
        return mode_sim(x, y)
    if kind == "exact":
        return exact_sim(x, y)
    raise ValueError(f"unknown dimension kind: {kind}")


# ---------------------------------------------------------------------------
# Composite scoring
# ---------------------------------------------------------------------------

def similarity(a, b, arc=None):
    """
    Weighted composite similarity of track b to track a.

    Returns (score, contributions) where score is 0..1 and contributions maps
    dimension name -> {"sim", "weight", "contribution"} for explanation.

    Dimensions missing on either side are simply skipped and the weights
    renormalised, so a track with partial analysis degrades gracefully instead
    of being penalised for what we failed to measure.
    """
    drift_map = ARC_PRESETS.get(arc, {}) if arc else {}

    contributions = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for dim in DIMENSIONS:
        drift = drift_map.get(dim["name"], 0.0)
        sim = dimension_similarity(dim, a, b, drift)
        if sim is None:
            continue

        weight = dim["weight"]
        if dim["provenance"] == "approximated":
            weight *= PROVENANCE_DISCOUNT

        contributions[dim["name"]] = {
            "sim": round(sim, 4),
            "weight": round(weight, 3),
            "contribution": round(sim * weight, 4),
        }
        weighted_sum += sim * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0, {}

    return round(weighted_sum / total_weight, 4), contributions


def _confident_lead(vec):
    """
    The vector's leading theme, and whether that lead is real.

    Returns (label, margin) where margin is the gap to the runner-up, or
    (None, 0.0) for an empty vector. A margin of exactly 0 means the "lead"
    was decided by dict insertion order, which is not a claim about the music.
    "Do Numbari" carries celebration=1.0 and aggression=1.0; plain max() calls
    it a celebration track and, worse, calls it thematically identical to a
    purely romantic one, because both lines up the same way.
    """
    if not vec:
        return None, 0.0
    ranked = sorted(vec.items(), key=lambda kv: (-kv[1], kv[0]))
    lead = ranked[0][0]
    margin = ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0.0)
    return lead, margin


def theme_drift(a, b):
    """
    How far b drifts thematically from a, as 0..1 where 0 is identical mood.

    Kept separate from `similarity` because it is a *constraint*, not a score:
    the arc control may want a track that is further away energetically but
    this must never let the mood family change.

    Returns None only when there is genuinely nothing to compare — see
    is_unclassified for the distinction between "no lyrics" and "no label".

    The lead-label term only counts when BOTH sides have an undisputed lead.
    An earlier version took plain argmax on both sides and awarded the full
    0.6 for equality, so two tracks that each merely *mention* a theme as
    loudly as their real one scored as the same mood. Measured on the library:
    tightening this newly excludes 18 of 8556 ordered pairs (0.2%), all of
    them same-label pairs whose shared label is a tie — no mass locking.
    """
    ta, tb = a.get("theme_scores") or {}, b.get("theme_scores") or {}
    if not ta or not tb:
        return None   # unknown, not "safe"

    lead_a, margin_a = _confident_lead(ta)
    lead_b, margin_b = _confident_lead(tb)
    same_lead = (1.0 if lead_a == lead_b
                 and margin_a > 0.0 and margin_b > 0.0 else 0.0)
    cosine = dict_cosine(ta, tb) or 0.0
    return round(1.0 - (0.6 * same_lead + 0.4 * cosine), 4)


def is_unclassified(track):
    """
    True when a track's theme is unknown rather than absent — unknown, not safe.

    An instrumental is not unclassified: there is no thematic content that
    could clash, so it passes at full weight. Everything else with no theme is
    something we failed to read, and that is ignorance, not safety. Two ways to
    fail:

      * lyrics found, lexicon could not agree on a theme (BLOOD IS BETTER THAN
        TEARS, one aggression term under the floor);
      * no lyrics found at all, but a voice is plainly audible — the lyrics
        exist and we did not fetch them. word_count == 0 here means "none
        found", not "none present", and the library is unambiguous about which:
        all 18 such tracks carry vocal_presence >= 0.65.
    """
    if track.get("theme_scores"):
        return False
    if (track.get("word_count") or 0) > 0:
        return True
    return (track.get("vocal_presence") or 0.0) >= VOCAL_PRESENCE_FLOOR


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def rank_neighbours(library, track_id, limit=10, arc=None,
                    respect_theme_lock=True, allow_explicit=True,
                    same_artist_penalty=0.0, lookahead=0):
    """
    Rank every other track by similarity to `track_id`.

    Deliberately a SOFT ranking with no hard similarity cutoff (PRD FR-3.10):
    a threshold would eventually filter everything out and stall the queue,
    whereas a ranking always yields a next track and merely gets less apt.
    The only hard filters are the ones the user explicitly asked for —
    explicit-lyric exclusion — and the theme lock, which is the product's
    central promise.
    """
    if track_id not in library:
        raise KeyError(f"track {track_id!r} not in library")

    anchor = library[track_id]
    scored = []

    for tid, cand in library.items():
        if tid == track_id:
            continue

        start = _artist_key(anchor)
        if same_artist_penalty and start and start == _artist_key(cand):
            penalty = same_artist_penalty
        else:
            penalty = 1.0

        # Apply lookahead penalty if enabled
        if lookahead > 0:
            penalty *= _calculate_lookahead_penalty(library, tid, track_id, lookahead)

        if not allow_explicit and cand.get("has_explicit"):
            continue

        if respect_theme_lock:
            drift = theme_drift(anchor, cand)
            if drift is not None and drift > MAX_THEME_DRIFT:
                continue

        if is_unclassified(cand):
            penalty = penalty * UNCLASSIFIED_THEME_PENALTY

        score, contributions = similarity(anchor, cand, arc=arc)
        score = round(score * penalty, 4)
        if score <= 0:
            continue

        scored.append({
            "track_id": tid,
            "score": score,
            "title": cand.get("title"),
            "artist": cand.get("artist"),
            "language": cand.get("language"),
            "theme": cand.get("primary_theme"),
            "emotion": cand.get("primary_emotion"),
            "tempo": cand.get("tempo_bpm"),
            "contributions": contributions,
            "_tb": tiebreak_rank(anchor, cand),
        })

    # Sort by score, then by the user's stated tie-break priority. The
    # tie-break is INSIDE the sort key rather than a second pass, so it can
    # only ever reorder tracks that are already equal on score — it can never
    # promote a track past a better-scoring one. This matters: a same-language
    # track must not outrank a closer match just because the words agree.
    scored.sort(key=lambda r: (-r["score"], r["_tb"]))

    results = scored[:limit]
    for r in results:
        r.pop("_tb", None)
        r["tiebreak"] = tiebreak_reason(anchor, library[r["track_id"]])
    return results


def _artist_key(track):
    """Normalised artist for same-artist comparisons."""
    artist = (track or {}).get("artist") or ""
    return artist.strip().lower()


def _language_key(track):
    """Normalised language for same-language comparisons."""
    lang = (track or {}).get("language") or ""
    return lang.strip().lower()


def _has_lyrics(track):
    """
    True when words were actually read for this track.

    Deliberately word_count, not primary_theme: a track whose lyrics we read
    but could not classify still HAS lyrics, and the tie-break should prefer it
    over a track that has none — the words are evidence even when the label is
    absent. See is_unclassified for the separate question of trust.
    """
    return bool((track or {}).get("word_count") or 0) > 0


# Tie-break priority, in the user's stated order. Applied ONLY when two
# candidates score identically — see rank_neighbours. Lower tuple = preferred.
TIE_BREAK_LABELS = ("same language", "same artist", "has lyrics")


def tiebreak_rank(anchor, cand):
    """
    Order two EQUAL-scoring candidates. Lower is better.

    One 0/1 per priority level, in this order:
      1. same language   — the words are in a language the listener's anchor is
      2. same artist     — a known voice
      3. has lyrics      — words exist at all

    None of these is part of the similarity score, and none of them can move a
    track past a differently-scoring one. That separation is the point: the
    score says how alike two tracks are, and this only decides which of two
    equally-alike tracks to play first.

    A missing value on either side never counts as a match — an anchor with no
    lyrics should not "share a language" with every other instrumental.
    """
    same_lang = (0 if _language_key(anchor)
                 and _language_key(anchor) == _language_key(cand) else 1)
    same_artist = (0 if _artist_key(anchor)
                   and _artist_key(anchor) == _artist_key(cand) else 1)
    has_lyr = 0 if _has_lyrics(cand) else 1
    return (same_lang, same_artist, has_lyr)


def tiebreak_reason(anchor, cand):
    """Which priority level prefers `cand`, for display. None if none does."""
    tb = tiebreak_rank(anchor, cand)
    for label, flag in zip(TIE_BREAK_LABELS, tb):
        if flag == 0:
            return label
    return None


def _next_track_in_queue(library, current_id, step):
    """
    Helper function to find the next track in the queue.

    Args:
        library: The library of tracks.
        current_id: The current track ID.
        step: The number of steps ahead to look.

    Returns:
        The ID of the next track in the queue.
    """
    all_tracks = list(library.keys())
    current_index = all_tracks.index(current_id)
    next_index = (current_index + step) % len(all_tracks)
    return all_tracks[next_index]

def _calculate_lookahead_penalty(library, candidate_id, anchor_id, lookahead):
    """
    Calculate penalty based on lookahead to ensure arc consistency.

    Args:
        library: The library of tracks.
        candidate_id: The candidate track ID.
        anchor_id: The anchor track ID.
        lookahead: Number of tracks to look ahead.

    Returns:
        Penalty factor (0.0 to 1.0) based on arc consistency.
    """
    anchor = library[anchor_id]
    candidate = library[candidate_id]
    arc_consistency = 1.0
    for i in range(1, lookahead + 1):
        next_id = _next_track_in_queue(library, anchor_id, i)
        if next_id is None or next_id == candidate_id:
            break

        next_track = library[next_id]
        score, _ = similarity(candidate, next_track, arc=None)
        if score < 0.7:
            arc_consistency *= 0.7
    return arc_consistency
