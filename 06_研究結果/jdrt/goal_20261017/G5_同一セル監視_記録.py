"""Compatibility entrypoint; canonical repeated monitoring lives in the runner skill."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[3]
    runpy.run_path(str(root / '.agents/skills/joso-jdrt-runner/scripts/choice_monitor.py'), run_name='__main__')
