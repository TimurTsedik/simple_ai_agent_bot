import sys
from pathlib import Path


projectRootPath = Path(__file__).resolve().parents[1]
projectRoot = str(projectRootPath)
if projectRoot not in sys.path:
    sys.path.insert(0, projectRoot)

