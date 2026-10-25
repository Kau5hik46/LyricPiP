@echo off
REM Convenience launcher for Windows: creates a venv on first run, then starts the app.
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\python -m lyricpip %*
