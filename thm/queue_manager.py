"""
Playback Queue Manager for True Hyper Mixing (THM).
Complies with PRD Section 6.3 (FR-3.1 - FR-3.10) & Phase 1 architecture.
"""

from typing import Dict, List, Optional, Any
from . import db, similarity as S


class PlaybackQueueManager:
    def __init__(self, db_path: str = "thm.db", history_limit: int = 20):
        self.db_path = db_path
        self.history_limit = history_limit
        self.history: List[str] = []         # Recently played track_ids
        self.queue: List[Dict[str, Any]] = [] # Upcoming candidate objects with scores
        self.current_track_id: Optional[str] = None
        self.arc_mode: str = "steady"        # "steady" | "rising" | "cooling_down"
        self.respect_theme_lock: bool = True
        self.allow_explicit: bool = True
        self.locked_track_ids: set = set()   # Tracks pinned by user
        self.skip_log: List[Dict[str, Any]] = []

        # Load library into memory
        self.refresh_library()

    def refresh_library(self):
        """Reload library data from SQLite database."""
        conn = db.connect(self.db_path)
        try:
            self.library = db.load_library(conn)
        finally:
            conn.close()

    def get_track(self, track_id: str) -> Optional[Dict[str, Any]]:
        return self.library.get(track_id)

    def set_arc(self, mode: str):
        """Set arc trajectory: 'steady', 'rising', 'cooling_down'."""
        if mode in ("steady", "rising", "cooling_down"):
            self.arc_mode = mode
            if self.current_track_id:
                self.generate_queue(self.current_track_id)

    def init_playback(self, track_id: str, queue_depth: int = 10) -> Dict[str, Any]:
        """Start or jump playback from a specific seed/anchor track."""
        if track_id not in self.library:
            raise KeyError(f"Track ID {track_id} not found in library.")

        self.current_track_id = track_id
        if track_id not in self.history:
            self.history.append(track_id)
        if len(self.history) > self.history_limit:
            self.history.pop(0)

        self.generate_queue(track_id, queue_depth=queue_depth)
        return {
            "current_track": self._format_track_summary(track_id),
            "queue": self.queue,
            "history_count": len(self.history),
            "arc_mode": self.arc_mode
        }

    def generate_queue(self, anchor_id: str, queue_depth: int = 10):
        """
        Regenerate upcoming queue using multi-dimensional similarity,
        arc control, theme locks, and history avoidance.
        """
        if anchor_id not in self.library:
            return

        # Prepare sub-library: MUST include anchor_id for rank_neighbours to look up anchor!
        sub_lib = {anchor_id: self.library[anchor_id]}
        for tid, track in self.library.items():
            if tid == anchor_id:
                continue
            if tid in self.history[-self.history_limit:] and tid not in self.locked_track_ids:
                continue
            sub_lib[tid] = track

        arc_val = None
        if self.arc_mode != "steady":
            arc_val = self.arc_mode

        # Run ranking using the proven Phase 1 engine
        results = S.rank_neighbours(
            sub_lib,
            anchor_id,
            limit=queue_depth,
            arc=arc_val,
            respect_theme_lock=self.respect_theme_lock,
            allow_explicit=self.allow_explicit,
        )

        # Fallback if pool is exhausted (FR-3.10 elasticity widening)
        if len(results) < 3 and self.respect_theme_lock:
            fallback_results = S.rank_neighbours(
                sub_lib,
                anchor_id,
                limit=queue_depth,
                arc=arc_val,
                respect_theme_lock=False,
                allow_explicit=self.allow_explicit,
            )
            existing_ids = {r["track_id"] for r in results}
            for fr in fallback_results:
                if fr["track_id"] not in existing_ids:
                    results.append(fr)
                    existing_ids.add(fr["track_id"])
                if len(results) >= queue_depth:
                    break

        # Attach formatted track details
        formatted_queue = []
        for r in results:
            tid = r["track_id"]
            track_data = self.library.get(tid, {})
            item = {
                "track_id": tid,
                "title": track_data.get("title") or "Unknown Title",
                "artist": track_data.get("artist") or "Unknown Artist",
                "album": track_data.get("album") or "",
                "duration": track_data.get("duration") or 0.0,
                "score": r.get("score", 0.0),
                "match_percentage": round(r.get("score", 0.0) * 100, 1),
                "theme": track_data.get("primary_theme") or "unclassified",
                "emotion": track_data.get("primary_emotion") or "neutral",
                "tempo_bpm": track_data.get("tempo_bpm") or 0.0,
                "language": track_data.get("language") or "unknown",
                "contributions": r.get("contributions", {}),
                "tiebreak": r.get("tiebreak"),
                "is_locked": tid in self.locked_track_ids
            }
            formatted_queue.append(item)

        self.queue = formatted_queue

    def next_track(self) -> Optional[Dict[str, Any]]:
        """Advance to the next track in the queue and dynamically replenish."""
        if not self.queue:
            return None

        next_item = self.queue.pop(0)
        new_track_id = next_item["track_id"]

        self.current_track_id = new_track_id
        self.history.append(new_track_id)
        if len(self.history) > self.history_limit:
            self.history.pop(0)

        # Replenish queue if low
        if len(self.queue) < 4:
            self.generate_queue(new_track_id)

        return self._format_track_summary(new_track_id)

    def on_track_skip(self, skipped_track_id: str) -> Optional[Dict[str, Any]]:
        """
        Learning signal: user rejected transition from current_track to skipped_track.
        Log difference and immediately advance to next candidate.
        """
        if self.current_track_id and skipped_track_id in self.library:
            from_track = self.library[self.current_track_id]
            to_track = self.library[skipped_track_id]
            
            event = {
                "from_id": self.current_track_id,
                "to_id": skipped_track_id,
                "from_title": from_track.get("title"),
                "to_title": to_track.get("title"),
                "from_theme": from_track.get("primary_theme"),
                "to_theme": to_track.get("primary_theme"),
            }
            self.skip_log.append(event)

        return self.next_track()

    def lock_track(self, track_id: str, locked: bool = True):
        """Pin/lock a track so regeneration does not evict it."""
        if locked:
            self.locked_track_ids.add(track_id)
        else:
            self.locked_track_ids.discard(track_id)

    def _format_track_summary(self, track_id: str) -> Dict[str, Any]:
        track = self.library.get(track_id, {})
        return {
            "track_id": track_id,
            "title": track.get("title") or "Unknown Title",
            "artist": track.get("artist") or "Unknown Artist",
            "album": track.get("album") or "",
            "duration": track.get("duration") or 0.0,
            "file_path": track.get("file_path"),
            "primary_theme": track.get("primary_theme") or "unclassified",
            "theme_scores": track.get("theme_scores") or {},
            "primary_emotion": track.get("primary_emotion") or "neutral",
            "tempo_bpm": track.get("tempo_bpm") or 0.0,
            "energy_level": track.get("energy_level") or 0.0,
            "valence_audio": track.get("valence_audio") or 0.0,
            "arousal": track.get("arousal") or 0.0,
            "danceability": track.get("danceability") or 0.0,
            "loudness_lufs": track.get("loudness_lufs") or -14.0,
            "acoustic_score": track.get("acoustic_score") or 0.0,
            "vocal_presence": track.get("vocal_presence") or 0.0,
            "language": track.get("language") or "unknown",
            "key_note": track.get("key_note") or "",
            "scale_mode": track.get("scale_mode") or "",
        }
