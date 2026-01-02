# Dreamer

Dreamer is a Python application that automates navigation in Raid: Shadow Legends using image recognition.

## Features
- Capture screenshots of game window
- Template-based image matching for reliable UI navigation
- Automated sequences (e.g., Arena navigation)

## Requirements
- Python 3.12
- PyQt5
- OpenCV
- PyAutoGUI
- pygetwindow

## Setup
1. Install dependencies:
   ```bash
   pip install pyqt5 pyautogui opencv-python numpy pygetwindow pillow pyscreeze
   ```

2. Run the application:
   ```bash
   python main.py
   ```

## How to Use

### Creating Templates
1. Open the game and navigate to the screen you want to automate
2. Click "Capture Window" in Dreamer
3. Click "Save Template" and name it (e.g., "Battle", "Arena", "Classic Arena")
4. Templates are saved in the `templates/` folder

### Running Sequences
1. Place your template images in the `templates/` folder with names:
   - `Battle.png`
   - `Arena.png`
   - `Classic Arena.png`
2. Click "Run: Arenas" to execute the automated sequence

## Project Structure
- `main.py` - Main GUI application
- `window_capture.py` - Window detection and screenshot capture
- `template_matcher.py` - Template matching and clicking logic
- `templates/` - Folder for template images (drop your screenshots here)
