#!/usr/bin/env python3
"""
Start HTTP server and print the facility page link
"""
import http.server
import socketserver
import webbrowser
import os
import sys

def start_server():
    # Change to the correct directory
    os.chdir(r'C:\Users\egold\PycharmProjects\pbj-root')
    
    PORT = 8004
    
    # Create server
    Handler = http.server.SimpleHTTPRequestHandler
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("=" * 60)
        print("🚀 PBJ Facility Dashboard Server Starting...")
        print("=" * 60)
        print(f"📁 Serving from: {os.getcwd()}")
        print(f"🌐 Server running on: http://localhost:{PORT}")
        print()
        print("📋 Available pages:")
        print(f"   🏠 Home: http://localhost:{PORT}/")
        print(f"   📊 Facility 335513: http://localhost:{PORT}/facility-335513.html")
        print(f"   ℹ️  About: http://localhost:{PORT}/about.html")
        print()
        print("🎯 FACILITY PAGE LINK:")
        print(f"   👉 http://localhost:{PORT}/facility-335513.html")
        print()
        print("=" * 60)
        print("✅ Server is running! Press Ctrl+C to stop")
        print("=" * 60)
        
        # Open the facility page automatically
        facility_url = f"http://localhost:{PORT}/facility-335513.html"
        print(f"🌐 Opening {facility_url} in your browser...")
        webbrowser.open(facility_url)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user")
            sys.exit(0)

if __name__ == "__main__":
    start_server()
