@echo off
REM FastAPI Server Startup Script
REM This script activates the virtual environment and starts the FastAPI server

echo ========================================
echo Starting FastAPI Backend Server
echo ========================================
echo.

REM Activate virtual environment
cd /d "%~dp0"
call venv\Scripts\activate

REM Check if GROQ_API_KEY is set
if "%GROQ_API_KEY%"=="" (
    echo WARNING: GROQ_API_KEY is not set!
    echo AI evaluation features will not work without it.
    echo Set it with: set GROQ_API_KEY=your_api_key_here
    echo.
)

REM Start FastAPI server with uvicorn
REM Use PORT env var if present (Render provides %PORT%)
if "%PORT%"=="" (
    set PORT=5000
)
echo Starting server at http://127.0.0.1:%PORT%
echo Press Ctrl+C to stop the server
echo.
echo API Documentation will be available at:
echo - Swagger UI: http://127.0.0.1:%PORT%/docs
echo - ReDoc: http://127.0.0.1:%PORT%/redoc
echo.

uvicorn fastapi_app:app --host 127.0.0.1 --port %PORT% --reload
