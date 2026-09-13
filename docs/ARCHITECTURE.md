# Technical Architecture & Pipeline

True Hyper Mixing (THM) is engineered around an offline-first, low-latency, modular pipeline.

```
+-------------------------------------------------------------------------+
|                              AUDIO INPUT                                |
|        (Local MP3, FLAC, WAV, M4A, OGG Files + LRC Lyric Sidecars)      |
+------------------------------------+------------------------------------+
                                     |
                +--------------------+--------------------+
                |                                         |
                v                                         v
+-------------------------------+       +---------------------------------+
|      AUDIO ANALYSIS ENGINE    |       |     LYRICAL ANALYSIS MODULE     |
|  - Librosa / Essentia Worker  |       |  - 3-Script Lexical Engine      |
|  - Temporal, Harmonic, Timbre |       |    (Gurmukhi, Devanagari, Latin)|
|  - HPSS Optimized Median Filts|       |  - Core vs Soft Vocabulary Split|
|  - LUFS & RMS Dynamics        |       |  - Sentiment & Perspective      |
+---------------+---------------+       +----------------+----------------+
                |                                        |
                +--------------------+-------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                        FEATURE STORE (SQLite)                           |
|        - tracks: Identity, format, duration, analysis status            |
|        - features: Audio dimensions (JSON blobs for vectors)            |
|        - lyrical: Theme vectors, sentiment, word count, script          |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                        SIMILARITY MATCHING CORE                         |
|  1. Normalization & Clamping: Map continuous scalars to [0, 1]          |
|  2. Multi-Metric Distance:                                              |
|     - Scaled Elastic Euclidean (with dimension-specific tolerance)      |
|     - Vector Cosine (MFCC, chroma, spectral balance)                    |
|     - Multi-label Cosine & Jaccard (themes, mood tags)                  |
|     - Circle of Fifths (harmonic key relationships)                     |
|  3. Provenance Discount: Approximated features downweighted by 0.5      |
|  4. Directional Arc Control: Shifts preference target (+4 BPM, +0.06 E) |
|  5. Hard Theme Lock: Prevents mood clashes (romance -> aggression)      |
|  6. Deterministic Tie-Breaker: Language -> Artist -> Lyrics             |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                        DYNAMIC QUEUE MANAGER                            |
|  - Rolling 20-track history window (no repetition)                      |
|  - Minimum 5-track upcoming buffer maintained                           |
|  - Elastic widening fallback (FR-3.10) to prevent queue exhaustion      |
|  - Transition skip learning event logger                                |
+------------------------------------+------------------------------------+
                                     |
                +--------------------+--------------------+
                |                                         |
                v                                         v
+-------------------------------+       +---------------------------------+
|      FLASK REST / STREAMING   |       |       INTERACTIVE WEB UI        |
|  - /api/queue, /api/tracks    |       |  - Studio Mastering Console     |
|  - HTTP 206 Byte-Range Audio  |       |  - Raftaar Video Poster Deck    |
|  - Timed LRC Lyric Streamer   |       |  - Intelligent Transition Card  |
|  - "Why this song?" Auditor   |       |  - Kinetic Synced Typography    |
+-------------------------------+       |  - Audio-Reactive Ambient Aura  |
                                        +---------------------------------+
```
