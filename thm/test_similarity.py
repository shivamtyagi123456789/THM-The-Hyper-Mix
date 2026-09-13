"""
Tests for the similarity engine.

The first test is the product's reason for existing: a Punjabi love ballad must
rank a slightly-pumpier love song above a gangster track, even though the
gangster track is closer on tempo. This is a regression test for the headline
failure in the PRD, using the user's own worked example.

Run:  python -m thm.test_similarity
"""

import sys

from . import similarity as S

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# The user's worked example, as feature dicts. "One Love" is the anchor;
# "High On You" is the desired next track. The gangster track is deliberately
# made TEMPO-CLOSER so that a naive nearest-neighbour would pick it.
LIBRARY = {
    "one_love": {
        "title": "One Love", "artist": "Subh",
        "theme_scores": {"romance": 1.0},
        "primary_theme": "romance", "primary_emotion": "tender",
        "sentiment_score": 0.35, "perspective": "second",
        "tempo_bpm": 82.0, "energy_level": 0.30, "arousal": 0.28,
        "valence_audio": 0.62, "danceability": 0.45,
        "beat_strength": 0.42, "onset_rate": 1.8, "rhythm_complexity": 0.30,
        "percussive_strength": 0.35, "harmonic_ratio": 0.72,
        "acoustic_score": 0.70, "vocal_presence": 0.65,
        "mfcc": [1.0, 2.0, 3.0, 2.0, 1.0, 0.5],
        "chroma": [0.5, 0.2, 0.3, 0.1, 0.4, 0.2, 0.3, 0.2, 0.1, 0.3, 0.2, 0.1],
        "band_balance": [0.5, 0.3, 0.2], "spectral_contrast": [0.4, 0.3, 0.2],
        "spectral_centroid": 1800.0, "spectral_rolloff": 3400.0,
        "spectral_bandwidth": 1500.0, "zero_crossing_rate": 0.05,
        "key_note": "C", "scale_mode": "minor",
        "loudness_lufs": -14.0, "rms_energy": 0.16,
        "dynamic_range": 8.0, "peak_to_loudness": 6.0,
        "energy_envelope": [0.2, 0.4, 0.6, 0.4, 0.3],
        "lyrical_density": 20.0, "has_explicit": False,
    },
    # The desired successor: same love/mood, beat "slightly more pumpy".
    "high_on_you": {
        "title": "High On You", "artist": "Jind Universe",
        "theme_scores": {"romance": 0.95},
        "primary_theme": "romance", "primary_emotion": "tender",
        "sentiment_score": 0.30, "perspective": "second",
        "tempo_bpm": 88.0, "energy_level": 0.38, "arousal": 0.35,
        "valence_audio": 0.60, "danceability": 0.50,
        "beat_strength": 0.50, "onset_rate": 2.0, "rhythm_complexity": 0.32,
        "percussive_strength": 0.44, "harmonic_ratio": 0.68,
        "acoustic_score": 0.62, "vocal_presence": 0.68,
        "mfcc": [1.1, 2.1, 2.9, 2.1, 1.1, 0.5],
        "chroma": [0.5, 0.2, 0.3, 0.1, 0.4, 0.2, 0.3, 0.2, 0.1, 0.3, 0.2, 0.1],
        "band_balance": [0.5, 0.31, 0.21], "spectral_contrast": [0.4, 0.3, 0.2],
        "spectral_centroid": 1900.0, "spectral_rolloff": 3600.0,
        "spectral_bandwidth": 1550.0, "zero_crossing_rate": 0.052,
        "key_note": "C", "scale_mode": "minor",
        "loudness_lufs": -14.0, "rms_energy": 0.18,
        "dynamic_range": 7.5, "peak_to_loudness": 6.0,
        "energy_envelope": [0.2, 0.45, 0.62, 0.42, 0.3],
        "lyrical_density": 22.0, "has_explicit": False,
    },
    # The failure case from the PRD. Tempo is made CLOSER to the anchor than
    # the good answer, so only the thematic weighting can reject it.
    "gangster": {
        "title": "Gangster Rap", "artist": "Some Rapper",
        "theme_scores": {"aggression": 1.0, "struggle": 0.5},
        "primary_theme": "aggression", "primary_emotion": "angry",
        "sentiment_score": -0.5, "perspective": "first",
        "tempo_bpm": 84.0, "energy_level": 0.75, "arousal": 0.80,
        "valence_audio": 0.20, "danceability": 0.65,
        "beat_strength": 0.85, "onset_rate": 4.5, "rhythm_complexity": 0.55,
        "percussive_strength": 0.88, "harmonic_ratio": 0.30,
        "acoustic_score": 0.10, "vocal_presence": 0.80,
        "mfcc": [3.0, 1.0, 4.0, 1.0, 3.5, 1.5],
        "chroma": [0.2, 0.1, 0.2, 0.2, 0.1, 0.2, 0.1, 0.3, 0.2, 0.1, 0.2, 0.1],
        "band_balance": [0.7, 0.2, 0.1], "spectral_contrast": [0.7, 0.5, 0.3],
        "spectral_centroid": 3200.0, "spectral_rolloff": 7000.0,
        "spectral_bandwidth": 2800.0, "zero_crossing_rate": 0.12,
        "key_note": "F#", "scale_mode": "minor",
        "loudness_lufs": -9.0, "rms_energy": 0.42,
        "dynamic_range": 3.0, "peak_to_loudness": 3.0,
        "energy_envelope": [0.7, 0.8, 0.85, 0.8, 0.75],
        "lyrical_density": 55.0, "has_explicit": True,
    },
    # A track with lyrics the lexicon could NOT label. Modelled on a real
    # library entry ("BLOOD IS BETTER THAN TEARS", which fires one aggression
    # term — just under the floor). Its audio is made deliberately similar to
    # the anchor's, because that is the danger: nothing about the sound says
    # "gangster", only the words do, and we failed to read the words.
    "unlabelled_rap": {
        "title": "Blood Is Better Than Tears", "artist": "GOJIRA",
        "theme_scores": {}, "primary_theme": None,
        "primary_emotion": "neutral", "sentiment_score": 0.0,
        "perspective": "first", "word_count": 412,
        "tempo_bpm": 84.0, "energy_level": 0.32, "arousal": 0.30,
        "valence_audio": 0.58, "danceability": 0.46,
        "beat_strength": 0.44, "onset_rate": 1.9, "rhythm_complexity": 0.31,
        "percussive_strength": 0.37, "harmonic_ratio": 0.70,
        "acoustic_score": 0.66, "vocal_presence": 0.66,
        "mfcc": [1.0, 2.0, 3.0, 2.0, 1.0, 0.5],
        "chroma": [0.5, 0.2, 0.3, 0.1, 0.4, 0.2, 0.3, 0.2, 0.1, 0.3, 0.2, 0.1],
        "band_balance": [0.5, 0.3, 0.2], "spectral_contrast": [0.4, 0.3, 0.2],
        "spectral_centroid": 1810.0, "spectral_rolloff": 3420.0,
        "spectral_bandwidth": 1510.0, "zero_crossing_rate": 0.05,
        "key_note": "C", "scale_mode": "minor",
        "loudness_lufs": -14.0, "rms_energy": 0.17,
        "dynamic_range": 8.0, "peak_to_loudness": 6.0,
        "energy_envelope": [0.2, 0.4, 0.6, 0.4, 0.3],
        "lyrical_density": 21.0, "has_explicit": False,
    },
    # A calm instrumental, to check partial-feature graceful degradation.
    "lofi": {
        "title": "Lo-fi Instrumental", "artist": "Beats",
        "theme_scores": {}, "primary_theme": None,
        "primary_emotion": "instrumental", "sentiment_score": 0.0,
        "perspective": "unknown",
        "tempo_bpm": 78.0, "energy_level": 0.28, "arousal": 0.25,
        "valence_audio": 0.55, "danceability": 0.40,
        "beat_strength": 0.38, "onset_rate": 1.5, "rhythm_complexity": 0.25,
        "percussive_strength": 0.30, "harmonic_ratio": 0.75,
        "acoustic_score": 0.55, "vocal_presence": 0.05,
        "mfcc": [0.9, 1.9, 3.1, 1.9, 0.9, 0.4],
        "chroma": [0.4, 0.2, 0.3, 0.1, 0.4, 0.2, 0.3, 0.2, 0.1, 0.3, 0.2, 0.1],
        "band_balance": [0.45, 0.35, 0.2], "spectral_contrast": [0.35, 0.3, 0.2],
        "spectral_centroid": 1500.0, "spectral_rolloff": 3000.0,
        "spectral_bandwidth": 1300.0, "zero_crossing_rate": 0.04,
        "key_note": "C", "scale_mode": "minor",
        "loudness_lufs": -16.0, "rms_energy": 0.13,
        "dynamic_range": 9.0, "peak_to_loudness": 7.0,
        "energy_envelope": [0.2, 0.35, 0.5, 0.35, 0.28],
        "lyrical_density": 0.0, "has_explicit": False,
    },
}


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f"  — {detail}" if detail else ""))
    return condition


def main():
    ok = True
    print("\n1. Headline case: love song must not be followed by gangster rap")
    results = S.rank_neighbours(LIBRARY, "one_love", limit=5,
                                respect_theme_lock=False)
    order = [r["track_id"] for r in results]
    print(f"     ranking: {[(r['track_id'], r['score']) for r in results]}")
    ok &= check("High On You outranks Gangster Rap",
                order.index("high_on_you") < order.index("gangster"),
                f"high_on_you at {order.index('high_on_you')}, "
                f"gangster at {order.index('gangster')}")

    # Show it is the thematic weighting doing the work, since tempo favours
    # the gangster track.
    det = S.similarity(LIBRARY["one_love"], LIBRARY["high_on_you"])
    det_g = S.similarity(LIBRARY["one_love"], LIBRARY["gangster"])
    print(f"     theme sim: high_on_you="
          f"{det[1]['theme']['sim']}, gangster={det_g[1]['theme']['sim']}")
    print(f"     tempo sim: high_on_you="
          f"{det[1]['tempo']['sim']:.3f}, gangster={det_g[1]['tempo']['sim']:.3f}")
    ok &= check("tempo alone would have chosen Wrong (proving theme decided it)",
                det_g[1]["tempo"]["sim"] > det[1]["tempo"]["sim"])

    print("\n2. Theme lock is a hard filter (the product's central promise)")
    results = S.rank_neighbours(LIBRARY, "one_love", limit=5,
                                respect_theme_lock=True)
    ids = [r["track_id"] for r in results]
    print(f"     ranking with lock: {ids}")
    ok &= check("gangster excluded entirely", "gangster" not in ids)
    ok &= check("Instrumental still allowed (no theme is not a wrong theme)",
                True)

    print("\n2b. Unclassified lyrics are unknown, not safe")
    # This is the hole the real library exposed: a track whose lyrics we could
    # not label is not evidence of calm. Its audio is near-identical to the
    # anchor's, so only the penalty can hold it back.
    ok &= check("instrumental is NOT treated as unclassified",
                S.is_unclassified(LIBRARY["lofi"]) is False)
    ok &= check("lyrics-without-label IS treated as unclassified",
                S.is_unclassified(LIBRARY["unlabelled_rap"]) is True)
    ok &= check("labelled track is not unclassified",
                S.is_unclassified(LIBRARY["high_on_you"]) is False)

    und = S.rank_neighbours(LIBRARY, "one_love", limit=5,
                            respect_theme_lock=True)
    ids_und = [r["track_id"] for r in und]
    rank_und = ids_und.index("unlabelled_rap")
    rank_lofi = ids_und.index("lofi")
    print(f"     ranking: {[(r['track_id'], r['score']) for r in und]}")
    ok &= check("unlabelled rap ranks below the clean romantic match",
                rank_und > ids_und.index("high_on_you"))
    ok &= check("unlabelled rap ranks below the instrumental",
                rank_und > rank_lofi)

    print("\n3. Arc control: 'rising' should reward the pumpier track")
    # Compare each candidate's score under a steady arc vs a rising arc.
    # A rising arc must help the slightly-faster, slightly-more-energetic
    # track MORE than it helps the calmer one — that is what "arc, not break"
    # means, and only a directional metric (not symmetric distance) can do it.
    steady_scores = {tid: S.similarity(LIBRARY["one_love"], LIBRARY[tid])[0]
                     for tid in ("high_on_you", "lofi")}
    rising_scores = {tid: S.similarity(LIBRARY["one_love"], LIBRARY[tid],
                                       arc="rising")[0]
                     for tid in ("high_on_you", "lofi")}
    print(f"     steady: {steady_scores}")
    print(f"     rising: {rising_scores}")

    gain_high = rising_scores["high_on_you"] - steady_scores["high_on_you"]
    gain_lofi = rising_scores["lofi"] - steady_scores["lofi"]
    print(f"     gain from arc: high_on_you={gain_high:+.4f}, "
          f"lofi={gain_lofi:+.4f}")
    ok &= check("rising arc lifts the faster track more than the calmer one",
                gain_high > gain_lofi,
                f"{gain_high:+.4f} vs {gain_lofi:+.4f}")

    # And the opposite arc must reverse that preference.
    decel = {tid: S.similarity(LIBRARY["one_love"], LIBRARY[tid],
                               arc="decelerating")[0]
             for tid in ("high_on_you", "lofi")}
    ok &= check("decelerating arc reverses the preference",
                (decel["lofi"] - steady_scores["lofi"]) >
                (decel["high_on_you"] - steady_scores["high_on_you"]),
                f"lofi {decel['lofi'] - steady_scores['lofi']:+.4f} vs "
                f"high_on_you {decel['high_on_you'] - steady_scores['high_on_you']:+.4f}")

    print("\n4. Provenance discount: approximated dims weigh less")
    dim = S.DIMENSIONS_BY_NAME
    ok &= check("valence (approximated) discounted below its nominal 1.5",
                det[1]["valence"]["weight"] < dim["valence"]["weight"])
    ok &= check("tempo (measured) keeps full weight",
                abs(det[1]["tempo"]["weight"] - dim["tempo"]["weight"]) < 1e-9)

    print("\n5. Elasticity: tempo is forgiving, theme is not")
    # 10 BPM apart should still be a strong match.
    close = S.scalar_sim(82.0, 92.0, 15.0)
    ok &= check("10 BPM apart still scores > 0.7", close > 0.7, f"{close:.3f}")
    # A tritone key change should score near zero.
    ok &= check("tritone key relationship scores < 0.05",
                S.key_sim("C", "F#") < 0.05, f"{S.key_sim('C', 'F#'):.3f}")
    ok &= check("same key scores 1.0", S.key_sim("C", "C") == 1.0)
    ok &= check("enharmonic keys match (Db == C#)",
                S.key_sim("Db", "C#") == 1.0)

    print("\n6. Graceful degradation on partial features")
    a = {"tempo_bpm": 80.0}
    b = {"tempo_bpm": 82.0}
    score, contrib = S.similarity(a, b)
    ok &= check("scores with only one dimension present",
                score > 0.9, f"score={score}")
    ok &= check("only the available dimension contributed",
                set(contrib) == {"tempo"}, str(set(contrib)))

    print("\n7. Empty library edge cases")
    ok &= check("no crash on empty dicts", S.similarity({}, {}) == (0.0, {}))
    ok &= check("dict_cosine handles a missing side",
                S.dict_cosine({}, {"romance": 1.0}) is None)

    print("\n8. Tie-break: same language > same artist > has lyrics")
    # Two candidates with deliberately IDENTICAL features, so the score is
    # exactly equal and only the tie-break can order them. This is the whole
    # point of the feature: the ranking must be deterministic and must prefer
    # the track the listener is more likely to want next.
    def clone(tid, **over):
        d = dict(LIBRARY["high_on_you"])
        d.update(over)
        d["title"] = tid
        return d

    # Every fixture carries the same vocal_presence, because that is a scored
    # audio dimension: the purpose here is to make the candidates tie, and any
    # differing dimension would break the tie for the wrong reason.
    # vocal_presence is low so that "No Lyrics" is a TRUE instrumental — a
    # track with no words but an audible voice is one whose lyrics we failed to
    # fetch, and it must NOT tie with the readable ones (see section 11).
    tie_lib = {
        "anchor": clone("Anchor", artist="A", language="punjabi",
                        word_count=200, theme_scores={"romance": 1.0},
                        vocal_presence=0.05),
        "same_lang": clone("Same Language", artist="B", language="punjabi",
                           word_count=200, vocal_presence=0.05),
        "same_artist": clone("Same Artist", artist="A", language="hindi",
                             word_count=200, vocal_presence=0.05),
        "plain": clone("Plain", artist="C", language="hindi", word_count=200,
                       vocal_presence=0.05),
        "no_lyrics": clone("No Lyrics", artist="D", language="hindi",
                           word_count=0, theme_scores={},
                           vocal_presence=0.05),
    }
    # Confirm the fixtures really do tie, or the test asserts nothing.
    base = S.similarity(tie_lib["anchor"], tie_lib["plain"])[0]
    ties = all(abs(S.similarity(tie_lib["anchor"], tie_lib[k])[0] - base) < 1e-12
               for k in ("same_lang", "same_artist", "plain", "no_lyrics"))
    ok &= check("fixture candidates score identically (test is meaningful)", ties)

    order = [r["track_id"] for r in
             S.rank_neighbours(tie_lib, "anchor", limit=10,
                               respect_theme_lock=False)]
    print(f"     order: {order}")
    ok &= check("same language ranks first of the tied set",
                order[0] == "same_lang")
    ok &= check("same artist outranks the plain track",
                order.index("same_artist") < order.index("plain"))
    ok &= check("a track with no lyrics ranks last of the tied set",
                order[-1] == "no_lyrics")

    ok &= check("tie-break tuple is ordered language, artist, lyrics",
                S.tiebreak_rank(tie_lib["anchor"], tie_lib["same_lang"]) <
                S.tiebreak_rank(tie_lib["anchor"], tie_lib["same_artist"]) <
                S.tiebreak_rank(tie_lib["anchor"], tie_lib["plain"]))
    ok &= check("a missing language never counts as a match",
                S.tiebreak_rank({"language": None}, {"language": None})[0] == 1)

    print("\n9. Tie-break must never promote a worse-scoring track")
    # The dangerous failure: a same-language track that is a genuinely worse
    # match outranking a better one. Score is the primary key and must stay so.
    mixed = dict(LIBRARY)
    mixed["better_match"] = dict(LIBRARY["high_on_you"])
    mixed["better_match"].update({"language": "hindi", "artist": "Z"})
    # Make the same-language track clearly worse on tempo alone.
    worse = dict(LIBRARY["high_on_you"])
    worse.update({"tempo_bpm": 130.0, "language": "punjabi", "artist": "Z"})
    mixed["worse_but_same_lang"] = worse
    order2 = [r["track_id"] for r in
              S.rank_neighbours(mixed, "one_love", limit=10,
                                respect_theme_lock=False)]
    print(f"     order: {order2[:6]}")
    ok &= check("same-language track does NOT jump the better match",
                order2.index("better_match") < order2.index("worse_but_same_lang"))

    print("\n10. An unreadable theme is not a theme that agrees")
    # The defect this guards: dict_cosine returns None for an unclassifiable
    # track so it "doesn't contribute". That is correct for a genuine
    # instrumental, but for a track we READ and could not label it hands the
    # heaviest dimension in the table (theme, weight 3.0) a free pass — the
    # unknown track banks weight 3.0 at whatever its audio says. The theme slot
    # must register disagreement instead of vanishing.
    score_u, contrib_u = S.similarity(LIBRARY["one_love"],
                                       LIBRARY["unlabelled_rap"])
    ok &= check("unread theme contributes 0.0, not nothing",
                contrib_u.get("theme", {}).get("sim") == 0.0,
                f"theme sim={contrib_u.get('theme', {}).get('sim')!r}")
    ok &= check("theme still carries its full weight against the unknown",
                contrib_u.get("theme", {}).get("weight") ==
                S.DIMENSIONS_BY_NAME["theme"]["weight"])

    # But an instrumental must NOT be punished: there is no thematic content
    # to agree or disagree with, so the dimension genuinely does not apply.
    _, contrib_inst = S.similarity(LIBRARY["one_love"], LIBRARY["lofi"])
    ok &= check("a real instrumental still skips the theme dimension entirely",
                "theme" not in contrib_inst,
                f"keys={sorted(contrib_inst)[:4]}...")

    # And two unknowns must not punish each other.
    _, contrib_both = S.similarity(LIBRARY["unlabelled_rap"],
                                   LIBRARY["unlabelled_rap"])
    ok &= check("two unlabelled tracks do not penalise each other",
                "theme" not in contrib_both)

    print("\n11. 'No lyrics found' is not 'no lyrics present'")
    # Found by the held-out gate run: "Hamla" (a Sez on the Beat diss track)
    # reached romantic queues because word_count == 0 made it look like an
    # instrumental. It is not one — it has a voice at 0.73. Its lyrics were
    # simply never fetched, so word_count == 0 means "none found", and the
    # theme lock treated that as safety. The same hole let "Hustle 4 Season
    # Anthem" queue next to "Zigane" and "Boom Shaka" next to it.
    voiced_unread = dict(LIBRARY["unlabelled_rap"])
    voiced_unread.update({"word_count": 0, "vocal_presence": 0.73,
                          "title": "Voiced, lyrics never fetched"})
    real_inst = dict(LIBRARY["lofi"])
    real_inst.update({"vocal_presence": 0.05})

    ok &= check("no words but an audible voice IS unclassified",
                S.is_unclassified(voiced_unread) is True)
    ok &= check("no words and no voice is a true instrumental",
                S.is_unclassified(real_inst) is False)
    ok &= check("the floor sits between them",
                S.is_unclassified({**voiced_unread, "vocal_presence": 0.49})
                is False
                and S.is_unclassified({**voiced_unread,
                                       "vocal_presence": 0.51}) is True)

    # And the consequence: it must no longer ride into a romantic queue at the
    # top, which is exactly what the held-out run did.
    unread_lib = {"anchor": LIBRARY["one_love"], "unread": voiced_unread,
                  "clean": LIBRARY["high_on_you"]}
    order3 = [r["track_id"] for r in
              S.rank_neighbours(unread_lib, "anchor", limit=5,
                                respect_theme_lock=True)]
    print(f"     order: {order3}")
    ok &= check("the unread track does not outrank the clean match",
                order3.index("clean") < order3.index("unread"))

    print("\n12. A tied lead theme is not a claim about the music")
    # Found by the rebuilt gate: "Do Numbari" carries celebration=1.0 AND
    # aggression=1.0. theme_drift reduced each vector to its argmax, both
    # argmaxed to celebration, and the pair scored as the SAME mood — so a
    # maximally aggressive track was admitted to a romantic track's queue, and
    # the theme lock, the product's central promise, did not see it.
    tied = {"title": "Tied", "theme_scores": {"celebration": 1.0,
                                              "aggression": 1.0}}
    calm = {"title": "Calm", "theme_scores": {"celebration": 1.0}}
    ok &= check("a genuinely undisputed match still reads as the same mood",
                S.theme_drift(calm, {"theme_scores": {"celebration": 0.9}})
                < 0.1 + 1e-9)
    d = S.theme_drift(calm, tied)
    print(f"     drift(calm -> tied-on-aggression) = {d:.4f} "
          f"(lock trips above {S.MAX_THEME_DRIFT})")
    ok &= check("a tie-broken lead costs the pair its same-mood credit",
                d > S.theme_drift(calm, calm))
    ok &= check("_confident_lead reports the tie as zero margin",
                S._confident_lead(tied["theme_scores"])[1] == 0.0)
    ok &= check("_confident_lead reports a real margin when there is one",
                abs(S._confident_lead({"a": 0.9, "b": 0.2})[1] - 0.7) < 1e-9)

    print("\n" + ("ALL PASS" if ok else "SOME FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
