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

### Voice Support

GearLedger supports multiple speech engines for voice feedback:

- **OS (free)** – Uses the system TTS:
  - macOS: `say`
  - Windows: `pyttsx3` (SAPI5)
- **OpenAI (premium)** – High quality cloud TTS (requires `OPENAI_API_KEY`).
- **Piper (offline)** – Local neural TTS with Armenian support.

To enable voice support:

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. (Optional) Install Piper binary:
   - Download Piper for your platform from the official project and ensure `piper` is on your `PATH`,
     or configure the binary path in Settings → Voice Support.

3. Download Armenian voice:
   - Open the desktop app → Settings → **Voice Support**.
   - Select **Piper (offline)** as the speech engine.
   - Click **Download Armenian Voice** (downloads `hy_AM-gor-medium` into the app data folder).

4. Use **Test voice** to play a short Armenian phrase with the selected engine.

Piper models are stored under the app data directory, e.g.:

- macOS/Linux: `~/.gearledger/voices/piper/hy_AM-gor-medium/`
- Windows: `%LOCALAPPDATA%/GearLedger/voices/piper/hy_AM-gor-medium/`
