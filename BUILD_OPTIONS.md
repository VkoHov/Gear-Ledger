# Build Options for Windows EXE

## Comparison: PyInstaller vs Nuitka

| Feature | PyInstaller | Nuitka |
|---------|-------------|--------|
| **Build Time** | 2-5 minutes | 5-15 minutes |
| **Runtime Speed** | Normal | Faster (compiled) |
| **File Size** | ~200-500 MB | ~100-300 MB |
| **Antivirus Reputation** | ⚠️ Often flagged | ✅ Usually trusted |
| **Windows Defender** | ❌ Usually needs exclusion | ✅ Usually no exclusion needed |
| **Setup Complexity** | Easy | Requires C++ compiler |
| **Distribution** | Folder (`--onedir`) | Single EXE |

## Option 1: PyInstaller (Current)

**Pros:**
- Fast build time
- Easy setup (no compiler needed)
- Well-documented

**Cons:**
- Often triggers antivirus false positives
- Usually needs Windows Defender exclusion
- Slower startup (with `--onefile`)

**Build:**
```bash
python build_exe.py
```

## Option 2: Nuitka (Recommended for Distribution) ⭐

**Pros:**
- ✅ **Better antivirus reputation** (usually no exclusions needed!)
- ✅ Faster runtime (compiled to C++)
- ✅ Smaller file size
- ✅ Single EXE (no folder)

**Cons:**
- Longer build time (5-15 minutes)
- Requires C++ compiler (Visual Studio Build Tools)

**Setup:**
1. Install Visual Studio Build Tools:
   - Download: https://visualstudio.microsoft.com/downloads/
   - Install "Desktop development with C++" workload

2. Build:
   ```bash
   pip install nuitka
   python build_nuitka.py
   ```

## Option 3: Code Signing (Professional)

If you have a code signing certificate:

**Pros:**
- ✅ Best antivirus reputation
- ✅ No exclusions needed
- ✅ Professional appearance

**Cons:**
- Costs money (~$200-400/year for certificate)
- Requires certificate setup

**Process:**
1. Purchase code signing certificate
2. Sign the EXE after building
3. Distribute signed EXE

## Recommendation

**For personal/internal use:**
- Use **PyInstaller** (current setup)
- Add Windows Defender exclusion (one-time setup)

**For public distribution:**
- Use **Nuitka** (better reputation, no exclusions usually needed)
- Or use code signing (most professional)

## Quick Start with Nuitka

```bash
# 1. Install Visual Studio Build Tools (one-time)
# Download from: https://visualstudio.microsoft.com/downloads/
# Select "Desktop development with C++"

# 2. Install Nuitka
pip install nuitka

# 3. Build
python build_nuitka.py
```

The EXE will be at `dist/GearLedger.exe` and usually won't need Windows Defender exclusions!

