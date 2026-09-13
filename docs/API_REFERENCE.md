# REST API Reference

The THM backend exposes a high-performance REST API on port `5000`.

### 1. Library & Tracks

#### `GET /api/tracks`
Returns all analyzed tracks in the database.
```json
{
  "total": 93,
  "tracks": [
    {
      "track_id": "uuid",
      "title": "High On You",
      "artist": "Jind Universe",
      "duration": 192.0,
      "tempo_bpm": 88.0,
      "primary_theme": "romance",
      "primary_emotion": "tender",
      "language": "punjabi",
      "energy_level": 0.38,
      "loudness_lufs": -13.5
    }
  ]
}
```

#### `GET /api/track/<track_id>`
Returns full 52-dimension profile for a single track.

---

### 2. Playback Queue Management

#### `POST /api/queue/init`
Starts playback anchored on a given track and initializes the vibe-matched queue.
```json
// Request Body
{
  "track_id": "subh-one-love-anchor",
  "queue_depth": 10
}
```

#### `POST /api/queue/next`
Advances playback to the next song, shifts history, and regenerates the buffer.

#### `POST /api/queue/skip`
Logs a transition rejection learning event and immediately advances to the next candidate.

#### `POST /api/queue/arc`
Changes the active session trajectory.
```json
// Request Body
{
  "mode": "rising" // "steady" | "rising" | "cooling_down"
}
```

---

### 3. Auditing & Streaming

#### `GET /api/explain/<anchor_id>/<candidate_id>`
Plain-language explanation and dimension-by-dimension contribution scores.
```json
{
  "overall_score": 95.9,
  "anchor_title": "One Love",
  "candidate_title": "High On You",
  "tiebreak": "same language",
  "top_matching_dimensions": [
    { "dimension": "theme", "similarity": 100.0, "effective_weight": 3.0, "provenance": "measured" },
    { "dimension": "tempo", "similarity": 89.5, "effective_weight": 2.5, "provenance": "measured" }
  ]
}
```

#### `GET /api/lyrics/<track_id>`
Returns parsed timestamped lyrics or tempo-interpolated lines.

#### `GET /api/stream/<track_id>`
Streams audio file supporting HTTP 206 Partial Content for byte-range seeking.
