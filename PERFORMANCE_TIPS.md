# Performance Tips for Windows EXE

## Why is the app slow on Windows?

There are several potential causes:

### 1. Startup Slowness

**Main culprit: PyInstaller's `--onefile` mode**

- Extracts all files to a temporary directory on EVERY launch
- Very slow on Windows (10-30+ seconds)

## Solution: Use `--onedir` instead

I've updated the build configuration to use `--onedir` which is **much faster**:

### Before (slow):

- `--onefile` → Single EXE file
- Extracts ~200-500 MB to temp folder on each launch
- Takes 10-30+ seconds to start

### After (fast):

- `--onedir` → Folder with EXE + dependencies
- No extraction needed
- Starts in 2-5 seconds

## How to Build with Faster Startup

Just rebuild using the updated config:

```bash
python build_exe.py
```

Or:

```bash
pyinstaller GearLedger.spec
```

## Distribution

Instead of a single EXE, you'll get:

- `dist/GearLedger/` folder containing:
  - `GearLedger.exe` (the main executable)
  - All dependencies (DLLs, Python libraries, etc.)

**To distribute:** Zip the entire `GearLedger` folder and share it. Users extract and run `GearLedger.exe` from inside the folder.

## Additional Speed Improvements

### 1. Add Windows Defender Exception

- Right-click `GearLedger.exe` → Properties
- Add exception in Windows Defender
- Prevents scanning on each launch

### 2. Disable UPX Compression (if still slow)

In `GearLedger.spec`, change:

```python
upx=True,  # Can be slow on some systems
```

to:

```python
upx=False,  # Faster startup, slightly larger size
```

### 3. Exclude Unused Modules

If you don't use certain features, exclude them in the spec file to reduce size and startup time.

## Performance Comparison

| Mode        | Startup Time   | File Size  | Distribution      |
| ----------- | -------------- | ---------- | ----------------- |
| `--onefile` | 10-30+ seconds | Single EXE | Easy (one file)   |
| `--onedir`  | 2-5 seconds    | Folder     | Easy (zip folder) |

**Recommendation:** Always use `--onedir` for Windows builds!

## Runtime Performance Issues

If the app is slow during operation (not just startup), here are common causes:

### 1. Windows Defender Real-time Scanning

- Windows Defender scans files as they're accessed
- **Solution:** Add the app folder to Windows Defender exclusions:
  - Windows Security → Virus & threat protection → Manage settings
  - Add exclusion → Folder → Select `dist/GearLedger/` folder

### 2. Multiprocessing Overhead on Windows

- Windows uses "spawn" method (slower than Linux/Mac "fork")
- Each process starts fresh (loads all libraries)
- **This is normal** - processing happens in background, UI stays responsive

### 3. Heavy Library Imports

- PaddleOCR, OpenCV, pandas are large libraries
- They load when needed (not at startup)
- First OCR operation may be slower (model loading)

### 4. Large Excel Files

- Reading/writing large Excel files can be slow
- **Solution:** Keep catalog files under 10,000 rows if possible

### 5. Network Latency (OpenAI API)

- If using OpenAI vision, API calls add latency
- This is expected and happens in background

## Quick Performance Checks

1. **Is it startup or runtime?**

   - Startup: Use `--onedir` (already fixed)
   - Runtime: Check Windows Defender exclusions

2. **Check Task Manager:**

   - CPU usage should be low when idle
   - High CPU during OCR/processing is normal

3. **Check disk activity:**
   - High disk usage = Windows Defender scanning
   - Add exclusion to fix

## Performance Optimization Checklist

- [x] Use `--onedir` instead of `--onefile` (already done)
- [ ] Add Windows Defender exclusion for app folder
- [ ] Disable UPX if still slow (in `GearLedger.spec`: `upx=False`)
- [ ] Keep Excel catalog files reasonably sized
- [ ] Use SSD instead of HDD for better file I/O
- [ ] Close other heavy applications while using the app
