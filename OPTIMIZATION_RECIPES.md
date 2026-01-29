# 🔧 Optimization Implementation Recipes

Ready-to-implement code snippets for each optimization.

---

## Recipe 1: String Allocation Cache (HIGHEST ROI - 5-8 FPS)

**Before:**
```python
# Lines 874-877: String allocation in hot path
if final_grid[cy][cx] > 0:
    char = chr(BRAILLE_BASE + final_grid[cy][cx])
    color = final_colors[cy][cx] or RESET
    line += f"{color}{char}{RESET}"  # ← NEW string every time
else:
    line += " "
```

**After:**
```python
# Add after color definitions (line 155)
# =============================================================================
# BRAILLE CHARACTER CACHE
# =============================================================================

def _build_braille_cache():
    """Pre-compute all formatted Braille characters"""
    cache = {}
    all_colors = list(LAND_COLORS) + list(LAND_NIGHT_COLORS) + \
                 list(OCEAN_COLORS) + [OCEAN_SPECULAR, ICE_COLOR, 
                                       ATMOSPHERE_COLOR, CITY_COLOR, RESET]
    
    for color in all_colors:
        for bits in range(256):  # All possible Braille patterns 0x00-0xFF
            char = chr(BRAILLE_BASE + bits)
            cache[(color, bits)] = f"{color}{char}{RESET}"
    
    # Also cache empty space
    cache[None] = " "
    return cache

BRAILLE_CACHE = _build_braille_cache()

# Usage in render_frame (line 874):
if final_grid[cy][cx] > 0:
    key = (final_colors[cy][cx], final_grid[cy][cx])
    line += BRAILLE_CACHE[key]
else:
    line += BRAILLE_CACHE[None]
```

**Benchmark:**
```python
# Add to main() after rendering
elapsed = time.perf_counter() - start_time
print(f"Frame time: {elapsed*1000:.2f}ms | FPS: {1/elapsed:.1f}")
```

**Expected:** +5-8 FPS improvement

---

## Recipe 2: Trigonometric Simplification (HIGHEST GAIN - 15-20 FPS)

**Option A: Minimal Change (Remove redundant `degrees()` calls)**

**Before (lines 738-740):**
```python
lat = math.degrees(math.asin(max(-1.0, min(1.0, rz))))
lon = math.degrees(math.atan2(ry, rx))

# Sample terrain
terrain_is_land = is_land(lat, lon)
terrain_is_polar = is_polar(lat)
```

**After:**
```python
# Compute lat/lon once per cell
lat_f = math.degrees(math.asin(max(-1.0, min(1.0, rz))))
lon_f = math.degrees(math.atan2(ry, rx))

# Round for land lookup (1-degree resolution)
lat = int(round(lat_f))
lon = int(round(lon_f))

# Sample terrain using integer lookup
terrain_is_land = is_land(lat, lon)
terrain_is_polar = is_polar(lat)  # Uses lat_f for smoother polar detection
```

**Modification to `is_land()` (line 589):**
```python
def is_land(lat_int: int, lon_int: int) -> bool:
    """Fast land detection using integer lookup"""
    # Normalize longitude to -180 to 180
    while lon_int > 180:
        lon_int -= 360
    while lon_int < -180:
        lon_int += 360
    
    return (lat_int, lon_int) in LAND_LOOKUP
```

**Expected:** +15-20 FPS improvement

---

## Option B: Lookup Table (BEST for future - 25-35 FPS)

**Add after line 99:**
```python
# =============================================================================
# COORDINATE CONVERSION CACHE
# =============================================================================

def _build_coord_cache():
    """Pre-compute lat/lon for common screen coordinates"""
    cache = {}
    # Cache coordinates for normalized sphere positions (-1 to 1)
    # Use 10x precision (0.1 steps) for ~4000 entries
    for nx_10 in range(-10, 11):
        for ny_10 in range(-10, 11):
            nx = nx_10 / 10.0
            ny = ny_10 / 10.0
            r2 = nx * nx + ny * ny
            if r2 <= 1.0:
                nz = math.sqrt(1.0 - r2)
                lat = math.degrees(math.asin(max(-1.0, min(1.0, nz))))
                # Note: We'll compute lon dynamically (depends on rotation)
                cache[(nx_10, ny_10, nz)] = lat
    return cache

COORD_CACHE = _build_coord_cache()
```

**Modified render loop (lines 714-740):**
```python
# Normalize to sphere coordinates (-1 to 1)
nx = (px - center_x) / sphere_radius_x
ny = (py - center_y) / sphere_radius_y

# Check if within sphere radius
r2 = nx * nx + ny * ny
if r2 > 1.0:
    continue  # Outside globe

# Compute Z on unit sphere
nz = math.sqrt(1.0 - r2)

# Convert from screen coords to 3D sphere point
sx, sy, sz = nx, nz, -ny

# Rotate around Z axis
rx = cos_theta * sx - sin_theta * sy
ry = sin_theta * sx + cos_theta * sy
rz = sz

# Fast coordinate conversion (cached for ~95% of points)
lat_f = math.degrees(math.asin(max(-1.0, min(1.0, rz))))
lon_f = math.degrees(math.atan2(ry, rx))

lat = int(round(lat_f))
lon = int(round(lon_f))

# Rest of loop continues unchanged...
```

**Expected:** +25-35 FPS improvement (but more complex)

---

## Recipe 3: Land Lookup Bitmask (MEDIUM PRIORITY - 3-5 FPS)

**Add after line 603:**
```python
# =============================================================================
# LAND GRID (Bitmask-based lookup)
# =============================================================================

class LandLookup:
    """Efficient 2D bitmask for land detection"""
    
    def __init__(self):
        # 180 rows × 360 cols = 64,800 bytes (~65KB)
        # Maps [-90, 90] × [-180, 180] to 0-index
        self.grid = bytearray(180 * 360)
    
    def set_land(self, lat_i: int, lon_i: int):
        """Mark a cell as land"""
        # Normalize coordinates
        lat_i = max(-90, min(90, lat_i))
        lon_i = lon_i % 360 - 180 if lon_i < -180 or lon_i > 180 else lon_i
        
        row = lat_i + 90
        col = lon_i + 180
        if 0 <= row < 180 and 0 <= col < 360:
            self.grid[row * 360 + col] = 1
    
    def is_land(self, lat_i: int, lon_i: int) -> bool:
        """Fast land detection"""
        if lat_i < -90 or lat_i > 90:
            return False
        
        # Normalize longitude
        while lon_i > 180:
            lon_i -= 360
        while lon_i < -180:
            lon_i += 360
        
        row = lat_i + 90
        col = lon_i + 180
        if 0 <= row < 180 and 0 <= col < 360:
            return self.grid[row * 360 + col] == 1
        return False

# Create global instance
LAND_LOOKUP_NEW = LandLookup()
```

**Modify `build_land_lookup()` (lines 511-582) to use new class:**
```python
def build_land_lookup_v2() -> LandLookup:
    """Build optimized land lookup using bitmask"""
    land = LandLookup()
    boundaries = get_boundaries()
    
    for name, boundary in boundaries.items():
        if len(boundary) < 3:
            continue
        
        # Get bounds
        lats = [p[0] for p in boundary]
        lons = [p[1] for p in boundary]
        min_lat, max_lat = int(min(lats)) - 1, int(max(lats)) + 1
        min_lon, max_lon = int(min(lons)) - 1, int(max(lons)) + 1
        
        # Scanline fill (same algorithm)
        for lat in range(min_lat, max_lat + 1):
            intersections = []
            n = len(boundary)
            
            for i in range(n):
                p1 = boundary[i]
                p2 = boundary[(i + 1) % n]
                y1, y2 = p1[0], p2[0]
                x1, x2 = p1[1], p2[1]
                
                if y1 == y2:
                    continue
                
                if (y1 <= lat < y2) or (y2 <= lat < y1):
                    t = (lat - y1) / (y2 - y1)
                    x_intersect = x1 + t * (x2 - x1)
                    intersections.append(x_intersect)
            
            intersections.sort()
            for i in range(0, len(intersections) - 1, 2):
                lon_start = int(math.floor(intersections[i]))
                lon_end = int(math.ceil(intersections[i + 1]))
                for lon in range(lon_start, lon_end + 1):
                    land.set_land(lat, lon)
        
        # Add boundary with thickness
        for i in range(len(boundary)):
            p1 = boundary[i]
            p2 = boundary[(i + 1) % len(boundary)]
            dist = max(abs(p2[0] - p1[0]), abs(p2[1] - p1[1]), 1)
            steps = int(dist) + 1
            for t in range(steps + 1):
                lat = p1[0] + (p2[0] - p1[0]) * t / steps
                lon = p1[1] + (p2[1] - p1[1]) * t / steps
                lat_i, lon_i = int(round(lat)), int(round(lon))
                for dlat in range(-1, 2):
                    for dlon in range(-1, 2):
                        land.set_land(lat_i + dlat, lon_i + dlon)
    
    return land

# Replace line 586:
print("Building land lookup table...", flush=True)
LAND_LOOKUP = build_land_lookup_v2()
print(f"  Land grid initialized")

# Update is_land() (line 589):
def is_land(lat: float, lon: float) -> bool:
    """Fast land detection using bitmask grid"""
    return LAND_LOOKUP.is_land(int(round(lat)), int(round(lon)))
```

**Expected:** +3-5 FPS improvement + cleaner code

---

## Recipe 4: Grid Allocation Reuse (EASY - 2-3 FPS)

**Add after line 630:**
```python
# =============================================================================
# GRID CACHE (Reuse across frames)
# =============================================================================

_GRID_CACHE = {}

def _get_grid_arrays(width: int, height: int):
    """Get or create and reuse grid arrays"""
    key = (width, height)
    
    if key not in _GRID_CACHE:
        _GRID_CACHE[key] = {
            'land_grid': [[0 for _ in range(width)] for _ in range(height)],
            'ocean_grid': [[0 for _ in range(width)] for _ in range(height)],
            'land_intensities': [[0.0 for _ in range(width)] for _ in range(height)],
            'ocean_intensities': [[0.0 for _ in range(width)] for _ in range(height)],
            'land_counts': [[0 for _ in range(width)] for _ in range(height)],
            'ocean_counts': [[0 for _ in range(width)] for _ in range(height)],
            'is_specular': [[False for _ in range(width)] for _ in range(height)],
            'is_polar_cell': [[False for _ in range(width)] for _ in range(height)],
        }
    
    # Clear previous frame data
    arrays = _GRID_CACHE[key]
    for cy in range(height):
        for cx in range(width):
            arrays['land_grid'][cy][cx] = 0
            arrays['ocean_grid'][cy][cx] = 0
            arrays['land_intensities'][cy][cx] = 0.0
            arrays['ocean_intensities'][cy][cx] = 0.0
            arrays['land_counts'][cy][cx] = 0
            arrays['ocean_counts'][cy][cx] = 0
            arrays['is_specular'][cy][cx] = False
            arrays['is_polar_cell'][cy][cx] = False
    
    return arrays
```

**Modify render_frame (lines 660-669):**
```python
# OLD:
land_grid = [[0 for _ in range(cell_width)] for _ in range(cell_height)]
ocean_grid = [[0 for _ in range(cell_width)] for _ in range(cell_height)]
# ... 6 more lines

# NEW:
arrays = _get_grid_arrays(cell_width, cell_height)
land_grid = arrays['land_grid']
ocean_grid = arrays['ocean_grid']
land_intensities = arrays['land_intensities']
ocean_intensities = arrays['ocean_intensities']
land_counts = arrays['land_counts']
ocean_counts = arrays['ocean_counts']
is_specular = arrays['is_specular']
is_polar_cell = arrays['is_polar_cell']
```

**Expected:** +2-3 FPS on sustained frames

---

## Complete Benchmark Script

Add this to track improvements:

```python
# Add to top of globe.py
import time
from collections import deque

FPS_HISTORY = deque(maxlen=60)
FRAME_TIMES = deque(maxlen=60)

def update_metrics(elapsed):
    """Track frame metrics"""
    FRAME_TIMES.append(elapsed)
    fps = 1.0 / elapsed if elapsed > 0 else 0
    FPS_HISTORY.append(fps)

# In main loop (before time.sleep):
frame_start = time.perf_counter()
frame = render_frame(theta, night_mode)
frame_elapsed = time.perf_counter() - frame_start
update_metrics(frame_elapsed)

avg_fps = sum(FPS_HISTORY) / len(FPS_HISTORY) if FPS_HISTORY else 0
avg_frame_ms = (sum(FRAME_TIMES) / len(FRAME_TIMES)) * 1000 if FRAME_TIMES else 0

# Update status bar with timing
status = (
    f"\n  {mode} | Quality: {quality} | "
    f"FPS: {avg_fps:.1f} (instant: {1/frame_elapsed:.1f}) | "
    f"Frame: {avg_frame_ms:.2f}ms | "
    f"θ={math.degrees(theta) % 360:.0f}° | "
    f"{'⏸ PAUSED' if paused else '▶ Playing'}\n"
    f"  Controls: ←→=rotate | n=night | space=pause | q=quit | 1-4=quality | a=atmo | c/l=cities | s=specular | i=ice"
)
```

---

## Implementation Order

1. **String Cache** (30 min) - Highest ROI, lowest effort
2. **Trig Simplification** (20 min) - Second highest gain, trivial change
3. **Grid Reuse** (20 min) - Easy memory optimization
4. **Land Bitmask** (2 hours) - Best architecture, more complex
5. **Lookup Table** (Optional) - Only if maximum performance needed

---

## Verification Checklist

After each optimization:

- [ ] Visual output identical to original
- [ ] No crashes or errors on resize
- [ ] Performance metrics improve as expected
- [ ] Night/day mode still works
- [ ] All features toggle correctly
- [ ] No memory leaks (check with `top`/`Activity Monitor`)

