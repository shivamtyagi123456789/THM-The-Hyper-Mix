import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from thm.explain import main

if __name__ == "__main__":
    if "--validate" not in sys.argv:
        sys.argv.append("--validate")
    sys.exit(main())
