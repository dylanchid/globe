#!/usr/bin/env python3
"""
Comprehensive test suite for Globe renderer.
Tests correctness, performance, and edge cases.
"""

import math
import time
import sys
from io import StringIO
from globe import (
    is_land, is_polar, to_cartesian, rotate_z, to_latlon,
    render_frame, CONFIG, LAND_GRID, BRAILLE_CACHE,
    LAND_LOOKUP, WIDTH, HEIGHT
)

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def pass_test(self, name):
        self.passed += 1
        print(f"  ✓ {name}")
    
    def fail_test(self, name, error):
        self.failed += 1
        self.errors.append((name, error))
        print(f"  ✗ {name}: {error}")
    
    def print_summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"RESULTS: {self.passed}/{total} passed")
        if self.errors:
            print(f"\nFailed tests:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        print(f"{'='*60}\n")

results = TestResults()

# =============================================================================
# UNIT TESTS
# =============================================================================

def test_land_detection():
    """Test land detection at known locations"""
    print("\n[UNIT TESTS] Land Detection")
    
    # Known land locations
    land_tests = [
        (0, 0, "Africa"),
        (40, -74, "New York"),
        (35, 139, "Tokyo"),
        (51, 0, "London"),
        (-33, 151, "Sydney"),
    ]
    
    for lat, lon, name in land_tests:
        is_land_result = is_land(lat, lon)
        if is_land_result:
            results.pass_test(f"Land detection at {name} ({lat}, {lon})")
        else:
            results.fail_test(f"Land detection at {name}", f"Expected land, got water")
    
    # Known ocean locations
    ocean_tests = [
        (0, 150, "Mid-Pacific"),
        (40, -60, "Atlantic"),
        (-50, 140, "Southern Ocean"),
    ]
    
    for lat, lon, name in ocean_tests:
        is_land_result = is_land(lat, lon)
        if not is_land_result:
            results.pass_test(f"Water detection at {name} ({lat}, {lon})")
        else:
            results.fail_test(f"Water detection at {name}", f"Expected water, got land")

def test_polar_detection():
    """Test polar ice cap detection"""
    print("\n[UNIT TESTS] Polar Detection")
    
    polar_tests = [
        (85, 0, True, "North Pole"),
        (-80, 0, True, "South Pole"),
        (45, 0, False, "Temperate"),
        (0, 0, False, "Equator"),
    ]
    
    for lat, lon, expected, name in polar_tests:
        result = is_polar(lat)
        if result == expected:
            results.pass_test(f"Polar detection at {name} ({lat})")
        else:
            results.fail_test(f"Polar detection at {name}", f"Expected {expected}, got {result}")

def test_coordinate_conversion():
    """Test lat/lon to cartesian and back"""
    print("\n[UNIT TESTS] Coordinate Conversion")
    
    test_coords = [
        (0, 0, "Prime meridian"),
        (45, 45, "NE quadrant"),
        (-45, -45, "SW quadrant"),
        (90, 0, "North pole"),
        (-90, 180, "South pole"),
    ]
    
    for lat, lon, name in test_coords:
        try:
            x, y, z = to_cartesian(lat, lon)
            # Check unit sphere
            distance = math.sqrt(x*x + y*y + z*z)
            if 0.99 < distance < 1.01:
                results.pass_test(f"Cartesian conversion {name}")
            else:
                results.fail_test(f"Cartesian conversion {name}", 
                                 f"Not on unit sphere: {distance}")
        except Exception as e:
            results.fail_test(f"Cartesian conversion {name}", str(e))

def test_rotation():
    """Test Z-axis rotation"""
    print("\n[UNIT TESTS] Rotation")
    
    try:
        x, y, z = 1, 0, 0
        
        # 90 degree rotation
        rx, ry, rz = rotate_z(x, y, z, math.pi / 2)
        if abs(rx) < 0.01 and abs(ry - 1) < 0.01 and abs(rz) < 0.01:
            results.pass_test("90° Z-rotation")
        else:
            results.fail_test("90° Z-rotation", f"Got ({rx}, {ry}, {rz})")
        
        # 360 degree rotation (should return to original)
        rx, ry, rz = rotate_z(x, y, z, 2 * math.pi)
        if abs(rx - x) < 0.01 and abs(ry - y) < 0.01 and abs(rz - z) < 0.01:
            results.pass_test("360° Z-rotation returns original")
        else:
            results.fail_test("360° Z-rotation", f"Not back to original")
    except Exception as e:
        results.fail_test("Rotation tests", str(e))

def test_braille_cache():
    """Test Braille cache is properly built"""
    print("\n[UNIT TESTS] Braille Cache")
    
    try:
        # Check cache size (should have ~4400 entries)
        cache_size = len(BRAILLE_CACHE)
        if 4000 < cache_size < 5000:
            results.pass_test(f"Braille cache size ({cache_size} entries)")
        else:
            results.fail_test("Braille cache size", 
                            f"Expected ~4400, got {cache_size}")
        
        # Check sample entries
        from globe import LAND_COLORS, RESET
        test_color = LAND_COLORS[0]
        test_bits = 0xFF
        key = (test_color, test_bits)
        
        if key in BRAILLE_CACHE:
            cached = BRAILLE_CACHE[key]
            if isinstance(cached, str) and test_color in cached and RESET in cached:
                results.pass_test("Braille cache entries are strings")
            else:
                results.fail_test("Braille cache entry format", "Not properly formatted")
        else:
            results.fail_test("Braille cache lookup", f"Missing key {key}")
    except Exception as e:
        results.fail_test("Braille cache test", str(e))

def test_land_grid():
    """Test LandGrid structure"""
    print("\n[UNIT TESTS] LandGrid Structure")
    
    try:
        # Check grid has data
        if LAND_GRID.count > 1000:
            results.pass_test(f"LandGrid populated ({LAND_GRID.count} cells)")
        else:
            results.fail_test("LandGrid population", f"Only {LAND_GRID.count} cells")
        
        # Check grid size
        if len(LAND_GRID.grid) == 180 * 360:
            results.pass_test("LandGrid dimensions (180x360)")
        else:
            results.fail_test("LandGrid dimensions", 
                            f"Wrong size: {len(LAND_GRID.grid)}")
        
        # Consistency check: grid queries should match
        from globe import LAND_LOOKUP
        consistent = True
        sample_count = 0
        for lat, lon in list(LAND_LOOKUP)[:100]:  # Check first 100
            if is_land(lat, lon):
                sample_count += 1
        
        if sample_count > 80:  # At least 80% should be land
            results.pass_test(f"LandGrid consistency (sampled {sample_count}/100)")
        else:
            results.fail_test("LandGrid consistency", 
                            f"Only {sample_count}% consistent")
    except Exception as e:
        results.fail_test("LandGrid test", str(e))

# =============================================================================
# RENDERING TESTS
# =============================================================================

def test_render_basic():
    """Test basic rendering works"""
    print("\n[RENDER TESTS] Basic Rendering")
    
    try:
        frame = render_frame(0, night_mode=False)
        
        if frame and isinstance(frame, str):
            results.pass_test("Frame renders as string")
        else:
            results.fail_test("Frame render", "Not a string")
        
        # Check frame has content
        if len(frame) > 100:
            results.pass_test(f"Frame has content ({len(frame)} chars)")
        else:
            results.fail_test("Frame content", f"Too short: {len(frame)} chars")
        
        # Check for Braille characters
        if any(ord(c) >= 0x2800 and ord(c) <= 0x28FF for c in frame):
            results.pass_test("Frame contains Braille characters")
        else:
            results.fail_test("Frame Braille", "No Braille characters found")
        
        # Check for ANSI color codes
        if '\033[38;5;' in frame or frame.count('\033') > 0:
            results.pass_test("Frame contains color codes")
        else:
            results.fail_test("Frame colors", "No color codes found")
    except Exception as e:
        results.fail_test("Basic rendering", str(e))

def test_render_night_mode():
    """Test night mode rendering"""
    print("\n[RENDER TESTS] Night Mode")
    
    try:
        frame_day = render_frame(0, night_mode=False)
        frame_night = render_frame(0, night_mode=True)
        
        # Frames should be different
        if frame_day != frame_night:
            results.pass_test("Night mode produces different frame")
        else:
            results.fail_test("Night mode difference", "Frames are identical")
        
        # Both should have content
        if len(frame_day) > 100 and len(frame_night) > 100:
            results.pass_test("Both day and night frames have content")
        else:
            results.fail_test("Frame content", "Frames too short")
    except Exception as e:
        results.fail_test("Night mode rendering", str(e))

def test_render_rotation():
    """Test rotation produces different frames"""
    print("\n[RENDER TESTS] Rotation")
    
    try:
        frame1 = render_frame(0, night_mode=False)
        frame2 = render_frame(0.5, night_mode=False)
        frame3 = render_frame(1.0, night_mode=False)
        
        # Different angles should produce different frames
        if frame1 != frame2 and frame2 != frame3:
            results.pass_test("Rotation produces different frames")
        else:
            results.fail_test("Rotation difference", "Frames are identical")
        
        # All should have content
        if len(frame1) > 100 and len(frame2) > 100 and len(frame3) > 100:
            results.pass_test("All rotation frames have content")
        else:
            results.fail_test("Rotation content", "Frames too short")
    except Exception as e:
        results.fail_test("Rotation rendering", str(e))

def test_config_changes():
    """Test CONFIG changes affect rendering"""
    print("\n[RENDER TESTS] Config Changes")
    
    try:
        # Render with current config
        frame1 = render_frame(0.5, night_mode=False)
        
        # Disable atmosphere
        original_atmo = CONFIG.enable_atmosphere
        CONFIG.enable_atmosphere = False
        frame2 = render_frame(0.5, night_mode=False)
        CONFIG.enable_atmosphere = original_atmo
        
        # Frames should differ
        if frame1 != frame2:
            results.pass_test("Atmosphere toggle affects rendering")
        else:
            results.fail_test("Atmosphere toggle", "No visual difference")
        
        # Test specular
        original_spec = CONFIG.enable_ocean_specular
        CONFIG.enable_ocean_specular = False
        frame3 = render_frame(0.5, night_mode=False)
        CONFIG.enable_ocean_specular = original_spec
        
        if frame1 != frame3:
            results.pass_test("Specular toggle affects rendering")
        else:
            results.fail_test("Specular toggle", "No visual difference")
    except Exception as e:
        results.fail_test("Config changes", str(e))

# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

def test_performance_baseline():
    """Measure baseline performance"""
    print("\n[PERFORMANCE TESTS] Baseline")
    
    try:
        times = []
        theta = 0
        
        # Warmup
        for _ in range(2):
            render_frame(theta, night_mode=False)
            theta += 0.1
        
        # Measure
        start = time.perf_counter()
        for i in range(10):
            render_frame(theta, night_mode=False)
            theta += 0.1
        elapsed = time.perf_counter() - start
        
        avg_time = elapsed / 10
        fps = 1.0 / avg_time
        
        print(f"  Average frame time: {avg_time*1000:.2f}ms")
        print(f"  Average FPS: {fps:.1f}")
        
        if fps > 30:
            results.pass_test(f"Performance >30 FPS ({fps:.1f} FPS)")
        else:
            results.fail_test("Performance >30 FPS", f"Only {fps:.1f} FPS")
        
        if avg_time < 0.04:  # 40ms for 25 FPS
            results.pass_test(f"Frame time <40ms ({avg_time*1000:.2f}ms)")
        else:
            results.fail_test("Frame time <40ms", f"Frame time {avg_time*1000:.2f}ms")
    except Exception as e:
        results.fail_test("Baseline performance", str(e))

def test_performance_night_mode():
    """Measure night mode performance"""
    print("\n[PERFORMANCE TESTS] Night Mode")
    
    try:
        times = []
        
        for _ in range(2):
            render_frame(0, night_mode=True)
        
        start = time.perf_counter()
        for i in range(10):
            render_frame(0.1 * i, night_mode=True)
        elapsed = time.perf_counter() - start
        
        avg_time = elapsed / 10
        fps = 1.0 / avg_time
        
        print(f"  Average frame time: {avg_time*1000:.2f}ms")
        print(f"  Average FPS: {fps:.1f}")
        
        if fps > 30:
            results.pass_test(f"Night mode >30 FPS ({fps:.1f} FPS)")
        else:
            results.fail_test("Night mode >30 FPS", f"Only {fps:.1f} FPS")
    except Exception as e:
        results.fail_test("Night mode performance", str(e))

def test_performance_detail_levels():
    """Measure performance at different detail levels"""
    print("\n[PERFORMANCE TESTS] Detail Levels")
    
    try:
        original_detail = CONFIG.detail_level
        
        for detail in [1, 2, 3, 4]:
            CONFIG.detail_level = detail
            
            # Warmup
            render_frame(0, night_mode=False)
            
            start = time.perf_counter()
            for i in range(5):
                render_frame(0.1 * i, night_mode=False)
            elapsed = time.perf_counter() - start
            
            avg_time = elapsed / 5
            fps = 1.0 / avg_time
            
            print(f"  Detail {detail}: {avg_time*1000:.2f}ms ({fps:.1f} FPS)")
            
            if fps > 20:
                results.pass_test(f"Detail level {detail} > 20 FPS ({fps:.1f})")
            else:
                results.fail_test(f"Detail level {detail} > 20 FPS", f"Only {fps:.1f} FPS")
        
        CONFIG.detail_level = original_detail
    except Exception as e:
        results.fail_test("Detail level performance", str(e))

def test_performance_features():
    """Measure performance with features enabled/disabled"""
    print("\n[PERFORMANCE TESTS] Feature Performance")
    
    try:
        features = [
            ('atmosphere', 'enable_atmosphere'),
            ('specular', 'enable_ocean_specular'),
            ('city_lights', 'enable_city_lights'),
            ('ice_caps', 'enable_polar_ice'),
        ]
        
        for feature_name, attr_name in features:
            original = getattr(CONFIG, attr_name)
            
            # Measure with feature off
            setattr(CONFIG, attr_name, False)
            start = time.perf_counter()
            for i in range(5):
                render_frame(0.1 * i, night_mode=False)
            elapsed_off = time.perf_counter() - start
            
            # Measure with feature on
            setattr(CONFIG, attr_name, True)
            start = time.perf_counter()
            for i in range(5):
                render_frame(0.1 * i, night_mode=False)
            elapsed_on = time.perf_counter() - start
            
            fps_off = 5.0 / elapsed_off
            fps_on = 5.0 / elapsed_on
            overhead = fps_off - fps_on
            
            print(f"  {feature_name:12}: {fps_on:.1f} FPS (overhead: {overhead:+.1f} FPS)")
            
            setattr(CONFIG, attr_name, original)
            
            if fps_on > 20:
                results.pass_test(f"{feature_name} maintains >20 FPS")
            else:
                results.fail_test(f"{feature_name} >20 FPS", f"Only {fps_on:.1f} FPS")
    except Exception as e:
        results.fail_test("Feature performance", str(e))

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*60)
    print("GLOBE RENDERER TEST SUITE")
    print("="*60)
    
    # Unit tests
    test_land_detection()
    test_polar_detection()
    test_coordinate_conversion()
    test_rotation()
    test_braille_cache()
    test_land_grid()
    
    # Rendering tests
    test_render_basic()
    test_render_night_mode()
    test_render_rotation()
    test_config_changes()
    
    # Performance tests
    test_performance_baseline()
    test_performance_night_mode()
    test_performance_detail_levels()
    test_performance_features()
    
    # Summary
    results.print_summary()
    
    return 0 if results.failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
