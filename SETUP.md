# Dreamer Setup Guide

This guide will help you set up the Dreamer game automation tool on your machine.

## Prerequisites

- Python 3.8 or higher
- Windows 10/11 (the game must be running)
- Git (for cloning the repository)

## Installation Steps

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Dreamer
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist, install these packages manually:

```bash
pip install PyQt5 opencv-python numpy pytesseract pyautogui pillow
```

### 3. Install Tesseract OCR

**The OCR functionality requires Tesseract to be installed on your system.**

#### Windows:
1. Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer (typically installs to `C:\Program Files\Tesseract-OCR\`)
3. **Important:** During installation, make sure to check "Add to PATH" option
4. If you forgot to add to PATH, you can either:
   - Re-run the installer and select the PATH option, OR
   - Manually add `C:\Program Files\Tesseract-OCR` to your system PATH

#### macOS:
```bash
brew install tesseract
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

### 4. Verify Tesseract Installation

Open a terminal/command prompt and run:

```bash
tesseract --version
```

You should see output like:
```
tesseract 5.x.x
```

If you get "command not found" or similar error, Tesseract is not in your PATH.

### 5. Configure Tesseract Path (if needed)

If Tesseract is installed but not in PATH, you can set it in `config.py`:

Create or edit the `TESSERACT_PATH` setting:

```python
# config.py
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Windows
# or
TESSERACT_PATH = '/usr/local/bin/tesseract'  # macOS/Linux
```

Then update `text_recognition.py` to use this path (if not already done).

### 6. Run the Application

```bash
python main.py
```

## Troubleshooting

### OCR Not Working

**Error:** `pytesseract not installed` or `TesseractNotFoundError`

**Solutions:**

1. **Check pytesseract is installed:**
   ```bash
   pip install pytesseract
   ```

2. **Verify Tesseract executable is installed:**
   ```bash
   tesseract --version
   ```

3. **If Tesseract is installed but not found:**
   - Windows: Add `C:\Program Files\Tesseract-OCR` to system PATH
   - Or set the path explicitly in Python (see section 5 above)

### Game Window Not Found

Make sure the game is running and visible on your screen before starting Dreamer.

### Template Matching Fails

Make sure your game resolution matches the expected window size (1734x703 by default). The app will resize the window automatically when started.

## Configuration

Edit `config.py` to customize:
- Arena max opponent power/level
- Iron Twins stage
- Clan Boss difficulty
- Template matching thresholds
- And more...

## Additional Notes

- The `debug/` folder contains screenshots used for debugging template matching and OCR
- The `logs/` folder contains daily log files
- Local settings are stored in `.claude/settings.local.json`

## Need Help?

Check the logs in `logs/dreamer_<date>.log` for detailed error messages and execution traces.
