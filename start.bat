@echo off

REM Check if .venv exists
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate
    echo Installing requirements...
    pip install Flask Flask-CORS requests
)

call .venv\Scripts\activate

REM Check if messages.db exists
if not exist messages.db (
    echo Processing messages...
    python parse_message.py
)

echo Starting server...
python server.py

start http://localhost:5000/
pause