import os
import tempfile
import glob
import json
import threading
from flask import Flask, request, render_template_string, jsonify, send_file
from waitress import serve
import yt_dlp
import imageio_ffmpeg

# Configuración del servidor para uso P2P
PIN_SECRETO = "2026"  # Cambia esto por la contraseña que le darás a tus amigos
MAX_DESCARGAS_CONCURRENTES = 2 # Máximo número de descargas simultáneas para no quemar la PC

# Controladores de concurrencia
semaforo_descargas = threading.Semaphore(MAX_DESCARGAS_CONCURRENTES)
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Music Downloader Local</title>
    <script src="https://unpkg.com/@phosphor-icons/web"></script>
    <style>
        :root {
            --bg-grad: linear-gradient(135deg, #2a0845 0%, #171c35 50%, #0d3b66 100%);
            --glass-bg: rgba(255, 255, 255, 0.05);
            --glass-border: rgba(255, 255, 255, 0.1);
            --primary: #8b5cf6;
            --primary-hover: #7c3aed;
            --text-main: #ffffff;
            --text-muted: #9ca3af;
        }

        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg-grad); background-attachment: fixed; color: var(--text-main); 
            text-align: center; padding: 40px 20px; margin: 0; min-height: 100vh;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
        }

        .glass-panel {
            width: 100%; max-width: 650px; background: var(--glass-bg);
            backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
            padding: 40px 30px; border-radius: 24px; border: 1px solid var(--glass-border);
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
        }

        h1 { margin-top: 0; font-size: 28px; font-weight: 700; letter-spacing: 0.5px; }
        p.subtitle { color: var(--text-muted); font-size: 14px; margin-bottom: 30px; }

        .platform-icons { display: flex; justify-content: center; gap: 15px; margin-bottom: 30px; }
        .platform-btn {
            background: rgba(219, 39, 119, 0.1); border: 1px solid rgba(219, 39, 119, 0.4);
            border-radius: 12px; padding: 10px 15px; display: flex; flex-direction: column; 
            align-items: center; color: #fff; font-size: 11px; gap: 5px;
        }
        .platform-btn i { font-size: 20px; }

        .input-group { display: flex; gap: 10px; margin-bottom: 20px; }
        .search-wrapper { position: relative; flex: 1; }
        .search-wrapper i {
            position: absolute; left: 15px; top: 50%; transform: translateY(-50%);
            color: var(--text-muted); font-size: 18px;
        }
        input { 
            width: 100%; box-sizing: border-box; padding: 16px 16px 16px 45px; 
            border-radius: 12px; border: 1px solid var(--glass-border); 
            background: rgba(0, 0, 0, 0.2); color: white; font-size: 15px;
            transition: border-color 0.2s;
        }
        input:focus { outline: none; border-color: var(--primary); background: rgba(0, 0, 0, 0.3); }
        
        .pin-wrapper { width: 130px; position: relative; }
        .pin-wrapper input { padding: 16px; text-align: center; }

        .btn-main { 
            width: 100%; padding: 16px; border-radius: 12px; border: none; 
            background: linear-gradient(135deg, #a855f7, #6366f1); color: white; 
            font-size: 16px; font-weight: 600; cursor: pointer; display: flex;
            justify-content: center; align-items: center; gap: 8px;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
        }
        .btn-main:hover { box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6); }
        .btn-main:disabled { background: #4b5563; box-shadow: none; cursor: not-allowed; color: #9ca3af; }

        #results { text-align: left; margin-top: 25px; }
        
        .result-item {
            background: rgba(0, 0, 0, 0.2); border-radius: 16px; padding: 12px;
            margin-bottom: 12px; display: flex; align-items: center;
            border: 1px solid var(--glass-border); gap: 15px;
        }
        .result-item:hover { border-color: rgba(168, 85, 247, 0.5); background: rgba(0, 0, 0, 0.4); }

        .result-thumb { width: 60px; height: 60px; border-radius: 10px; object-fit: cover; background-color: #333; }
        .result-info { flex: 1; overflow: hidden; }
        .result-title { font-weight: 600; font-size: 15px; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .result-meta { color: var(--text-muted); font-size: 12px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
        .badge-quality { background: rgba(219, 39, 119, 0.2); color: #fbcfe8; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; border: 1px solid rgba(219, 39, 119, 0.3); }
        
        .btn-download-small {
            background: transparent; border: 1px solid var(--primary); color: #c4b5fd;
            width: 40px; height: 40px; border-radius: 50%; display: flex;
            align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; transition: 0.2s;
        }
        .btn-download-small:hover:not(:disabled) { background: var(--primary); color: white; box-shadow: 0 0 10px rgba(139, 92, 246, 0.5); }
        .btn-download-small:disabled { opacity: 0.5; cursor: not-allowed; }

        #status { margin-top: 20px; font-size: 14px; padding: 12px; border-radius: 8px; display: none; }
        .success { background-color: rgba(16, 185, 129, 0.2); color: #34d399; display: block !important; }
        .error { background-color: rgba(239, 68, 68, 0.2); color: #f87171; display: block !important; }
        .loading { background-color: var(--glass-bg); color: var(--text-main); display: block !important; border: 1px solid var(--glass-border); }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .ph-spinner { animation: spin 1s linear infinite; }
    </style>
</head>
<body>
    <div class="glass-panel">
        <h1>Music Downloader Local</h1>
        <p class="subtitle">Descarga música sin bloqueos (Hosteado Privadamente)</p>
        
        <div class="platform-icons">
            <div class="platform-btn">
                <i class="ph-fill ph-youtube-logo"></i>
                <span>YouTube Music</span>
            </div>
        </div>

        <div class="input-group">
            <div class="search-wrapper">
                <i class="ph ph-link"></i>
                <input type="text" id="query" placeholder="Enlace o nombre de la canción...">
            </div>
            <div class="pin-wrapper">
                <input type="password" id="pin" placeholder="PIN Secreto" maxlength="4">
            </div>
        </div>
        
        <button id="btn-buscar" class="btn-main" onclick="buscar()">
            <i class="ph-bold ph-magnifying-glass"></i> Buscar Canción
        </button>
        
        <div id="status"></div>
        <div id="results"></div>
    </div>

    <script>
        document.getElementById('query').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') buscar();
        });
        document.getElementById('pin').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') buscar();
        });

        function mostrarEstado(mensaje, tipo) {
            const status = document.getElementById('status');
            status.className = tipo;
            status.innerHTML = mensaje;
        }

        function buscar() {
            const query = document.getElementById('query').value.trim();
            const pin = document.getElementById('pin').value.trim();
            if(!query || !pin) {
                mostrarEstado("❌ Debes ingresar la búsqueda y el PIN", "error");
                return;
            }
            
            mostrarEstado('<i class="ph ph-spinner"></i> Buscando...', 'loading');
            const btn = document.getElementById('btn-buscar');
            const resultsDiv = document.getElementById('results');
            
            btn.disabled = true;
            resultsDiv.innerHTML = "";
            
            fetch('/buscar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: query, pin: pin})
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    mostrarEstado("", "");
                    document.getElementById('status').style.display = 'none';
                    if (data.results.length === 0) {
                        mostrarEstado("❌ No se encontraron resultados.", "error");
                        return;
                    }
                    data.results.forEach(vid => {
                        const div = document.createElement('div');
                        div.className = 'result-item';
                        div.innerHTML = `
                            <img src="${vid.thumbnail}" class="result-thumb" alt="Portada" onerror="this.src='https://via.placeholder.com/60?text=🎵'">
                            <div class="result-info">
                                <div class="result-title">${vid.title}</div>
                                <div class="result-meta">
                                    <span class="channel"><i class="ph-fill ph-user"></i> ${vid.channel}</span>
                                    <span class="duration"><i class="ph-fill ph-clock"></i> ${vid.duration}</span>
                                    <span class="badge-quality"><i class="ph-fill ph-headphones"></i> MP3 320kbps</span>
                                </div>
                            </div>
                            <button class="btn-download-small" title="Descargar MP3" onclick="descargar('${vid.url}', this)">
                                <i class="ph-bold ph-download-simple"></i>
                            </button>
                        `;
                        resultsDiv.appendChild(div);
                    });
                } else {
                    mostrarEstado("❌ Error: " + data.error, "error");
                }
            })
            .catch(err => mostrarEstado("❌ Error de red.", "error"))
            .finally(() => btn.disabled = false);
        }

        function descargar(url_descarga, btnElement) {
            const pin = document.getElementById('pin').value.trim();
            const todosBotones = document.querySelectorAll('.btn-download-small');
            todosBotones.forEach(b => b.disabled = true);
            
            const originalIcon = btnElement.innerHTML;
            btnElement.innerHTML = '<i class="ph ph-spinner"></i>';
            btnElement.style.background = "#ff9800";
            btnElement.style.borderColor = "#ff9800";
            btnElement.style.color = "white";
            
            mostrarEstado('<i class="ph ph-spinner"></i> Solicitando descarga. Si la PC está ocupada, estarás en cola...', "loading");
            
            fetch('/descargar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: url_descarga, pin: pin})
            })
            .then(res => {
                if(res.ok) {
                    mostrarEstado('<i class="ph ph-spinner"></i> ¡Descarga aceptada! Procesando MP3 (Paciencia)...', "loading");
                    const disposition = res.headers.get('Content-Disposition');
                    let filename = "cancion.mp3";
                    if (disposition && disposition.indexOf('attachment') !== -1) {
                        const matches = /filename[^;=\\n]*=((['"]).*?\\2|[^;\\n]*)/.exec(disposition);
                        if (matches != null && matches[1]) { 
                            filename = matches[1].replace(/['"]/g, '');
                            if (filename.startsWith("UTF-8''")) {
                                filename = decodeURIComponent(filename.replace("UTF-8''", ""));
                            }
                        }
                    }
                    return res.blob().then(blob => ({blob, filename}));
                }
                if (res.status === 429) {
                    throw new Error("El servidor está ocupado con otros usuarios. Intenta en 15 segundos.");
                }
                return res.json().then(err => { throw new Error(err.error) });
            })
            .then(({blob, filename}) => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                
                mostrarEstado("✅ ¡Descarga Completa!", "success");
                btnElement.innerHTML = '<i class="ph-bold ph-check"></i>';
                btnElement.style.background = "#10b981";
                btnElement.style.borderColor = "#10b981";
            })
            .catch(err => {
                mostrarEstado("❌ Falló: " + err.message, "error");
                btnElement.innerHTML = originalIcon;
                btnElement.style.background = "transparent";
                btnElement.style.borderColor = "var(--primary)";
                btnElement.style.color = "#c4b5fd";
            })
            .finally(() => {
                todosBotones.forEach(b => {
                    if(b !== btnElement) b.disabled = false;
                });
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/buscar', methods=['POST'])
def buscar():
    data = request.json
    pin = data.get('pin', '')
    if pin != PIN_SECRETO:
        return jsonify({"success": False, "error": "PIN incorrecto"}), 403

    query = data.get('query', '').strip()
    if not query:
        return jsonify({"success": False, "error": "Búsqueda vacía"}), 400
        
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch5',
        'ffmpeg_location': FFMPEG_PATH
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch5:{query}" if "http" not in query else query
            info = ydl.extract_info(search_query, download=False)
            
            videos = []
            entries = info['entries'] if 'entries' in info else [info]
            
            for entry in entries:
                if not entry: continue
                duracion_seg = entry.get('duration', 0)
                if duracion_seg:
                    mins = int(duracion_seg) // 60
                    secs = int(duracion_seg) % 60
                    duracion_str = f"{mins}:{secs:02d}"
                else:
                    duracion_str = "?:??"
                
                thumb = entry.get('thumbnail')
                if not thumb and entry.get('thumbnails'):
                    thumb = entry['thumbnails'][-1]['url']
                    
                videos.append({
                    "title": entry.get('title', 'Sin título'),
                    "channel": entry.get('uploader', 'Desconocido'),
                    "duration": duracion_str,
                    "thumbnail": thumb or '',
                    "url": entry.get('url', entry.get('webpage_url', ''))
                })
                
                if len(videos) >= 5:
                    break
                    
            return jsonify({"success": True, "results": videos})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/descargar', methods=['POST'])
def descargar():
    data = request.json
    pin = data.get('pin', '')
    if pin != PIN_SECRETO:
        return jsonify({"success": False, "error": "PIN incorrecto"}), 403

    query = data.get('query', '').strip()
    if not query:
        return jsonify({"success": False, "error": "URL vacía"}), 400
    
    # Control de concurrencia: si el semáforo está bloqueado, rechazamos rápido
    if not semaforo_descargas.acquire(blocking=False):
        return jsonify({"success": False, "error": "Servidor muy ocupado. Intenta en unos segundos"}), 429
    
    try:
        temp_dir = tempfile.mkdtemp()
        
        # Opciones puras y limpias de ffmpeg y yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'writethumbnail': True,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                },
                {
                    'key': 'EmbedThumbnail',
                },
                {
                    'key': 'FFmpegMetadata',
                }
            ],
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': FFMPEG_PATH
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([query])
            
        archivos = glob.glob(os.path.join(temp_dir, "*.mp3"))
        if archivos:
            archivo_final = archivos[0]
            nombre_archivo = os.path.basename(archivo_final)
            return send_file(archivo_final, as_attachment=True, download_name=nombre_archivo, mimetype="audio/mpeg")
        else:
            return jsonify({"success": False, "error": "No se generó el MP3"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        # Liberamos el slot del semáforo, falle o sea exitoso
        semaforo_descargas.release()

if __name__ == '__main__':
    print(f"==================================================")
    print(f" Inciando SERVIDOR LOCAL ROBUSTO (Waitress WSGI)")
    print(f" - Limite concurrente de descargas: {MAX_DESCARGAS_CONCURRENTES}")
    print(f" - PIN de acceso: {PIN_SECRETO}")
    print(f"==================================================")
    print(f"Servidor escuchando en http://0.0.0.0:5000")
    # Usar waitress para manejo robusto de múltiples conexiones en producción local
    serve(app, host='0.0.0.0', port=5000, threads=10)
