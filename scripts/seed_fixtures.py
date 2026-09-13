import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from thm import db
from thm.test_similarity import LIBRARY

BENCHMARK_TRACKS = [
    {
        "track_id": "subh-one-love-anchor",
        "file_path": "sample://Subh_One_Love.mp3",
        "title": "One Love",
        "artist": "Subh",
        "album": "One Love EP",
        "duration": 184.0,
        "file_format": "mp3",
        "features": LIBRARY["one_love"]
    },
    {
        "track_id": "jind-high-on-you",
        "file_path": "sample://Jind_High_On_You.mp3",
        "title": "High On You",
        "artist": "Jind Universe",
        "album": "High On You",
        "duration": 192.0,
        "file_format": "mp3",
        "features": LIBRARY["high_on_you"]
    },
    {
        "track_id": "gangster-drill-hostile",
        "file_path": "sample://Gangster_Drill.mp3",
        "title": "Gangster Drill Anthem",
        "artist": "Underground Syndicate",
        "album": "Street Rule",
        "duration": 165.0,
        "file_format": "mp3",
        "features": LIBRARY["gangster"]
    },
    {
        "track_id": "lofi-moonlight-instrumental",
        "file_path": "sample://Lofi_Moonlight.mp3",
        "title": "Moonlight Tape",
        "artist": "Chill Beatmaker",
        "album": "Bedroom Sessions",
        "duration": 140.0,
        "file_format": "mp3",
        "features": LIBRARY["lofi"]
    },
    {
        "track_id": "raftaar-woh-raat",
        "file_path": "sample://Raftaar_Woh_Raat.mp3",
        "title": "Woh Raat",
        "artist": "Raftaar x KR$NA",
        "album": "Mr. Nair",
        "duration": 215.0,
        "file_format": "mp3",
        "features": {
            "title": "Woh Raat", "artist": "Raftaar x KR$NA",
            "theme_scores": {"struggle": 0.88, "introspection": 0.72},
            "primary_theme": "struggle", "primary_emotion": "melancholic",
            "sentiment_score": -0.25, "perspective": "first",
            "tempo_bpm": 84.0, "energy_level": 0.68, "arousal": 0.65,
            "valence_audio": 0.40, "danceability": 0.62,
            "beat_strength": 0.72, "onset_rate": 2.4, "rhythm_complexity": 0.45,
            "percussive_strength": 0.78, "harmonic_ratio": 0.42,
            "acoustic_score": 0.15, "vocal_presence": 0.85,
            "loudness_lufs": -9.5, "rms_energy": 0.28, "dynamic_range": 6.2,
            "peak_to_loudness": 4.5, "key_note": "C#", "scale_mode": "minor",
            "lyrical_density": 45.0, "has_explicit": True, "language": "hindi",
        }
    },
    {
        "track_id": "krsna-saza-e-maut",
        "file_path": "sample://KRSNA_Saza_e_Maut.mp3",
        "title": "Saza-e-Maut",
        "artist": "KR$NA ft. Raftaar",
        "album": "Still Here",
        "duration": 230.0,
        "file_format": "mp3",
        "features": {
            "title": "Saza-e-Maut", "artist": "KR$NA ft. Raftaar",
            "theme_scores": {"aggression": 0.96, "struggle": 0.65},
            "primary_theme": "aggression", "primary_emotion": "angry",
            "sentiment_score": -0.65, "perspective": "first",
            "tempo_bpm": 140.0, "energy_level": 0.94, "arousal": 0.92,
            "valence_audio": 0.32, "danceability": 0.75,
            "beat_strength": 0.88, "onset_rate": 3.6, "rhythm_complexity": 0.58,
            "percussive_strength": 0.92, "harmonic_ratio": 0.28,
            "acoustic_score": 0.05, "vocal_presence": 0.90,
            "loudness_lufs": -7.2, "rms_energy": 0.38, "dynamic_range": 4.5,
            "peak_to_loudness": 3.8, "key_note": "F", "scale_mode": "minor",
            "lyrical_density": 65.0, "has_explicit": True, "language": "hindi",
        }
    },
    {
        "track_id": "raftaar-goat-dekho",
        "file_path": "sample://Raftaar_GOAT_Dekho.mp3",
        "title": "GOAT Dekho",
        "artist": "Raftaar",
        "album": "Hard Drive Vol. 1",
        "duration": 178.0,
        "file_format": "mp3",
        "features": {
            "title": "GOAT Dekho", "artist": "Raftaar",
            "theme_scores": {"celebration": 0.92, "party": 0.70},
            "primary_theme": "celebration", "primary_emotion": "confident",
            "sentiment_score": 0.55, "perspective": "first",
            "tempo_bpm": 92.0, "energy_level": 0.88, "arousal": 0.85,
            "valence_audio": 0.75, "danceability": 0.80,
            "beat_strength": 0.82, "onset_rate": 2.8, "rhythm_complexity": 0.40,
            "percussive_strength": 0.85, "harmonic_ratio": 0.55,
            "acoustic_score": 0.20, "vocal_presence": 0.82,
            "loudness_lufs": -8.0, "rms_energy": 0.32, "dynamic_range": 5.0,
            "peak_to_loudness": 4.0, "key_note": "G", "scale_mode": "minor",
            "lyrical_density": 50.0, "has_explicit": False, "language": "hindi",
        }
    }
]

def seed(db_path="thm.db"):
    orig_db = Path(r"C:\Users\LENOVO\thm\thm.db")
    target = Path(db_path)
    if orig_db.exists() and not target.exists():
        import shutil
        shutil.copy2(orig_db, target)
        print(f"Copied analyzed production database ({orig_db}) to {target}")
        return

    conn = db.connect(db_path)
    for t in BENCHMARK_TRACKS:
        tid = t["track_id"]
        db.upsert_track(conn, t["file_path"], t["title"], t["artist"], t["album"], t["duration"], t["file_format"])
        f = t["features"]
        db.save_features(conn, tid, f)
        db.save_lyrical(conn, tid, {
            "language": f.get("language", "punjabi"),
            "primary_theme": f.get("primary_theme", "unclassified"),
            "theme_scores": f.get("theme_scores", {}),
            "primary_emotion": f.get("primary_emotion", "neutral"),
            "sentiment_score": f.get("sentiment_score", 0.0),
            "word_count": int(f.get("lyrical_density", 20) * 3),
            "lyrical_density": f.get("lyrical_density", 20.0),
            "perspective": f.get("perspective", "first"),
            "has_explicit": f.get("has_explicit", False),
            "script": "latin",
        })
    conn.close()
    print(f"Seeded {len(BENCHMARK_TRACKS)} benchmark tracks into {db_path}")

if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else "thm.db"
    seed(db_file)
