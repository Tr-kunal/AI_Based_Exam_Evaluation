from evaluation_engine import evaluate_student_answers, save_evaluation
from config import CONFIG

# Adjust if you keep files elsewhere
MODEL_JSON = "data/model_answers.json"
STUDENT_JSON = "data/student_answers.json"

if __name__ == "__main__":
    print("🚀 Running Automated Evaluation Engine...")

    result = evaluate_student_answers(
        model_json_path=MODEL_JSON,
        student_json_path=STUDENT_JSON,
        config=CONFIG
    )

    save_evaluation(result, "evaluation_report.json")
    print("\n✅ Done! Check evaluation_report.json for results.")
