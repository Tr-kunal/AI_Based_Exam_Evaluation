# AI-Based Answer Sheet Evaluation System

Automated examination grading system using ML/NLP. Teachers upload answer keys, students submit handwritten answer sheets, and the AI evaluates them using semantic similarity and keyword matching.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Database** | MongoDB (Atlas or local) |
| **AI/ML** | Sentence Transformers, YAKE, Groq AI (Llama 3.3) |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |

## Quick Start

### 1. Clone & Setup

```bash
git clone <repo-url>
cd AI_Based_Exam_Evaluation/backend
python -m venv venv
```

### 2. Activate Environment

```powershell
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (CMD)
.\venv\Scripts\activate.bat

# Linux / macOS
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials:
#   MONGODB_URI=mongodb+srv://...
#   GROQ_API_KEY=gsk_...
```

### 5. Run Backend

```bash
uvicorn fastapi_app:app --reload --host 127.0.0.1 --port 5000
```

### 6. Open Frontend

Open `frontend/HTML Files/index.html` in your browser, or use VS Code Live Server.

## API Documentation

Once the backend is running, visit:
- **Swagger UI**: http://127.0.0.1:5000/docs
- **ReDoc**: http://127.0.0.1:5000/redoc

## Project Structure

```
AI_Based_Exam_Evaluation/
├── backend/
│   ├── fastapi_app.py              # Main FastAPI application
│   ├── database.py                 # MongoDB connection (resilient)
│   ├── requirements.txt
│   ├── .env.example
│   ├── start_server.bat
│   ├── routes/
│   │   └── ai_routes.py            # AI evaluation endpoints
│   ├── models/
│   │   ├── extraction_service.py   # Groq PDF extraction wrapper
│   │   └── evaluation_service.py   # ML evaluation wrapper
│   ├── Final_Model_Descriptive/
│   │   ├── integrated_evaluation.py    # Sentence Transformers + YAKE scorer
│   │   └── Extraction_modelanswers/
│   │       └── integrated_extraction.py  # Groq-based PDF extractor
│   └── uploads/                    # User uploads (gitignored)
├── frontend/
│   ├── HTML Files/
│   │   ├── index.html              # Landing page
│   │   ├── login.html
│   │   ├── signup.html
│   │   ├── teacher-dashboard.html
│   │   └── student-dashboard.html
│   ├── CSS Files/
│   │   ├── global.css
│   │   ├── landing.css
│   │   ├── auth.css
│   │   └── dashboard.css
│   └── js/
│       ├── auth.js                 # Login/Signup API calls
│       ├── dashboard.js            # Dashboard API integration
│       ├── theme.js
│       ├── landing.js
│       └── chart.js
└── ml/                             # Standalone ML experiments
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGODB_URI` | Yes | MongoDB connection string |
| `DB_NAME` | No | Database name (default: `exam_system`) |
| `GEMINI_API_KEY` | For AI | Gemini API key for PDF extraction |
| `BASE_URL` | No | Backend URL (default: `http://127.0.0.1:5000`) |
| `FRONTEND_BASE_URL` | No | Frontend URL (default: `http://127.0.0.1:5500`) |
| `PORT` | No | Server port (default: `5000`) |

