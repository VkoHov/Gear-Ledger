import easyocr

# Initialize reader with needed languages
reader = easyocr.Reader(["en", "ru"])  # add 'de', 'fr', etc. if needed

# Run OCR
results = reader.readtext(".jpg")

# Print all detected texts
for bbox, text, prob in results:
    print(f"Text: {text}, Confidence: {prob:.2f}")
