"""
Tests for the audio layer's pure logic.

The extraction pipeline itself needs audio files and is verified against the
real library; what is tested here is the part that can be wrong *silently* —
key detection and the bounded composite heuristics. A key detector that returns
a confident wrong key would poison the similarity engine without ever raising
an error, so it gets an explicit test with synthetic chroma vectors.

Run:  python -m thm.test_audio
"""

import math
import sys

from . import audio as A

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f"  — {detail}" if detail else ""))
    return condition


def chroma_for(tonic_index, mode="major", noise=0.0):
    """
    Build a chroma vector for a key by rotating the Krumhansl profile.

    Uses the profiles from a *different* source than the detector would be
    cheating; this reuses the same ones deliberately, because the question
    here is whether the rotation-and-correlate machinery picks the right
    rotation, not whether the profiles are empirically correct.
    """
    import random
    profile = A._KS_MAJOR if mode == "major" else A._KS_MINOR
    import numpy as np
    v = np.roll(profile, tonic_index).astype(float)
    if noise:
        rng = random.Random(tonic_index * 7 + len(mode))
        v = v + np.array([rng.uniform(-noise, noise) for _ in v])
    return v


def main():
    ok = True

    print("\n1. Key detection finds the right key from a clean chroma vector")
    for idx, (name, mode) in enumerate([
        (0, "major"), (9, "minor"), (7, "major"), (2, "minor"), (5, "major"),
    ]):
        tonic = [0, 9, 7, 2, 5][idx]
        v = chroma_for(tonic, mode)
        got_key, got_mode, conf = A.detect_key(v)
        expected = A._PITCH_NAMES[tonic]
        ok &= check(f"{expected} {mode}", got_key == expected and got_mode == mode,
                    f"got {got_key} {got_mode} (conf {conf})")

    print("\n2. Key detection survives realistic noise")
    for tonic, mode in [(0, "major"), (9, "minor"), (4, "major")]:
        v = chroma_for(tonic, mode, noise=1.5)
        got_key, got_mode, conf = A.detect_key(v)
        expected = A._PITCH_NAMES[tonic]
        ok &= check(f"{expected} {mode} with noise",
                    got_key == expected and got_mode == mode,
                    f"got {got_key} {got_mode} (conf {conf})")

    print("\n3. Ambiguous input must not report confidence")
    # A flat chroma vector carries no key information at all. After centring it
    # is all zeros, so every candidate correlation is undefined and the honest
    # answer is "unknown" — not a key with a low confidence attached.
    import numpy as np
    flat = A.detect_key(np.ones(12))
    ok &= check("flat chroma reports unknown key, not a guess",
                flat == (None, None, None), f"got {flat}")

    # A vector that is exactly between two keys should not be confident.
    mixed = chroma_for(0, "major") + chroma_for(6, "major")
    key_mixed, _, conf_mixed = A.detect_key(mixed)
    ok &= check("two-way ambiguous chroma gives low confidence",
                conf_mixed is not None and conf_mixed < 0.5,
                f"picked {key_mixed} conf={conf_mixed}")

    print("\n4. Key detection on degenerate input")
    ok &= check("empty vector returns None",
                A.detect_key([]) == (None, None, None))
    ok &= check("wrong-length vector returns None",
                A.detect_key([1.0, 2.0]) == (None, None, None))
    ok &= check("all-zero vector returns None",
                A.detect_key([0.0] * 12) == (None, None, None))

    print("\n5. Composite heuristics stay in 0..1 under extreme input")
    extremes = [
        ("silent", dict(mode="minor", tempo=0.0, centroid_hz=0.0)),
        ("deafening", dict(mode="major", tempo=300.0, centroid_hz=20000.0)),
    ]
    for label, kw in extremes:
        v = A._valence(**kw)
        ok &= check(f"_valence({label}) in range", 0.0 <= v <= 1.0, f"{v}")

    for label, kw in [
        ("silent", dict(rms_db=-120.0, onset_rate=0.0, tempo=0.0)),
        ("loud", dict(rms_db=0.0, onset_rate=50.0, tempo=300.0)),
    ]:
        v = A._arousal(**kw)
        ok &= check(f"_arousal({label}) in range", 0.0 <= v <= 1.0, f"{v}")

    for tempo in (0.0, 60.0, 120.0, 200.0, 400.0):
        v = A._danceability(0.8, tempo, 0.5)
        ok &= check(f"_danceability(tempo={tempo}) in range", 0.0 <= v <= 1.0,
                    f"{v}")

    print("\n6. Heuristics respond in the right direction")
    ok &= check("major reads brighter than minor",
                A._valence("major", 100.0, 2000.0)
                > A._valence("minor", 100.0, 2000.0))
    ok &= check("faster reads brighter than slower",
                A._valence("major", 150.0, 2000.0)
                > A._valence("major", 60.0, 2000.0))
    ok &= check("dance tempo beats a ballad tempo",
                A._danceability(0.6, 120.0, 0.4)
                > A._danceability(0.6, 50.0, 0.4))
    ok &= check("louder reads more aroused",
                A._arousal(-8.0, 2.0, 100.0) > A._arousal(-28.0, 2.0, 100.0))

    print("\n7. Vocal presence discriminates a vocal band from a bass band")
    import numpy as np
    freqs = np.linspace(0, 11025, 1025)
    # Energy concentrated in the vocal range vs. in the low end.
    vocal = np.zeros(1025)
    vocal[(freqs >= 300) & (freqs <= 3400)] = 1.0
    bass = np.zeros(1025)
    bass[(freqs >= 40) & (freqs <= 200)] = 1.0

    v_vocal = A._vocal_presence(vocal[:, None], freqs, (300.0, 3400.0))
    v_bass = A._vocal_presence(bass[:, None], freqs, (300.0, 3400.0))
    ok &= check("vocal-band energy scores higher than bass-band",
                v_vocal > v_bass, f"vocal={v_vocal} bass={v_bass}")
    ok &= check("bass-only scores near zero", v_bass < 0.1, f"{v_bass}")

    print("\n8. Vocal presence does not crash on an empty spectrum")
    ok &= check("all-zero spectrum returns 0",
                A._vocal_presence(np.zeros((1025, 1)), freqs,
                                  (300.0, 3400.0)) == 0.0)

    print("\n" + ("ALL PASS" if ok else "SOME FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
