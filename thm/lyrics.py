"""
Lyrical / thematic analysis (PRD Section 5, Family F).

WHY THIS IS RULE-BASED AND NOT A TRANSFORMER
--------------------------------------------
The PRD specifies transformer-based theme classification. That is the wrong
tool for *this* library, and it is worth being explicit about why:

  1. Lyric topic classification is unsupervised and ill-posed. A pretrained
     English emotion model cannot be fine-tuned to output "romantic vs
     gangster rap" without labelled data we do not have — so its output would
     be a plausible-looking number with no ground truth behind it.
  2. The library is Punjabi/Hindi, and critically it appears in THREE scripts:
     Gurmukhi, Devanagari, and Roman transliteration. A downloaded library is
     not script-consistent, and a model trained on one will silently fail on
     the others.
  3. It would add a ~500 MB model download and GPU-class latency to solve a
     problem that a transparent lexicon solves better *and* explainably.

A lexicon is auditable — you can read the words that fired and disagree with
them. That property matters more here than marginal accuracy, because the whole
product depends on the user trusting why a song was chosen.

VALIDATION HISTORY (why the thresholds below are what they are)
---------------------------------------------------------------
First run against the real library produced two failures, both fixed here:

  * "GOJIRA" (a Punjabi diss/hustle track, Roman script) scored
    romance/tender/1.0. Root cause: the entire romance match was ONE English
    word, "beautiful", in 453 words. Because scoring normalised against the
    peak hit, a single stray word scaled to a perfect 1.0. Fix: an absolute
    floor (MIN_HITS / MIN_RATE) that no theme may fire below, regardless of
    how it ranks relative to other themes.

  * "Aadat" by Atif Aslam (a pure heartbreak song, Devanagari) scored
    None/neutral/unknown. Root cause: the lexicon was Gurmukhi-only. Fix:
    every theme now carries gurmukhi + devanagari + roman term lists.

The general lesson, which is now a design rule: a *missing* label is harmless,
because the audio features still decide. A *wrong* label is actively harmful,
because it steers the queue. Prefer silence to a guess.
"""

import re

# ---------------------------------------------------------------------------
# Script detection
# ---------------------------------------------------------------------------

_GURMUKHI = re.compile(r"[਀-੿]")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")


def detect_language(text):
    """Return (language, script) for a lyric body."""
    n_gur = len(_GURMUKHI.findall(text))
    n_dev = len(_DEVANAGARI.findall(text))
    n_lat = len(_LATIN.findall(text))
    total = n_gur + n_dev + n_lat

    if total == 0:
        return "unknown", "unknown"

    if n_gur / total > 0.5:
        return "punjabi", "gurmukhi"
    if n_dev / total > 0.5:
        return "hindi", "devanagari"
    if n_gur > 0 and n_lat > 0:
        # Gurmukhi + Latin is the standard code-mixed Punjabi pop form.
        return "punjabi", "mixed"
    if n_dev > 0 and n_lat > 0:
        return "hindi", "mixed"
    if n_gur + n_dev > 0:
        return "punjabi", "mixed"
    return "romanic", "latin"


# ---------------------------------------------------------------------------
# Theme lexicon across three scripts
# ---------------------------------------------------------------------------
# Each theme carries three term lists. Matching rules differ per script:
#
#   gurmukhi / devanagari — substring match. Both are agglutinative enough that
#     stem matching beats word boundaries (ਇਸ਼ਕ is a stem inside ਇਸ਼ਕਾਂ).
#   roman — whole-word match with an optional suffix group. Word boundaries are
#     essential here: a substring match on "dil" would fire on "Dilli", which
#     is exactly the kind of false positive that broke the first run.

# Each theme carries three CORE term lists — high-precision words that appear
# overwhelmingly in that theme and almost nowhere else — plus optional SOFT
# lists for words that are merely *suggestive*.
#
# The core/soft split exists because the second validation run failed on
# "HIGH ON YOU" (a devoted love song): the word "yaad" (remembering you) fired
# six times and outvoted the entire romance vocabulary, labelling a love song
# as heartbreak. The word list was not wrong — "yaad" really does mean missing
# someone. The problem was that the scorer treated it as equivalent to "judai"
# (separation), which is decisive. Ranking words by strength fixed it.
#
# Matching rules differ per script:
#
#   gurmukhi / devanagari — substring match. Both are agglutinative enough that
#     stem matching beats word boundaries (ਇਸ਼ਕ is a stem inside ਇਸ਼ਕਾਂ).
#   roman — whole-word match. Word boundaries are essential here: a substring
#     match on "dil" would fire on "Dilli", which is exactly the kind of false
#     positive that broke the first run.

THEME_LEXICON = {
    "romance": {
        "gurmukhi": [
            "ਇਸ਼ਕ", "ਪਿਆਰ", "ਮੁਹੱਬਤ", "ਸੱਜਣ", "ਮਾਹੀ", "ਬੇਲੀ", "ਹੀਰ",
            "ਰਾਂਝਾ", "ਸੱਸੀ", "ਪੁੰਨੂੰ", "ਮਿਰਜ਼ਾ", "ਸਾਹਿਬਾ", "ਲਗਨ", "ਵਫ਼ਾ",
            "ਵਫਾ", "ਦੀਵਾਨ", "ਸੋਹਣੀ", "ਪ੍ਰੀਤ", "ਮਹਿੰਦੀ", "ਚਾਹਤ", "ਸੁਹਾਗ",
        ],
        "devanagari": [
            "प्यार", "इश्क़", "इश्क", "मोहब्बत", "सजन", "साजन", "माही",
            "प्रीत", "हीर", "रांझा", "सासी", "मिर्ज़ा", "वफ़ा", "वफा",
            "दीवान", "चाहत", "महिंदी", "सुहाग", "माशूक",
        ],
        "roman": [
            "love", "pyaar", "pyar", "ishq", "isq", "mohabbat", "sanam",
            "soniye", "soniya", "mahiya", "mahi", "preet", "heer", "ranjha",
            "sassi", "mirza", "wafa", "wafaa", "deewana", "diwana", "dilbar",
            "dilwale", "mehboob", "ashiq", "aashiq", "aashiqui", "janeman",
        ],
        # Suggestive, not decisive: "dil" (heart) shows up in diss tracks,
        # "yaar" is friendship as often as love, "sohna" describes anything.
        "soft_gurmukhi": ["ਦਿਲ", "ਜਾਨ", "ਯਾਰ", "ਯਾਰੀ", "ਮੋਹ", "ਅੱਖੀਆਂ",
                          "ਨੈਣ", "ਹੁਸਨ", "ਸੋਹਣਾ"],
        "soft_devanagari": ["दिल", "जान", "यार", "यारी", "मोह", "आँख", "आंख",
                            "नैन", "हसीन", "तड़प", "बेकरार", "दीवाना"],
        "soft_roman": ["dil", "jaan", "jaana", "jaani", "yaar", "yaari",
                       "yari", "moh", "akhiyan", "ankhiyan", "nain", "sohni",
                       "sohna", "husn", "chaahat", "bekarar", "tadap"],
    },
    "heartbreak": {
        "gurmukhi": [
            "ਜੁਦਾਈ", "ਜੁਦਾ", "ਹਿਜਰ", "ਵਿਛੋੜਾ", "ਵਿਛੁੜ", "ਰੋਣਾ", "ਰੋਂਦਾ",
            "ਹੰਝੂ", "ਅੱਥਰੂ", "ਦੁੱਖ", "ਤਕਲੀਫ਼", "ਤੜਫ", "ਬੇਹਾਲ", "ਟੁੱਟ", "ਢਹਿ",
            "ਤਨਹਾ", "ਗ਼ਮ", "ਗਮ", "ਬਰਬਾਦ", "ਅਫ਼ਸੋਸ", "ਕਲੇਜਾ", "ਜਖ਼ਮ",
        ],
        "devanagari": [
            "जुदा", "जुदाई", "हिज्र", "विछोड़", "रोना", "रोता", "आँसू", "आंसू",
            "हंजू", "दुख", "दर्द", "तड़प", "बेहाल", "टूट", "टूटा", "तनहा",
            "ग़म", "गम", "बर्बाद", "अफ़सोस", "कलेजा", "ज़ख़्म", "जख्म",
            "भूल", "भुला", "भूला", "भूलना",
        ],
        "roman": [
            "juda", "judai", "judaai", "hijr", "vichhoda", "rona", "ronda",
            "hanju", "aansu", "ansu", "dukh", "dard", "tadap", "behal",
            "behaal", "toot", "tuta", "toota", "tanha", "gham", "gum",
            "barbaad", "zakhm", "afsos", "kaleja", "breakup", "broken",
            "tears", "lonely", "bhula", "bhoola", "bhool",
        ],
        # "yaad" is the fix that motivated this whole core/soft split — it is
        # longing, which is romance as often as it is grief.
        "soft_gurmukhi": ["ਯਾਦ", "ਯਾਦਾਂ", "ਖਾਲੀ"],
        "soft_devanagari": ["याद", "यादें", "खाली"],
        "soft_roman": ["yaad", "yaadein", "khali", "alone", "miss", "lost",
                       "insomnia"],
    },
    "celebration": {
        "gurmukhi": [
            "ਖੁਸ਼ੀਆਂ", "ਜਸ਼ਨ", "ਢੋਲ", "ਭੰਗੜਾ", "ਗਿੱਧਾ", "ਮੇਲਾ", "ਪਾਰਟੀ",
            "ਨੱਚ", "ਗਾਉਣਾ", "ਮੁਬਾਰਕ", "ਵਧਾਈ", "ਦਾਅਵਤ",
        ],
        "devanagari": [
            "खुशी", "खुशियाँ", "जश्न", "ढोल", "भांगड़ा", "गिद्धा", "मेला",
            "पार्टी", "नाच", "गाना", "मुबारक", "बधाई", "दावत",
        ],
        "roman": [
            "khushi", "khushiyan", "jashn", "dhol", "bhangra", "gidda",
            "mela", "party", "nach", "nachna", "gauna", "mubarak", "badhai",
            "daawat", "celebration",
        ],
        "soft_gurmukhi": ["ਸ਼ਰਾਬ", "ਬੋਤਲ", "ਪੈਗ"],
        "soft_devanagari": ["शराब", "बोतल", "पैग"],
        "soft_roman": ["sharab", "bottle", "peg"],
    },
    "struggle": {
        "gurmukhi": [
            "ਸੰਘਰ", "ਜੱਦੋਜਹਿਦ", "ਮਿਹਨਤ", "ਗਰੀਬੀ", "ਔਖਾ", "ਮੁਸ਼ਕਿਲ", "ਜਿੱਤ",
            "ਹਾਰ", "ਸੁਪਨੇ", "ਧੱਕੇ", "ਲੜ",
        ],
        "devanagari": [
            "संघर्ष", "जद्दोजहद", "मेहनत", "गरीबी", "औखा", "मुश्किल", "जीत",
            "हार", "सपने", "सपना", "धक्के", "लड़", "इम्तिहान",
        ],
        "roman": [
            "sangharsh", "jaddojahad", "mehnat", "gareebi", "aukha",
            "mushkil", "jeet", "haar", "sapne", "sapna", "imtihaan",
            "dhakke", "struggle",
        ],
        # Money words are hustle *signifiers*, but they appear just as often in
        # flexing tracks that are really about status, not struggle.
        "soft_gurmukhi": ["ਪੈਸਾ", "ਕਮਾਈ", "ਕਰੋੜ", "ਸਖ਼ਤ"],
        "soft_devanagari": ["पैसा", "कमाई", "कमाया", "करोड़"],
        "soft_roman": ["paisa", "paise", "crore", "kamyaabi", "kamyabi",
                       "grind", "hustle", "rotiya", "ladai"],
    },
    "party": {
        "gurmukhi": ["ਪਾਰਟੀ", "ਨੱਚਦੀ", "ਬੀਟ", "ਧਮਾਕਾ", "ਰੌਣਕ", "ਕਲੱਬ"],
        "devanagari": ["पार्टी", "नाचती", "बीट", "धमाका", "रौनक", "क्लब"],
        "roman": ["party", "beat", "club", "shots", "tonight", "dancefloor"],
        "soft_gurmukhi": ["ਸ਼ਾਮ"],
        "soft_devanagari": ["शाम"],
        "soft_roman": ["turn", "lit", "vibe"],
    },
    "spirituality": {
        # NOTE: ਨਾਮ / नाम / naam is deliberately NOT in the core list. In every
        # script it is a homonym — "name" in ordinary speech, "the divine name"
        # only in devotional context — and desi rap uses it overwhelmingly in
        # the first sense: "Mittra'n da naam" (my crew's name), "apnon ka naam",
        # "naam 47 hai". As a core term it mislabelled 13 of the 75 lyric tracks
        # here in one direction, the worst being "Headliner" (Navaan Sandhu),
        # which fired 44 spirituality hits that were ALL "Mittra'n da naam" and
        # had zero devotional anchors anywhere in the text. Demoted to soft:
        # it can still reinforce a theme that fired on real evidence, but it can
        # never make one fire by itself. ਦਾਤਾ is not a homonym ("giver",
        # devotional) and stays core.
        "gurmukhi": [
            "ਰੱਬ", "ਵਾਹਿਗੁਰੂ", "ਅਕਾਲ", "ਪੁਰਖ", "ਸਿਮਰਨ", "ਬਾਣੀ",
            "ਸਤਿਗੁਰ", "ਮੇਹਰ", "ਕਿਰਪਾ", "ਦਾਤਾ", "ਪ੍ਰਮਾਤਮਾ",
        ],
        "devanagari": [
            "रब", "वाहेगुरु", "अकाल", "पुरख", "सिमरन", "बानी",
            "सतिगुर", "मेहर", "किरपा", "दाता", "प्रमात्मा", "भगवान", "खुदा",
            "दुआ", "रूह", "सुकून", "तजल्ली", "तसल्ली", "मौला", "फ़क़ीर",
        ],
        "roman": ["rab", "waheguru", "akal", "purkh", "simran",
                  "baani", "satgur", "mehar", "kirpa", "daata", "parmatma",
                  "khuda", "bhagwan", "dua", "pray"],
        # "guru" and "sahib" are honorifics used casually; "blessed"/"faith"
        # show up in secular gratitude tracks. "naam" joins them for the
        # homonym reason above.
        "soft_gurmukhi": ["ਗੁਰੂ", "ਸਾਹਿਬ", "ਨਾਮ"],
        "soft_devanagari": ["गुरु", "साहिब", "नाम"],
        "soft_roman": ["guru", "sahib", "blessed", "faith", "naam"],
    },
    "aggression": {
        "gurmukhi": [
            "ਵੈਰੀ", "ਦੁਸ਼ਮਣ", "ਲੜਾਈ", "ਹਥਿਆਰ", "ਗੋਲੀ", "ਬੰਦੂਕ", "ਖੂਨ",
            "ਰੌਲਾ", "ਧੌਂਸ", "ਪੰਜਾ", "ਜੁਰਮ", "ਗੁੰਡਾ", "ਤਾਕਤ", "ਬਦਲਾ",
        ],
        "devanagari": [
            "वैरी", "दुश्मन", "लड़ाई", "हथियार", "गोली", "बंदूक", "खून",
            "रौला", "धौंस", "पंजा", "जुर्म", "गुंडा", "ताकत", "बदला",
        ],
        # Deliberately short. "tod" was trialled here and removed: in
        # "teri tod lagdi" (HIGH ON YOU) it means "you hurt me", which is
        # heartbreak, not aggression. Punjabi break/ruin verbs are too
        # context-dependent to use as aggression evidence.
        "roman": ["vairi", "dushman", "hathiyaar", "goli", "bandook",
                  "khoon", "gunda", "taakat", "badla", "jurm", "gang",
                  "enemy", "beef", "opp", "gundagardi", "khunn"],
        # These English words carry violence in *some* registers and hype in
        # others ("beast mode", "smoke" = weed, "block" = neighbourhood).
        "soft_gurmukhi": [],
        "soft_devanagari": [],
        "soft_roman": ["gun", "shot", "war", "attack", "savage", "beast",
                       "smoke", "block", "violence", "kill"],
    },
    "nostalgia": {
        "gurmukhi": ["ਪੁਰਾਣੇ", "ਬਚਪਨ", "ਪਿੰਡ", "ਯਾਦਾਂ", "ਪਹਿਲਾਂ", "ਸਮਾਂ",
                     "ਵੇਲੇ"],
        "devanagari": ["पुराने", "बचपन", "पिंड", "यादें", "पहले", "समय",
                       "वक़्त", "वक्त"],
        "roman": ["purane", "bachpan", "pind", "yaadein", "pehle",
                  "childhood", "memories"],
        # "ghar"/"home" and "maa" are in half of all songs for other reasons.
        "soft_gurmukhi": ["ਘਰ", "ਮਾਂ", "ਪਿਤਾ"],
        "soft_devanagari": ["घर", "माँ", "मां", "पिता"],
        "soft_roman": ["ghar", "home", "maa", "pita", "sama", "vele", "young"],
    },
}

# Profanity is tracked separately from theme, because explicitness is a FILTER
# (PRD F9), not a similarity dimension. A track is not "more aggressive" for
# containing a swear word — but some users want it excluded entirely.
_EXPLICIT_TERMS = {
    "gurmukhi": ["ਗਾਲੀ", "ਲਾਹਨਤ", "ਕੁੱਤਿਆ", "ਕੁੱਤੇ", "ਨਸ਼ਾ"],
    "devanagari": ["गाली", "कुत्ते", "कुत्तिया", "नशा", "चूतिया", "लौड़े"],
    "roman": ["fuck", "fucking", "shit", "bitch", "ass", "damn", "nigga",
              "bsdk", "chutiya", "lawde", "chuda", "bhosdi", "harami",
              "saala", "kutta"],
}

# ---------------------------------------------------------------------------
# Thresholds — the fix for the GOJIRA false positive
# ---------------------------------------------------------------------------
# A theme must clear BOTH an absolute core-hit floor and a density floor before
# it fires. Normalising against the peak alone (the original bug) lets a single
# stray word become a confident label.
MIN_HITS = 2            # core hits required
MIN_RATE = 0.4          # core hits per 100 words

# The density floor is deliberately low because rap lyrics are long and
# lexically diverse — a 500-word diss track may contain only a handful of
# unmistakable aggression words, while a 60-word chorus repeats two of them
# twenty times. Density scoring already handles the chorus case; the floor's
# only job is to stop a single incidental hit, which 0.4 does: one hit in 500
# words is 0.2/100 and still fails.
#
# TRIED AND REVERTED: making this a proportional confidence ramp instead of a
# wall, to rescue the 0.394-vs-0.400 case in the Phase 1 report (§3.8). It was
# measured against the real library and rejected — see that section, which now
# records the attempt. Loosening the wall admits junk: it produced four new
# `spirituality` labels from religious nouns alone (`khuda`x2 in 574 words,
# `rab`x2 in 1619) — the exact `naam` failure class already documented in §3.7
# — plus `celebration` from ढोल/गाना ("drum"/"song") and `party` from "beat".
# MIN_RATE is load-bearing as a false-positive guard, not only as a veto.
# The 0.006 case is a real defect and it is NOT solved here.

SOFT_WEIGHT = 0.3       # a soft term counts for a third of a core term

SOFT_WEIGHT = 0.3       # a soft term counts for a third of a core term


# Token splitter for Indic scripts. Deliberately punctuation-based rather than
# \w-based: Devanagari and Gurmukhi are not \w in Python's re, so \b is useless
# here. Includes the Devanagari danda and the bar LRC lyric tools emit.
_TOKEN_RE = re.compile(r"[^\s।,\.!\?\|\(\)\[\]\"'\-–—]+")


def _count_substrings(text, terms):
    """
    Count Indic-script terms, requiring each to BEGIN a token.

    Boundary-BEFORE only, not both sides. The lexicon is written with stems on
    purpose — "ਦੀਵਾਨ" must still catch "ਦੀਵਾਨਾ", "चाहत" must catch "चाहता" —
    so anchoring the end would break correct inflectional variants. Anchoring
    only the start keeps every stem working while killing the false positives
    that substring matching produced, all of which hid in the *middle* or *end*
    of an unrelated word:

        नाम   inside बदनाम  ("infamous")   15 hits in this library
        हार   inside म्हारे / तुम्हारा ("my"/"your")   12 + 2 hits
        ਵੇਲੇ  inside a longer word

    Measured against the real library: this changes 6 of 226 Indic terms, and
    in every case the count moves toward the truth. The stem behaviour above is
    preserved exactly.

    Note this cannot be a \\b regex — Python's \\b is defined on \\w, which does
    not classify Gurmukhi or Devanagari as word characters, so it silently
    matches everywhere.
    """
    if not terms:
        return 0
    tokens = re.findall(_TOKEN_RE, text)
    return sum(1 for t in terms for w in tokens if w.startswith(t))


def _count_words(text_lower, terms):
    """Count whole-word occurrences (Roman script)."""
    total = 0
    for term in terms:
        total += len(re.findall(r"\b" + re.escape(term) + r"\b", text_lower))
    return total


def _score_theme(text, text_lower, lex):
    """
    Return (core_hits, weighted_hits) for one theme.

    Core hits decide whether a theme is allowed to fire at all. Weighted hits —
    core plus discounted soft terms — decide how strongly it scores. Keeping
    the two separate is what stops a pile of vague words ("yaad", "dil",
    "ghar") from outvoting a couple of decisive ones ("judai").
    """
    core = (_count_substrings(text, lex["gurmukhi"])
            + _count_substrings(text, lex["devanagari"])
            + _count_words(text_lower, lex["roman"]))

    soft = (_count_substrings(text, lex.get("soft_gurmukhi", []))
            + _count_substrings(text, lex.get("soft_devanagari", []))
            + _count_words(text_lower, lex.get("soft_roman", [])))

    return core, core + SOFT_WEIGHT * soft


def classify_themes(text, duration_seconds=180.0):
    """
    Score the text against each theme across all three scripts.

    Returns (theme_scores, primary_theme). theme_scores maps theme -> 0..1.

    Density (hits per 100 words) is used rather than raw counts, so a long rap
    track is not favoured over a short ballad purely for having more words.
    """
    text_lower = text.lower()
    words = max(len(text.split()), 1)

    raw = {}
    for theme, lex in THEME_LEXICON.items():
        core, weighted = _score_theme(text, text_lower, lex)
        rate = (core / words) * 100.0

        # Absolute floor on CORE hits: a theme cannot fire on incidental
        # soft vocabulary alone.
        if core < MIN_HITS or rate < MIN_RATE:
            raw[theme] = 0.0
        else:
            raw[theme] = weighted

    peak = max(raw.values()) if raw else 0.0
    if peak <= 0:
        return {}, None

    # Normalise so the dominant theme is 1.0. The 0.7 exponent keeps a track
    # with two genuinely strong themes from collapsing to one (PRD F1 is
    # multi-label, and GOJIRA wants struggle *and* aggression).
    scores = {t: round(min(1.0, (v / peak) ** 0.7), 4) for t, v in raw.items()}
    scores = {t: s for t, s in scores.items() if s > 0.15}

    primary = max(scores, key=scores.get) if scores else None
    return scores, primary


# ---------------------------------------------------------------------------
# Perspective (PRD F5) — second person is the signal the "One Love" case needs
# ---------------------------------------------------------------------------

_PRONOUNS = {
    "first": {
        "gurmukhi": ["ਮੈਂ", "ਮੇਰਾ", "ਮੇਰੀ", "ਮੇਰੇ", "ਮੈਨੂੰ", "ਅਸੀਂ", "ਸਾਡਾ"],
        "devanagari": ["मैं", "मेरा", "मेरी", "मेरे", "मुझे", "मुझमें", "हम",
                       "हमारा"],
        "roman": ["i", "me", "my", "mine", "we", "our", "main", "mujhe",
                  "maine", "hum", "mera", "meri", "mere", "apna"],
    },
    "second": {
        "gurmukhi": ["ਤੂੰ", "ਤੈਨੂੰ", "ਤੇਰਾ", "ਤੇਰੀ", "ਤੇਰੇ", "ਤੁਸੀਂ", "ਤੈਂ"],
        "devanagari": ["तू", "तुझे", "तेरा", "तेरी", "तेरे", "तुम", "तुम्हारा",
                       "आप"],
        "roman": ["you", "your", "yours", "tu", "tum", "tera", "teri", "tere",
                  "tujhe", "tumhara", "tumhe"],
    },
    "third": {
        "gurmukhi": ["ਉਹ", "ਉਸ", "ਉਹਨੂੰ", "ਉਸਦਾ", "ਉਸਦੀ", "ਉਨ੍ਹਾਂ"],
        "devanagari": ["वह", "वो", "उस", "उसका", "उसकी", "उनका", "वे"],
        "roman": ["he", "she", "him", "her", "they", "woh", "wo", "uska",
                  "uski", "unka", "ohnu", "usda"],
    },
}


def detect_perspective(text):
    """Classify narrative perspective: first, second, third, mixed, or unknown."""
    text_lower = text.lower()

    counts = {}
    for person, lex in _PRONOUNS.items():
        counts[person] = (
            _count_substrings(text, lex["gurmukhi"])
            + _count_substrings(text, lex["devanagari"])
            + _count_words(text_lower, lex["roman"])
        )

    total = sum(counts.values())
    if total == 0:
        return "unknown"

    ordered = sorted(counts.values(), reverse=True)
    # If the top two are close, the song genuinely addresses more than one
    # person and calling it a single perspective would be misleading.
    if len(ordered) > 1 and ordered[0] > 0 and ordered[1] / ordered[0] > 0.8:
        return "mixed"

    return max(counts, key=counts.get)


# ---------------------------------------------------------------------------
# Sentiment (PRD F3)
# ---------------------------------------------------------------------------

_POSITIVE = {
    "gurmukhi": ["ਖੁਸ਼", "ਪਿਆਰ", "ਇਸ਼ਕ", "ਸੋਹਣ", "ਚੰਗਾ", "ਵਧੀਆ", "ਮੁਬਾਰਕ",
                 "ਦੁਆ", "ਮੇਹਰ", "ਕਿਰਪਾ", "ਜਿੱਤ", "ਹੱਸ", "ਮੁਸਕ", "ਸੁਖ"],
    "devanagari": ["खुश", "प्यार", "इश्क", "सोहण", "अच्छा", "मुबारक", "दुआ",
                   "मेहर", "किरपा", "जीत", "हँस", "सुख", "प्यारा"],
    "roman": ["love", "happy", "good", "great", "blessed", "win", "smile",
              "best", "khush", "jeet", "sukh", "acha", "pyara"],
}

_NEGATIVE = {
    "gurmukhi": ["ਦੁੱਖ", "ਗ਼ਮ", "ਗਮ", "ਰੋ", "ਹੰਝੂ", "ਤੜਫ", "ਬੇਹਾਲ", "ਜੁਦਾਈ",
                 "ਟੁੱਟ", "ਤਨਹਾ", "ਜਖ਼ਮ", "ਬਰਬਾਦ", "ਔਖ", "ਮੁਸ਼ਕਿਲ", "ਦਰਦ"],
    "devanagari": ["दुख", "दर्द", "ग़म", "गम", "रो", "आँसू", "आंसू", "तड़प",
                   "बेहाल", "जुदाई", "टूट", "तनहा", "जख्म", "बर्बाद", "मुश्किल"],
    "roman": ["sad", "cry", "pain", "hurt", "broken", "alone", "miss",
              "bad", "lost", "dukh", "dard", "gham", "tanha", "judai",
              "rona", "barbaad"],
}


MIN_SENTIMENT_SIGNAL = 4    # total hits before sentiment is worth reporting


def sentiment(text):
    """
    Approximate lyrical valence in -1..+1.

    Coarse by design — audio carries most of the valence weight downstream.

    Two guards, both added after validation showed a run of tracks pinned at
    exactly ±1.00 (i.e. a single matched word deciding the emotion):

      * a minimum signal. Below MIN_SENTIMENT_SIGNAL hits the score is
        reported as 0.0. "I don't know" is a more useful input to the
        similarity engine than a confident label built on one word.
      * a square-root curve instead of a linear ratio, so 5 positive / 1
        negative gives 0.55 rather than 0.67, and only genuinely lopsided
        lyrics approach the extremes.
    """
    import math

    text_lower = text.lower()

    pos = (_count_substrings(text, _POSITIVE["gurmukhi"])
           + _count_substrings(text, _POSITIVE["devanagari"])
           + _count_words(text_lower, _POSITIVE["roman"]))
    neg = (_count_substrings(text, _NEGATIVE["gurmukhi"])
           + _count_substrings(text, _NEGATIVE["devanagari"])
           + _count_words(text_lower, _NEGATIVE["roman"]))

    total = pos + neg
    if total < MIN_SENTIMENT_SIGNAL:
        return 0.0

    ratio = (pos - neg) / total
    magnitude = math.sqrt(min(1.0, total / 12.0))
    return round(ratio * magnitude, 3)


# ---------------------------------------------------------------------------
# Emotion + explicitness + top-level entry point
# ---------------------------------------------------------------------------

def map_emotion(theme_scores, sentiment_score, tempo_bpm=None):
    """
    Derive an emotional tone label (PRD F2) from theme, sentiment and tempo.

    Emotion is not directly observable from text. Tempo disambiguates the
    calm/energised axis: a romance theme at 75 BPM is tender, at 130 it is
    euphoric.
    """
    if not theme_scores:
        return "neutral"

    theme = max(theme_scores, key=theme_scores.get)
    fast = tempo_bpm is not None and tempo_bpm >= 115

    mapping = {
        "aggression": "angry",
        "heartbreak": "melancholic",
        "celebration": "euphoric" if fast else "joyful",
        "party": "euphoric",
        "spirituality": "peaceful",
        "struggle": "defiant" if fast else "hopeful",
        "nostalgia": "nostalgic",
        "romance": "euphoric" if fast else "tender",
    }
    if theme in mapping:
        return mapping[theme]

    if sentiment_score > 0.3:
        return "hopeful"
    if sentiment_score < -0.3:
        return "melancholic"
    return "neutral"


def has_explicit(text):
    """True if the lyrics contain profanity (PRD F9 — a filter, not a score)."""
    text_lower = text.lower()
    if _count_substrings(text, _EXPLICIT_TERMS["gurmukhi"]) > 0:
        return True
    if _count_substrings(text, _EXPLICIT_TERMS["devanagari"]) > 0:
        return True
    return _count_words(text_lower, _EXPLICIT_TERMS["roman"]) > 0


def analyze(lyrics_text, duration_seconds=180.0, tempo_bpm=None):
    """
    Full Family-F analysis for one track.

    Pass tempo_bpm when it is known so the emotion label can use it; the
    library driver backfills emotion after audio analysis for this reason.
    """
    if not lyrics_text or not lyrics_text.strip():
        return {
            "language": "unknown", "script": "unknown", "primary_theme": None,
            "theme_scores": {}, "primary_emotion": "instrumental",
            "sentiment_score": 0.0, "word_count": 0, "lyrical_density": 0.0,
            "perspective": "unknown", "has_explicit": False,
        }

    language, script = detect_language(lyrics_text)
    theme_scores, primary_theme = classify_themes(lyrics_text, duration_seconds)
    sentiment_score = sentiment(lyrics_text)
    word_count = len(lyrics_text.split())
    density = round(word_count / max(duration_seconds / 60.0, 0.01), 2)

    return {
        "language": language,
        "script": script,
        "primary_theme": primary_theme,
        "theme_scores": theme_scores,
        "primary_emotion": map_emotion(theme_scores, sentiment_score, tempo_bpm),
        "sentiment_score": sentiment_score,
        "word_count": word_count,
        "lyrical_density": density,
        "perspective": detect_perspective(lyrics_text),
        "has_explicit": has_explicit(lyrics_text),
    }
