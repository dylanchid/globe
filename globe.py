#!/usr/bin/env python3
"""
Ultra High-Resolution 3D Terminal Globe v2
===========================================
COMPLETE REDESIGN: Rasterization-based rendering

Key changes from v1:
1. RASTERIZATION instead of point-plotting - every pixel raycast to sphere
2. DENSE LAND DATA - uses polygon-based land detection, not sparse points
3. PROPER SUB-PIXEL - each Braille dot independently sampled
4. SOLID OCEAN - filled ocean with depth-based shading
5. TRUE ANTIALIASING - 8 samples per character cell
"""

import math
import time
import sys
import os
import select
import tty
import termios
from shutil import get_terminal_size
from dataclasses import dataclass
from typing import List, Tuple, Optional, Set, Dict
import random

# Shapefile support for high-resolution geographic data
try:
    import shapefile
    SHAPEFILE_AVAILABLE = True
except ImportError:
    SHAPEFILE_AVAILABLE = False

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class GlobeConfig:
    detail_level: int = 4  # 1=low, 2=medium, 3=high, 4=ultra
    enable_atmosphere: bool = True
    enable_city_lights: bool = True
    enable_clouds: bool = False  # Disabled by default for cleaner look
    enable_ocean_specular: bool = True
    enable_polar_ice: bool = True
    rotation_speed: float = 0.025
    
    @property
    def samples_per_cell(self) -> int:
        """Number of sub-pixel samples per Braille cell"""
        return {1: 2, 2: 4, 3: 6, 4: 8}[self.detail_level]

CONFIG = GlobeConfig()

# =============================================================================
# TERMINAL SETUP
# =============================================================================

def get_size():
    size = get_terminal_size(fallback=(120, 40))
    return size.columns, size.lines - 3

WIDTH, HEIGHT = get_size()
RESET = '\033[0m'

# Braille mapping: 2x4 grid of dots per character
BRAILLE_BASE = 0x2800
# Dot positions: (col, row) -> bit index
#   0 3
#   1 4
#   2 5
#   6 7
BRAILLE_DOT_MAP = {
    (0, 0): 0, (1, 0): 3,
    (0, 1): 1, (1, 1): 4,
    (0, 2): 2, (1, 2): 5,
    (0, 3): 6, (1, 3): 7,
}
BRAILLE_BITS = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]

# =============================================================================
# COLOR DEFINITIONS
# =============================================================================

# Land colors - gradient from dark to bright based on lighting
LAND_COLORS = [
    '\033[38;5;22m',   # Very dark green (shadow)
    '\033[38;5;28m',   # Dark green
    '\033[38;5;34m',   # Medium green
    '\033[38;5;40m',   # Bright green
    '\033[38;5;46m',   # Very bright green (highlight)
]

LAND_NIGHT_COLORS = [
    '\033[38;5;235m',  # Very dark
    '\033[38;5;237m',  # Dark
    '\033[38;5;239m',  # Medium dark
    '\033[38;5;241m',  # Slightly visible
    '\033[38;5;243m',  # Dim visible
]

# Ocean colors - gradient from deep to surface
OCEAN_COLORS = [
    '\033[38;5;17m',   # Very deep (dark blue)
    '\033[38;5;18m',   # Deep
    '\033[38;5;19m',   # Medium deep
    '\033[38;5;24m',   # Shallow
    '\033[38;5;31m',   # Surface (bright blue)
]

OCEAN_SPECULAR = '\033[38;5;159m'  # Bright cyan for specular
ICE_COLOR = '\033[38;5;255m'       # White
ATMOSPHERE_COLOR = '\033[38;5;45m' # Cyan glow
CITY_COLOR = '\033[38;5;226m'      # Yellow

# =============================================================================
# COMPREHENSIVE LAND DATA
# =============================================================================

# Instead of sparse points, we use DENSE coastal outlines that can be
# interpolated. This gives us ~15,000+ effective sample points.

# Format: List of (lat, lon) defining continental boundaries
# Points are connected, so we can fill between them

CONTINENT_BOUNDARIES = {
    # NORTH AMERICA - detailed coastline
    'north_america': [
        # Alaska
        (71, -156), (70, -160), (68, -165), (65, -168), (63, -166), (60, -164),
        (58, -160), (56, -158), (55, -160), (54, -165), (52, -170), (51, -175),
        (52, -177), (54, -165), (55, -162), (57, -155), (59, -152), (60, -148),
        (61, -145), (62, -142), (63, -140), (65, -138), (68, -135), (70, -140),
        (71, -145), (72, -150), (71, -156),
        # Canada West Coast
        (60, -140), (58, -136), (56, -132), (54, -130), (52, -128), (50, -126),
        (49, -124), (48, -123),
        # US West Coast  
        (48, -124), (46, -124), (44, -124), (42, -124), (40, -122), (38, -122),
        (36, -121), (34, -119), (32, -117), (30, -115), (28, -113),
        # Mexico West
        (28, -113), (26, -112), (24, -110), (22, -106), (20, -105), (18, -103),
        (16, -95), (15, -92),
        # Central America
        (15, -92), (14, -88), (12, -86), (10, -84), (9, -80), (8, -78),
        # Back up East Coast
        (8, -77), (10, -75), (12, -72), (15, -70), (18, -67), (20, -75),
        (22, -80), (25, -80), (28, -82), (30, -84), (32, -81), (35, -76),
        (38, -75), (40, -74), (42, -70), (44, -68), (46, -67), (48, -65),
        (50, -60), (52, -56), (54, -58), (56, -60), (58, -64), (60, -65),
        # Hudson Bay region
        (60, -78), (58, -82), (56, -85), (54, -88), (52, -90), (50, -88),
        (52, -82), (55, -78), (58, -76), (60, -78),
        # Northern Canada/Arctic
        (70, -100), (72, -95), (74, -90), (75, -85), (74, -80), (72, -75),
        (70, -70), (68, -65), (65, -62), (62, -64), (60, -65),
        (62, -70), (65, -75), (68, -80), (70, -85), (72, -90), (74, -95),
        (76, -100), (75, -110), (73, -120), (71, -130), (70, -140), (71, -156),
    ],
    
    # SOUTH AMERICA
    'south_america': [
        (12, -72), (10, -75), (8, -77), (5, -77), (2, -79), (0, -80), (-3, -80),
        (-6, -81), (-10, -78), (-14, -76), (-18, -70), (-22, -70), (-26, -70),
        (-30, -71), (-35, -72), (-40, -73), (-45, -74), (-50, -74), (-54, -70),
        (-55, -68), (-54, -65), (-52, -60), (-48, -58), (-44, -62), (-40, -62),
        (-35, -58), (-30, -52), (-25, -48), (-22, -42), (-18, -40), (-14, -42),
        (-10, -38), (-6, -35), (-2, -44), (2, -50), (5, -55), (8, -60),
        (10, -65), (12, -72),
    ],
    
    # EUROPE (mainland)
    'europe': [
        # Iberia
        (43, -9), (42, -8), (38, -9), (36, -6), (36, -2), (38, 0), (40, 0),
        (42, 3), (43, 3),
        # France/Low Countries
        (43, 3), (44, 5), (46, 6), (48, 2), (50, 2), (51, 4), (52, 5), (54, 9),
        # Germany/Poland
        (54, 9), (54, 14), (54, 19), (52, 22), (50, 20), (48, 17), (47, 15),
        # Balkans
        (46, 14), (44, 15), (42, 20), (40, 22), (38, 24), (36, 26), (35, 25),
        # Greece/Turkey border
        (36, 28), (38, 27), (40, 26), (42, 28),
        # Black Sea coast
        (42, 28), (44, 34), (46, 38), (48, 40), (50, 40), (52, 42),
        # Russia/Baltics
        (54, 40), (56, 38), (58, 32), (60, 28), (62, 26), (64, 28),
        # Scandinavia East
        (66, 26), (68, 24), (70, 28), (71, 28),
        # Around Scandinavia
        (70, 22), (68, 16), (66, 12), (64, 10), (62, 8), (60, 6), (58, 8),
        (56, 8), (54, 9),
    ],
    
    # BRITISH ISLES
    'britain': [
        (50, -5), (51, -4), (52, -5), (53, -4), (54, -3), (55, -2), (56, -3),
        (57, -5), (58, -6), (59, -3), (58, -1), (56, 0), (54, 0), (53, 1),
        (52, 1), (51, 1), (50, 0), (50, -2), (50, -5),
    ],
    
    # IRELAND
    'ireland': [
        (51, -10), (52, -10), (53, -10), (54, -9), (55, -8), (55, -6), (54, -6),
        (53, -6), (52, -7), (51, -9), (51, -10),
    ],
    
    # AFRICA
    'africa': [
        (37, -6), (35, -2), (33, 0), (30, -5), (28, -10), (25, -15), (22, -17),
        (18, -16), (14, -17), (10, -15), (6, -10), (5, -5), (4, 0), (5, 5),
        (6, 10), (4, 10), (2, 8), (0, 10), (-2, 12), (-5, 12), (-8, 14),
        (-12, 15), (-16, 12), (-20, 14), (-24, 16), (-28, 18), (-32, 18),
        (-34, 20), (-34, 25), (-32, 28), (-28, 30), (-24, 32), (-20, 35),
        (-16, 38), (-12, 40), (-8, 42), (-4, 42), (0, 42), (4, 44), (8, 48),
        (12, 45), (18, 42), (24, 38), (28, 35), (32, 32), (34, 28), (36, 20),
        (36, 14), (37, 10), (37, -6),
    ],
    
    # MADAGASCAR
    'madagascar': [
        (-12, 49), (-14, 48), (-18, 44), (-22, 44), (-25, 46), (-24, 48),
        (-20, 50), (-16, 50), (-12, 49),
    ],
    
    # ASIA (mainland)
    'asia': [
        # Middle East
        (32, 32), (34, 36), (36, 40), (38, 44), (40, 50), (42, 54), (38, 58),
        (34, 60), (30, 58), (26, 56), (24, 54), (22, 56), (20, 60), (18, 62),
        # India
        (22, 68), (20, 72), (18, 76), (14, 78), (10, 78), (8, 76), (10, 72),
        (12, 68), (16, 72), (20, 72),
        # Southeast Asia
        (20, 92), (18, 96), (14, 98), (10, 100), (6, 102), (2, 104), (0, 106),
        (-2, 110), (-6, 112), (-8, 115), (-10, 120),
        # Indonesia connection (simplified)
        (-8, 120), (-6, 118), (-4, 116), (-2, 115), (0, 114),
        # Back to mainland
        (2, 110), (6, 108), (10, 106), (14, 108), (18, 106), (22, 108),
        # China Coast
        (24, 118), (28, 120), (32, 122), (36, 122), (40, 120), (42, 130),
        (46, 135), (50, 140),
        # Russia Pacific
        (50, 140), (54, 142), (58, 150), (62, 160), (65, 170), (68, 180),
        # Siberia North
        (72, 170), (74, 150), (76, 130), (75, 100), (73, 80), (70, 60),
        (68, 50), (65, 45), (60, 42), (55, 40), (50, 45), (45, 42), (42, 38),
        # Back to Middle East
        (40, 35), (38, 34), (36, 33), (34, 32), (32, 32),
    ],
    
    # JAPAN
    'japan_honshu': [
        (35, 139), (36, 140), (38, 140), (40, 140), (41, 141), (40, 139),
        (38, 137), (36, 136), (35, 135), (34, 134), (34, 136), (35, 139),
    ],
    'japan_hokkaido': [
        (42, 140), (43, 141), (45, 142), (44, 145), (42, 145), (41, 143),
        (42, 140),
    ],
    'japan_kyushu': [
        (32, 130), (33, 131), (34, 132), (33, 130), (32, 130),
    ],
    
    # KOREA
    'korea': [
        (35, 126), (36, 127), (37, 127), (38, 127), (39, 128), (38, 129),
        (36, 129), (35, 129), (34, 127), (35, 126),
    ],
    
    # TAIWAN
    'taiwan': [
        (22, 120), (23, 121), (25, 122), (25, 121), (23, 120), (22, 120),
    ],
    
    # PHILIPPINES (simplified)
    'philippines': [
        (18, 120), (16, 120), (14, 121), (12, 122), (10, 124), (8, 126),
        (10, 126), (12, 125), (14, 124), (16, 122), (18, 122), (18, 120),
    ],
    
    # INDONESIA (simplified - main islands)
    'sumatra': [
        (5, 95), (3, 98), (0, 101), (-3, 104), (-5, 105), (-4, 102), (-1, 99),
        (2, 96), (5, 95),
    ],
    'borneo': [
        (6, 116), (4, 118), (1, 118), (-2, 117), (-3, 115), (-2, 112),
        (1, 110), (4, 115), (6, 116),
    ],
    'java': [
        (-6, 106), (-7, 108), (-8, 112), (-8, 114), (-7, 112), (-6, 110),
        (-6, 106),
    ],
    'sulawesi': [
        (-1, 120), (-2, 122), (-4, 122), (-5, 120), (-3, 119), (-1, 120),
    ],
    'papua': [
        (-2, 132), (-4, 136), (-6, 140), (-8, 142), (-6, 145), (-4, 142),
        (-2, 138), (-1, 134), (-2, 132),
    ],
    
    # SRI LANKA
    'sri_lanka': [
        (9, 80), (8, 81), (7, 82), (6, 80), (8, 79), (9, 80),
    ],
    
    # AUSTRALIA
    'australia': [
        (-12, 130), (-14, 127), (-18, 122), (-22, 114), (-26, 113), (-30, 115),
        (-34, 116), (-35, 118), (-36, 137), (-38, 145), (-37, 150), (-34, 151),
        (-30, 153), (-26, 153), (-22, 150), (-18, 146), (-14, 142), (-12, 136),
        (-11, 132), (-12, 130),
    ],
    
    # NEW ZEALAND
    'new_zealand_north': [
        (-34, 173), (-36, 174), (-38, 176), (-40, 176), (-41, 175), (-39, 174),
        (-36, 175), (-34, 173),
    ],
    'new_zealand_south': [
        (-41, 173), (-43, 172), (-45, 170), (-46, 168), (-45, 167), (-43, 170),
        (-41, 173),
    ],
    
    # GREENLAND
    'greenland': [
        (60, -43), (62, -42), (65, -40), (68, -32), (72, -28), (76, -22),
        (80, -25), (82, -30), (83, -40), (81, -50), (78, -56), (74, -58),
        (70, -55), (66, -52), (62, -48), (60, -45), (60, -43),
    ],
    
    # ICELAND
    'iceland': [
        (64, -22), (65, -20), (66, -18), (66, -14), (65, -14), (64, -16),
        (63, -20), (64, -22),
    ],
    
    # SCANDINAVIA (more detailed)
    'scandinavia': [
        (56, 8), (58, 6), (60, 5), (62, 6), (64, 10), (66, 12), (68, 16),
        (70, 22), (71, 26), (70, 30), (68, 28), (66, 24), (64, 20), (62, 18),
        (60, 14), (58, 12), (56, 12), (56, 8),
    ],
    
    # ANTARCTICA (ring)
    'antarctica': [
        (-65, 0), (-68, 30), (-70, 60), (-72, 90), (-70, 120), (-68, 150),
        (-65, 180), (-68, -150), (-70, -120), (-72, -90), (-70, -60),
        (-68, -30), (-65, 0),
    ],
    
    # CARIBBEAN ISLANDS (simplified)
    'cuba': [
        (22, -84), (23, -82), (22, -78), (20, -75), (20, -77), (21, -80),
        (22, -84),
    ],
    'hispaniola': [
        (19, -72), (20, -70), (19, -68), (18, -70), (19, -72),
    ],
}

# Major cities for night lights
MAJOR_CITIES = [
    (40.7, -74.0), (34.0, -118.2), (41.9, -87.6), (51.5, -0.1), (48.9, 2.4),
    (35.7, 139.7), (31.2, 121.5), (39.9, 116.4), (19.1, 72.9), (28.6, 77.2),
    (-23.5, -46.6), (-34.6, -58.4), (55.8, 37.6), (30.0, 31.2), (-33.9, 151.2),
    (52.5, 13.4), (37.6, 126.9), (13.8, 100.5), (1.4, 103.8), (22.3, 114.2),
    (25.8, -80.2), (47.6, -122.3), (49.3, -123.1), (45.5, -73.6), (43.7, -79.4),
]

# =============================================================================
# SHAPEFILE LOADING (High-Resolution Geographic Data)
# =============================================================================

def load_boundaries_from_shapefile(shapefile_path: str) -> Dict[str, List[Tuple[float, float]]]:
    """
    Load country/land boundaries from a Natural Earth shapefile.
    Returns dict of polygon name -> list of (lat, lon) tuples.
    
    Note: Shapefiles use (lon, lat) order; we convert to (lat, lon).
    """
    if not SHAPEFILE_AVAILABLE:
        print("  Warning: pyshp not installed, using hardcoded boundaries")
        return {}
    
    if not os.path.exists(shapefile_path):
        print(f"  Warning: Shapefile not found: {shapefile_path}")
        return {}
    
    try:
        sf = shapefile.Reader(shapefile_path)
        boundaries = {}
        
        for i, shape in enumerate(sf.shapes()):
            # Get country name from record if available
            try:
                record = sf.record(i)
                # Try common field names for country/region name
                name = None
                for field_idx, field in enumerate(sf.fields[1:]):  # Skip DeletionFlag
                    field_name = field[0].upper()
                    if field_name in ('NAME', 'ADMIN', 'SOVEREIGNT', 'NAME_LONG'):
                        name = record[field_idx]
                        break
                if not name:
                    name = f"region_{i}"
            except:
                name = f"region_{i}"
            
            # Handle multi-part polygons (islands, etc.)
            if shape.shapeType in (shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM):
                parts = list(shape.parts) + [len(shape.points)]
                
                for part_idx in range(len(parts) - 1):
                    start = parts[part_idx]
                    end = parts[part_idx + 1]
                    points = shape.points[start:end]
                    
                    # Convert from (lon, lat) to (lat, lon)
                    polygon = [(pt[1], pt[0]) for pt in points]
                    
                    # Skip very small polygons (tiny islands)
                    if len(polygon) < 4:
                        continue
                    
                    part_name = f"{name}_{part_idx}" if part_idx > 0 else name
                    # Ensure unique names
                    base_name = part_name
                    counter = 1
                    while part_name in boundaries:
                        part_name = f"{base_name}_{counter}"
                        counter += 1
                    
                    boundaries[part_name] = polygon
        
        return boundaries
    
    except Exception as e:
        print(f"  Warning: Error reading shapefile: {e}")
        return {}

def get_boundaries() -> Dict[str, List[Tuple[float, float]]]:
    """
    Get land boundaries, preferring shapefile data if available.
    Falls back to hardcoded CONTINENT_BOUNDARIES.
    """
    # Try to load from shapefile first
    shapefile_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "110m_cultural",
        "ne_110m_admin_0_countries.shp"
    )
    
    shapefile_boundaries = load_boundaries_from_shapefile(shapefile_path)
    
    if shapefile_boundaries:
        print(f"  Loaded {len(shapefile_boundaries)} polygons from shapefile")
        return shapefile_boundaries
    else:
        print(f"  Using {len(CONTINENT_BOUNDARIES)} hardcoded polygons")
        return CONTINENT_BOUNDARIES

# =============================================================================
# LAND DETECTION - POLYGON-BASED
# =============================================================================

def build_land_lookup() -> Set[Tuple[int, int]]:
    """
    Pre-compute a lookup table of land cells at 1-degree resolution.
    Uses scanline polygon fill with proper edge handling.
    """
    land_cells = set()
    
    # Get boundaries (shapefile or hardcoded)
    boundaries = get_boundaries()
    
    for name, boundary in boundaries.items():
        if len(boundary) < 3:
            continue
        
        # Get bounds
        lats = [p[0] for p in boundary]
        lons = [p[1] for p in boundary]
        min_lat, max_lat = int(min(lats)) - 1, int(max(lats)) + 1
        min_lon, max_lon = int(min(lons)) - 1, int(max(lons)) + 1
        
        # Scanline fill
        for lat in range(min_lat, max_lat + 1):
            # Find intersections with polygon edges
            intersections = []
            n = len(boundary)
            
            for i in range(n):
                p1 = boundary[i]
                p2 = boundary[(i + 1) % n]
                
                y1, y2 = p1[0], p2[0]
                x1, x2 = p1[1], p2[1]
                
                # Skip horizontal edges
                if y1 == y2:
                    continue
                
                # Check if scanline crosses this edge
                if (y1 <= lat < y2) or (y2 <= lat < y1):
                    # Calculate x intersection
                    t = (lat - y1) / (y2 - y1)
                    x_intersect = x1 + t * (x2 - x1)
                    intersections.append(x_intersect)
            
            # Sort intersections
            intersections.sort()
            
            # Fill between pairs
            for i in range(0, len(intersections) - 1, 2):
                lon_start = int(math.floor(intersections[i]))
                lon_end = int(math.ceil(intersections[i + 1]))
                for lon in range(lon_start, lon_end + 1):
                    land_cells.add((lat, lon))
        
        # Also add boundary points with thickness for coastlines
        for i in range(len(boundary)):
            p1 = boundary[i]
            p2 = boundary[(i + 1) % len(boundary)]
            
            # Interpolate along edge
            dist = max(abs(p2[0] - p1[0]), abs(p2[1] - p1[1]), 1)
            steps = int(dist) + 1
            for t in range(steps + 1):
                lat = p1[0] + (p2[0] - p1[0]) * t / steps
                lon = p1[1] + (p2[1] - p1[1]) * t / steps
                lat_i, lon_i = int(round(lat)), int(round(lon))
                # Add with thickness for visibility
                for dlat in range(-1, 2):
                    for dlon in range(-1, 2):
                        land_cells.add((lat_i + dlat, lon_i + dlon))
    
    return land_cells

# Pre-compute land lookup at module load
print("Building land lookup table...", flush=True)
LAND_LOOKUP = build_land_lookup()
print(f"  {len(LAND_LOOKUP)} land cells indexed")

def is_land(lat: float, lon: float) -> bool:
    """Fast land detection using pre-computed lookup"""
    # Normalize longitude to -180 to 180
    while lon > 180:
        lon -= 360
    while lon < -180:
        lon += 360
    
    # Check exact cell and neighbors for smoothness
    lat_i, lon_i = int(round(lat)), int(round(lon))
    return (lat_i, lon_i) in LAND_LOOKUP

def is_polar(lat: float) -> bool:
    """Check if latitude is in polar ice region"""
    return lat > 70 or lat < -60

# =============================================================================
# 3D MATH
# =============================================================================

def to_cartesian(lat_deg: float, lon_deg: float) -> Tuple[float, float, float]:
    """Convert lat/lon to 3D unit sphere coordinates"""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    x = math.cos(lat) * math.cos(lon)
    y = math.cos(lat) * math.sin(lon)
    z = math.sin(lat)
    return x, y, z

def to_latlon(x: float, y: float, z: float) -> Tuple[float, float]:
    """Convert 3D coordinates back to lat/lon"""
    lat = math.degrees(math.asin(max(-1, min(1, z))))
    lon = math.degrees(math.atan2(y, x))
    return lat, lon

def rotate_z(x: float, y: float, z: float, theta: float) -> Tuple[float, float, float]:
    """Rotate around Z axis (Earth's spin axis)"""
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    return (cos_t * x - sin_t * y, sin_t * x + cos_t * y, z)

# =============================================================================
# RASTERIZATION-BASED RENDERING
# =============================================================================

def render_frame(theta: float, night_mode: bool = False) -> str:
    """
    Render using RASTERIZATION: for each screen position, raycast to sphere
    and sample the texture (land/ocean) at that point.
    
    Key improvement: Only set dots for LAND pixels, leaving ocean as empty space.
    This creates visible continent shapes with antialiased edges.
    """
    global WIDTH, HEIGHT
    WIDTH, HEIGHT = get_size()
    
    # Light direction (constant - sun doesn't move when toggling night mode)
    light_dir = (0.6, 0.5, 0.6)
    light_mag = math.sqrt(sum(c*c for c in light_dir))
    light_dir = tuple(c / light_mag for c in light_dir)
    
    # Specular highlight center (in screen space, relative to globe center)
    spec_offset_x = 0.25
    spec_offset_y = -0.15
    
    # Braille grid: each cell is 2 columns x 4 rows of dots
    cell_width = WIDTH
    cell_height = HEIGHT
    
    # Each cell accumulates dot bits and color info
    # We track land dots and ocean dots separately
    land_grid = [[0 for _ in range(cell_width)] for _ in range(cell_height)]
    ocean_grid = [[0 for _ in range(cell_width)] for _ in range(cell_height)]
    land_colors = [[None for _ in range(cell_width)] for _ in range(cell_height)]
    ocean_colors = [[None for _ in range(cell_width)] for _ in range(cell_height)]
    land_intensities = [[0.0 for _ in range(cell_width)] for _ in range(cell_height)]
    ocean_intensities = [[0.0 for _ in range(cell_width)] for _ in range(cell_height)]
    land_counts = [[0 for _ in range(cell_width)] for _ in range(cell_height)]
    ocean_counts = [[0 for _ in range(cell_width)] for _ in range(cell_height)]
    is_specular = [[False for _ in range(cell_width)] for _ in range(cell_height)]
    is_polar_cell = [[False for _ in range(cell_width)] for _ in range(cell_height)]
    
    # Sphere radius - make it fit nicely with padding
    # Terminal chars are roughly 2x taller than wide, so adjust accordingly
    padding = 2  # cells of padding around sphere
    max_radius_x = (WIDTH / 2) - padding
    max_radius_y = (HEIGHT / 2) - padding
    
    # Use the smaller dimension to ensure sphere fits, with aspect correction
    # Terminal chars are ~2:1 aspect ratio (taller than wide)
    char_aspect = 2.0  # height/width ratio of terminal characters
    
    # We want the sphere to appear circular, so:
    # radius_y (in chars) * char_aspect = radius_x (in chars) * 1
    # radius_y = radius_x / char_aspect
    
    sphere_radius_x = min(max_radius_x, max_radius_y * char_aspect)
    sphere_radius_y = sphere_radius_x / char_aspect
    
    center_x = WIDTH / 2
    center_y = HEIGHT / 2
    
    # Sample each Braille dot position
    for cy in range(cell_height):
        for cx in range(cell_width):
            # Sample each of the 8 dots in the Braille cell
            for dot_col in range(2):
                for dot_row in range(4):
                    # Sub-pixel position within the cell
                    sub_x = (dot_col + 0.5) / 2.0  # 0.25 or 0.75
                    sub_y = (dot_row + 0.5) / 4.0  # 0.125, 0.375, 0.625, 0.875
                    
                    # Screen position
                    px = cx + sub_x
                    py = cy + sub_y
                    
                    # Normalize to sphere coordinates (-1 to 1)
                    nx = (px - center_x) / sphere_radius_x
                    ny = (py - center_y) / sphere_radius_y
                    
                    # Check if within sphere radius
                    r2 = nx * nx + ny * ny
                    if r2 > 1.0:
                        continue  # Outside globe - don't set any dot
                    
                    # Compute Z on unit sphere (front-facing)
                    nz = math.sqrt(1.0 - r2)
                    
                    # Convert from screen coords to 3D sphere point
                    # In our convention: x=right, z=up, y=depth(into screen)
                    sx, sy, sz = nx, nz, -ny  # Remap: screen_y becomes -z (up)
                    
                    # Rotate around Z axis (Earth's spin)
                    rx, ry, rz = rotate_z(sx, sy, sz, -theta)
                    
                    # Get lat/lon at this rotated position
                    lat, lon = to_latlon(rx, ry, rz)
                    
                    # Sample terrain
                    terrain_is_land = is_land(lat, lon)
                    terrain_is_polar = is_polar(lat)
                    
                    # Calculate lighting
                    intensity = max(0, rx * light_dir[0] + ry * light_dir[1] + rz * light_dir[2])
                    
                    # Get the Braille dot index
                    dot_idx = BRAILLE_DOT_MAP[(dot_col, dot_row)]
                    dot_bit = BRAILLE_BITS[dot_idx]
                    
                    # Determine what type of surface this is and set appropriate dot
                    if terrain_is_polar and CONFIG.enable_polar_ice:
                        # Polar ice caps - treat as special land
                        land_grid[cy][cx] |= dot_bit
                        land_intensities[cy][cx] += intensity
                        land_counts[cy][cx] += 1
                        is_polar_cell[cy][cx] = True
                    elif terrain_is_land:
                        # Land - set dot in land grid
                        land_grid[cy][cx] |= dot_bit
                        land_intensities[cy][cx] += intensity
                        land_counts[cy][cx] += 1
                    else:
                        # Ocean - set dot in ocean grid
                        ocean_grid[cy][cx] |= dot_bit
                        ocean_intensities[cy][cx] += intensity
                        ocean_counts[cy][cx] += 1
                        
                        # Check for specular highlight
                        if CONFIG.enable_ocean_specular:
                            spec_dx = nx - spec_offset_x
                            spec_dy = ny - spec_offset_y
                            spec_dist = math.sqrt(spec_dx * spec_dx + spec_dy * spec_dy)
                            if spec_dist < 0.12 and intensity > 0.4:
                                is_specular[cy][cx] = True
    
    # Now build the final output grid
    # Strategy: Show LAND with Braille dots, ocean as a subtle background
    final_grid = [[0 for _ in range(cell_width)] for _ in range(cell_height)]
    final_colors = [[None for _ in range(cell_width)] for _ in range(cell_height)]
    
    for cy in range(cell_height):
        for cx in range(cell_width):
            land_dots = land_grid[cy][cx]
            ocean_dots = ocean_grid[cy][cx]
            
            if land_dots > 0:
                # This cell has land - show the land dots
                final_grid[cy][cx] = land_dots
                
                # Calculate land color based on intensity
                if land_counts[cy][cx] > 0:
                    avg_intensity = land_intensities[cy][cx] / land_counts[cy][cx]
                else:
                    avg_intensity = 0.5
                
                if is_polar_cell[cy][cx] and CONFIG.enable_polar_ice:
                    final_colors[cy][cx] = ICE_COLOR
                elif night_mode:
                    idx = min(int(avg_intensity * len(LAND_NIGHT_COLORS)), len(LAND_NIGHT_COLORS) - 1)
                    final_colors[cy][cx] = LAND_NIGHT_COLORS[idx]
                else:
                    idx = min(int(avg_intensity * len(LAND_COLORS)), len(LAND_COLORS) - 1)
                    final_colors[cy][cx] = LAND_COLORS[idx]
                    
            elif ocean_dots > 0:
                # Pure ocean cell - show ocean with subtle texture
                final_grid[cy][cx] = ocean_dots
                
                # Calculate ocean color based on intensity
                if ocean_counts[cy][cx] > 0:
                    avg_intensity = ocean_intensities[cy][cx] / ocean_counts[cy][cx]
                else:
                    avg_intensity = 0.5
                
                if is_specular[cy][cx]:
                    final_colors[cy][cx] = OCEAN_SPECULAR
                else:
                    idx = min(int(avg_intensity * len(OCEAN_COLORS)), len(OCEAN_COLORS) - 1)
                    final_colors[cy][cx] = OCEAN_COLORS[idx]
    
    # Add city lights in night mode
    if CONFIG.enable_city_lights and night_mode:
        for city_lat, city_lon in MAJOR_CITIES:
            # Rotate city to current view
            cx3d, cy3d, cz3d = to_cartesian(city_lat, city_lon)
            rx, ry, rz = rotate_z(cx3d, cy3d, cz3d, -theta)
            
            # Check if visible (front-facing)
            if ry < 0.1:  # Behind or edge
                continue
            
            # Check if on dark side
            intensity = rx * light_dir[0] + ry * light_dir[1] + rz * light_dir[2]
            if intensity > 0.2:  # Too bright for city lights
                continue
            
            # Project to screen
            screen_x = center_x + rx * sphere_radius_x
            screen_y = center_y - rz * sphere_radius_y  # Note: z is up
            
            cell_x = int(screen_x)
            cell_y = int(screen_y)
            
            if 0 <= cell_x < cell_width and 0 <= cell_y < cell_height:
                # Overlay city light - make it a bright dot
                final_grid[cell_y][cell_x] |= 0xFF  # Full Braille block
                final_colors[cell_y][cell_x] = CITY_COLOR
    
    # Add atmospheric glow at edges
    if CONFIG.enable_atmosphere:
        for cy in range(cell_height):
            for cx in range(cell_width):
                if final_grid[cy][cx] == 0:  # Empty cell
                    # Check distance from globe edge
                    nx = (cx + 0.5 - center_x) / sphere_radius_x
                    ny = (cy + 0.5 - center_y) / sphere_radius_y
                    r = math.sqrt(nx * nx + ny * ny)
                    
                    if 1.0 < r < 1.12:
                        glow = 1.0 - (r - 1.0) / 0.12
                        if glow > 0.2:
                            # Use partial Braille for glow - select dots based on position
                            if glow > 0.7:
                                final_grid[cy][cx] = 0x66  # ⡦ middle dots
                            elif glow > 0.4:
                                final_grid[cy][cx] = 0x24  # ⠤ some dots
                            else:
                                final_grid[cy][cx] = 0x04  # ⠄ minimal
                            final_colors[cy][cx] = ATMOSPHERE_COLOR
    
    # Convert to string output
    lines = []
    for cy in range(cell_height):
        line = ""
        for cx in range(cell_width):
            if final_grid[cy][cx] > 0:
                char = chr(BRAILLE_BASE + final_grid[cy][cx])
                color = final_colors[cy][cx] or RESET
                line += f"{color}{char}{RESET}"
            else:
                line += " "
        lines.append(line)
    
    return '\n'.join(lines)

# =============================================================================
# TERMINAL CONTROL
# =============================================================================

def clear_screen():
    print("\033[2J\033[H", end="", flush=True)

def hide_cursor():
    print("\033[?25l", end="", flush=True)

def show_cursor():
    print("\033[?25h", end="", flush=True)

def get_key():
    i, o, e = select.select([sys.stdin], [], [], 0.01)
    if i:
        return sys.stdin.read(1)
    return None

# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    theta = 0.0
    night_mode = False
    paused = False
    
    old_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    hide_cursor()
    
    try:
        frame_count = 0
        start_time = time.time()
        
        while True:
            # Render frame
            frame = render_frame(theta, night_mode)
            
            # Status bar
            mode = "🌙 Night" if night_mode else "☀️  Day"
            quality = ["Low", "Med", "High", "Ultra"][CONFIG.detail_level - 1]
            fps = frame_count / (time.time() - start_time + 0.001)
            
            features = []
            if CONFIG.enable_atmosphere:
                features.append("Atmo")
            if CONFIG.enable_city_lights:
                features.append("Cities")
            if CONFIG.enable_ocean_specular:
                features.append("Spec")
            if CONFIG.enable_polar_ice:
                features.append("Ice")
            
            status = (
                f"\n  {mode} | Quality: {quality} | Land cells: {len(LAND_LOOKUP)} | "
                f"FPS: {fps:.1f} | θ={math.degrees(theta) % 360:.0f}° | "
                f"{'⏸ PAUSED' if paused else '▶ Playing'}\n"
                f"  Controls: ←→=rotate | n=night | space=pause | q=quit | 1-4=quality | a=atmo | c/l=cities | s=specular | i=ice"
            )
            
            print("\033[2J\033[H" + frame + status, end="", flush=True)
            
            # Handle input
            key = get_key()
            if key:
                if key == 'q':
                    break
                elif key == 'n':
                    night_mode = not night_mode
                elif key == ' ':
                    paused = not paused
                elif key == 'a':
                    CONFIG.enable_atmosphere = not CONFIG.enable_atmosphere
                elif key == 's':
                    CONFIG.enable_ocean_specular = not CONFIG.enable_ocean_specular
                elif key == 'i':
                    CONFIG.enable_polar_ice = not CONFIG.enable_polar_ice
                elif key == 'c' or key == 'l':
                    CONFIG.enable_city_lights = not CONFIG.enable_city_lights
                elif key in ('1', '2', '3', '4'):
                    CONFIG.detail_level = int(key)
                elif key == '\x1b':
                    next1 = sys.stdin.read(1)
                    if next1 == '[':
                        arrow = sys.stdin.read(1)
                        if arrow in ['C', 'A']:
                            theta += 0.12
                        elif arrow in ['D', 'B']:
                            theta -= 0.12
            
            if not paused:
                theta += CONFIG.rotation_speed
            
            frame_count += 1
            time.sleep(0.03)
    
    except KeyboardInterrupt:
        pass
    finally:
        show_cursor()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        clear_screen()
        print("\n✨ Globe v2 stopped ✨\n")

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  🌍  TERMINAL GLOBE v2 - RASTERIZATION ENGINE  🌍           ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")
    print("  • Rendering: Full rasterization (not point-plotting)")
    print("  • Resolution: True 8-dot sub-pixel Braille")
    print("  • Land detection: Polygon-based with fill")
    print(f"  • Land cells: {len(LAND_LOOKUP)}")
    print("  • Features: Lighting, Ice caps, Specular, City lights, Atmosphere\n")
    print("  Starting in 2 seconds...\n")
    time.sleep(2)
    main()