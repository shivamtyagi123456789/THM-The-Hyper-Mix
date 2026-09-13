"""
Automated validation of THM web server and API layer.
"""

import os
import sys
import unittest

sys.path.insert(0, r"C:\Users\LENOVO\thm")
from app import app, queue_manager

class TestTHMAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_index_page(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"TRUE HYPER MIXING", res.data)
        self.assertIn(b"STUDIO MASTERING CONSOLE", res.data)
        self.assertIn(b"FEATURED ARTIST SHOWCASE", res.data)

    def test_posters_endpoint(self):
        res = self.client.get("/api/posters")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("posters", data)
        self.assertEqual(len(data["posters"]), 5)
        titles = [p["title"] for p in data["posters"]]
        self.assertIn("Woh Raat", titles)
        self.assertIn("Saza-e-Maut", titles)
        self.assertIn("GOAT Dekho", titles)
        self.assertIn("Nahi Hai Woh", titles)
        self.assertIn("Top Off", titles)

    def test_tracks_endpoint(self):
        res = self.client.get("/api/tracks")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertGreaterEqual(data["total"], 90)
        self.assertTrue(len(data["tracks"]) >= 90)

    def test_queue_init_and_arc(self):
        # Find a seed track
        sample_id = next(iter(queue_manager.library.keys()))
        res = self.client.post("/api/queue/init", json={"track_id": sample_id, "queue_depth": 5})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("current_track", data)
        self.assertIn("queue", data)
        self.assertGreaterEqual(len(data["queue"]), 3)

        # Test arc change
        res_arc = self.client.post("/api/queue/arc", json={"mode": "rising"})
        self.assertEqual(res_arc.status_code, 200)
        arc_data = res_arc.get_json()
        self.assertEqual(arc_data["arc_mode"], "rising")

        # Test explanation
        candidate_id = data["queue"][0]["track_id"]
        res_exp = self.client.get(f"/api/explain/{sample_id}/{candidate_id}")
        self.assertEqual(res_exp.status_code, 200)
        exp_data = res_exp.get_json()
        self.assertIn("overall_score", exp_data)
        self.assertIn("top_matching_dimensions", exp_data)

    def test_lyrics_endpoint(self):
        # Find a track with lyrics
        tracks_with_lyrics = [tid for tid, tr in queue_manager.library.items() if (tr.get("word_count") or 0) > 0]
        if tracks_with_lyrics:
            tid = tracks_with_lyrics[0]
            res = self.client.get(f"/api/lyrics/{tid}")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("has_lyrics"))
            self.assertGreater(len(data.get("lines", [])), 0)

if __name__ == "__main__":
    unittest.main()
