# LinkedIn Video Creation Instructions

## State Staffing Evolution Animation

This document explains how to create a LinkedIn-optimized video from the State Staffing Evolution animation.

## Files Created

1. **state-evolution-linkedin.html** - Standalone HTML file with auto-playing animation
   - Optimized for 1920x1080 resolution (LinkedIn recommended)
   - Automatically starts animation when loaded
   - Loops continuously from Q1 2017 to latest quarter

## Method 1: Screen Recording (Easiest)

**IMPORTANT**: The HTML file must be served from a web server due to browser security (CORS). 

1. **Start a local web server** (choose one):
   - **Windows**: Double-click `start_linkedin_server.bat`
   - **Or manually**:
     ```bash
     # Python 3
     python -m http.server 8000
     
     # Or Python 2
     python -m SimpleHTTPServer 8000
     
     # Or Node.js
     npx http-server
     ```

2. Open `http://localhost:8000/state-evolution-linkedin.html` in Chrome or Edge
3. Press F11 for fullscreen
4. Use screen recording software:
   - **Windows**: Windows + G (Game Bar) or OBS Studio
   - **Mac**: QuickTime Player (File > New Screen Recording)
   - **Online**: Loom, Screencastify
4. Record for 20-30 seconds (one full animation cycle)
5. Export as MP4, 1920x1080 resolution

## Method 2: Automated Recording (Requires Setup)

1. Install Playwright:
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. Run the recording script:
   ```bash
   python record_linkedin_video.py
   ```

3. Convert WebM to MP4 (if needed):
   ```bash
   ffmpeg -i state-evolution-linkedin.webm -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 192k state-evolution-linkedin.mp4
   ```

## LinkedIn Video Specifications

- **Format**: MP4
- **Resolution**: 1920x1080 (or 1280x720)
- **Aspect Ratio**: 16:9 (horizontal) or 1:1 (square)
- **Max Length**: 10 minutes (but shorter is better for engagement)
- **Max File Size**: 200MB
- **Recommended Length**: 15-60 seconds for best engagement

## Tips for LinkedIn

1. **Add a title card** at the beginning (2-3 seconds):
   - "US Nursing Home Staffing Evolution"
   - "2017-2025"
   - PBJ320 logo

2. **Add a call-to-action** at the end (2-3 seconds):
   - "Explore the data at pbj320.com/insights"
   - Website URL

3. **Keep it short**: 15-30 seconds is ideal for LinkedIn feed
   - One full cycle (Q1 2017 to Q3 2025) takes ~7 seconds at 200ms per quarter
   - Consider speeding up to 150ms per quarter for a 5-second video

4. **Add captions/text overlay**:
   - "Watch how staffing levels changed across states"
   - "Darker purple = Higher HPRD"

## Customization

To modify the animation speed, edit `state-evolution-linkedin.html`:
- Line with `}, 200);` - Change 200 to adjust milliseconds per quarter
- Lower number = faster animation
- Higher number = slower animation

To change resolution, edit the CSS in `state-evolution-linkedin.html`:
- `width: 1920px; height: 1080px;` in the body style
