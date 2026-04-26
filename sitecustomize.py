# sitecustomize.py
# Place this in the project root alongside run.py
# Automatically adds the project root to sys.path when any script runs
# so "from graph.state import ..." works without run.py

import sys
import pathlib

root = pathlib.Path(__file__).parent.resolve()
if str(root) not in sys.path:
    sys.path.insert(0, str(root))