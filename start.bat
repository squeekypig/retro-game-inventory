@echo off
REM The Anthropic API key is loaded from the gitignored .env file (see .env.example).
echo Starting RetroVault...
echo Open http://localhost:8000 in your browser
echo Press Ctrl+C to stop
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
