#!/usr/bin/env python3
"""
Script to record the State Staffing Evolution animation as a LinkedIn-optimized video.

This script uses Playwright to:
1. Open the state-evolution-linkedin.html file
2. Wait for the animation to complete one full cycle
3. Record the animation as an MP4 video
4. Output optimized for LinkedIn (1920x1080, MP4 format)

Requirements:
    pip install playwright
    playwright install chromium

Usage:
    python record_linkedin_video.py
"""

import asyncio
import os
from pathlib import Path

try:
    # Playwright is an optional dependency - import is handled gracefully if missing
    from playwright.async_api import async_playwright  # pyright: ignore[reportMissingImports]
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    # Type stub for when playwright is not available
    async_playwright = None  # type: ignore[assignment]

async def record_animation():
    """Record the state evolution animation as a video"""
    
    if not PLAYWRIGHT_AVAILABLE:
        print("Error: Playwright is not installed.")
        print("Install it with: pip install playwright")
        print("Then run: playwright install chromium")
        return
    
    # Get the HTML file path
    html_file = Path(__file__).parent / 'state-evolution-linkedin.html'
    html_path = html_file.resolve().as_uri()
    
    print(f"Recording animation from: {html_path}")
    print("This will take approximately 30-60 seconds...")
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        
        # Create a new context with video recording
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            record_video_dir='./',
            record_video_size={'width': 1920, 'height': 1080}
        )
        
        # Create a new page
        page = await context.new_page()
        
        # Navigate to the HTML file
        await page.goto(html_path)
        
        # Wait for the map to load
        await page.wait_for_selector('#stateMap svg', timeout=30000)
        print("Map loaded, waiting for animation to start...")
        
        # Wait a bit for initial render
        await asyncio.sleep(2)
        
        # Calculate how long to record (35 quarters * 200ms + buffer)
        # One full cycle + restart = ~10 seconds, record 2 cycles = ~20 seconds
        recording_duration = 25000  # 25 seconds (covers 2 full cycles)
        
        print(f"Recording for {recording_duration/1000} seconds...")
        await asyncio.sleep(recording_duration / 1000)
        
        # Close context to finalize video
        await context.close()
        await browser.close()
        
        # Find the video file (Playwright saves it with a timestamp)
        video_dir = Path('./')
        video_files = sorted(video_dir.glob('*.webm'), key=os.path.getmtime, reverse=True)
        
        if video_files:
            video_file = video_files[0]
            output_file = Path('state-evolution-linkedin.mp4')
            
            print(f"\nVideo recorded: {video_file}")
            print(f"Converting to MP4 for LinkedIn...")
            print(f"\nTo convert WebM to MP4, you can use ffmpeg:")
            print(f"  ffmpeg -i {video_file.name} -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 192k {output_file}")
            print(f"\nOr use an online converter or video editing software.")
            print(f"\nLinkedIn video requirements:")
            print(f"  - Format: MP4")
            print(f"  - Resolution: 1920x1080 (or 1280x720)")
            print(f"  - Max length: 10 minutes (shorter is better)")
            print(f"  - Max file size: 200MB")
        else:
            print("Error: Video file not found")

if __name__ == '__main__':
    try:
        asyncio.run(record_animation())
    except Exception as e:
        print(f"Error: {e}")
        print("\nAlternative: Open state-evolution-linkedin.html in a browser and screen record it.")
