# Globe Renderer - Quick Start Guide

## Run the Globe

### Basic Command
```bash
python3 globe.py
```

The globe will start after a 2-second countdown. You'll see a spinning 3D Earth in your terminal!

---

## Interactive Controls

### Rotation
- **`←` / `→` (Left/Right arrows)** - Rotate the globe manually
- **Auto-rotate** - Happens automatically when not paused

### Modes & Features
- **`n`** - Toggle Night/Day mode
- **`space`** - Pause/Resume rotation
- **`q`** - Quit

### Visual Features (Toggle with keys)
- **`a`** - Atmosphere glow (cyan outline)
- **`s`** - Ocean specular highlights (shiny reflections)
- **`c` or `l`** - City lights (visible in night mode)
- **`i`** - Polar ice caps (white at poles)

### Quality Settings (1-4)
- **`1`** - Low detail (31.2 FPS) - Fast
- **`2`** - Medium detail (43.1 FPS) - **Recommended**
- **`3`** - High detail (31.4 FPS)
- **`4`** - Ultra detail (24.7 FPS) - Best visuals

---

## Example Commands

### Run with specific detail level
```bash
# Modify in globe.py line 40 (CONFIG = GlobeConfig())
# Change: detail_level: int = 4
# To:     detail_level: int = 2
python3 globe.py
```

### Run tests
```bash
# Run all tests (45 tests, ~2 min)
python3 test_globe.py

# Quick performance benchmark
python3 benchmark.py

# Detailed performance analysis
python3 performance_analysis.py
```

---

## Requirements

### Minimum
- Python 3.6+
- Terminal with 256 colors (most modern terminals)
- At least 80×24 terminal size

### Optimal
- Python 3.8+
- Fast terminal (iTerm2, Alacritty, Kitty)
- Terminal size 120×40 or larger
- Modern system (2010+)

### No External Dependencies
- Pure Python (uses only standard library)
- Optional: `pyshp` for shapefile support (not required)

---

## Recommended Settings

### For Smooth Interactive Use
```
Detail Level: 2 (Medium)
Atmosphere: On
Specular: On
Ice Caps: On
City Lights: Off (adds jitter)
```

Expected FPS: **43.1** ✓

### For Maximum Performance
```
Detail Level: 1 (Low)
All features: Off
```

Expected FPS: **31.2** ✓ (very stable)

### For Best Visuals
```
Detail Level: 4 (Ultra)
All features: On
Night Mode: On
```

Expected FPS: **20-24** (beautiful detail)

---

## Troubleshooting

### Globe doesn't appear
- Make sure terminal is at least 80×24
- Try resizing: `stty rows 40 cols 120`
- Check you have 256-color support: `echo $TERM`

### Choppy/Laggy Performance
- Switch to Detail Level 1-2 (press `1` or `2`)
- Disable features: Press `a`, `s`, `c`, `i`
- Try a faster terminal (iTerm2, Alacritty)

### Colors don't look right
- Make sure terminal supports 256 colors
- Set: `export TERM=xterm-256color`

### Crashes on startup
- Try running tests first: `python3 test_globe.py`
- Check Python version: `python3 --version`
- Make sure you're in an interactive TTY

### High variance/jitter
- This is normal - caused by terminal I/O buffering
- Use Detail Level 1-2 for more consistent FPS
- Not a rendering issue

---

## What You're Seeing

### Visual Elements
- **Green continents** - Land masses with height-based shading
- **Blue ocean** - Water with depth gradient (dark = deep)
- **Cyan atmosphere** - Glow at globe edges
- **Bright dots** (night mode) - City lights on dark side
- **White dots** - Polar ice caps
- **Cyan highlights** - Ocean specular reflections

### Braille Characters
The globe uses Braille Unicode characters (⠀-⣿) as pixels:
- Each character cell is 2×4 dots
- 8 sub-pixel samples per character
- Creates smooth antialiased rendering

### Lighting
- **Sun from upper right** - Creates realistic shadows
- **Terminator line** - Day/night boundary visible
- **City lights** - Only visible on dark side (night mode)

---

## File Structure

```
globe.py                    Main renderer (1100 lines)
test_globe.py              45 comprehensive tests
performance_analysis.py    Detailed profiling
benchmark.py               Quick performance test

Documentation:
├── QUICKSTART.md          This file
├── README.md              Project overview
├── TESTING_README.md      Testing guide
├── TESTING_SUMMARY.txt    Test results summary
├── TEST_RESULTS.md        Detailed test results
├── performance_report.md  Performance analysis
├── IMPLEMENTATION_SUMMARY.md  What was optimized
├── OPTIMIZATIONS.md       Optimization opportunities
└── OPTIMIZATION_RECIPES.md   Implementation guide
```

---

## Performance Tips

### If FPS is too low
1. Switch to Detail Level 1-2
2. Disable specular highlights (`s`)
3. Disable atmosphere (`a`)
4. Use smaller terminal size
5. Close other programs (reduce system load)

### If you want better visuals
1. Switch to Detail Level 3-4
2. Enable all features (`a`, `s`, `i`)
3. Make terminal larger
4. Use night mode (`n`) for city lights

### If you want maximum stability
1. Use Detail Level 1
2. Disable all features
3. Small terminal (80×24)
4. Dedicated terminal window

---

## What Happens Behind the Scenes

1. **Initialization (2 sec startup)**
   - Builds land detection grid (20,318 cells)
   - Pre-computes Braille cache (4,864 entries)
   - Sets up color palettes

2. **Each Frame (~22-40ms)**
   - Rotates sphere by 0.025 radians
   - Ray-casts from each screen position
   - Samples land/ocean/atmosphere
   - Calculates lighting
   - Generates Braille characters
   - Outputs to terminal

3. **Input Handling**
   - Checks for keypresses (non-blocking)
   - Updates config in real-time
   - Responds immediately

---

## Example Sessions

### Quick Demo (Default)
```bash
$ python3 globe.py
# Watch for 30 seconds, then press 'q'
```

### Performance Test
```bash
$ python3 benchmark.py
# Runs 20 frames and shows FPS stats
```

### Full Validation
```bash
$ python3 test_globe.py
# Runs 45 tests covering all features
$ python3 performance_analysis.py
# Detailed performance profiling
```

### Interactive Exploration
```bash
$ python3 globe.py
# Then try:
# - Press '1' to '4' to see different detail levels
# - Press 'a', 's', 'c', 'i' to toggle features
# - Press 'n' to switch night/day
# - Press 'space' to pause and manually rotate with arrows
```

---

## FAQ

**Q: Can I save the output?**
A: Not directly (requires TTY). You can:
- Take screenshot in terminal
- Use `script` to record output
- Redirect to file (but it won't render correctly)

**Q: Does it work over SSH?**
A: Yes! If your SSH terminal supports 256 colors and is fast enough.

**Q: Why does FPS vary?**
A: Terminal I/O buffering causes variance (60-70% of frame time). Not rendering.

**Q: Can I use a different coordinate system?**
A: Yes - modify `to_cartesian()` function in globe.py

**Q: How accurate is the map?**
A: Uses 29 polygon coastlines covering major continents. Good for demo/visualization.

**Q: Can I render to file?**
A: Would need to redirect output, but ANSI codes won't render in static files.

---

## Next Steps

1. **Run it:** `python3 globe.py`
2. **Explore:** Press keys to change settings
3. **Test it:** `python3 test_globe.py`
4. **Analyze:** `python3 performance_analysis.py`
5. **Read docs:** Check TESTING_README.md for deep dive

---

## Support

For issues or questions:
- Check TESTING_README.md - Troubleshooting section
- Review performance_report.md - Bottleneck analysis
- Run test_globe.py to verify installation

Enjoy your 3D terminal globe! 🌍
