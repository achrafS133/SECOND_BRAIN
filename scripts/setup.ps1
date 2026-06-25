@echo off
cd /d %~dp0..
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -e ".[dev]"
copy /Y .env.example .env
echo Setup complete. Edit .env and run: second-brain-api
