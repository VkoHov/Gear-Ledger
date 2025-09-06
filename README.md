## GearLedger

GearLedger is a CLI tool that:

reads car part codes from photos (PaddleOCR),

optionally lets GPT pick the most likely article code,

finds that code in your Excel inventory and reports the matched row (client + article).

Works fully offline (OCR + heuristics) if you don't set an OpenAI key; GPT improves ranking.

### Features

🧠 OCR (PaddleOCR) with multi-language support (en,ru by default), EXIF auto-rotate, safe downscale.

🧩 Smart selection: heuristics + optional GPT (gpt-4o-mini) to choose the best vendor/OEM code.

📗 Excel lookup: matches normalized part codes against invoice.xlsx (Артикул, Клиент).

🎯 Target modes:

--target vendor (e.g., PK-5396)

--target oem (e.g., A 221 501 26 91)

--target auto (default; auto-choose)

🪵 Verbose logs for every step (sizes, OCR items, GPT raw output, match debug).

### Quick Install

```bash
git clone <your-repo-url> gearledger
cd gearledger

python3 -m venv venv
source venv/bin/activate # macOS/Linux

# .\venv\Scripts\activate # Windows

python -m pip install -U pip wheel setuptools
pip install -r requirements.txt
```

#### HEIC/iPhone photos (optional):

```bash
pip install pillow-heif
```

### Requirements

Python 3.9–3.12

macOS or Linux (Windows may work with small tweaks)

(Optional) OpenAI API key for GPT ranking
