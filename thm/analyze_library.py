"""
Batch library analysis — the CLI that populates thm.db.

Scans a music folder, and for each track:
  1. reads identity from the file's tags (mutagen)
  2. reads the .lrc lyric sidecar, if present
  3. extracts audio features (audio.py)
  4. classifies the lyrics (lyrics.py)
  5. writes all three rows to SQLite (db.py)

RESUMABLE BY DESIGN
-------------------
Audio analysis takes roughly a minute per track, so a 93-track library is a
long run and WILL be interrupted. `analysis_status='analyzed'` is the
checkpoint: re-running skips finished tracks. Pass --force to redo them.

The lyrics pass writes primary_emotion from text alone, which cannot use tempo.
After the audio pass every track has a tempo, so this driver backfills emotion
for tracks whose emotion was decided without one — see lyrics.analyze's note on
why that matters.

Usage:
    python -m thm.analyze_library                    # analyse everything new
    python -m thm.analyze_library --limit 5          # just try five
    python -m thm.analyze_library --force            # redo everything
    python -m thm.analyze_library --audio-only       # skip the lyric pass
    python -m thm.analyze_library --status           # report DB state, no work
"""

import argparse
import sys
import time
import traceback
from pathlib import Path

from . import audio, db, lyrics

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus"}


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def read_tags(path):
    """
    Pull title/artist/album/duration from the file's tags.

    Falls back to the filename for the title, because an untagged file is
    better labelled with its own name than with NULL — the explanations the
    user reads are built from these strings.
    """
    title = artist = album = None
    duration = None
    try:
        import mutagen
        mf = mutagen.File(str(path), easy=True)
        if mf is not None:
            def first(key):
                v = mf.get(key)
                return str(v[0]).strip() if v else None

            title = first("title")
            artist = first("artist")
            album = first("album")
            if getattr(mf, "info", None) is not None:
                duration = getattr(mf.info, "length", None)
    except Exception:
        pass   # untagged or exotic file — filename fallback below

    if not title:
        title = path.stem
    return title, artist, album, duration


def find_lyrics(path):
    """
    Locate the .lrc sidecar for an audio file, or return None.

    This library's sidecars are named "<song>_private.lrc" — the lyrics tool
    that produced them appends that suffix — so matching only "<song>.lrc"
    finds 1 file out of 93. Both spellings are tried, in order of exactness.
    """
    for candidate in (
        path.with_suffix(".lrc"),
        path.parent / f"{path.stem}_private.lrc",
    ):
        if candidate.exists():
            return candidate
    return None


def read_lrc(path):
    """Read an .lrc file, stripping timestamps and ID tags."""
    import re
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    raw = re.sub(r"\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]", " ", raw)   # [01:23.45]
    raw = re.sub(r"\[[a-zA-Z]+:[^\]]*\]", " ", raw)                # [ar: ...]
    return raw.replace("♪", " ").strip()


# ---------------------------------------------------------------------------
# Per-track work
# ---------------------------------------------------------------------------

def analyze_one(conn, path, force=False, audio_only=False):
    """
    Analyse a single track end to end and persist it.

    Returns one of: 'skipped', 'ok', 'failed'.
    """
    file_path = str(path.resolve())

    row = conn.execute(
        "SELECT track_id, analysis_status FROM tracks WHERE file_path = ?",
        (file_path,),
    ).fetchone()

    if row and row["analysis_status"] == "analyzed" and not force:
        return "skipped"
    if row and row["analysis_status"] == "failed" and not force:
        # Do not silently retry files that already blew up; --force is the
        # explicit way to try again, so a persistent failure isn't retried
        # on every run.
        return "skipped"

    title, artist, album, tag_duration = read_tags(path)
    lyric_path = find_lyrics(path)

    try:
        feats = audio.extract_features(path)
    except Exception as exc:
        print(f"      audio failed: {type(exc).__name__}: {exc}")
        if row:
            conn.execute("UPDATE tracks SET analysis_status='failed' "
                         "WHERE track_id=?", (row["track_id"],))
            conn.commit()
        return "failed"

    duration = tag_duration
    if duration is None:
        duration = feats.get("_duration")

    track_id = db.upsert_track(
        conn, file_path, title, artist, album, duration,
        path.suffix.lower().lstrip("."),
        lyrics_source=str(lyric_path.name) if lyric_path else None,
    )
    db.save_features(conn, track_id, feats)

    if audio_only:
        return "ok"

    lyr = {
        "language": None, "script": None, "primary_theme": None,
        "theme_scores": {}, "primary_emotion": None, "sentiment_score": None,
        "word_count": 0, "lyrical_density": 0.0, "perspective": "unknown",
        "has_explicit": False, "lyrics_source": None,
    }
    if lyric_path:
        text = read_lrc(lyric_path)
        if text:
            mins = (duration or 180.0) / 60.0
            lyr = lyrics.analyze(text, duration_seconds=duration or 180.0,
                                 tempo_bpm=feats.get("tempo_bpm"))
            lyr["lyrics_source"] = lyric_path.name

    db.save_lyrical(conn, track_id, lyr)
    return "ok"


def relyric(conn):
    """
    Re-run ONLY the lyric pass over tracks that already have audio features.

    Exists because the two halves of analysis change at completely different
    rates. The audio pass costs ~13s per track of DSP and has not changed since
    the HPSS work; the lexicon is edited often and costs nothing to re-run.
    Forcing the whole analyser to redo 93 tracks to pick up a lexicon change
    would spend ~20 minutes re-deriving identical numbers.

    Tempo and duration come from the DB, which is exactly what the original
    lyric pass received — `lyrics.map_emotion` reads tempo, and density divides
    by duration, so both must be the same values or the output differs for a
    reason unrelated to the lexicon.
    """
    rows = conn.execute(
        """SELECT t.track_id, t.file_path, t.duration, f.tempo_bpm
             FROM tracks t
             LEFT JOIN features f ON f.track_id = t.track_id
             LEFT JOIN lyrical  l ON l.track_id = t.track_id
            WHERE t.analysis_status = 'analyzed'""",
    ).fetchall()

    updated = 0
    for row in rows:
        path = Path(row["file_path"])
        lyric_path = find_lyrics(path)
        if not lyric_path:
            continue
        text = read_lrc(lyric_path)
        if not text:
            continue
        duration = row["duration"] or 180.0
        lyr = lyrics.analyze(text, duration_seconds=duration,
                             tempo_bpm=row["tempo_bpm"])
        lyr["lyrics_source"] = lyric_path.name
        db.save_lyrical(conn, row["track_id"], lyr)
        updated += 1
    return updated


def backfill_emotions(conn):
    """
    Re-derive primary_emotion using tempo, now that audio analysis has run.

    The lyric pass runs before (or without) audio in the general case, and
    lyrics.map_emotion reads tempo when it is available — a fast breakup song
    and a slow one are not the same emotion. Any track analysed without a tempo
    gets a second, better-informed pass here. Cheap: no audio decoding.
    """
    rows = conn.execute(
        """SELECT t.track_id, t.file_path, t.duration, f.tempo_bpm,
                  l.theme_scores, l.sentiment_score, l.primary_emotion
           FROM tracks t
           JOIN lyrical l  ON l.track_id = t.track_id
           JOIN features f ON f.track_id = t.track_id
           WHERE t.analysis_status = 'analyzed'"""
    ).fetchall()

    changed = 0
    for row in rows:
        lyric_path = find_lyrics(Path(row["file_path"]))
        if not lyric_path:
            continue
        text = read_lrc(lyric_path)
        if not text:
            continue

        import json
        raw = row["theme_scores"]
        scores = json.loads(raw) if raw else {}
        sent = row["sentiment_score"] if row["sentiment_score"] is not None else 0.0
        updated = lyrics.map_emotion(scores, sent, tempo_bpm=row["tempo_bpm"])

        if updated != row["primary_emotion"]:
            conn.execute("UPDATE lyrical SET primary_emotion=? WHERE track_id=?",
                         (updated, row["track_id"]))
            changed += 1
    conn.commit()
    return changed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def report_status(conn):
    total = conn.execute("SELECT COUNT(*) c FROM tracks").fetchone()["c"]
    by_status = conn.execute(
        "SELECT analysis_status, COUNT(*) c FROM tracks GROUP BY analysis_status"
    ).fetchall()
    feats = conn.execute("SELECT COUNT(*) c FROM features").fetchone()["c"]
    lyr = conn.execute("SELECT COUNT(*) c FROM lyrical").fetchone()["c"]
    with_lyrics = conn.execute(
        "SELECT COUNT(*) c FROM lyrical WHERE theme_scores != '{}'"
    ).fetchone()["c"]

    print(f"  tracks in DB     : {total}")
    for r in by_status:
        print(f"    {r['analysis_status']:<12} {r['c']}")
    print(f"  feature rows     : {feats}")
    print(f"  lyric rows       : {lyr}  ({with_lyrics} with a theme)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--music-dir", default=r"C:\Users\LENOVO\Music")
    ap.add_argument("--db", default="thm.db")
    ap.add_argument("--limit", type=int, default=0, help="stop after N tracks")
    ap.add_argument("--force", action="store_true", help="redo analysed tracks")
    ap.add_argument("--audio-only", action="store_true",
                    help="skip the lyric pass")
    ap.add_argument("--lyrics-only", action="store_true",
                    help="re-run only the lyric pass over already-analysed "
                         "tracks (use after a lexicon change)")
    ap.add_argument("--status", action="store_true",
                    help="report state and exit without analysing")
    args = ap.parse_args()

    conn = db.connect(args.db)

    if args.status:
        return report_status(conn)

    if args.lyrics_only:
        n = relyric(conn)
        changed = backfill_emotions(conn)
        print(f"  re-scored lyrics for {n} tracks")
        print(f"  emotion backfill updated {changed} tracks\n")
        report_status(conn)
        return 0

    music_dir = Path(args.music_dir)
    if not music_dir.is_dir():
        print(f"Not a directory: {music_dir}")
        return 1

    files = sorted(p for p in music_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)
    if not files:
        print(f"No audio files in {music_dir}")
        return 1

    print(f"Found {len(files)} audio files in {music_dir}")
    print(f"Database: {Path(args.db).resolve()}\n")

    counts = {"ok": 0, "skipped": 0, "failed": 0}
    started = time.time()

    for i, path in enumerate(files, 1):
        if args.limit and counts["ok"] >= args.limit:
            break

        name = path.stem[:58]
        print(f"  [{i}/{len(files)}] {name}")

        t0 = time.time()
        try:
            result = analyze_one(conn, path, force=args.force,
                                 audio_only=args.audio_only)
        except KeyboardInterrupt:
            print("\n  interrupted — progress is saved, re-run to resume")
            break
        except Exception:
            print("      unexpected failure:")
            traceback.print_exc(limit=2)
            result = "failed"

        counts[result] += 1
        if result == "ok":
            print(f"      done in {time.time() - t0:.1f}s")
        elif result == "skipped":
            print("      already analysed (--force to redo)")

    elapsed = time.time() - started
    print(f"\n  analysed {counts['ok']}  skipped {counts['skipped']}  "
          f"failed {counts['failed']}  in {elapsed / 60:.1f} min")

    if not args.audio_only:
        changed = backfill_emotions(conn)
        print(f"  emotion backfill updated {changed} tracks")

    print()
    report_status(conn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
