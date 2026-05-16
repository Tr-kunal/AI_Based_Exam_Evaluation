"""
FastAPI Backend Application
============================

Main FastAPI application for AI-Based Answer Sheet Evaluation.
Integrates AI models for automated answer evaluation.

Author: AI Evaluator System
Version: 2.0 (FastAPI)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError
from pathlib import Path
from dotenv import load_dotenv
import logging
import os
import re
import shutil
from typing import List, Optional
import datetime
import json

# Import centralized database collections
from database import client, db, users, exams, uploads

# Import AI routes
from routes.ai_routes import router as ai_router

# Load env before anything else
load_dotenv()

# logging
logger = logging.getLogger("fastapi_app")
logging.basicConfig(level=logging.INFO)

# Environment mode
ENV = os.environ.get('ENV', 'development').lower()
IS_PRODUCTION = ENV == 'production'

# Base URL used when generating file URLs (can be overridden in env)
BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')
FRONTEND_BASE_URL = os.environ.get('FRONTEND_BASE_URL', 'http://127.0.0.1:5500')

# Folder configuration
BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = Path(os.environ.get('UPLOAD_FOLDER', str(BASE_DIR / "uploads")))
KEY_FOLDER = UPLOAD_FOLDER / "keys"
ANSWER_FOLDER = UPLOAD_FOLDER / "answers"
DESCRIPTIVE_FOLDER = ANSWER_FOLDER / "descriptive"
OMR_FOLDER = ANSWER_FOLDER / "omr"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}


# ---------------------------------------------------------------------------
# Pure-Python replacement for werkzeug.utils.secure_filename
# ---------------------------------------------------------------------------
_FILENAME_STRIP_RE = re.compile(r'[^\w\s\-.]')
_FILENAME_MULTI_SPACE = re.compile(r'\s+')


def secure_filename(filename: str) -> str:
    """Return a safe version of a filename.

    Strips path separators and special characters, collapses whitespace,
    and ensures the name is never empty.
    """
    # Keep only the basename (handles Windows & Unix paths)
    for sep in (os.sep, os.altsep, '/', '\\'):
        if sep:
            filename = filename.split(sep)[-1]

    filename = _FILENAME_STRIP_RE.sub('', filename)
    filename = _FILENAME_MULTI_SPACE.sub('_', filename).strip('._')
    return filename or 'unnamed'


# ---------------------------------------------------------------------------
# Lifespan handler (replaces deprecated @app.on_event)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if IS_PRODUCTION:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown tasks."""
    # --- STARTUP ---
    logger.info(f"Environment: {ENV}")

    # Validate critical env vars
    if IS_PRODUCTION and not os.environ.get('MONGODB_URI'):
        logger.error("[FATAL] MONGODB_URI is required in production")
    if not os.environ.get('GROQ_API_KEY'):
        logger.warning("[WARN] GROQ_API_KEY not set - AI features will be unavailable")

    # Create upload directories
    for folder in [KEY_FOLDER, DESCRIPTIVE_FOLDER, OMR_FOLDER]:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create folder {folder}: {e}")

    # Verify DB connectivity
    try:
        client.admin.command('ping')
        logger.info("[OK] Connected to MongoDB")
    except Exception as e:
        logger.warning(f"[WARN] Could not connect to MongoDB: {e}")

    yield  # app runs here

    # --- SHUTDOWN ---
    logger.info("Shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="AI-Based Answer Sheet Evaluation System",
    description="Automated answer evaluation using ML/NLP models",
    version="2.0",
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
)


# Exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


# CORS configuration – locked down in production
if IS_PRODUCTION:
    _origins = [origin.strip() for origin in os.environ.get('ALLOWED_ORIGINS', FRONTEND_BASE_URL).split(',')]
else:
    _origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=IS_PRODUCTION,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)


# Helper functions
def allowed_file(filename: str) -> bool:
    """Check if file has allowed extension"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_url(folder: str, subfolder: str, filename: str) -> str:
    """Generate file URL"""
    return f"{BASE_URL}/uploads/{folder}/{subfolder}/{filename}"


# Routes

@app.get("/")
async def home():
    """Root endpoint"""
    return {"message": "FastAPI backend is running!", "version": "2.0"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    status_obj = {"app": "ok"}
    try:
        client.admin.command('ping')
        status_obj['db'] = 'ok'
    except Exception as e:
        status_obj['db'] = f'error: {str(e)}'

    for p in [UPLOAD_FOLDER, KEY_FOLDER, DESCRIPTIVE_FOLDER, OMR_FOLDER]:
        status_obj[str(p)] = 'exists' if p.exists() else 'missing'

    return status_obj


@app.post("/api/signup")
async def signup(request: Request):
    """User signup endpoint"""
    data = await request.json()

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data received"
        )

    if users.find_one({"email": data.get("email")}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )

    users.insert_one({
        "fullname": data.get("fullname", ""),
        "email": data.get("email", ""),
        "password": data.get("password", ""),   # TODO: hash in production
        "role": data.get("role", "student")
    })

    return {"message": "Signup successful ✅"}


@app.post("/api/login")
async def login(request: Request):
    """User login endpoint"""
    data = await request.json()

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data received"
        )

    user = users.find_one({
        "email": data.get("email"),
        "password": data.get("password"),
        "role": data.get("role")
    })

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials ❌"
        )

    redirect_url = (
        f"{FRONTEND_BASE_URL}/teacher-dashboard.html"
        if user["role"] == "teacher"
        else f"{FRONTEND_BASE_URL}/student-dashboard.html"
    )

    return {
        "message": f"Welcome, {user['fullname']} ✅",
        "redirect": redirect_url,
        "user": {
            "fullname": user["fullname"],
            "email": user["email"],
            "role": user["role"],
        }
    }


@app.post("/api/upload-key")
async def upload_key(
    file: UploadFile = File(...),
    exam_name: str = Form(...),
    subject: str = Form(...),
    total_marks: str = Form(...),
    key_type: str = Form(...),
    teacher: str = Form("Unknown Teacher")
):
    """Teacher uploads answer key with metadata"""
    logger.info(f"Upload key: file={file.filename}, exam={exam_name}, subject={subject}")

    try:
        total_marks_int = int(total_marks)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Total marks must be a valid number"
        )

    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded"
        )

    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type"
        )

    filename = secure_filename(file.filename)
    save_path = KEY_FOLDER / filename

    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    uploads.insert_one({
        "type": "answer_key",
        "exam_name": exam_name,
        "subject": subject,
        "total_marks": total_marks_int,
        "key_type": key_type,
        "uploaded_by": teacher,
        "filename": filename,
        "file_url": f"{BASE_URL}/uploads/keys/{filename}",
        "timestamp": datetime.datetime.now().isoformat()
    })

    return {"message": "Answer key and exam details uploaded successfully ✅"}


@app.post("/api/upload-answer")
async def upload_answer(
    files: List[UploadFile] = File(...),
    exam_name: str = Form(...),
    subject: str = Form(...),
    roll_number: str = Form(...),
    notes: str = Form(""),
    answer_sheet_type: str = Form("Descriptive"),
    student: str = Form("Unknown Student")
):
    """Student uploads answer sheet"""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded"
        )

    if not (exam_name and subject and roll_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All required fields must be filled"
        )

    try:
        sheet_type = answer_sheet_type.strip().lower()
        folder_path = OMR_FOLDER if sheet_type == "omr" else DESCRIPTIVE_FOLDER

        saved_files = []
        file_urls = []

        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                save_path = folder_path / filename

                with open(save_path, "wb") as f:
                    content = await file.read()
                    f.write(content)

                saved_files.append(filename)
                file_urls.append(get_file_url("answers", sheet_type, filename))

        if not saved_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid files uploaded"
            )

        record = {
            "type": "answer_sheet",
            "exam_name": exam_name,
            "subject": subject,
            "roll_number": roll_number,
            "notes": notes,
            "answer_sheet_type": sheet_type,
            "student": student,
            "files": saved_files,
            "file_urls": file_urls,
            "status": "pending",
            "timestamp": datetime.datetime.now().isoformat()
        }

        uploads.insert_one(record)

        # Remove ObjectId before returning (insert_one mutates the dict)
        record.pop("_id", None)

        return {
            "message": f"{len(saved_files)} file(s) uploaded successfully ✅",
            "data": record
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading files: {str(e)}"
        )


@app.get("/api/get-student-submissions")
async def get_student_submissions(
    roll_number: Optional[str] = None,
    student: Optional[str] = None
):
    """Get student's own submissions"""
    query = {"type": "answer_sheet"}

    if roll_number:
        query["roll_number"] = roll_number
    if student:
        query["student"] = {"$regex": f"^{student}$", "$options": "i"}

    submissions = list(uploads.find(query, {"_id": 0}))
    submissions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {"submissions": submissions}


@app.get("/api/student-submissions")
async def get_all_student_submissions():
    """Teacher views all student submissions"""
    submissions = list(uploads.find({"type": "answer_sheet"}, {"_id": 0}))
    submissions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {"submissions": submissions}


@app.get("/api/pending-answers")
async def get_pending_answers():
    """Get all pending answer sheets"""
    submissions = list(uploads.find({
        "type": "answer_sheet",
        "status": "pending"
    }, {"_id": 0}))
    submissions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {"pending": submissions}


@app.post("/api/start-evaluation/{roll_number}")
async def start_evaluation(roll_number: str):
    """
    Mock AI Evaluation (kept for backward compatibility).
    Use /api/ai-evaluate/{roll_number} for real AI evaluation.
    """
    submission = uploads.find_one({
        "roll_number": roll_number,
        "status": "pending"
    })

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found or already evaluated"
        )

    marks = 60 + (hash(roll_number) % 40)
    feedback = "Good effort! Improve handwriting and conceptual explanations."

    uploads.update_one(
        {"roll_number": roll_number},
        {"$set": {
            "status": "evaluated",
            "marks_obtained": marks,
            "total_marks": 100,
            "feedback": feedback,
            "evaluated_on": datetime.datetime.now().isoformat(),
            "evaluation_method": "mock"
        }}
    )

    return {
        "message": f"✅ Evaluation complete for Roll No {roll_number}",
        "marks_obtained": marks,
        "feedback": feedback
    }


@app.post("/api/evaluate-submission")
async def evaluate_submission(request: Request):
    """Teacher manually evaluates submission"""
    data = await request.json()

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No evaluation data received"
        )

    roll_number = data.get("roll_number")
    exam_name = data.get("exam_name")
    marks_obtained = data.get("marks_obtained")
    total_marks = data.get("total_marks", 100)
    feedback = data.get("feedback", "")

    if not (roll_number and exam_name and marks_obtained is not None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields"
        )

    result = uploads.update_one(
        {"roll_number": roll_number, "exam_name": exam_name},
        {"$set": {
            "status": "evaluated",
            "marks_obtained": marks_obtained,
            "total_marks": total_marks,
            "feedback": feedback,
            "evaluated_on": datetime.datetime.now().isoformat(),
            "evaluation_method": "manual"
        }}
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching submission found"
        )

    return {"message": "✅ Submission evaluated successfully"}


@app.get("/api/dashboard-stats")
async def dashboard_stats():
    """Get dashboard statistics"""
    try:
        total_exams = uploads.count_documents({"type": "answer_key"})
        total_submissions = uploads.count_documents({"type": "answer_sheet"})
        evaluated = uploads.count_documents({
            "type": "answer_sheet",
            "status": "evaluated"
        })
        pending = uploads.count_documents({
            "type": "answer_sheet",
            "status": "pending"
        })

        return {
            "total_exams": total_exams,
            "total_submissions": total_submissions,
            "evaluated": evaluated,
            "pending": pending
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/uploads/{filepath:path}")
async def serve_file(filepath: str):
    """Serve uploaded files"""
    safe_path = UPLOAD_FOLDER / filepath

    if not str(safe_path.resolve()).startswith(str(UPLOAD_FOLDER.resolve())):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized file access attempt"
        )

    if not safe_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {filepath}"
        )

    return FileResponse(safe_path)


@app.get("/api/get-exams")
async def get_exams():
    """Get list of available exams from uploaded answer keys"""
    keys = list(uploads.find({"type": "answer_key"}, {"_id": 0}))

    exam_list = []
    seen = set()

    for key in keys:
        name = key.get("exam_name")
        if not name:
            filename = key.get("filename", "")
            name = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()

        subject = key.get("subject", "General")
        exam_id = f"{name}|{subject}"

        if exam_id not in seen:
            exam_list.append({
                "exam_name": name,
                "subject": subject,
                "filename": key.get("filename")
            })
            seen.add(exam_id)

    return {"exams": exam_list}


# Include AI routes
app.include_router(ai_router)


# Run with: uvicorn fastapi_app:app --reload --host 127.0.0.1 --port 5000
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
