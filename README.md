# ShopShieldAI — Website & Image Checker

A beginner-friendly Flask web project with two tools:
1. **Website URL checker** — flags common suspicious URL patterns.
2. **Image file checker** — accepts common image formats including JPG/JPEG, PNG, BMP, GIF, WEBP, TIFF, JFIF, DIB and ICO, and validates that the upload is a readable image.

## Important limitation
The website checker uses transparent rules, not a trained AI model or live threat-intelligence database. A low-risk result is **not a guarantee** that a shop is legitimate. The image checker validates image file type and basic properties; it does **not** determine whether a product is genuine or fake. Those stronger claims need a verified dataset/model and additional sources.

## Requirements
- Python 3.10 or newer
- Internet browser
- VS Code (recommended)

## Windows setup
1. Extract the ZIP file.
2. Open the extracted `ShopShieldAI_Full_Project` folder in VS Code.
3. Open **Terminal → New Terminal**.
4. Run these commands one at a time:

```powershell
python -m venv venv
```

If PowerShell blocks activation, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```
Then:
```powershell
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -u app.py
```

5. Open `http://127.0.0.1:5000` in your browser.
6. Keep the terminal open while using the website. Press `Ctrl+C` in the terminal to stop it.

If `python` is not recognized, install Python from the official Python website and select **Add Python to PATH** during setup.

## Image upload notes
- Maximum upload size: 12 MB.
- The app checks both the filename extension and the actual image contents.
- Animated GIFs are accepted; basic dimensions and frame count are shown.
- Pillow support depends on the installed Pillow build. Formats such as AVIF/HEIC are not included in the accepted list by default.

## Main files
- `app.py` — Flask routes and upload validation
- `utils/website_detector.py` — URL heuristics
- `templates/` — page templates
- `static/css/style.css` — styling
