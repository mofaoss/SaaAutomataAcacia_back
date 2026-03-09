#!/usr/bin/env python
# coding:utf-8
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(cmd, timeout=120):
    p = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return p.returncode, p.stdout, p.stderr


def check_compile():
    code, out, err = run([sys.executable, "-m", "compileall", "app"], timeout=180)
    if code != 0:
        return False, f"compileall failed\n{out}\n{err}"

    code, out, err = run([sys.executable, "-m", "py_compile", "SAA.py"])
    if code != 0:
        return False, f"SAA.py py_compile failed\n{out}\n{err}"
    return True, "compile checks passed"


def check_runtime_start():
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, "SAA.py"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        time.sleep(8)
        code = proc.poll()
        if code is not None and code != 0:
            out, err = proc.communicate(timeout=5)
            return False, f"SAA.py exited early with code {code}\nSTDOUT:\n{out}\nSTDERR:\n{err}"

        # consider still-running process as successful startup
        return True, "SAA.py started successfully (process running after 8s)"
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def main():
    ok, msg = check_compile()
    print(msg)
    if not ok:
        return 1

    ok, msg = check_runtime_start()
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

