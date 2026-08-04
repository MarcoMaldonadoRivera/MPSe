#!/usr/bin/env python3
"""
Dashboard Eléctrico - Sonoff POW
Inicia el servidor backend y sirve el frontend.
Ejecutar: python run.py
Luego abrir: http://127.0.0.1:8000
"""

import uvicorn
import webbrowser
import threading
import time
import os
from app import app
from fastapi.responses import FileResponse

# Servir index.html en la raíz
@app.get("/")
def serve_index():
    return FileResponse("index.html")

# Servir styles.css
@app.get("/styles.css")
def serve_css():
    return FileResponse("styles.css")

# Servir script.js
@app.get("/script.js")
def serve_js():
    return FileResponse("script.js")

if __name__ == "__main__":
    # Abrir navegador automáticamente después de 1 segundo
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8000")
    
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()
    
    print("=" * 50)
    print("  Dashboard Eléctrico - Sonoff POW")
    print("  Servidor iniciado en:")
    print("  → http://127.0.0.1:8000")
    print("  → Documentación API: http://127.0.0.1:8000/docs")
    print("=" * 50)
    
    uvicorn.run(app, host="127.0.0.1", port=8000)