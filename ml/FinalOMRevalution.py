import cv2
import numpy as np
from collections import OrderedDict
import os

# --- Helper Functions ---

def order_points(pts):
    """Orders the four points of the sheet contour (top-left, top-right, bottom-right, bottom-left)."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def four_point_transform(image, pts):
    """Applies a perspective transform to get a 'birds-eye view' of the document."""
    pass

#Scoring Function

def grade_test(detected_answers: dict, answer_key: dict, marks_correct: int = 4, marks_incorrect: int = -1) -> dict:
    """
    Compares student answers against the master key and calculates the score.
    """
    total_score = 0
    correct_count = 0
    incorrect_count = 0
    unanswered_count = 0
    invalid_count = 0
    
    detailed_results = {}
    
    for q_num, key_answer in answer_key.items():
        
        student_response = detected_answers.get(q_num, "UNANSWERED") 
        
        status = "UNKNOWN"
        score = 0
        
        if student_response == "UNANSWERED":
            status = "UNANSWERED"
            unanswered_count += 1
            score = 0
        elif student_response.startswith("INVALID"):
            # Penalize for multiple marks
            status = "INVALID"
            invalid_count += 1
            score = marks_incorrect 
        elif student_response == key_answer:
            status = "CORRECT"
            correct_count += 1
            score = marks_correct
        else:
            # Response is present but does not match the key
            status = "INCORRECT"
            incorrect_count += 1
            score = marks_incorrect
            
        total_score += score
        detailed_results[q_num] = {
            "key": key_answer,
            "student_answer": student_response,
            "status": status,
            "score": score
        }
        
    return {
        "score": total_score,
        "correct": correct_count,
        "incorrect": incorrect_count,
        "unanswered": unanswered_count,
        "invalid": invalid_count,
        "total_questions": len(answer_key),
        "details": detailed_results
    }


# OMR Processing Class

class OMRProcessor:
    """
    Handles the Optical Mark Recognition (OMR) processing for a single sheet image.
    This class is the core model that takes the image and returns the answers dictionary.
    """
    def __init__(self, expected_answers_per_question=4):
        self.expected_answers_per_question = expected_answers_per_question
        self.options = [chr(65 + i) for i in range(expected_answers_per_question)]

    def generate_bubble_template(self, start_x, start_y, bubble_size, y_step, x_col_step, num_questions=100) -> dict:
        """
        Generates a coordinate dictionary (Calibration Template) for a 4-column OMR sheet.
        """
        template = OrderedDict()
        questions_per_column = num_questions // 4
        COLUMN_WIDTH = x_col_step
        ROW_HEIGHT = y_step
        OPTION_SPACING = int(bubble_size * 1.5) 
        
        for q_index in range(1, num_questions + 1):
            col_index = (q_index - 1) // questions_per_column
            row_index = (q_index - 1) % questions_per_column
            
            # Calculate the starting X coordinate for the current column
            current_col_x = start_x + (col_index * COLUMN_WIDTH)
            current_row_y = start_y + (row_index * ROW_HEIGHT)
            
            question_options = {}
            for i, option in enumerate(self.options):
                # X position of the specific option bubble
                option_x = current_col_x + (i * OPTION_SPACING)
                
                # Define the Region for the bubble
                question_options[option] = (
                    option_x,                     
                    current_row_y,                
                    bubble_size,                   
                    bubble_size                   
                )
            
            template[f"Q{q_index}"] = question_options
            
        return template

    def extract_answers(self, image_path: str, bubble_positions: dict) -> dict:
        """
        Processes the OMR image and extracts the marked answers using pixel intensity.
        """
        # Image Loading and Preprocessing
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: Could not load image at {image_path}. Please check the file path.")
            return {}

        # Convert to grayscale and apply Gaussian blur
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Marked areas (dark) become white (255) for easy counting.
        thresh = cv2.threshold(blurred, 0, 255, 
                               cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
        
        final_answers = {}
        MIN_MARK_THRESHOLD = 500  # Minimum filled area to be considered a mark

        #Segmentation and Evaluation
        for q_num, positions in bubble_positions.items():
            
            filled_counts = []
            
            for option_key, (x, y, w, h) in positions.items():
                
                bubble_roi = thresh[int(y):int(y + h), int(x):int(x + w)]
                
                total_marked_pixels = cv2.countNonZero(bubble_roi)
                
                filled_counts.append((total_marked_pixels, option_key))
            
            filled_counts.sort(key=lambda x: x[0], reverse=True)
            
            max_count, selected_option = filled_counts[0]
            
            # Decision Logic
            if max_count > MIN_MARK_THRESHOLD:
                # Check for multiple marks
                # If the difference between top two is small
                if len(filled_counts) > 1 and (max_count - filled_counts[1][0]) < 150: 
                    final_answers[q_num] = "INVALID (Multiple Marks)"
                else:
                    final_answers[q_num] = selected_option
            else:
                final_answers[q_num] = "UNANSWERED"

        return final_answers

# Main Execution Block

if __name__ == '__main__':
    
    MASTER_KEY_PATH = "DATAREQIREMENTS/master_omr.png"  # Teacher's correctly filled OMR sheet
    STUDENT_SHEET_PATH = "DATAREQIREMENTS/student_omr.png" # Student's filled OMR sheet

    # OMR Template Calibration Parameters
    NUM_QUESTIONS = 100
    START_X = 100       
    START_Y = 200        
    BUBBLE_SIZE = 35     
    Y_STEP_SIZE = 45    
    X_COL_STEP_SIZE = 300 

    # SCORING RULES
    MARKS_PER_CORRECT = 4
    MARKS_PER_INCORRECT_OR_INVALID = -1

    # Initialize processor and generate coordinates (used for both sheets)
    processor = OMRProcessor(expected_answers_per_question=4)
    BUBBLE_POSITIONS = processor.generate_bubble_template(
        START_X, START_Y, BUBBLE_SIZE, Y_STEP_SIZE, X_COL_STEP_SIZE, NUM_QUESTIONS
    )

    # 2. STEP A: EXTRACT MASTER ANSWER KEY

    if os.path.exists(MASTER_KEY_PATH):
        print(f"--- 1. Extracting Master Key from: {MASTER_KEY_PATH} ---")
        master_key = processor.extract_answers(MASTER_KEY_PATH, BUBBLE_POSITIONS)
        print(f"Master Key extracted for {len(master_key)} questions.")
    else:
        print("\nFATAL ERROR: Master key image not found. Cannot proceed to grade.")
        master_key = {} # Empty key to prevent crashes


    # 3. STEP B: PROCESS STUDENT SHEET AND GRADE

    if os.path.exists(STUDENT_SHEET_PATH) and master_key:
        print(f"--- 2. Processing Student Sheet: {STUDENT_SHEET_PATH} ---")
        student_answers = processor.extract_answers(STUDENT_SHEET_PATH, BUBBLE_POSITIONS)
        
        print("--- 3. Grading Test ---")
        evaluation_report = grade_test(
            student_answers, 
            master_key, 
            MARKS_PER_CORRECT, 
            MARKS_PER_INCORRECT_OR_INVALID
        )

        # PRINT FINAL REPORT
        
        print("\n==================================")
        print("      FINAL EVALUATION REPORT     ")
        print("==================================")
        print(f"Total Questions: {evaluation_report['total_questions']}")
        print(f"Correct Answers: {evaluation_report['correct']}")
        print(f"Incorrect Answers: {evaluation_report['incorrect']}")
        print(f"Unanswered:      {evaluation_report['unanswered']}")
        print(f"Invalid Marks:   {evaluation_report['invalid']}")
        print("----------------------------------")
        print(f"SCORE:           {evaluation_report['score']} points (Max possible: {NUM_QUESTIONS * MARKS_PER_CORRECT} points)")
        print(f"Scoring: +{MARKS_PER_CORRECT} Correct, {MARKS_PER_INCORRECT_OR_INVALID} Incorrect/Invalid")
        print("==================================\n")
        
        # Optionally print detailed results for review
        print("--- Detailed Results (Non-Correct Answers) ---")
        for q, data in evaluation_report['details'].items():
             if data['status'] != "CORRECT":
                 print(f"{q} | Key: {data['key']} | Student: {data['student_answer']} | Status: {data['status']} | Score: {data['score']}")
                 
    else:
         print(f"FATAL ERROR: Student sheet not found or Master Key extraction failed.")