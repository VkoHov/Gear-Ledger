# Building GearLedger as Windows EXE

## Quick Start (On Windows)

1. **Install PyInstaller:**

   ```bash
   pip install pyinstaller
   ```

2. **Build the EXE:**

   ```bash
   python build_exe.py
   ```

   Or use the spec file directly:

   ```bash
   pyinstaller GearLedger.spec
   ```

3. **Find your EXE:**
   - Location: `dist/GearLedger.exe`
   - Size: ~200-500 MB (includes all dependencies)

## What Gets Built

- **Single EXE file** - No Python installation needed on target machine
- **All dependencies included** - PyQt6, OpenCV, pandas, etc.
- **Settings stored in** - `%LOCALAPPDATA%\GearLedger\`
- **Result files default to** - `%LOCALAPPDATA%\GearLedger\data\`

## Distribution

Simply copy `dist/GearLedger.exe` to any Windows 10/11 machine and run it!

**Note:** First-time users may need to:

- Allow the app through Windows Defender (false positive warnings are common)
- Install Visual C++ Redistributable if missing: https://aka.ms/vs/17/release/vc_redist.x64.exe

## Troubleshooting

### Build fails with "Module not found"

- Add the missing module to `hiddenimports` in `GearLedger.spec`
- Rebuild: `pyinstaller GearLedger.spec --clean`

### EXE is very large

- This is normal (includes Python + all libraries)
- Consider `--onedir` instead of `--onefile` for faster startup

### Antivirus flags the EXE

- Common with PyInstaller executables
- Users can add an exception or you can code-sign the EXE

## Advanced

See `BUILD_INSTRUCTIONS.md` for detailed information.
