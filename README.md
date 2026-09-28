# Dreamer - Raid: Shadow Legends Automation Tool

Automated task runner for Raid: Shadow Legends using computer vision and OCR.

## Quick Start

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Tesseract OCR:**
   - **Windows:** Download from https://github.com/UB-Mannheim/tesseract/wiki
   - **macOS:** `brew install tesseract`
   - **Linux:** `sudo apt-get install tesseract-ocr`

3. **Verify Tesseract installation:**
   ```bash
   tesseract --version
   ```

4. **Run the app:**
   ```bash
   python main.py
   ```

**⚠️ Important:** OCR features will not work without Tesseract installed! See [SETUP.md](SETUP.md) for detailed instructions.

## Features

- **Classic Arena:** Automated opponent scanning, filtering, and battle execution with vision-based targeting
- **Clan Boss:** Difficulty selection, key management, and automated battles
- **Iron Twins:** Stage selection and farming
- **Daily Tasks:** Collection automation for gems, shop items, quests, playtime rewards
- **Guardian Ring:** Automated upgrades
- **Daily Loop:** Run all tasks in sequence with automatic retries

## Configuration

Edit `config.py` to customize:
- **Arena:** Max opponent power, max level, OR power threshold
- **Iron Twins:** Stage selection (1-15)
- **Clan Boss:** Difficulty and player name for leaderboard tracking
- **Tesseract Path:** If not in system PATH
- Template matching thresholds

## Troubleshooting

### OCR Not Working

If you see errors related to OCR or text recognition:

1. **Check if pytesseract is installed:**
   ```bash
   pip install pytesseract
   ```

2. **Check if Tesseract executable is installed:**
   ```bash
   tesseract --version
   ```

3. **If installed but not found:**
   - Windows: Add `C:\Program Files\Tesseract-OCR` to system PATH
   - Or set `TESSERACT_PATH` in `config.py`:
     ```python
     TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
     ```

### Game Window Not Found

Make sure Raid: Shadow Legends is running and the window title is "Raid: Shadow Legends".

## Project Structure

- `main.py` - Main application entry point with GUI
- `config.py` - Configuration settings
- `sequences/` - Task automation modules
  - `arena_sequence_v2.py` - Arena orchestrator
  - `arena_scanner_v2.py` - Vision-based opponent scanning
  - `arena_battle_v2.py` - Battle execution with template matching
  - `clan_boss.py` - Clan Boss automation
  - `iron_twins.py` - Iron Twins farming
- `text_recognition.py` - OCR module for reading game text
- `natural_click.py` - Human-like mouse clicking with variance
- `templates/` - Reference images for template matching
- `debug/` - Debug screenshots (auto-generated, gitignored)
- `logs/` - Daily log files (gitignored)

## Requirements

- Python 3.8+
- Windows 10/11 (game must be running)
- Tesseract OCR 5.x
- See `requirements.txt` for Python packages

## Contributing

When contributing:
- Test all changes with the actual game
- Update `SETUP.md` if adding new dependencies
- Follow existing code style and patterns
- Don't commit debug/ or logs/ folders (gitignored)

## License

Personal automation tool. Use responsibly and in accordance with game terms of service.
