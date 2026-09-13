# True Hyper Mixing (THM)
### *A Context-Aware Playback Engine That Understands What a Song Actually Is - and Plays the Next One That Belongs Beside It.*

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Phase 1 Gate](https://img.shields.io/badge/Phase%201%20Gate-17%2F17%20Clean-success.svg)](docs/PHASE_1_REPORT.md)
[![Vibe Model](https://img.shields.io/badge/Perceptual%20Model-52%20Dimensions-orange.svg)](docs/52_DIMENSIONS.md)

---

## 1. The Core Problem

Traditional music players rely on three broken playback mechanisms:
1. **Sequential Playback (by date or filename):** Zero musical awareness. An accidental shuffle dictated by when a file downloaded.
2. **Uniform Random Shuffle:** Adversarial to mood. The classic failure: an intimate love ballad followed directly by a 140 BPM aggressive drill track.
3. **Genre / Artist Mix (Spotify / Apple Music):** Far too coarse. "Punjabi" contains both a whispered acoustic bedroom ballad and a 140 BPM wedding bhangra anthem. An artist's catalogue spans a decade of contradictory moods.

> **The One-Sentence Product:**  
> **Play any song, and THM keeps the room in the exact same emotional and experiential space - indefinitely, without you touching the skip button.**

---

## 2. The Headline Benchmark: "One Love" by Subh

THM is built to guarantee this specific inversion:

```text
Anchor Track:  "One Love" by Subh (Punjabi romantic ballad, acoustic guitar, ~82 BPM)
Candidate A:   "High On You" (Punjabi romantic theme, slightly pumpier beat ~88 BPM)
Candidate B:   Gangster Drill Rap (deliberately tempo-matched at 82.5 BPM)

Results:
  - THM Composite Ranking:
      1. "High On You"          -> 0.9586  [MATCH]
      2. Instrumental Lofi        -> 0.8191
      3. Gangster Drill Rap       -> 0.2965  [REJECTED - THEME LOCK]

  - The Crucial Detail:
      Gangster track tempo similarity: 0.988  vs  High On You: 0.895
      THM outranks the love song by 3x despite the drill track being tempo-closer.
```

---

## 3. Architecture & 52-Dimensional Perceptual Model

Music is not a genre label. It is an interplay of **52 measurable dimensions** across seven families:

| Family | Count | Focus | Key Features |
| :--- | :---: | :--- | :--- |
| **A: Temporal & Rhythmic** | 7 | Rhythm & Speed | Tempo (BPM), Beat Pattern, Rhythm Complexity, Onset Density, HPSS Percussive Strength |
| **B: Harmonic & Tonal** | 6 | Pitch & Emotion | Circle of Fifths Key Distance, Scale/Mode (Major/Minor), Harmonic Complexity, Tonal Stability |
| **C: Spectral & Timbre** | 8 | Instrument Texture | 13-MFCC Cosine Fingerprint, Spectral Centroid, Band Balance (5 Bands), Zero-Crossing Rate |
| **D: Dynamics & Loudness** | 5 | Physical Sensation | ITU-R BS.1770 Integrated Loudness (LUFS), Dynamic Range, Peak-to-Loudness, RMS Envelope |
| **E: Instrumentation** | 8 | Production World | Primary Instruments, Acoustic vs Electronic Score, Vocal Presence, Delivery (Tender vs Shouted) |
| **F: Lyrical & Thematic** | 9 | Subject Matter | Primary Theme (Multi-label), Emotional Tone, Sentiment Polarity (-1 to +1), 3-Script Detection |
| **G: Perceptual & Cultural**| 9 | Perceived Vibe | Energy Level (0-1), Valence, Arousal, Danceability, Intimacy (Bedroom vs Stadium) |

Read the complete specification in [docs/52_DIMENSIONS.md](docs/52_DIMENSIONS.md).

---

## 4. Key Engineering Highlights

* **Auditable 3-Script Lexical Engine:** Zero-dependency NLP covering **Gurmukhi, Devanagari, and Latin/Romanized** lyrics without brittle 500MB GPU models.
* **Per-Dimension Elasticity:** Tolerance is dimension-specific. Tempo allows +-15 BPM before penalty, while mood changes face a strict drift cap.
* **Directional Arc Control ("Slightly More Pumpy"):** Symmetric distance metrics only reward sameness. THM carries an explicit drift target (e.g. +4 BPM, +0.06 energy) so transitions can naturally build energy.
* **"Unknown" is Not "Safe":** Songs with audible vocals (>0.5 vocal presence) lacking lyric labels are penalized (x0.5) rather than treated as harmless instrumentals.
* **Deterministic Tie-Breaking:** Exact score ties are broken by: `Same Language` -> `Same Artist` -> `Has Lyrics`.

---

## 5. Visual Experience & UI Highlights

The frontend represents a cyber-studio mixing console tailored to music production aesthetics:

* **Studio Mastering Turntable:** Interactive vinyl platter that spins on needle drop with an engaging stylus tonearm and real-time dual stereo VU meters.
* **Raftaar Music Video Showcase:** Dedicated interactive cards for Raftaar's tracks (*Woh Raat*, *Nahi Hai Woh*, *Saza-e-Maut*, *GOAT Dekho*, *Top Off* ft. Ikka) with instant vibe-anchored smart mixing.
* **Intelligent Transition Visualizer:** Live bridge card visualizing incoming song alignment, waveform flow, and vibe match percentage.
* **Kinetic Synced Lyrics:** Real-time typography with active line autoscrolling, karaoke word illumination, and script-aware font rendering.
* **Audio-Reactive Ambient Aura:** Dynamic canvas extracting color palettes from album artwork, pulsating to low- and mid-frequency audio dynamics.

---

## 6. Quickstart

### Prerequisites
* Python 3.10+
* Git

### Installation
```bash
# 1. Clone repository
git clone https://github.com/shivamtyagi123456789/THM-The-Hyper-Mix.git
cd THM-The-Hyper-Mix

# 2. Install dependencies
pip install -r requirements.txt
pip install -e .

# 3. Seed benchmark database
python scripts/seed_fixtures.py

# 4. Launch web application
python app.py
```
Open your browser at **`http://127.0.0.1:5000`**.

---

## 7. CLI Tools & Verification

```bash
# Run core regression tests (One Love benchmark, arc, elasticity, tie-breaks)
python -m thm.test_similarity

# Run audio feature extraction unit tests
python -m thm.test_audio

# Run Phase 1 Acceptance Gate
python -m thm.explain --validate

# Explain similarity between two tracks
python -m thm.explain "one love" --why

# Debug which words fired in lyrics
python -m thm.debug_lyrics "HIGH ON YOU"

# Analyze your local music library
python -m thm.analyze_library /path/to/music
```

---

## 8. Delivery Roadmap

* [x] **Phase 1: Core Analysis & Matching Engine** - 52-dimension model, 3-script lexicon, elastic similarity, arc control, acceptance gate (17/17 clean).
* [x] **Phase 2: Playback & Interface** - Web console, LUFS leveling, queue manager, kinetic lyrics, Raftaar visual showcase, transition visualizer.
* [ ] **Phase 3: Learning & Personalization** - Long-term skip/replay weight adaptation, custom user mood presets.
* [ ] **Phase 4: Platform Expansion** - Mobile apps, streaming service bridges (Spotify/Apple Music), FAISS vector search for 100,000+ tracks.

---

## 9. License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
