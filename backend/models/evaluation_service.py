"""
Evaluation Service Wrapper
===========================

This module provides a clean interface to the integrated evaluation model
for use in FastAPI endpoints. It wraps the functionality from 
Final_Model_Descriptive/integrated_evaluation.py

Functions:
    - evaluate_answers(model_answers, student_answers): Evaluate student answers against model
    - get_evaluation_config(): Get current evaluation configuration
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Add the evaluation model directory to Python path
EVALUATION_DIR = Path(__file__).parent.parent / "Final_Model_Descriptive"
sys.path.insert(0, str(EVALUATION_DIR))

try:
    from integrated_evaluation import (
        evaluate_student_answers,
        CONFIG as EVAL_CONFIG
    )
except ImportError as e:
    print(f"⚠️ Warning: Could not import evaluation module: {e}")
    evaluate_student_answers = None
    EVAL_CONFIG = None


class EvaluationError(Exception):
    """Custom exception for evaluation errors"""
    pass


def evaluate_answers(
    model_answers: Dict[str, Any],
    student_answers: Dict[str, Any],
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Evaluate student answers against model answers.
    
    Args:
        model_answers: Dictionary containing model answers with structure:
            {
                "questions": [
                    {
                        "question_number": "Q1",
                        "total_marks": 10,
                        "subparts": [
                            {
                                "id": "a",
                                "question": "...",
                                "model_answer": "...",
                                "marks": 5
                            }
                        ]
                    }
                ]
            }
        student_answers: Dictionary containing student answers
        config: Optional custom configuration (uses default if None)
        
    Returns:
        Evaluation report dictionary with structure:
        {
            "total_awarded": 45.5,
            "total_max": 100.0,
            "percentage": 45.5,
            "by_question": {
                "Q1": {
                    "policy": {...},
                    "subparts": {
                        "a": {
                            "semantic_score": 0.85,
                            "keyword_score": 0.75,
                            "score": 0.83,
                            "marks": 4.25
                        }
                    },
                    "total_marks": 10.0,
                    "final_score": 8.5,
                    "notes": []
                }
            }
        }
        
    Raises:
        EvaluationError: If evaluation fails
    """
    if evaluate_student_answers is None:
        raise EvaluationError("Evaluation module not available. Check dependencies.")
    
    try:
        # Use default config if none provided
        if config is None:
            config = EVAL_CONFIG
        
        # Create temporary JSON files for the evaluation function
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as model_file:
            json.dump(model_answers, model_file, ensure_ascii=False)
            model_path = model_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as student_file:
            json.dump(student_answers, student_file, ensure_ascii=False)
            student_path = student_file.name
        
        try:
            # Run evaluation
            report = evaluate_student_answers(model_path, student_path, config)
            return report
            
        finally:
            # Clean up temporary files
            try:
                os.unlink(model_path)
                os.unlink(student_path)
            except:
                pass
                
    except Exception as e:
        raise EvaluationError(f"Failed to evaluate answers: {str(e)}")


def get_evaluation_config() -> Dict[str, Any]:
    """
    Get the current evaluation configuration.
    
    Returns:
        Configuration dictionary with weights, thresholds, and settings
    """
    if EVAL_CONFIG is None:
        # Return default config if module not available
        return {
            "weights": {
                "semantic": 0.8,
                "keyword": 0.2
            },
            "thresholds": {
                "min_partial_score": 0.20,
                "mcq_min_correct_score": 0.60,
                "min_length_ratio": 0.15,
                "length_penalty_strength": 0.4
            }
        }
    
    return EVAL_CONFIG


def format_evaluation_summary(report: Dict[str, Any]) -> str:
    """
    Format evaluation report into a human-readable summary.
    
    Args:
        report: Evaluation report dictionary
        
    Returns:
        Formatted summary string
    """
    total_awarded = report.get("total_awarded", 0)
    total_max = report.get("total_max", 0)
    percentage = report.get("percentage", 0)
    
    summary_lines = [
        f"Total Score: {total_awarded:.2f} / {total_max:.2f}",
        f"Percentage: {percentage:.2f}%",
        "",
        "Question-wise Breakdown:"
    ]
    
    by_question = report.get("by_question", {})
    for qno, qdata in by_question.items():
        final_score = qdata.get("final_score", 0)
        total_marks = qdata.get("total_marks", 0)
        summary_lines.append(f"  {qno}: {final_score:.2f} / {total_marks:.2f}")
        
        # Add notes if any
        notes = qdata.get("notes", [])
        for note in notes:
            summary_lines.append(f"    ℹ️ {note}")
    
    return "\n".join(summary_lines)


def generate_feedback(report: Dict[str, Any]) -> str:
    """
    Generate constructive feedback based on evaluation report.
    
    Args:
        report: Evaluation report dictionary
        
    Returns:
        Feedback string
    """
    percentage = report.get("percentage", 0)
    
    if percentage >= 90:
        feedback = "Excellent work! Your answers demonstrate strong understanding of the concepts."
    elif percentage >= 75:
        feedback = "Good effort! Your answers show solid grasp of most topics."
    elif percentage >= 60:
        feedback = "Satisfactory performance. Focus on improving conceptual clarity and detail."
    elif percentage >= 40:
        feedback = "Needs improvement. Review the topics and practice writing more detailed answers."
    else:
        feedback = "Significant improvement needed. Please review the course material thoroughly."
    
    # Add specific suggestions based on low-scoring questions
    by_question = report.get("by_question", {})
    low_scoring = [
        qno for qno, qdata in by_question.items()
        if (qdata.get("final_score", 0) / max(qdata.get("total_marks", 1), 1)) < 0.5
    ]
    
    if low_scoring:
        feedback += f"\n\nFocus on improving: {', '.join(low_scoring)}"
    
    return feedback
