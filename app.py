"""
True Hyper Mixing (THM) Web Application Backend.
Connects the Phase 1 feature store & similarity engine to the interactive frontend.
"""

import os
import re
import json
import mimetypes
from pathlib import Path
from flask import Flask, jsonify, request, render_template, send_from_directory, Response

from thm import db, similarity as S
from thm.queue_manager import PlaybackQueueManager
from thm.analyze_library import find_lyrics

app = Flask(__name__, template_folder="templates", static_folder="static")

# Initialize Queue Manager
DB_PATH = os.path.join(os.path.dirname(__file__), "thm.db")
queue_manager = PlaybackQueueManager(db_path=DB_PATH)

# Featured Raftaar Visual Showcase Data (Video Concept 1 & Directives)
FEATURED_POSTERS = [
    {
        "id": "woh_raat",
        "title": "Woh Raat",
        "artist": "Raftaar x KR$NA",
        "album": "Mr. Nair",
        "vibe": "Midnight Drill / Noir Introspection",
        "theme": "struggle",
        "accent": "#ef4444",
        "accent_glow": "rgba(239, 68, 68, 0.4)",
        "gradient": "linear-gradient(135deg, #180507 0%, #3e0b11 50%, #0d0103 100%)",
        "tagline": "Late night confessions over nocturnal 808s",
        "visual_style": "Rainy cyberpunk streets, neon crimson rim light, cold nocturnal smoke",
        "sample_lyric": "Woh raat maine dekhi jab andhere mein bhi roshni thi...",
        "bpm": 84,
        "energy": 0.68,
        "key": "C# Minor"
    },
    {
        "id": "saza_e_maut",
        "title": "Saza-e-Maut",
        "artist": "KR$NA ft. Raftaar",
        "album": "Still Here",
        "vibe": "Aggressive Hardcore Drill",
        "theme": "aggression",
        "accent": "#f97316",
        "accent_glow": "rgba(249, 115, 22, 0.4)",
        "gradient": "linear-gradient(135deg, #1c0f05 0%, #431f06 50%, #0d0501 100%)",
        "tagline": "Relentless lyrical warfare & UK drill sliding subs",
        "visual_style": "High-contrast prison yard, brutalist shadows, amber flash strobe",
        "sample_lyric": "Khel yeh shuru kiya humne, ab maut hi saza hai...",
        "bpm": 140,
        "energy": 0.94,
        "key": "F Minor"
    },
    {
        "id": "goat_dekho",
        "title": "GOAT Dekho",
        "artist": "Raftaar",
        "album": "Hard Drive Vol. 1",
        "vibe": "Opulent Swagger & Elite Flow",
        "theme": "celebration",
        "accent": "#eab308",
        "accent_glow": "rgba(234, 179, 8, 0.4)",
        "gradient": "linear-gradient(135deg, #1a1503 0%, #3d3107 50%, #0d0b01 100%)",
        "tagline": "Regal bars, brass fanfares & pure technical mastery",
        "visual_style": "Polished black marble, 24K gold ornaments, royal crown emblem",
        "sample_lyric": "GOAT dekho, saamne khada jo tere hai...",
        "bpm": 92,
        "energy": 0.88,
        "key": "G Minor"
    },
    {
        "id": "nahi_hai_woh",
        "title": "Nahi Hai Woh",
        "artist": "Raftaar ft. Shah Rule",
        "album": "Mr. Nair",
        "vibe": "Melodic Melancholy / Atmospheric Hip-Hop",
        "theme": "heartbreak",
        "accent": "#a855f7",
        "accent_glow": "rgba(168, 85, 247, 0.4)",
        "gradient": "linear-gradient(135deg, #12051c 0%, #310d4c 50%, #09010e 100%)",
        "tagline": "Lush Rhodes chords, tender regret & soaring hooks",
        "visual_style": "Deep violet neon haze, twilight silhouettes, blurred bokeh lights",
        "sample_lyric": "Dhoondhta hoon jisko main, ab nahi hai woh...",
        "bpm": 78,
        "energy": 0.45,
        "key": "Bb Minor"
    },
    {
        "id": "top_off",
        "title": "Top Off",
        "artist": "Ikka & Raftaar",
        "album": "I",
        "vibe": "High-Octane Street Club Banger",
        "theme": "party",
        "accent": "#06b6d4",
        "accent_glow": "rgba(6, 182, 212, 0.4)",
        "gradient": "linear-gradient(135deg, #021619 0%, #083b44 50%, #010c0e 100%)",
        "tagline": "Convertible drops, synthwave basslines & effortless charisma",
        "visual_style": "Emerald cyan underglow, metallic chrome chassis, expressway blur",
        "sample_lyric": "Gaadi kare drop top, beat kare pop pop...",
        "bpm": 105,
        "energy": 0.82,
        "key": "D Minor"
    }
]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/posters", methods=["GET"])
def get_posters():
    """Return the curated Raftaar poster showcases."""
    posters = []
    for p in FEATURED_POSTERS:
        item = dict(p)
        item["library_track_id"] = None
        for tid, tr in queue_manager.library.items():
            t_title = (tr.get("title") or "").lower()
            if p["title"].lower() in t_title or p["id"] in t_title:
                item["library_track_id"] = tid
                break
        posters.append(item)
    return jsonify({"posters": posters})


@app.route("/api/tracks", methods=["GET"])
def get_tracks():
    """Return all analyzed tracks in library."""
    tracks = []
    for tid, tr in queue_manager.library.items():
        tracks.append({
            "track_id": tid,
            "title": tr.get("title") or "Unknown Title",
            "artist": tr.get("artist") or "Unknown Artist",
            "album": tr.get("album") or "",
            "duration": tr.get("duration") or 0.0,
            "tempo_bpm": round(tr.get("tempo_bpm") or 0.0, 1),
            "primary_theme": tr.get("primary_theme") or "unclassified",
            "primary_emotion": tr.get("primary_emotion") or "neutral",
            "language": tr.get("language") or "unknown",
            "energy_level": round(tr.get("energy_level") or 0.0, 2),
            "vocal_presence": round(tr.get("vocal_presence") or 0.0, 2),
            "loudness_lufs": round(tr.get("loudness_lufs") or -14.0, 1)
        })
    tracks.sort(key=lambda x: x["title"].lower())
    return jsonify({"total": len(tracks), "tracks": tracks})


@app.route("/api/track/<track_id>", methods=["GET"])
def get_track_detail(track_id):
    """Return full detailed feature breakdown of a single track."""
    track = queue_manager.get_track(track_id)
    if not track:
        return jsonify({"error": "Track not found"}), 404
    return jsonify({"track": queue_manager._format_track_summary(track_id)})


@app.route("/api/queue/init", methods=["POST"])
def init_queue():
    """Start playback on a given track and generate the initial vibe queue."""
    data = request.get_json() or {}
    track_id = data.get("track_id")
    queue_depth = data.get("queue_depth", 10)

    if not track_id:
        for tid, tr in queue_manager.library.items():
            if "high on you" in (tr.get("title") or "").lower() or "one love" in (tr.get("title") or "").lower():
                track_id = tid
                break
        if not track_id and queue_manager.library:
            track_id = next(iter(queue_manager.library.keys()))

    if not track_id or track_id not in queue_manager.library:
        return jsonify({"error": "No valid track found"}), 404

    result = queue_manager.init_playback(track_id, queue_depth=queue_depth)
    return jsonify(result)


@app.route("/api/queue/next", methods=["POST"])
def next_queue_item():
    """Advance to next track in queue and dynamically refill."""
    next_track = queue_manager.next_track()
    if not next_track:
        return jsonify({"error": "Queue empty"}), 404
    return jsonify({
        "current_track": next_track,
        "queue": queue_manager.queue,
        "history_count": len(queue_manager.history),
        "arc_mode": queue_manager.arc_mode
    })


@app.route("/api/queue/skip", methods=["POST"])
def skip_queue_item():
    """Handle skip event: record learning feedback and advance."""
    data = request.get_json() or {}
    skipped_id = data.get("track_id") or queue_manager.current_track_id
    next_track = queue_manager.on_track_skip(skipped_id)
    if not next_track:
        return jsonify({"error": "Queue empty"}), 404
    return jsonify({
        "current_track": next_track,
        "queue": queue_manager.queue,
        "history_count": len(queue_manager.history),
        "arc_mode": queue_manager.arc_mode,
        "skip_logged": True
    })


@app.route("/api/queue/arc", methods=["POST"])
def set_arc_mode():
    """Change arc trajectory: 'steady' | 'rising' | 'cooling_down'."""
    data = request.get_json() or {}
    mode = data.get("mode", "steady")
    queue_manager.set_arc(mode)
    return jsonify({
        "arc_mode": queue_manager.arc_mode,
        "queue": queue_manager.queue
    })


@app.route("/api/queue/lock", methods=["POST"])
def lock_queue_item():
    """Lock/unlock a track in queue."""
    data = request.get_json() or {}
    track_id = data.get("track_id")
    locked = data.get("locked", True)
    if track_id:
        queue_manager.lock_track(track_id, locked)
    return jsonify({"track_id": track_id, "is_locked": locked})


@app.route("/api/explain/<anchor_id>/<candidate_id>", methods=["GET"])
def explain_similarity(anchor_id, candidate_id):
    """Detailed dimension-by-dimension similarity explanation."""
    anchor = queue_manager.get_track(anchor_id)
    candidate = queue_manager.get_track(candidate_id)
    if not anchor or not candidate:
        return jsonify({"error": "Track not found"}), 404

    arc_val = queue_manager.arc_mode if queue_manager.arc_mode != "steady" else None
    score, contributions = S.similarity(anchor, candidate, arc=arc_val)
    drift = S.theme_drift(anchor, candidate)
    tb_reason = S.tiebreak_reason(anchor, candidate)

    # Resolve provenance cleanly
    dim_map = getattr(S, "DIMENSIONS_BY_NAME", {})

    sorted_contribs = []
    for dim_name, info in contributions.items():
        prov = info.get("provenance") or dim_map.get(dim_name, {}).get("provenance", "measured")
        sorted_contribs.append({
            "dimension": dim_name,
            "similarity": round(info["sim"] * 100, 1),
            "effective_weight": round(info["weight"], 2),
            "provenance": prov
        })
    sorted_contribs.sort(key=lambda x: -(x["similarity"] * x["effective_weight"]))

    explanation = {
        "overall_score": round(score * 100, 1),
        "theme_drift": drift,
        "tiebreak": tb_reason,
        "anchor_title": anchor.get("title"),
        "anchor_artist": anchor.get("artist"),
        "candidate_title": candidate.get("title"),
        "candidate_artist": candidate.get("artist"),
        "top_matching_dimensions": sorted_contribs[:6],
        "all_dimensions": sorted_contribs
    }
    return jsonify(explanation)


@app.route("/api/lyrics/<track_id>", methods=["GET"])
def get_lyrics(track_id):
    """Parse and return synced or static lyrics."""
    track = queue_manager.get_track(track_id)
    if not track:
        return jsonify({"has_lyrics": False, "lines": []}), 404

    file_path = track.get("file_path")
    if not file_path:
        return jsonify({"has_lyrics": False, "lines": []})

    p = Path(file_path)
    lrc_path = find_lyrics(p)

    if not lrc_path or not lrc_path.exists():
        return jsonify({"has_lyrics": False, "lines": []})

    content = lrc_path.read_text(encoding="utf-8", errors="replace")
    
    # Parse LRC lines
    pattern = re.compile(r"\[(\d{2}):(\d{2}(?:\.\d{1,3})?)\](.*)")
    timed_lines = []
    raw_lines = []

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        m = pattern.match(line)
        if m:
            mins = int(m.group(1))
            secs = float(m.group(2))
            ms = int((mins * 60 + secs) * 1000)
            text = m.group(3).strip()
            if text:
                timed_lines.append({
                    "time_ms": ms,
                    "text": text,
                    "words": text.split()
                })
        else:
            if not line.startswith("["):
                raw_lines.append(line)

    if timed_lines:
        return jsonify({
            "has_lyrics": True,
            "is_timed": True,
            "lines": timed_lines
        })
    elif raw_lines:
        # Interpolate timings evenly across track duration
        duration_sec = track.get("duration") or 180.0
        line_count = len(raw_lines)
        step_ms = int((duration_sec * 1000) / max(1, line_count))
        synthesized_timed = []
        for i, text in enumerate(raw_lines):
            synthesized_timed.append({
                "time_ms": i * step_ms,
                "text": text,
                "words": text.split()
            })
        return jsonify({
            "has_lyrics": True,
            "is_timed": False,
            "lines": synthesized_timed
        })

    return jsonify({"has_lyrics": False, "lines": []})


@app.route("/api/stream/<track_id>", methods=["GET"])
def stream_audio(track_id):
    """
    Stream audio with HTTP 206 Partial Content (Range requests)
    for seamless seeking in browser audio element.
    """
    track = queue_manager.get_track(track_id)
    if not track:
        return "Track not found", 404

    file_path = track.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return "Audio file missing", 404

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("Range", None)
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or "audio/mpeg"

    if not range_header:
        def generate():
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk
        return Response(
            generate(),
            mimetype=content_type,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes"
            }
        )

    match = re.search(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        return "Invalid Range", 416

    byte_start = int(match.group(1))
    byte_end = int(match.group(2)) if match.group(2) else file_size - 1

    if byte_start >= file_size:
        return "Range Out of Bounds", 416

    byte_end = min(byte_end, file_size - 1)
    chunk_length = (byte_end - byte_start) + 1

    def generate_range():
        with open(file_path, "rb") as f:
            f.seek(byte_start)
            bytes_left = chunk_length
            while bytes_left > 0:
                read_len = min(bytes_left, 65536)
                data = f.read(read_len)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    response = Response(
        generate_range(),
        status=206,
        mimetype=content_type,
        headers={
            "Content-Range": f"bytes {byte_start}-{byte_end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_length),
        }
    )
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting True Hyper Mixing (THM) Web Player on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
