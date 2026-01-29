#!/usr/bin/env python3
"""
Benchmarking script to measure frame rendering performance before/after optimizations.
"""

import time
import math
from globe import render_frame

def benchmark(iterations=10):
    """Benchmark the render_frame function"""
    print(f"Benchmarking with {iterations} frames...")
    
    times = []
    theta = 0.0
    night_mode = False
    
    # Warmup
    for i in range(2):
        render_frame(theta, night_mode)
        theta += 0.1
    
    # Actual benchmark
    start_total = time.perf_counter()
    
    for i in range(iterations):
        start = time.perf_counter()
        frame = render_frame(theta, night_mode)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        
        if (i + 1) % (iterations // 4) == 0:
            print(f"  Progress: {i + 1}/{iterations}")
        
        theta += 0.025
        if i % 5 == 0:
            night_mode = not night_mode
    
    total_elapsed = time.perf_counter() - start_total
    
    # Statistics
    times = sorted(times)
    avg_time = sum(times) / len(times)
    min_time = times[0]
    max_time = times[-1]
    median_time = times[len(times) // 2]
    fps = 1.0 / avg_time if avg_time > 0 else 0
    
    print("\n" + "="*60)
    print("BENCHMARK RESULTS")
    print("="*60)
    print(f"Iterations:     {iterations}")
    print(f"Total time:     {total_elapsed:.3f}s")
    print(f"Min frame:      {min_time*1000:.2f}ms ({1/min_time:.1f} FPS)")
    print(f"Max frame:      {max_time*1000:.2f}ms ({1/max_time:.1f} FPS)")
    print(f"Median frame:   {median_time*1000:.2f}ms ({1/median_time:.1f} FPS)")
    print(f"Average frame:  {avg_time*1000:.2f}ms")
    print(f"Average FPS:    {fps:.1f}")
    print("="*60)
    
    return avg_time, fps

if __name__ == "__main__":
    avg_time, fps = benchmark(iterations=20)
