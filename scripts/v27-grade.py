"""Reuse the existing postgame grader; never touch the six V26 targets."""
import runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    ns=runpy.run_path(str(ROOT/'scripts/v26-grade.py'))
    ns['main'](snapshot_paths={'V27RollingR1':ROOT/'docs/research/V27_PROSPECTIVE_R1.json.gz',
                              'V27BankR2':ROOT/'docs/research/V27_BANK_GRADE_INPUT_R2.json.gz'},
               output_root=ROOT/'artifacts/evidence-and-joint-v27/grades',public_prefix='V27')
