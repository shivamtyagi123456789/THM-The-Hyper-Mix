"""
Storage layer for THM.

Single SQLite file, no server. Three tables:
  tracks   — identity + provenance
  features — audio-derived values (Section 5 families A-E)
  lyrical  — lyric-derived values (Section 5 family F)

Vector-valued features (MFCC, chroma, band balance, energy envelope) are stored
as JSON blobs. At 93 tracks this is faster to load whole than to normalise into
child tables; at 10k+ tracks this table would move behind the vector index
described in the PRD (Section 8.1).
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    track_id        TEXT PRIMARY KEY,
    file_path       TEXT UNIQUE NOT NULL,
    title           TEXT,
    artist          TEXT,
    album           TEXT,
    duration        REAL,
    file_format     TEXT,
    date_added      TEXT,
    last_analyzed   TEXT,
    analysis_status TEXT DEFAULT 'pending',
    lyrics_source   TEXT
);

CREATE TABLE IF NOT EXISTS features (
    track_id           TEXT PRIMARY KEY REFERENCES tracks(track_id) ON DELETE CASCADE,
    -- Family A: temporal & rhythmic
    tempo_bpm          REAL,
    beat_strength      REAL,
    onset_rate         REAL,
    rhythm_complexity  REAL,
    -- Family B: harmonic
    key_note           TEXT,
    scale_mode         TEXT,
    key_confidence     REAL,
    chroma_json        TEXT,
    -- Family C: spectral / timbre
    spectral_centroid  REAL,
    spectral_rolloff   REAL,
    spectral_bandwidth REAL,
    zero_crossing_rate REAL,
    spectral_contrast_json TEXT,
    band_balance_json  TEXT,
    mfcc_json          TEXT,
    -- Family D: loudness & dynamics
    loudness_lufs      REAL,
    rms_energy         REAL,
    dynamic_range      REAL,
    peak_to_loudness   REAL,
    energy_envelope_json TEXT,
    -- Family E: instrumentation & production (heuristics)
    percussive_strength REAL,
    harmonic_ratio      REAL,
    acoustic_score      REAL,
    vocal_presence      REAL,
    -- Family G: perceptual composites
    energy_level       REAL,
    valence_audio      REAL,
    arousal            REAL,
    danceability       REAL
);

CREATE TABLE IF NOT EXISTS lyrical (
    track_id        TEXT PRIMARY KEY REFERENCES tracks(track_id) ON DELETE CASCADE,
    language        TEXT,
    primary_theme   TEXT,
    theme_scores    TEXT,      -- JSON {theme: 0..1}
    primary_emotion TEXT,
    sentiment_score REAL,      -- -1..+1
    word_count      INTEGER,
    lyrical_density REAL,      -- words per minute
    perspective     TEXT,      -- first | second | third | mixed
    has_explicit    INTEGER,
    script          TEXT       -- gurmukhi | latin | mixed
);

CREATE INDEX IF NOT EXISTS idx_tempo  ON features(tempo_bpm);
CREATE INDEX IF NOT EXISTS idx_energy ON features(energy_level);
CREATE INDEX IF NOT EXISTS idx_theme  ON lyrical(primary_theme);
"""


def connect(db_path="thm.db"):
    """Open (and initialise) the library database."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_track(conn, file_path, title, artist, album, duration, file_format,
                 lyrics_source=None):
    """Insert or update a track's identity row. Returns its track_id."""
    file_path = str(Path(file_path).resolve())
    row = conn.execute(
        "SELECT track_id FROM tracks WHERE file_path = ?", (file_path,)
    ).fetchone()

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if row:
        track_id = row["track_id"]
        conn.execute(
            """UPDATE tracks SET title=?, artist=?, album=?, duration=?,
               file_format=?, lyrics_source=? WHERE track_id=?""",
            (title, artist, album, duration, file_format, lyrics_source, track_id),
        )
    else:
        track_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO tracks (track_id, file_path, title, artist, album,
               duration, file_format, date_added, lyrics_source)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (track_id, file_path, title, artist, album, duration, file_format,
             now, lyrics_source),
        )
    conn.commit()
    return track_id


# Column order matters here — it must match the INSERT below.
_FEATURE_COLUMNS = [
    "tempo_bpm", "beat_strength", "onset_rate", "rhythm_complexity",
    "key_note", "scale_mode", "key_confidence", "chroma_json",
    "spectral_centroid", "spectral_rolloff", "spectral_bandwidth",
    "zero_crossing_rate", "spectral_contrast_json", "band_balance_json",
    "mfcc_json",
    "loudness_lufs", "rms_energy", "dynamic_range", "peak_to_loudness",
    "energy_envelope_json",
    "percussive_strength", "harmonic_ratio", "acoustic_score", "vocal_presence",
    "energy_level", "valence_audio", "arousal", "danceability",
]

_JSON_COLUMNS = {
    "chroma_json", "spectral_contrast_json", "band_balance_json",
    "mfcc_json", "energy_envelope_json",
}

# Provenance: which features are measured vs. approximated. Recorded so the
# similarity engine can down-weight the ones that are guesses, and so a user
# reading a "why this song" explanation isn't misled.
FEATURE_PROVENANCE = {
    "tempo_bpm": "measured",
    "key_note": "measured",
    "scale_mode": "measured",
    "loudness_lufs": "measured",
    "mfcc_json": "measured",
    "spectral_centroid": "measured",
    "energy_level": "measured",
    "valence_audio": "approximated",   # mode + tempo + brightness proxy
    "acoustic_score": "approximated",
    "vocal_presence": "approximated",
    "danceability": "approximated",
    "arousal": "measured",
}


def save_features(conn, track_id, feats):
    """Write the audio feature row for a track, replacing any previous one."""
    values = []
    for col in _FEATURE_COLUMNS:
        v = feats.get(col)
        if col in _JSON_COLUMNS and v is not None:
            v = json.dumps(v)
        values.append(v)

    placeholders = ",".join("?" * len(_FEATURE_COLUMNS))
    cols = ",".join(_FEATURE_COLUMNS)
    conn.execute(
        f"INSERT OR REPLACE INTO features (track_id,{cols}) VALUES (?,{placeholders})",
        [track_id] + values,
    )
    conn.execute(
        "UPDATE tracks SET analysis_status='analyzed', last_analyzed=? WHERE track_id=?",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"), track_id),
    )
    conn.commit()


def save_lyrical(conn, track_id, lyr):
    """Write the lyrical feature row for a track, replacing any previous one."""
    conn.execute(
        """INSERT OR REPLACE INTO lyrical (track_id, language, primary_theme,
           theme_scores, primary_emotion, sentiment_score, word_count,
           lyrical_density, perspective, has_explicit, script)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            track_id,
            lyr.get("language"),
            lyr.get("primary_theme"),
            json.dumps(lyr.get("theme_scores", {})),
            lyr.get("primary_emotion"),
            lyr.get("sentiment_score"),
            lyr.get("word_count"),
            lyr.get("lyrical_density"),
            lyr.get("perspective"),
            1 if lyr.get("has_explicit") else 0,
            lyr.get("script"),
        ),
    )
    conn.commit()


def load_library(conn):
    """
    Load every analysed track as a flat dict for the similarity engine.

    Returns {track_id: {...}} where each dict merges the three tables and
    decodes the JSON vector columns back into lists.
    """
    rows = conn.execute(
        """SELECT t.track_id, t.file_path, t.title, t.artist, t.album,
                  t.duration, t.lyrics_source,
                  f.*, l.language, l.primary_theme, l.theme_scores,
                  l.primary_emotion, l.sentiment_score, l.word_count,
                  l.lyrical_density, l.perspective, l.has_explicit, l.script
           FROM tracks t
           LEFT JOIN features f ON f.track_id = t.track_id
           LEFT JOIN lyrical  l ON l.track_id = t.track_id
           WHERE t.analysis_status = 'analyzed'"""
    ).fetchall()

    library = {}
    for row in rows:
        d = dict(row)
        tid = d.pop("track_id")
        # f.* and l.* both carry a track_id; keep one.
        d.pop("track_id", None)

        for key in ("mfcc_json", "chroma_json", "band_balance_json",
                    "spectral_contrast_json", "energy_envelope_json"):
            raw = d.pop(key, None)
            d[key.replace("_json", "")] = json.loads(raw) if raw else []

        raw = d.pop("theme_scores", None)
        d["theme_scores"] = json.loads(raw) if raw else {}

        library[tid] = d

    return library
