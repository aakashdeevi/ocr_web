import os
import requests
import cv2
import re
from flask import Flask, request, render_template, redirect, url_for
from difflib import SequenceMatcher

# === Configuration ===
API_KEY = 'K85017367888957'
UPLOAD_FOLDER = 'uploads'
PROCESSED_IMAGE_PATH = os.path.join(UPLOAD_FOLDER, "processed_image.jpg")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# === OCR.space API Call ===
def ocr_space_extract(image_path, api_key):
    with open(image_path, 'rb') as image_file:
        response = requests.post(
            'https://api.ocr.space/parse/image',
            files={'filename': image_file},
            data={'apikey': api_key, 'language': 'eng', 'isOverlayRequired': False},
        )
        result = response.json()
        return result['ParsedResults'][0]['ParsedText'].strip()

# === Image Preprocessing ===
def preprocess_image(input_path, output_path):
    image = cv2.imread(input_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LINEAR)
    _, thresh = cv2.threshold(resized, 200, 255, cv2.THRESH_BINARY)
    cv2.imwrite(output_path, thresh)

# === Word Selection Heuristic ===
def is_better_word(word_a, word_b):
    if '.' in word_a and '.' not in word_b:
        return word_a
    if '.' in word_b and '.' not in word_a:
        return word_b
    if word_a != word_a.upper() and word_b == word_b.upper():
        return word_a
    if word_b != word_b.upper() and word_a == word_a.upper():
        return word_b
    if len(word_a) >= len(word_b):
        return word_a
    return word_b

# === Merge Two Lines Word-by-Word ===
def merge_lines(line1, line2):
    words1 = re.findall(r'\S+', line1)
    words2 = re.findall(r'\S+', line2)

    matcher = SequenceMatcher(None, words1, words2)
    merged = []

    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == 'equal':
            merged.extend(words1[i1:i2])
        else:
            for k in range(max(i2 - i1, j2 - j1)):
                word_a = words1[i1 + k] if i1 + k < len(words1) else ""
                word_b = words2[j1 + k] if j1 + k < len(words2) else ""
                merged.append(is_better_word(word_a, word_b))

    return ' '.join(merged)

# === Merge Full Text Line-by-Line ===
def merge_texts_with_line_breaks(text1, text2):
    lines1 = text1.splitlines()
    lines2 = text2.splitlines()
    max_lines = max(len(lines1), len(lines2))
    merged_lines = []

    for i in range(max_lines):
        line1 = lines1[i] if i < len(lines1) else ""
        line2 = lines2[i] if i < len(lines2) else ""
        merged_lines.append(merge_lines(line1, line2))

    return '\n'.join(merged_lines)

# === Routes ===
@app.route('/', methods=['GET', 'POST'])
def index():
    final_text = ""
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Run OCR pipeline - don't wait for preprocessing to finish
            original_text = ocr_space_extract(filepath, API_KEY)
            
            # Process image in background and get second OCR result
            preprocess_image(filepath, PROCESSED_IMAGE_PATH)
            processed_text = ocr_space_extract(PROCESSED_IMAGE_PATH, API_KEY)
            
            final_text = merge_texts_with_line_breaks(original_text, processed_text)
            
            # Clean up uploaded files
            if os.path.exists(filepath):
                os.remove(filepath)
            if os.path.exists(PROCESSED_IMAGE_PATH):
                os.remove(PROCESSED_IMAGE_PATH)
            
            return render_template('index.html', text=final_text)
    
    return render_template('index.html', text=final_text)

if __name__ == '__main__':
    app.run(debug=True)