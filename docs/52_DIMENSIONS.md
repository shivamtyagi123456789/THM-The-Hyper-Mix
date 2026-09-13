# The 52-Dimensional Perceptual Similarity Model

True Hyper Mixing (THM) rejects the premise that music transitions can be effectively driven by coarse metadata tags like "Genre" or "Artist". Music is a complex interplay of temporal, harmonic, timbral, lyrical, and perceptual dynamics.

THM profiles every track across **52 perceptually meaningful dimensions**, grouped into seven distinct families (A-G). The stored feature vector per track spans ~150-200 numeric values.

---

## Family A: Temporal & Rhythmic (A1-A7)
1. **A1 - Tempo (BPM)** [P0]: Detected via onset-envelope autocorrelation. The single strongest predictor of perceived physical energy.
2. **A2 - Time Signature** [P1]: Metre (4/4, 3/4, 6/8). A metre shift disrupts groove continuity even when tempo is constant.
3. **A3 - Beat Pattern** [P1]: Straight, swung, syncopated, off-beat. Separates laid-back ballads from driving four-on-the-floor rhythms.
4. **A4 - Rhythm Complexity** [P1]: Variance in inter-onset intervals (simple vs polyrhythmic).
5. **A5 - Onset Density** [P2]: Note onsets per second. Distinguishes fingerpicked acoustic guitar from dense synth arpeggiators.
6. **A6 - Groove Consistency** [P2]: Sectional rhythmic stability (hypnotic loop vs shifting polyrhythm).
7. **A7 - Percussive Strength** [P1]: Transient-to-sustained energy ratio derived from Harmonic/Percussive Source Separation (HPSS).

---

## Family B: Harmonic & Tonal (B1-B6)
8. **B1 - Key Note** [P1]: Tonic pitch class (C, C#, D...). Evaluated using the musical Circle of Fifths (adjacent keys blend; tritone clashes).
9. **B2 - Mode / Scale** [P1]: Major, minor, Dorian, Mixolydian, pentatonic, raga-derived. Governs emotional color (major bright, minor wistful).
10. **B3 - Harmonic Complexity** [P1]: Diatonic vs chromatic content (folk simplicity vs jazz extensions).
11. **B4 - Chord Progression Archetype** [P2]: Clustered harmonic movement (e.g. I-V-vi-IV).
12. **B5 - Tuning Reference** [P2]: Concert pitch deviation (guards against microtonal pitch drift).
13. **B6 - Tonal Stability** [P2]: Degree of harmonic anchoring (drone anchor vs wandering modulation).

---

## Family C: Spectral & Timbre (C1-C8)
14. **C1 - Spectral Centroid** [P0]: Center of spectral mass in Hz (warm/dark vs glassy/bright).
15. **C2 - Spectral Rolloff** [P1]: 85% energy frequency ceiling. Separates lo-fi muffled sound from airy high-fidelity production.
16. **C3 - MFCC Vector (13 Coefficients)** [P0]: Mel-frequency cepstral coefficients. The primary timbral fingerprint, compared via cosine similarity.
17. **C4 - Spectral Contrast** [P1]: Energy peaks vs valleys across sub-bands (clean acoustic mix vs dense wall-of-sound).
18. **C5 - Zero-Crossing Rate** [P0]: Noisiness and percussiveness indicator.
19. **C6 - Frequency Band Balance (5 Bands)** [P1]: Energy split across sub-bass, bass, low-mid, high-mid, and treble.
20. **C7 - Harmonics-to-Noise Ratio (HNR)** [P2]: Tonality vs breathiness/distortion.
21. **C8 - Spectral Flatness** [P2]: Peaky vs white-noise spectral distribution.

---

## Family D: Loudness & Dynamics (D1-D5)
22. **D1 - Integrated Loudness (LUFS)** [P0]: ITU-R BS.1770 perceptual loudness. Standardized for playback leveling to avoid volume jumps.
23. **D2 - Dynamic Range** [P1]: Spread between quietest and loudest passages.
24. **D3 - Peak-to-Loudness Ratio (PLR)** [P1]: Transient headroom (punchy uncompressed vs heavily limited mastering).
25. **D4 - RMS Energy Envelope** [P0]: Continuous frame-wise energy contour over time.
26. **D5 - Loudness Trajectory** [P2]: Long-term volume build vs decay vs steady loop.

---

## Family E: Instrumentation & Production (E1-E8)
27. **E1 - Primary Instrumentation** [P0]: Dominant instrument families (acoustic guitar, electric guitar, synth, strings, tabla/dhol, 808 subs).
28. **E2 - Acoustic vs Electronic Score** [P1]: Ratio of organic to synthesized timbre.
29. **E3 - Vocal Presence** [P0]: Vocal density and foreground dominance.
30. **E4 - Vocal Style & Delivery** [P0]: Smooth/melodic, rap/spoken, aggressive/shouted, autotuned, raw.
31. **E5 - Production Style** [P1]: Lo-fi, hi-fi, minimalist, maximalist, live room, studio polished.
32. **E6 - Sound Texture** [P1]: Reverb-drenched, bone-dry, gritty, crystalline.
33. **E7 - Layering & Density** [P1]: Number of simultaneous musical layers.
34. **E8 - Effects Profile** [P2]: Prominence of delay, chorus, distortion, and spatialization.

---

## Family F: Lyrical & Thematic (F1-F9)
35. **F1 - Primary Theme** [P0]: Multi-label classification (love/romance, heartbreak, aggression, celebration, struggle, spirituality, party, introspection).
36. **F2 - Emotional Tone** [P1]: Happy, melancholic, angry, peaceful, nostalgic, confident.
37. **F3 - Sentiment Valence** [P1]: Continuous -1.0 to +1.0 lyrical polarity.
38. **F4 - Language / Script** [P0]: Gurmukhi, Devanagari, Latin/Romanized, Hindi, Punjabi, English.
39. **F5 - Narrative Perspective** [P1]: First person, second person ("you"), third person, abstract.
40. **F6 - Subject Specificity** [P2]: Personal confession vs universal narrative.
41. **F7 - Lyrical Density** [P1]: Words per minute (rap cadence vs ambient sparse vocal).
42. **F8 - Lyrical Complexity** [P2]: Vocabulary richness and metaphor density.
43. **F9 - Explicit Content Flag** [P1]: Boolean filter respected on user demand.

---

## Family G: Perceptual, Structural & Cultural (G1-G9)
44. **G1 - Energy Level** [P0]: 0-1 composite of tempo, RMS, onset density, and brightness.
45. **G2 - Valence** [P0]: Musical positivity (0.0 sad/angry to 1.0 cheerful).
46. **G3 - Arousal** [P1]: Calming/sedative to intense/stimulated.
47. **G4 - Danceability** [P1]: Rhythmic regularity combined with tempo suitability for movement.
48. **G5 - Intensity** [P2]: Perceived assertiveness (distinct from raw decibel loudness).
49. **G6 - Intimacy Level** [P1]: Bedroom confessional vs stadium anthem.
50. **G7 - Mood Descriptors** [P0]: Multi-label tags compared via Jaccard similarity.
51. **G8 - Genre & Cultural Context** [P1]: Origin, sub-genre, regional sound, era.
52. **G9 - Structure & Context** [P2]: Intro/outro transitions, verse-chorus arrangement, usage tags.
