import cv2
import numpy as np
from collections import OrderedDict
import os

#Helper Functions

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
            
            # --- 3. Decision Logic ---
            if max_count > MIN_MARK_THRESHOLD:
                # Check for multiple marks (if the second darkest is too close)
                # If the difference between top two is small
                if len(filled_counts) > 1 and (max_count - filled_counts[1][0]) < 150: 
                    final_answers[q_num] = "INVALID (Multiple Marks)"
                else:
                    final_answers[q_num] = selected_option
            else:
                final_answers[q_num] = "UNANSWERED"

        return final_answers

# --- Main Execution Block ---

if __name__ == '__main__':
    #Image Path
    IMAGE_FILE_PATH = "DATAREQIREMENTS\dummyomr.png"

    NUM_QUESTIONS = 100
    
    # **APPROXIMATE PARAMETERS for the 100Q sheet in the document**
    START_X = 100       
    START_Y = 200        
    BUBBLE_SIZE = 35     
    Y_STEP_SIZE = 45    
    X_COL_STEP_SIZE = 300 

    #RUN THE OMR PROCESS

    if not os.path.exists(IMAGE_FILE_PATH):
        print(f"\nFATAL ERROR: Image file not found at '{IMAGE_FILE_PATH}'")
        print("Please edit the script and set IMAGE_FILE_PATH to your file location.")
    else:
        print(f"--- Processing OMR Sheet: {IMAGE_FILE_PATH} ---")
        
        # Initialize processor and generate coordinates
        processor = OMRProcessor(expected_answers_per_question=4)
        BUBBLE_POSITIONS = processor.generate_bubble_template(
            START_X, START_Y, BUBBLE_SIZE, Y_STEP_SIZE, X_COL_STEP_SIZE, NUM_QUESTIONS
        )
        

        detected_answers = processor.extract_answers(IMAGE_FILE_PATH, BUBBLE_POSITIONS)

        #RESULT DICTIONARY    
        print("    DETECTED STUDENT ANSWERS      ")        
        # Print the dictionary in a structured format
        for q, a in detected_answers.items():
            print(f"{q}: {a}")
            
        print("==================================")
        print(f"Total Questions Detected: {len(detected_answers)}")
