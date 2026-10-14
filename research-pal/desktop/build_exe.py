"""Prepare the files for the Windows .exe. Run:  python desktop/build_exe.py
Then:  cd desktop/electron && npm run dist      (the installer is made in desktop/electron/dist)

The stage folder (desktop/electron/stage) gets:
- python/  a private copy of Python and the packages of .venv, so the installed app needs no Python on the computer,
- server/  the backend code, desktop/app.py and the UI (desktop/ui).
Secrets are never copied: backend/.env is not part of the stage. Each person adds their own keys in settings.env.
"""
import shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STAGE = HERE / "electron" / "stage"
VENV = ROOT / ".venv"
BASE = Path(subprocess.check_output([str(VENV / "Scripts" / "python.exe"), "-c", "import sys; print(sys.base_prefix)"], text=True).strip())

LIB_SKIP = shutil.ignore_patterns("__pycache__", "test", "idlelib", "turtledemo", "tkinter", "ensurepip", "site-packages")
PKG_SKIP = shutil.ignore_patterns("__pycache__", "pip", "pip-*", "pytest", "pytest-*", "_pytest")


def main() -> None:
    if not (HERE / "ui" / "index.html").exists():
        raise SystemExit("The UI is not built. Run first:  python desktop/build_ui.py")
    shutil.rmtree(STAGE, ignore_errors=True)
    py = STAGE / "python"
    py.mkdir(parents=True)

    print("1/4 Python", BASE)
    for name in ("python.exe", "pythonw.exe", "python3.dll", "LICENSE.txt", *[f.name for f in BASE.glob("python3*.dll")], *[f.name for f in BASE.glob("vcruntime*.dll")]):
        if (BASE / name).exists():
            shutil.copy2(BASE / name, py / name)
    shutil.copytree(BASE / "DLLs", py / "DLLs", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(BASE / "Lib", py / "Lib", ignore=LIB_SKIP)

    print("2/4 packages of .venv")
    shutil.copytree(VENV / "Lib" / "site-packages", py / "Lib" / "site-packages", ignore=PKG_SKIP)

    print("3/4 server files (no .env)")
    srv = STAGE / "server"
    shutil.copytree(ROOT / "backend" / "app", srv / "backend" / "app", ignore=shutil.ignore_patterns("__pycache__"))
    (srv / "desktop").mkdir(parents=True)
    shutil.copy2(HERE / "app.py", srv / "desktop" / "app.py")
    shutil.copytree(HERE / "ui", srv / "desktop" / "ui")

    print("4/4 compile (faster first start) and check")
    exe = str(py / "python.exe")
    subprocess.run([exe, "-I", "-m", "compileall", "-q", "-j", "0", str(py / "Lib")])  # errors in packages for other Python versions are normal
    subprocess.run([exe, "-I", "-m", "compileall", "-q", str(srv)])
    subprocess.run([exe, "-I", "-c", "import fastapi, uvicorn, chromadb, pypdf, httpx, dotenv, piper; print('imports OK')"], check=True)
    mb = sum(f.stat().st_size for f in STAGE.rglob("*") if f.is_file()) / 1e6
    print(f"Stage is ready: {STAGE}  ({mb:,.0f} MB)")


if __name__ == "__main__":
    main()
