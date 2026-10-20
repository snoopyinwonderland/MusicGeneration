"""musigen: composition from a written request - spec -> chords -> tune -> lead sheet -> musicomp arrangement.

musicomp (K:\\Music Composition, github.com/snoopyinwonderland/MusicComposition) is used as a library, not copied:
its chord statistics, spelling, MusicXML reading and the whole arrangement pipeline.  It is not a pip package, so
its folder is put on sys.path: MUSICOMP_ROOT, else the sibling folder 'Music Composition'.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUSICOMP_ROOT = Path(os.environ.get("MUSICOMP_ROOT") or ROOT.parent / "Music Composition")
if not (MUSICOMP_ROOT / "musicomp").is_dir():
    raise ImportError(f"musicomp not found at {MUSICOMP_ROOT} - set MUSICOMP_ROOT to the Music Composition folder")
if str(MUSICOMP_ROOT) not in sys.path:
    sys.path.insert(0, str(MUSICOMP_ROOT))
