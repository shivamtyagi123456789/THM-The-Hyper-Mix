import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app, DB_PATH
from scripts.seed_fixtures import seed

if not os.path.exists(DB_PATH):
    print("Database not found. Seeding benchmark fixtures...")
    seed(DB_PATH)

port = int(os.environ.get("PORT", 5000))
print("\n=======================================================")
print("  TRUE HYPER MIXING (THM) - VIBE PRESERVATION ENGINE")
print(f"  Server running on http://127.0.0.1:{port}")
print("=======================================================\n")
app.run(host="0.0.0.0", port=port, debug=True)
