"""Compatibility wrapper for the skillized 14-setting smoke sequence."""
from pathlib import Path
import runpy


SKILL_SCRIPT = Path(__file__).resolve().parents[3] / '.agents/skills/joso-jdrt-runner/scripts/choice_smoke_sequence.py'
runpy.run_path(str(SKILL_SCRIPT), run_name='__main__')
