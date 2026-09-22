import http.server
import socketserver
import webbrowser
import os

PORT = 8080
Handler = http.server.SimpleHTTPRequestHandler

print(f"🐕 Starting Bobik Web App Server...")
print(f"🌍 Open in your browser: http://localhost:{PORT}")

webbrowser.open(f"http://localhost:{PORT}")

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Bobik server. Goodbye! 🐾")
