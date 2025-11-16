# Building GearLedger Windows EXE

This guide explains how to build a Windows executable (.exe) from the GearLedger desktop application.

## Prerequisites

1. **Windows 10/11**
2. **Python 3.9+** installed
3. **All dependencies** from `requirements.txt` installed

## Quick Build

### Option 1: Using the Build Script (Recommended)

```bash
# Install PyInstaller if not already installed
pip install pyinstaller

# Run the build script
python build_exe.py
```

The EXE will be created in the `dist/` folder as `GearLedger.exe`.

### Option 2: Using PyInstaller Directly

```bash
# Install PyInstaller
pip install pyinstaller

# Build using the spec file
pyinstaller GearLedger.spec

# Or build with command line options
pyinstaller --name=GearLedger --windowed --onefile app_desktop.py
```

## Build Output

After building, you'll find:

- **`dist/GearLedger.exe`** - The final executable (single file)
- **`build/`** - Temporary build files (can be deleted)
- **`GearLedger.spec`** - PyInstaller spec file (configuration)

## Testing the EXE

1. Navigate to the `dist/` folder
2. Double-click `GearLedger.exe` to run
3. The first launch may be slower (Windows Defender scan)

## Distribution

To distribute the app:

1. Copy `dist/GearLedger.exe` to the target machine
2. The EXE is self-contained (no Python installation needed)
3. First-time users may need to allow the app through Windows Defender

## Troubleshooting

### "Module not found" errors

- Add missing modules to `hiddenimports` in `GearLedger.spec`
- Rebuild: `pyinstaller GearLedger.spec --clean`

### Large EXE size

- This is normal (includes Python + all dependencies)
- Typical size: 200-500 MB
- Consider using `--onedir` instead of `--onefile` for faster startup

### Antivirus warnings

- False positives are common with PyInstaller
- Sign the EXE with a code signing certificate (optional)
- Users may need to add an exception

### Missing DLL errors

- Install Visual C++ Redistributable on target machine
- Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe

## Advanced Options

### Add an Icon

1. Create or download an `.ico` file
2. Update `GearLedger.spec`:
   ```python
   icon='path/to/icon.ico'
   ```
3. Rebuild

### Reduce Size

- Use `--onedir` instead of `--onefile` (creates a folder instead)
- Exclude unused modules in the spec file
- Use UPX compression (already enabled)

### Debug Build

- Remove `--windowed` flag to see console output
- Or set `console=True` in the spec file

## Notes

- The EXE includes all Python dependencies
- Settings are stored in: `%LOCALAPPDATA%\GearLedger\settings.json`
- Result files default to: `%LOCALAPPDATA%\GearLedger\data\`
- No internet connection needed after build (unless using OpenAI API)
