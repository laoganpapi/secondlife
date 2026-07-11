"""Make the standalone llm_parser importable from inside the slkit package
regardless of how Blender set up sys.path."""

import os
import sys

_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _here not in sys.path:
    sys.path.insert(0, _here)

from llm_parser import parse_llm  # noqa: E402,F401
