"""
Why-this-song — the Phase 1 validation gate.

Given a track, print its nearest neighbours with the per-dimension scores that
produced the ranking. This is the piece that makes the system auditable: if the
queue does something stupid, this says which dimension caused it, and the answer
is a number you can argue with rather than a black box.

It is also the acceptance test for Phase 1. The product's whole reason for
existing is that a love song must not be followed by a gangster song, so the
check is: pick a romantic track, read the top five, and confirm none of them is
thematically hostile.

Usage:
    python -m thm.explain --list-themes
    python -m thm.explain "one love"
    python -m thm.explain --id <track_id> --arc rising
    python -m thm.explain --random
    python -m thm.explain --validate          # run the Phase 1 acceptance gate
    python -m thm.explain "song" --why        # full per-dimension breakdown
"""

import argparse
import random
import sys

from . import db, similarity as S

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Dimensions shown in the compact view: the ones that actually decide a queue.
HEADLINE_DIMS = ["theme", "emotion", "tempo", "energy", "mfcc", "percussive",
                 "acoustic", "valence"]

# Themes that must never neighbour a romantic track, for the acceptance gate.
# Deliberately just the one: this asserts the PRD's specific failure (love song
# -> gangster song) and nothing broader, so the gate can actually pass.
#
# Retained for reference; the gate asserts on theme VECTORS now, not labels —
# see run_validation. A track with aggression=0.9 that argmax'd to `struggle`
# is a failure this set would have missed, and 7 such tracks exist here.
HOSTILE_TO_ROMANCE = {"aggression"}

# Gate thresholds, applied to the theme VECTOR rather than the argmax label.
# ROMANCE_BAR is deliberately high — an anchor must be unambiguously romantic,
# or the gate is asserting about a track whose own theme is contested.
ROMANCE_BAR = 0.5
HOSTILE_BAR = 0.5

# Fixed seed for held-out anchor sampling. The first version shuffled without
# one, so the held-out number moved between runs and could not be compared to
# anything — including a change you just made. A gate whose result is not
# reproducible is worse than no gate: it looks like evidence. The seed is
# chosen once and reported with the number.
DEFAULT_SEED = 20250913


def _find(library, needle):
    """Resolve a user-supplied name to track ids by substring match."""
    needle = needle.lower()
    hits = []
    for tid, tr in library.items():
        hay = f"{tr.get('title') or ''} {tr.get('artist') or ''} " \
              f"{tr.get('file_path') or ''}".lower()
        if needle in hay:
            hits.append(tid)
    return hits


def fmt_track(tr, width=44):
    title = (tr.get("title") or "?")[:width]
    artist = tr.get("artist") or "?"
    return f"{title:<{width}}  {artist[:22]}"


def show_ranking(library, anchor_id, args):
    anchor = library[anchor_id]
    results = S.rank_neighbours(
        library, anchor_id, limit=args.limit, arc=args.arc,
        respect_theme_lock=not args.no_lock,
        allow_explicit=not args.no_explicit,
        same_artist_penalty=0.0 if args.no_artist_penalty else 0.1,
    )

    print(f"\n{'=' * 78}")
    print(f"NOW PLAYING   {fmt_track(anchor)}")
    print(f"  theme={anchor.get('primary_theme')}  "
          f"emotion={anchor.get('primary_emotion')}  "
          f"tempo={anchor.get('tempo_bpm')}  "
          f"energy={anchor.get('energy_level')}")
    label = f"arc={args.arc}" if args.arc else "arc=steady"
    lock = "off" if args.no_lock else "on"
    print(f"  {label}  theme-lock={lock}  "
          f"explicit={'allowed' if not args.no_explicit else 'excluded'}")
    print(f"{'=' * 78}")

    if not results:
        print("\n  No candidates survived the filters. Either the library is "
              "tiny or the theme lock is too tight.")
        return 0

    for rank, r in enumerate(results, 1):
        print(f"\n  {rank}. {fmt_track(r)}")
        # Flag a tie-break only when the previous track actually scored the
        # same — otherwise "same language" on every row is noise, and the
        # reader stops seeing the one row where it decided something.
        tb = ""
        if rank > 1 and r["score"] == results[rank - 2]["score"] and r["tiebreak"]:
            tb = f"   [tied — {r['tiebreak']}]"
        print(f"     score {r['score']:.4f}   theme={r['theme']}  "
              f"emotion={r['emotion']}  tempo={r['tempo']}{tb}")

        contrib = r["contributions"]
        if args.why:
            print(f"     {'dimension':<18} {'sim':>6} {'weight':>7} {'impact':>8}")
            ordered = sorted(contrib.items(),
                             key=lambda kv: -kv[1]["contribution"])
            for name, c in ordered:
                print(f"     {name:<18} {c['sim']:>6.3f} {c['weight']:>7.2f} "
                      f"{c['contribution']:>8.3f}")
        else:
            parts = []
            for name in HEADLINE_DIMS:
                if name in contrib:
                    parts.append(f"{name}={contrib[name]['sim']:.2f}")
            print(f"     {'  '.join(parts)}")

    drift = S.theme_drift(anchor, results[0])
    if drift is not None:
        print(f"\n  theme drift to top pick: {drift:.3f} "
              f"(lock trips above {S.MAX_THEME_DRIFT})")
    return 0


def run_validation(library, limit=5, anchor_mode="vectors", n_random=20,
                   report_loss=True, seed=DEFAULT_SEED, lookahead=0):
    """
    Phase 1 acceptance gate.

    For every track the ENGINE ITSELF considers substantially romantic, check
    that no track it considers substantially aggressive appears in the top
    neighbours. This is the exact failure from the PRD ("a love song followed
    by a gangster song") expressed as a test.

    WHY THIS NO LONGER USES primary_theme (the circularity fix)
    -----------------------------------------------------------
    The first version selected anchors with `primary_theme in ("romance",
    "spirituality")` and flagged failures with `r["theme"] in ("aggression",)`
    — i.e. it chose and asserted with the same thresholded argmax label. A gate
    cannot discover that its own labels are wrong. Two measured facts show how
    much that cost:

      * "Angaar" is labelled `celebration` but its vector carries
        romance=0.8998 against celebration=1.0. The argmax decided the anchor
        membership on a near-tie.
      * 16 tracks carry an aggression component; only 9 are labelled
        `aggression`. The old hostile test would silently pass a track whose
        aggression is 0.9 but which argmax'd to something else.

    So both sides now use the THEME VECTOR — the same continuous quantity the
    engine compares — with an explicit bar. No argmax, no label round-trip.

    THIS GATE CAN STILL NOT PROVE THE ENGINE RIGHT
    ----------------------------------------------
    It is an internal consistency check: the engine's own claims about two
    tracks, checked against its own ranking. Closing the loop on real
    correctness needs a judgement the engine did not make — a held-out human
    label. `anchor_mode="random"` exists for exactly that: it samples anchors
    regardless of what the lexicon said, so the gate cannot select its own
    passing sample. The real bar is §5.2's held-out judgement; this is the
    strongest thing that can be automated before that exists.
    """
    print(f"\n{'=' * 78}")
    print("PHASE 1 ACCEPTANCE GATE  (v2 — vector anchors, not argmax labels)")
    print(f"{'=' * 78}")

    def vec(track):
        return track.get("theme_scores") or {}

    def comp(track, theme):
        return float(vec(track).get(theme, 0.0))

    if anchor_mode == "random":
        # Held-out: anchors chosen regardless of their labels, so the gate
        # cannot pick its own passing sample. Reported separately because a
        # random anchor has no assertion to make about it — the number here is
        # a loss rate, not a pass rate.
        pool = sorted(tid for tid in library
                      if (library[tid].get("energy_level") or 0) < 0.75)
        rng = random.Random(seed)
        anchors = [(tid, library[tid]) for tid in rng.sample(pool, n_random)]
        print(f"\n  HELD-OUT MODE: {len(anchors)} anchors sampled at random "
              f"from {len(pool)} tracks, ignoring their labels.")
        print(f"  seed {seed} — fixed, so this number is reproducible and "
              f"comparable\n")
    else:
        anchors = [(tid, tr) for tid, tr in library.items()
                   if comp(tr, "romance") >= ROMANCE_BAR
                   and (tr.get("energy_level") or 0) < 0.75]
        print(f"\n  {len(anchors)} anchors assert romance >= {ROMANCE_BAR} in "
              f"their theme vector (no argmax, no label round-trip)")

    if not anchors:
        print("\n  No anchors found. Analyse more tracks, or the lyric pass "
              "produced no theme vectors.")
        return 1

    contention = sum(1 for tr in library.values()
                     if comp(tr, "aggression") >= HOSTILE_BAR)
    print(f"  {contention} of {len(library)} tracks carry aggression >= "
          f"{HOSTILE_BAR} — these are what the gate is trying to keep away")
    print(f"  checking top {limit} each, theme lock ON\n")

    failures = []
    hostile_slots = 0
    unclass_slots = 0
    total_slots = 0
    # Held-out anchors do not all support the same assertion, and reporting one
    # number for all of them is how the first run of this produced a "45% loss"
    # that was mostly an artifact of applying a romance rule to a gangster song.
    judged = 0
    no_assertion = []
    self_aggressive = []
    inverse_leaks = []

    for tid, tr in anchors:
        results = S.rank_neighbours(library, tid, limit=limit,
                                    respect_theme_lock=True)
        bad = [r for r in results if comp(library[r["track_id"]],
                                          "aggression") >= HOSTILE_BAR]
        unc = [r for r in results
               if S.is_unclassified(library[r["track_id"]])]
        hostile_slots += len(bad)
        unclass_slots += len(unc)
        total_slots += len(results)

        anchor_hostile = comp(tr, "aggression") >= HOSTILE_BAR
        anchor_readable = bool(vec(tr))

        if not anchor_readable:
            # No theme vector: the engine has no claim about this track's mood,
            # so there is nothing for the queue to contradict. Not a pass and
            # not a failure — unjudgeable, and reported as such.
            status = "n/a"
            no_assertion.append((tr, results))
        elif anchor_hostile:
            # The anchor is itself aggressive. "No aggressive neighbour" is the
            # wrong claim here — aggressive neighbours are the correct answer.
            # The claim that DOES apply is the mirror image: it must not be
            # followed by a romantic track either. The lock is symmetric, so
            # this is a real consistency check, not a restatement.
            inverse = [r for r in results
                       if comp(library[r["track_id"]], "romance") >= ROMANCE_BAR]
            status = "ok " if not inverse else "BAD"
            self_aggressive.append((tr, inverse))
            if inverse:
                inverse_leaks.append((tr, inverse))
        else:
            status = "ok " if not bad else "BAD"
            judged += 1
            if bad:
                failures.append((tr, bad))

        top = ", ".join(
            (f"{library[r['track_id']].get('primary_theme') or 'none'}"
             f"/{comp(library[r['track_id']], 'aggression'):.2f}")
            for r in results)
        print(f"  [{status}] {(tr.get('title') or '?')[:40]:42} "
              f"rom={comp(tr, 'romance'):.2f}")
        print(f"        -> {top}")

    print(f"\n{'=' * 78}")
    print("  RESULT")
    print(f"{'=' * 78}")
    print(f"  anchors sampled        : {len(anchors)}")
    print(f"  unjudgeable (no theme) : {len(no_assertion)}   — the engine "
          f"makes no claim, so the queue cannot contradict one")
    print(f"  anchors themselves hostile : {len(self_aggressive)}   — checked "
          f"in the mirror: no romantic neighbour (leaks {len(inverse_leaks)})")
    print(f"  judged (assertion applies) : {judged}")
    if judged:
        clean = judged - len(failures)
        print(f"  anchors clean          : {clean}/{judged}"
              f"   (loss {100.0 * len(failures) / judged:.1f}% of judged)")
    if total_slots:
        print(f"  hostile in queue slots : {hostile_slots}/{total_slots}"
              f"   ({100.0 * hostile_slots / total_slots:.1f}%)")
        print(f"  unclassified in slots  : {unclass_slots}/{total_slots}"
              f"   ({100.0 * unclass_slots / total_slots:.1f}% — queue-"
              f"exhaustion signal, §5.2)")

    if failures:
        print("\n  FAILURES — an aggressive track reached a queue the engine "
              "does not call aggressive:")
        for tr, bad in failures:
            print(f"    {tr.get('title')}: "
                  + ", ".join(f"{b['title']} "
                              f"(agg={comp(library[b['track_id']], 'aggression'):.2f})"
                              for b in bad))
    if inverse_leaks:
        print("\n  INVERSE LEAKS — a romantic track reached a hostile anchor's "
              "queue (the lock should be symmetric):")
        for tr, inv in inverse_leaks:
            print(f"    {tr.get('title')}: "
                  + ", ".join(f"{b['title']} "
                              f"(rom={comp(library[b['track_id']], 'romance'):.2f})"
                              for b in inv))

    if not failures and not inverse_leaks:
        print("\n  No judged anchor was contradicted by its own queue.")
    if anchor_mode != "random":
        print("  Read with §5.2: this is internal consistency, not accuracy. "
              "Close the loop with --random-anchors.")
    return 1 if (failures or inverse_leaks) else 0


def list_themes(library):
    counts = {}
    for tr in library.values():
        key = tr.get("primary_theme") or "(none)"
        counts[key] = counts.get(key, 0) + 1

    print(f"\n  {len(library)} analysed tracks\n")
    for theme, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"    {theme:<16} {n}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?", help="substring of title/artist/path")
    ap.add_argument("--db", default="thm.db")
    ap.add_argument("--id", dest="track_id", help="exact track id")
    ap.add_argument("--random", action="store_true",
                    help="pick a random track as the anchor")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--arc", choices=sorted(S.ARC_PRESETS), default=None)
    ap.add_argument("--why", action="store_true",
                    help="full per-dimension breakdown")
    ap.add_argument("--no-lock", action="store_true",
                    help="disable the theme lock (to see what it excludes)")
    ap.add_argument("--no-explicit", action="store_true",
                    help="exclude explicit tracks")
    ap.add_argument("--list-themes", action="store_true")
    ap.add_argument("--validate", action="store_true",
                    help="run the Phase 1 acceptance gate")
    ap.add_argument("--random-anchors", action="store_true",
                    help="with --validate: sample anchors at random instead of "
                         "by their own labels (held-out mode, §5.2)")
    args = ap.parse_args()

    conn = db.connect(args.db)
    library = db.load_library(conn)

    if not library:
        print("No analysed tracks in the database yet.\n"
              "Run:  python -m thm.analyze_library")
        return 1

    if args.list_themes:
        return list_themes(library)
    if args.validate:
            lookahead=args.lookahead
        )

    if args.track_id:
        if args.track_id not in library:
            print(f"No track with id {args.track_id}")
            return 1
        return show_ranking(library, args.track_id, args)

    if args.random:
        return show_ranking(library, random.choice(list(library)), args)

    if not args.name:
        ap.error("give a track name, --id, --random, --list-themes or --validate")

    hits = _find(library, args.name)
    if not hits:
        print(f"No track matching {args.name!r}")
        return 1
    if len(hits) > 1:
        print(f"{len(hits)} tracks match {args.name!r}; showing the first:")
        for tid in hits[:10]:
            print(f"    {tid}  {fmt_track(library[tid])}")
        print()

    return show_ranking(library, hits[0], args)


if __name__ == "__main__":
    sys.exit(main())
        return run_validation(
            library, limit=args.limit,
            anchor_mode="random" if args.random_anchors else "vectors",
            seed=DEFAULT_SEED, lookahead=args.lookahead
            lookahead=args.lookahead
        )
