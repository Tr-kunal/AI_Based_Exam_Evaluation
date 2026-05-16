"""
AI Evaluation Routes
=====================

FastAPI routes for AI-powered answer evaluation.
Integrates extraction and evaluation models.
"""

from fastapi import APIRouter, HTTPException, status
import logging
from datetime import datetime
import os
from pathlib import Path
from bson import ObjectId
import numpy as np

# centralized DB
from database import uploads

# logging
logger = logging.getLogger("ai_routes")
logging.basicConfig(level=logging.INFO)

from models.extraction_service import (
    extract_student_answers,
    extract_question_paper,
    ExtractionError
)
from models.evaluation_service import (
    evaluate_answers,
    generate_feedback,
    EvaluationError
)

router = APIRouter()

# File paths
BASE_DIR = Path(__file__).parent.parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
KEY_FOLDER = UPLOAD_FOLDER / "keys"
DESCRIPTIVE_FOLDER = UPLOAD_FOLDER / "answers" / "descriptive"


def serialize_clean(obj):
    """Recursively convert MongoDB ObjectIds, numpy types, and sets to JSON-friendly types"""
    try:
        if isinstance(obj, list):
            return [serialize_clean(i) for i in obj]
        if isinstance(obj, tuple):
            return [serialize_clean(i) for i in obj]
        if isinstance(obj, set):
            return [serialize_clean(i) for i in obj]
        if isinstance(obj, dict):
            return {k: serialize_clean(v) for k, v in obj.items()}
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, (np.intc, np.intp, np.int8,
            np.int16, np.int32, np.int64, np.uint8,
            np.uint16, np.uint32, np.uint64)):
            return int(obj)
        if isinstance(obj, (np.float16, np.float32, np.float64)):
            if np.isnan(obj) or np.isinf(obj):
                return 0.0
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return serialize_clean(obj.tolist())
        return obj
    except Exception as e:
        print(f"⚠️ Serialization error for {type(obj)}: {e}")
        return str(obj)


@router.post("/api/ai-evaluate/{roll_number}")
async def ai_evaluate_submission(roll_number: str):
    """
    AI-powered evaluation of a student submission.
    
    Process:
    1. Find the pending submission by roll number
    2. Extract student answers from their uploaded PDF
    3. Find and extract model answers from teacher's answer key
    4. Run evaluation model to compare answers
    5. Update submission with marks and feedback
    
    Args:
        roll_number: Student's roll number
        
    Returns:
        Evaluation results with marks and feedback
    """
    # Find the pending submission
    logger.info(f"Evaluating {roll_number}")
    
    submission = uploads.find_one({
        "roll_number": roll_number,
        "status": "pending",
        "type": "answer_sheet"
    }, sort=[("timestamp", -1)])
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pending submission found for roll number {roll_number}"
        )
    
    # Check if it's a descriptive answer sheet (AI evaluation only for descriptive)
    if submission.get("answer_sheet_type", "").lower() != "descriptive":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI evaluation is only available for descriptive answer sheets"
        )
    
    try:
        # Step 1: Extract student answers from their PDF
        student_files = submission.get("files", [])
        if not student_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files found in submission"
            )
        
        # Use the first PDF file
        student_pdf = DESCRIPTIVE_FOLDER / student_files[0]
        if not student_pdf.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student answer file not found: {student_files[0]}"
            )
        
        logger.info(f"📄 Extracting student answers from: {student_pdf}")
        student_answers = extract_student_answers(str(student_pdf))
        
        # Step 2: Find the answer key for this exam
        exam_name = submission.get("exam_name", "")
        subject = submission.get("subject", "")
        
        # Try to find matching answer key
        answer_key = uploads.find_one({
            "type": "answer_key",
            "exam_name": exam_name,
            "subject": subject
        })
        
        # Fallback: if no exact match, try finding any key (for backward compatibility or testing)
        if not answer_key:
            print(f"⚠️ No exact answer key match for {exam_name} ({subject}). Using latest uploaded key.")
            answer_key = uploads.find_one({
                "type": "answer_key"
            }, sort=[("timestamp", -1)])
        
        if not answer_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No answer key found. Teacher must upload answer key first."
            )
        
        # Step 3: Extract model answers from answer key PDF
        key_filename = answer_key.get("filename")
        key_pdf = KEY_FOLDER / key_filename
        
        if not key_pdf.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Answer key file not found: {key_filename}"
            )
        
        logger.info(f"📚 Extracting model answers from: {key_pdf}")
        model_answers = extract_question_paper(str(key_pdf))
        
        # Step 4: Run evaluation
        logger.info("🤖 Running AI evaluation...")
        logger.debug(f"Model keys: {model_answers.keys() if model_answers else 'None'}")
        logger.debug(f"Student keys: {student_answers.keys() if student_answers else 'None'}")
        
        try:
            evaluation_report = evaluate_answers(model_answers, student_answers)
        except Exception as eval_err:
            print(f"❌ Evaluation internal error: {eval_err}")
            import traceback
            traceback.print_exc()
            raise eval_err
        
        # Step 5: Generate feedback
        feedback = generate_feedback(evaluation_report)
        
        # Extract key metrics
        total_awarded = evaluation_report.get("total_awarded", 0)
        total_max = evaluation_report.get("total_max", 100)
        percentage = evaluation_report.get("percentage", 0)
        
        # Step 6: Update submission in database
        uploads.update_one(
            {"roll_number": roll_number, "status": "pending"},
            {"$set": {
                "status": "evaluated",
                "marks_obtained": round(total_awarded, 2),
                "total_marks": round(total_max, 2),
                "percentage": round(percentage, 2),
                "feedback": feedback,
                "evaluation_report": evaluation_report,
                "evaluated_on": datetime.now().isoformat(),
                "evaluation_method": "AI"
            }}
        )
        
        # Debug log the report
        logger.info(f"Report type: {type(evaluation_report)}")
        logger.debug(f"Report content: {str(evaluation_report)[:2000]}")

        return serialize_clean({
            "message": f"✅ AI Evaluation complete for Roll No {roll_number}",
            "marks_obtained": round(total_awarded, 2),
            "total_marks": round(total_max, 2),
            "percentage": round(percentage, 2),
            "feedback": feedback,
            "detailed_report": evaluation_report
        })
        
    except ExtractionError as e:
        logger.error(f"Extraction failed for roll number {roll_number}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )
    except EvaluationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during AI evaluation: {str(e)}"
        )


@router.get("/api/evaluation-config")
async def get_evaluation_config():
    """
    Get the current evaluation configuration.
    
    Returns:
        Configuration dictionary with weights and thresholds
    """
    from models.evaluation_service import get_evaluation_config
    
    config = get_evaluation_config()
    return {
        "config": config,
        "description": "Current AI evaluation configuration"
    }


@router.get("/api/evaluation-report/{roll_number}")
async def get_evaluation_report(roll_number: str):
    """
    Get detailed evaluation report for a student.
    
    Args:
        roll_number: Student's roll number
        
    Returns:
        Detailed evaluation report if available
    """
    submission = uploads.find_one({
        "roll_number": roll_number,
        "status": "evaluated",
        "type": "answer_sheet"
    })
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evaluated submission found for roll number {roll_number}"
        )
    
    evaluation_report = submission.get("evaluation_report")
    
    if not evaluation_report:
        return {
            "message": "Submission was evaluated manually, no detailed AI report available",
            "marks_obtained": submission.get("marks_obtained", 0),
            "total_marks": submission.get("total_marks", 100),
            "feedback": submission.get("feedback", "")
        }
    
    return serialize_clean({
        "roll_number": roll_number,
        "exam_name": submission.get("exam_name", ""),
        "subject": submission.get("subject", ""),
        "marks_obtained": submission.get("marks_obtained", 0),
        "total_marks": submission.get("total_marks", 100),
        "percentage": submission.get("percentage", 0),
        "feedback": submission.get("feedback", ""),
        "evaluated_on": submission.get("evaluated_on", ""),
        "evaluation_method": submission.get("evaluation_method", "manual"),
        "detailed_report": evaluation_report
    })
