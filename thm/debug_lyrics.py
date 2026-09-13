"""
Explain WHY a track got its lyrical label, by printing the exact terms that
fired for each theme.

This is the whole reason the engine is a lexicon and not a transformer: when a
label is wrong, you can point at the words responsible and fix them. A neural
score would give you a number and no recourse.

Usage:  python -m thm.debug_lyrics "HIGH ON YOU"
        python -m thm.debug_lyrics --all-none     (every unlabelled track)
"""

import argparse
import re
import sys
from pathlib import Path

from . import lyrics
from .validate_lyrics import read_lrc

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def matched_terms(text, theme):
    """Return the terms that fired for a theme, with counts."""
    lex = lyrics.THEME_LEXICON[theme]
    text_lower = text.lower()
    hits = {}

    for term in lex["gurmukhi"]:
        c = text.count(term)
        if c:
            hits[term] = c
    for term in lex["devanagari"]:
        c = text.count(term)
        if c:
            hits[term] = c
    for term in lex["roman"]:
        c = len(re.findall(r"\b" + re.escape(term) + r"\b", text_lower))
        if c:
            hits[term] = c
    return hits


def explain(path, show_text=False):
    text = read_lrc(path)
    result = lyrics.analyze(text)
    words = max(len(text.split()), 1)

    print(f"\n{'=' * 78}")
    print(f"{path.stem}")
    print(f"{'=' * 78}")
    print(f"  words={words}  script={result['script']}  "
          f"theme={result['primary_theme']}  emotion={result['primary_emotion']}  "
          f"sentiment={result['sentiment_score']}")

    print("\n  Theme hits (absolute floor = "
          f"{lyrics.MIN_HITS} hits AND {lyrics.MIN_RATE}/100 words):")
    for theme in lyrics.THEME_LEXICON:
        hits = matched_terms(text, theme)
        total = sum(hits.values())
        rate = (total / words) * 100.0
        verdict = "PASS" if (total >= lyrics.MIN_HITS
                             and rate >= lyrics.MIN_RATE) else "----"
        if total:
            top = sorted(hits.items(), key=lambda kv: -kv[1])[:6]
            rendered = ", ".join(f"{t}:{c}" for t, c in top)
            print(f"    [{verdict}] {theme:<13} {total:>4} hits "
                  f"({rate:>5.2f}/100w)  {rendered}")
        else:
            print(f"    [{verdict}] {theme:<13}    0 hits")

    # Sentiment breakdown — the ±1.00 degeneracy shows up here.
    text_lower = text.lower()
    pos, neg = {}, {}
    for term in lyrics._POSITIVE["gurmukhi"]:
        if text.count(term):
            pos[term] = text.count(term)
    for term in lyrics._POSITIVE["devanagari"]:
        if text.count(term):
            pos[term] = text.count(term)
    for term in lyrics._POSITIVE["roman"]:
        c = len(re.findall(r"\b" + re.escape(term) + r"\b", text_lower))
        if c:
            pos[term] = c
    for term in lyrics._NEGATIVE["gurmukhi"]:
        if text.count(term):
            neg[term] = text.count(term)
    for term in lyrics._NEGATIVE["devanagari"]:
        if text.count(term):
            neg[term] = text.count(term)
    for term in lyrics._NEGATIVE["roman"]:
        c = len(re.findall(r"\b" + re.escape(term) + r"\b", text_lower))
        if c:
            neg[term] = c

    print(f"\n  Sentiment: {sum(pos.values())} positive vs "
          f"{sum(neg.values())} negative")
    print(f"    pos: {pos}")
    print(f"    neg: {neg}")

    if show_text:
        print(f"\n  --- first 400 chars ---\n{text[:400]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?", help="substring of the track filename")
    ap.add_argument("--all-none", action="store_true",
                    help="explain every track that got no theme label")
    ap.add_argument("--music-dir", default=r"C:\Users\LENOVO\Music")
    ap.add_argument("--text", action="store_true", help="also dump lyric text")
    args = ap.parse_args()

    files = sorted(Path(args.music_dir).glob("*.lrc"))

    if args.all_none:
        for path in files:
            result = lyrics.analyze(read_lrc(path))
            if result["primary_theme"] is None:
                explain(path, args.text)
        return 0

    if not args.name:
        ap.error("give a track name substring or --all-none")

    needle = args.name.lower()
    matches = [p for p in files if needle in p.stem.lower()]
    if not matches:
        print(f"No .lrc matching {args.name!r}")
        return 1

    for path in matches:
        explain(path, args.text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
