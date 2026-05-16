import os
import cv2
import numpy as np
from PIL import Image
import pytesseract

# ---------- CONFIG ----------
IMAGE_PATH = "sample\Handwrittenimg.jpg"  # change here
OUTPUT_TEXT = "single_image_cleaned_text.txt"
DEBUG_DIR = "debug_single_img"

os.makedirs(DEBUG_DIR, exist_ok=True)

# Optional: Set Tesseract install location
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---------- helper functions ----------
def save_img(path, img):
    cv2.imwrite(path, img)

def apply_clahe(gray):
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    return clahe.apply(gray)

def deskew_image(gray):
    coords = np.column_stack(np.where(gray < 255))
    if coords.shape[0] < 10:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = gray.shape[:2]
    M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h),
                          flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)

def ocr_and_confidence(img, config):
    data = pytesseract.image_to_data(img, config=config,
                                     output_type=pytesseract.Output.DICT)
    confs = []
    for t, c in zip(data['text'], data['conf']):
        if t.strip() != "" and c not in ("-1", "-1\n"):
            try: confs.append(float(c))
            except: pass
    mean_conf = np.mean(confs) if confs else -1.0
    text = "\n".join(data['text'])
    return text, mean_conf, data

# ---------- Load input image ----------
img_color = cv2.imread(IMAGE_PATH)
gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

# ---------- Candidate preprocessing ----------
candidates = []
candidates.append(("orig_gray", gray))
clahe = apply_clahe(gray)
clahe = cv2.medianBlur(clahe, 3)
candidates.append(("clahe_med", clahe))
adapt = cv2.adaptiveThreshold(clahe, 255,
                              cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                              cv2.THRESH_BINARY, 11, 2)
candidates.append(("adaptive", adapt))
_, otsu = cv2.threshold(clahe, 0, 255,
                        cv2.THRESH_BINARY + cv2.THRESH_OTSU)
candidates.append(("otsu", otsu))
candidates.append(("otsu_inv", 255 - otsu))
desk = deskew_image(gray)
desk_clahe = apply_clahe(desk)
desk_adapt = cv2.adaptiveThreshold(desk_clahe, 255,
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
candidates.append(("desk_adapt", desk_adapt))

# ---------- OCR configs ----------
psm_list = ["--oem 1 --psm 6", "--oem 1 --psm 3", "--oem 1 --psm 4"]

best = {"conf": -1, "text": "", "img": None, "name": None, "data": None}

for name, im in candidates:
    pil = Image.fromarray(im)
    for cfg in psm_list:
        txt, conf, data = ocr_and_confidence(pil, config=cfg)
        print(f"{name} + {cfg}: conf={conf:.2f}")

        if conf > best["conf"]:
            best.update({"conf": conf, "text": txt,
                         "img": im, "name": name, "data": data})

# ---------- Save results ----------
save_img(os.path.join(DEBUG_DIR, "best_candidate.png"), best["img"])

with open(OUTPUT_TEXT, "w", encoding="utf-8") as f:
    f.write(f"Best: {best['name']} conf={best['conf']:.2f}\n\n")
    f.write(best["text"])

# ---------- Overlay bounding boxes ----------
overlay = cv2.cvtColor(best["img"], cv2.COLOR_GRAY2BGR)
for i in range(len(best["data"]['text'])):
    t = best["data"]['text'][i].strip()
    c = float(best["data"]['conf'][i])
    if t != "" and c > 10:
        x,y,w,h = best["data"]['left'][i],best["data"]['top'][i], \
                  best["data"]['width'][i],best["data"]['height'][i]
        cv2.rectangle(overlay, (x,y), (x+w,y+h), (0,255,0), 1)

save_img(os.path.join(DEBUG_DIR, "overlay_boxes.png"), overlay)

print("\n✅ Done! Best preprocessing:", best["name"])
print("Output saved:", OUTPUT_TEXT)
