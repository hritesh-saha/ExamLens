Hand-label guide (Member 2)
1. Crop 30+ text regions and 15+ equation regions from real board photos (use Member 1's output crops).
2. Save images here (t01.png, e01.png ...).
3. Create labels.json (format in scripts/eval_ocr.py docstring). Type text exactly as written on the board.
4. Run: python -m scripts.eval_ocr --labels data/ocr_eval/labels.json
