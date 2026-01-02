# Terminal Globe - Copilot Instructions

## Project Overview
A Python terminal application that renders a 3D rotating Earth globe using Unicode Braille characters for sub-pixel precision. Single-file architecture (~850 lines) with rasterization-based rendering.

## Quick Start
```bash
python3 globe.py
```
No dependencies beyond Python 3 standard library.

## Architecture

### Core Rendering Pipeline
The globe uses **rasterization** (raycast each screen pixel to sphere), not point-plotting:
1. For each Braille cell (2×4 dots = 8 samples), raycast to unit sphere
2. Convert 3D position to lat/lon via `to_latlon()`
3. Query land/ocean via `is_land()` using pre-computed `LAND_LOOKUP` set
4. Apply lighting based on dot product with `light_dir`
5. Accumulate Braille bits per cell, then output Unicode characters (U+2800 base)

### Key Data Structures

| Structure | Purpose |
|-----------|---------|
| `CONTINENT_BOUNDARIES` | Dict of named polygon outlines (lat/lon tuples) |
| `LAND_LOOKUP` | Pre-computed `Set[Tuple[int,int]]` of 1-degree land cells |
| `GlobeConfig` | Dataclass with feature toggles and quality settings |
| `BRAILLE_DOT_MAP` | Maps (col, row) → bit index for Braille encoding |

### Configuration Pattern
All visual features are toggled via `CONFIG` (global `GlobeConfig` instance):
```python
CONFIG.enable_atmosphere = True  # Cyan edge glow
CONFIG.enable_city_lights = True  # Night-side city markers
CONFIG.enable_ocean_specular = True  # Sunlight reflection on water
CONFIG.enable_polar_ice = True  # White polar caps
```

## Code Conventions

### Adding Geographic Data
Add continent/island outlines to `CONTINENT_BOUNDARIES` dict:
```python
'region_name': [
    (lat1, lon1), (lat2, lon2), ...  # Closed polygon
],
```
The `build_land_lookup()` function auto-fills polygons using scanline algorithm.

### Braille Rendering
Each terminal cell = 2×4 dot grid. Bits map as:
```
0 3
1 4
2 5
6 7
```
Use bitwise OR to accumulate: `grid[cy][cx] |= BRAILLE_BITS[dot_idx]`

### 3D Transformations
- `to_cartesian(lat, lon)` → unit sphere (x, y, z)
- `to_latlon(x, y, z)` → geographic coordinates
- `rotate_z(x, y, z, theta)` → globe rotation around spin axis

### Color Definitions
ANSI 256-color escapes defined at top of file:
- `LAND_COLORS` / `LAND_NIGHT_COLORS` - intensity gradients
- `OCEAN_COLORS` - depth-based blue gradient
- Single-purpose: `ICE_COLOR`, `CITY_COLOR`, `ATMOSPHERE_COLOR`, `OCEAN_SPECULAR`

## Terminal Interaction
- Uses raw terminal mode via `tty.setcbreak()` for real-time key input
- `get_key()` polls stdin with `select.select()` (non-blocking)
- Always restore terminal with `termios.tcsetattr()` in finally block

## Performance Notes
- `LAND_LOOKUP` built once at module load (~4000+ cells)
- Frame target: ~30 FPS at 0.03s sleep
- Reducing `CONFIG.detail_level` (1-4) changes samples per cell

## Shapefile Integration (Enhancement Opportunity)

The `110m_cultural/` directory contains Natural Earth shapefiles with much higher-resolution geographic data than the hardcoded `CONTINENT_BOUNDARIES`. Key files:

| File | Contents |
|------|----------|
| `ne_110m_admin_0_countries.shp` | Country polygons with detailed coastlines |
| `ne_110m_admin_0_countries_lakes.shp` | Countries with lake boundaries cut out |

### Integration approach:
1. **Parse shapefiles** - Use `shapefile` library (pyshp): `pip install pyshp`
2. **Extract polygons** - Each shape has `.points` (list of (lon, lat) tuples—note: lon first!)
3. **Replace `CONTINENT_BOUNDARIES`** - Convert shapefile polygons to the existing format
4. **Rebuild `LAND_LOOKUP`** - The scanline fill algorithm works unchanged

Example parsing:
```python
import shapefile
sf = shapefile.Reader("110m_cultural/ne_110m_admin_0_countries.shp")
for shape in sf.shapes():
    # shape.points = [(lon, lat), ...] - swap to (lat, lon) for our format
    polygon = [(pt[1], pt[0]) for pt in shape.points]
```

**Note:** Shapefiles use (longitude, latitude) order; this project uses (latitude, longitude).

## File Reference
- [globe.py](../globe.py) - Entire application (rendering, data, controls)
- [110m_cultural/](../110m_cultural/) - Natural Earth 1:110m shapefiles (higher detail than hardcoded data)
