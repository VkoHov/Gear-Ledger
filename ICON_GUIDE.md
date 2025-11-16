# Adding an Icon/Logo to Your App

## Step 1: Create or Get an Icon File

You need a `.ico` file for Windows. Here are your options:

### Option A: Convert PNG to ICO (Recommended)

1. **Create or find a PNG image** (256x256 or 512x512 pixels works best)
2. **Convert to ICO** using one of these methods:

   **Online converter:**

   - https://convertio.co/png-ico/
   - https://www.icoconverter.com/
   - Upload your PNG → Download .ico file

   **Using Python (Pillow):**

   ```python
   from PIL import Image
   img = Image.open('logo.png')
   img.save('icon.ico', format='ICO', sizes=[(256,256), (128,128), (64,64), (32,32), (16,16)])
   ```

   **Or use the helper script:**

   ```bash
   python create_icon.py logo.png
   ```

### Option B: Use an Existing ICO File

If you already have an `.ico` file, just place it in the project root as `icon.ico`.

## Step 2: Place the Icon File

Place your `icon.ico` file in the project root directory:

```
Gear-Ledger/
  ├── icon.ico          ← Place your icon here
  ├── app_desktop.py
  ├── build_exe.py
  └── ...
```

## Step 3: Build with Icon

The build scripts will automatically detect and use `icon.ico` if it exists:

```bash
# PyInstaller
python build_exe.py

# Nuitka
python build_nuitka.py
```

## Step 4: Verify

After building:

1. Check the EXE file in `dist/` folder
2. The EXE should show your icon in Windows Explorer
3. The app window should also show the icon in the title bar

## Icon Requirements

- **Format:** `.ico` (Windows Icon format)
- **Recommended sizes:** 256x256, 128x128, 64x64, 32x32, 16x16 pixels
- **Location:** Project root directory (`icon.ico`)
- **Name:** Must be exactly `icon.ico`

## Troubleshooting

**Icon not showing in EXE:**

- Make sure file is named exactly `icon.ico`
- Make sure it's in the project root directory
- Try rebuilding: `python build_exe.py --clean` or delete `build/` and `dist/` folders

**Icon not showing in window:**

- The app will try to load `icon.ico` from the same directory as the EXE
- Make sure the icon file is included in the build (it should be automatic)

## Quick Test

To test if your icon works before building:

1. Place `icon.ico` in project root
2. Run the app: `python app_desktop.py`
3. The window should show your icon in the title bar
