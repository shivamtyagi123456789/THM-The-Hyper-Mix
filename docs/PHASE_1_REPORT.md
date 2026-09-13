# Phase 1 Summary Report

## The Headline Inversion
* **Anchor:** *One Love* by Subh (Punjabi acoustic love ballad, ~82 BPM).
* **Desired Next Song:** *High On You* (Punjabi romantic song, ~88 BPM).
* **Adversarial Candidate:** Gangster drill track deliberately constructed at 82.5 BPM.
* **Result:**
  * Naive tempo matching picks the gangster song (0.988 vs 0.895).
  * THM similarity engine ranks *High On You* at **0.9586** and rejects the gangster track at **0.2965**.
  * **The inversion is structurally achieved.**

## Key Bug Resolutions
1. **Absolute Vocabulary Floors:** Prevents single words from firing full-confidence themes (`MIN_HITS = 2`, `MIN_RATE = 0.4 / 100 words`).
2. **Core vs Soft Term Split:** Core terms decide if a theme can fire; soft terms (like *yaad*) only modulate magnitude.
3. **Unknown is Not Safe:** Tracks with vocal presence >= 0.5 that lack lyric labels are penalized (x0.5) rather than treated as safe instrumentals.
4. **Confident Lead in Theme Lock:** Argmax alone caused ties (celebration=1.0, aggression=1.0) to match love songs. A strict margin is now enforced.
5. **Deterministic Tie-Breaking:** Exact score ties are resolved by: Same Language -> Same Artist -> Has Lyrics.
