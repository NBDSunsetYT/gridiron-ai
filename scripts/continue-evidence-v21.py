"""Compatibility entry point for the current bounded V21 queue."""
import sys,runpy
from pathlib import Path
sys.argv=[str(Path(__file__).with_name('resume-v21.py')),'--run']
runpy.run_path(sys.argv[0],run_name='__main__')
