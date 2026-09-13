"""
Find vocabulary the theme lexicon is MISSING, by measuring the corpus.

Rather than guessing Hinglish words and hoping, this counts which Roman-script
tokens actually recur across the library and are not yet matched by any theme.
A word that appears in 20 of 77 tracks and belongs to no theme is either a
genuine gap or a stopword — both worth knowing.

This is the evidence-driven alternative to adding words by intuition, which is
how "tod" got into the aggression list and mislabelled HIGH ON YOU.

Usage:  python -m thm.suggest_terms [--min-docs 6] [--top 50]
"""

import argparse
import collections
import re
import sys
from pathlib import Path

from . import lyrics
from .validate_lyrics import read_lrc

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Romanised function words and vocalisations. These recur everywhere and
# carry no theme; listing them here keeps the report focused on content words.
STOPWORDS = set("""
a an the and or but if then than that this these those there here when where
why how what which who whom whose is are was were be been being am do does did
done doing have has had having will would shall should can could may might must
i me my mine we us our ours you your yours he him his she her hers it its they
them their theirs of in on at to for with from by about into over under again
further once all any both each few more most other some such no nor not only own
same so too very just now also get got go going gone come came coming make made
make take took taking give gave giving say said saying see saw seen know knew
known think thought tell told want wanted need needed like liked let lets up
down out off back still even well oh yeah ya yeh ye hai na ni nai nahi jo ke ki
ka ko se mein main hun ho hu hai to bhi tha thi the ne wo woh kya kyun kuch koi
aur par bas ab jab tab jaisa jaise jahan wahan bhi karke kar ke raha rahi rahe
lagta lagdi lagda kivein kiven jivein jiven saanu tainu mainu tenu mere tere
meri teri mera tera asi assi tusi ohi ehe uh eda oda jiddan kiddan vich te ton
da de di nu nal naal utte varga vargi wangu je ta vi tan hun fer phir hunda
hundi hunde hoyi hoya gaya gayi gae reh reha rehi rahiya aaya aayi aaye oye
oye ho oh ah eh mm ooo la laa ai ay
""".split())


def all_theme_terms():
    """Every term the lexicon already knows, across all scripts."""
    known = set()
    for lex in lyrics.THEME_LEXICON.values():
        for key, terms in lex.items():
            known.update(terms)
    return known


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--music-dir", default=r"C:\Users\LENOVO\Music")
    ap.add_argument("--min-docs", type=int, default=6,
                    help="only report tokens appearing in at least this many tracks")
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--script", default="latin",
                    choices=["latin", "all"],
                    help="restrict to Roman-script tracks (where the gap is)")
    args = ap.parse_args()

    known = all_theme_terms()
    doc_freq = collections.Counter()

    files = sorted(Path(args.music_dir).glob("*.lrc"))
    inspected = 0

    for path in files:
        text = read_lrc(path)
        language, script = lyrics.detect_language(text)
        if args.script == "latin" and script != "latin":
            continue
        inspected += 1

        tokens = set(re.findall(r"[a-z]{3,}", text.lower()))
        for tok in tokens:
            if tok in STOPWORDS or tok in known:
                continue
            doc_freq[tok] += 1

    print(f"Inspected {inspected} Roman-script tracks "
          f"({len(files)} files total)\n")
    print(f"Tokens appearing in >= {args.min_docs} tracks and matching "
          f"no theme term:\n")
    print(f"{'token':<18} {'tracks':>7}")
    print("-" * 28)

    shown = 0
    for tok, count in doc_freq.most_common():
        if count < args.min_docs:
            break
        print(f"{tok:<18} {count:>7}")
        shown += 1
        if shown >= args.top:
            break

    if shown == 0:
        print("(none — the lexicon covers the corpus vocabulary)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
