"""Run every research project's test suite. Works on Windows, macOS and Linux.
Usage: python run_checks.py"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SUITES = [("mosaic", "tests/test_core.py"), ("opensight", "tests/test_optics.py"), ("lohc", "tests/test_lohc.py")]
failed = []
for folder, test in SUITES:
    cwd = os.path.join(ROOT, folder)
    env = dict(os.environ, PYTHONPATH=cwd, OMP_NUM_THREADS="1")
    print(f"== {folder} ==", flush=True)
    r = subprocess.run([sys.executable, test], cwd=cwd, env=env)
    if r.returncode != 0:
        failed.append(folder)
print("\nALL CHECKS PASSED" if not failed else f"\nFAILED: {', '.join(failed)}")
sys.exit(1 if failed else 0)
