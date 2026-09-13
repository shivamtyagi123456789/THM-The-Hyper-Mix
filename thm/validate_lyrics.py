"""
Validation sweep: run the lyrics engine over every .lrc sidecar in the library
and print a table for manual review.

This exists because the first sweep found two real bugs (see lyrics.py docstring)
and the only way to know the fixes worked is to look at the output.

Usage:  python -m thm.validate_lyrics [--music-dir DIR] [--verbose]
"""

import argparse
import sys
from pathlib import Path

from . import lyrics

# Windows consoles default to cp1252, which cannot encode Gurmukhi or
# Devanagari. Force UTF-8 on stdout so the table below doesn't die mid-run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_lrc(path):
    """Strip LRC timestamps ([00:12.34]) and metadata tags, return plain text."""
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        # Remove leading [mm:ss.xx] timestamps (a line may carry several).
        while line.startswith("["):
            close = line.find("]")
            if close == -1:
                break
            tag = line[1:close]
            # Skip ID tags like [ar:Artist]; keep the rest of the line.
            if ":" in tag and not tag.split(":")[0].isdigit():
                line = line[close + 1:].strip()
                break
            line = line[close + 1:].strip()
        if line and line != "\u266a":   # drop bare music-note markers
            out.append(line)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--music-dir", default=r"C:\Users\LENOVO\Music")
    ap.add_argument("--verbose", action="store_true",
                    help="print full theme score vectors")
    args = ap.parse_args()

    lrc_files = sorted(Path(args.music_dir).glob("*.lrc"))
    if not lrc_files:
        print(f"No .lrc files found in {args.music_dir}")
        return 1

    print(f"Validating {len(lrc_files)} lyric files\n")
    print(f"{'track':<44} {'lang':<10} {'script':<11} {'theme':<13} "
          f"{'emotion':<12} {'sent':>6} {'persp':<7} {'exp':<4}")
    print("-" * 122)

    unlabelled = []
    stats = {}

    for path in lrc_files:
        text = read_lrc(path)
        result = lyrics.analyze(text)

        name = path.stem[:42]
        if result["primary_theme"] is None:
            unlabelled.append((name, result["word_count"], result["script"]))

        key = result["primary_theme"]
        stats[key] = stats.get(key, 0) + 1

        print(f"{name:<44} {result['language']:<10} {result['script']:<11} "
              f"{str(result['primary_theme']):<13} "
              f"{result['primary_emotion']:<12} "
              f"{result['sentiment_score']:>6.2f} "
              f"{result['perspective']:<7} "
              f"{'yes' if result['has_explicit'] else '-':<4}")

        if args.verbose and result["theme_scores"]:
            print(f"    {result['theme_scores']}")

    print("-" * 122)
    print("\nTheme distribution:")
    for theme, count in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"  {str(theme):<14} {count:>3}")

    if unlabelled:
        print(f"\n{len(unlabelled)} track(s) got no theme label:")
        for name, wc, script in unlabelled:
            print(f"  {name:<44} words={wc:<5} script={script}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
