import os
import sys
import tempfile
import glob
import io
import shutil
import threading
from flask import Flask, request, render_template_string, jsonify, send_file
from waitress import serve
import yt_dlp
import imageio_ffmpeg

# Configuración y Seguridad
SECRET_PIN = os.environ.get("SECRET_PIN")
if not SECRET_PIN:
    print("ERROR CRITICO: La variable de entorno 'SECRET_PIN' no esta configurada.")
    print("El servidor no puede iniciar de forma insegura. Abortando.")
    sys.exit(1)

MAX_DESCARGAS_CONCURRENTES = 2

# Controladores de concurrencia y dependencias
semaforo_descargas = threading.Semaphore(MAX_DESCARGAS_CONCURRENTES)
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# Fuentes permitidas para descarga
FUENTES_PERMITIDAS = ['soundcloud.com']

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Music Hub Cloud</title>
    <script src="https://unpkg.com/@phosphor-icons/web" defer></script>
    <style>
        :root {
            --bg-grad: linear-gradient(135deg, #2a0845 0%, #171c35 50%, #0d3b66 100%);
            --glass-bg: rgba(255, 255, 255, 0.05);
            --glass-border: rgba(255, 255, 255, 0.1);
            --primary: #8b5cf6;
            --primary-hover: #7c3aed;
            --text-main: #ffffff;
            --text-muted: #9ca3af;
            --danger: #ef4444;
            --success: #10b981;
        }

        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg-grad); background-attachment: fixed; color: var(--text-main); 
            text-align: center; padding: 40px 20px; margin: 0; min-height: 100vh;
            display: flex; flex-direction: column; align-items: center; justify-content: flex-start;
        }

        .glass-panel {
            width: 100%; max-width: 650px; background: var(--glass-bg);
            backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
            padding: 40px 30px; border-radius: 24px; border: 1px solid var(--glass-border);
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
            margin-bottom: 20px;
            box-sizing: border-box;
        }

        h1 { margin-top: 0; font-size: 28px; font-weight: 700; letter-spacing: 0.5px; }
        p.subtitle { color: var(--text-muted); font-size: 14px; margin-bottom: 30px; }

        .platform-icons { display: flex; justify-content: center; gap: 15px; margin-bottom: 30px; }
        .platform-btn {
            background: rgba(255, 255, 255, 0.1); border: 1px solid var(--glass-border);
            border-radius: 12px; padding: 10px 15px; display: flex; flex-direction: column; 
            align-items: center; color: #fff; font-size: 11px; gap: 5px;
        }
        .platform-btn.active {
            background: rgba(139, 92, 246, 0.2); border: 1px solid var(--primary);
        }
        .platform-btn i { font-size: 20px; }

        .input-group { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
        .search-wrapper { position: relative; flex: 1; min-width: 250px; }
        .search-wrapper i {
            position: absolute; left: 15px; top: 50%; transform: translateY(-50%);
            color: var(--text-muted); font-size: 18px;
        }
        input, select { 
            width: 100%; box-sizing: border-box; padding: 16px; 
            border-radius: 12px; border: 1px solid var(--glass-border); 
            background: rgba(0, 0, 0, 0.2); color: white; font-size: 16px;
            transition: border-color 0.2s;
        }
        input[type="text"] { padding-left: 45px; }
        input:focus, select:focus { outline: none; border-color: var(--primary); background: rgba(0, 0, 0, 0.3); }
        select option { background: #171c35; color: white; }
        
        .pin-wrapper { width: 130px; flex-shrink: 0; }
        .pin-wrapper input { text-align: center; }

        .btn-main { 
            width: 100%; padding: 16px; border-radius: 12px; border: none; 
            background: linear-gradient(135deg, #a855f7, #6366f1); color: white; 
            font-size: 16px; font-weight: 600; cursor: pointer; display: flex;
            justify-content: center; align-items: center; gap: 8px;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
        }
        .btn-main:hover { box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6); }
        .btn-main:disabled { background: #4b5563; box-shadow: none; cursor: not-allowed; color: #9ca3af; }

        #player-container { margin-top: 25px; display: none; width: 100%; border-radius: 16px; overflow: hidden; border: 1px solid var(--glass-border); }
        iframe { width: 100%; height: 200px; border: none; display: block; }
        
        #results { text-align: left; margin-top: 25px; }
        
        .result-item {
            background: rgba(0, 0, 0, 0.2); border-radius: 16px; padding: 12px;
            margin-bottom: 12px; display: flex; align-items: center;
            border: 1px solid var(--glass-border); gap: 15px;
        }

        .result-thumb { width: 60px; height: 60px; border-radius: 10px; object-fit: cover; background-color: #333; }
        .result-info { flex: 1; overflow: hidden; }
        .result-title { font-weight: 600; font-size: 15px; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .result-meta { color: var(--text-muted); font-size: 12px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
        
        .badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; border: 1px solid; }
        .badge-yt { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border-color: rgba(239, 68, 68, 0.3); }
        .badge-sc { background: rgba(249, 115, 22, 0.2); color: #fdba74; border-color: rgba(249, 115, 22, 0.3); }
        
        .btn-action {
            background: transparent; border: 1px solid var(--primary); color: #c4b5fd;
            width: 40px; height: 40px; border-radius: 50%; display: flex;
            align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; transition: 0.2s;
        }
        .btn-action:hover:not(:disabled) { background: var(--primary); color: white; box-shadow: 0 0 10px rgba(139, 92, 246, 0.5); }
        .btn-action.play { border-color: #ef4444; color: #fca5a5; }
        .btn-action.play:hover { background: #ef4444; color: white; box-shadow: 0 0 10px rgba(239, 68, 68, 0.5); }
        .btn-action:disabled { opacity: 0.5; cursor: not-allowed; }

        #status { margin-top: 20px; font-size: 14px; padding: 12px; border-radius: 8px; display: none; }
        .success { background-color: rgba(16, 185, 129, 0.2); color: #34d399; display: block !important; }
        .error { background-color: rgba(239, 68, 68, 0.2); color: #f87171; display: block !important; }
        .loading { background-color: var(--glass-bg); color: var(--text-main); display: block !important; border: 1px solid var(--glass-border); }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .ph-spinner { animation: spin 1s linear infinite; }
        .dev-signature {
            margin-top: auto; padding: 25px 20px 15px; width: 100%;
            text-align: center; font-size: 12px; color: rgba(255, 255, 255, 0.4);
        }
        .dev-signature .footer-divider {
            width: 60px; height: 1px; background: rgba(255, 255, 255, 0.1);
            margin: 0 auto 15px auto;
        }
        .dev-signature p { margin: 4px 0; letter-spacing: 0.5px; }
        .dev-signature .dev-name {
            font-weight: 600; color: rgba(255, 255, 255, 0.6);
            transition: all 0.3s ease; cursor: default;
        }
        .dev-signature .dev-name:hover {
            color: rgba(255, 255, 255, 0.95); text-shadow: 0 0 10px rgba(168, 85, 247, 0.8);
        }
    </style>
</head>
<body>
    <div class="glass-panel">
        <h1>Music Hub Cloud</h1>
        <p class="subtitle">Buscador Oficial y Descargas Autorizadas</p>
        
        <div class="platform-icons">
            <div class="platform-btn active" id="icon-yt">
                <i class="ph-fill ph-youtube-logo"></i>
                <span>YouTube (Escuchar)</span>
            </div>
            <div class="platform-btn" id="icon-sc">
                <i class="ph-fill ph-soundcloud-logo"></i>
                <span>SoundCloud (Descargar)</span>
            </div>
        </div>

        <div class="input-group">
            <select id="source" onchange="cambiarFuente()">
                <option value="youtube">Buscar en YouTube Music (Solo Escuchar)</option>
                <option value="soundcloud">Buscar en SoundCloud (Para Descargar)</option>
            </select>
        </div>

        <div class="input-group">
            <div class="search-wrapper">
                <i class="ph ph-magnifying-glass"></i>
                <input type="text" id="query" placeholder="Escribe el nombre de la canción o pega el enlace...">
            </div>
            <div class="pin-wrapper">
                <input type="password" id="pin" placeholder="PIN Secreto" maxlength="10">
            </div>
        </div>
        
        <button id="btn-buscar" class="btn-main" onclick="buscar()">
            <i class="ph-bold ph-magnifying-glass"></i> Buscar Canción
        </button>
        
        <div id="status"></div>
        <div id="player-container"></div>
        <div id="results"></div>
    </div>

    <script>
        let isProcessing = false;

        document.getElementById('query').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') buscar();
        });
        document.getElementById('pin').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') buscar();
        });

        function cambiarFuente() {
            const src = document.getElementById('source').value;
            document.getElementById('icon-yt').classList.toggle('active', src === 'youtube');
            document.getElementById('icon-sc').classList.toggle('active', src === 'soundcloud');
        }

        function mostrarEstado(mensaje, tipo) {
            const status = document.getElementById('status');
            status.className = tipo;
            status.innerHTML = mensaje;
            if(!mensaje) status.style.display = 'none';
        }

        function reproducir(video_id) {
            const player = document.getElementById('player-container');
            player.style.display = 'block';
            player.innerHTML = `<iframe src="https://www.youtube.com/embed/${video_id}?autoplay=1" allow="autoplay; encrypted-media" allowfullscreen></iframe>`;
        }

        function buscar() {
            if(isProcessing) return;
            
            const query = document.getElementById('query').value.trim();
            const pin = document.getElementById('pin').value.trim();
            const source = document.getElementById('source').value;
            
            if(!query || !pin) {
                mostrarEstado("❌ Debes ingresar la búsqueda y el PIN", "error");
                return;
            }
            
            isProcessing = true;
            mostrarEstado('<i class="ph ph-spinner"></i> Buscando metadatos...', 'loading');
            const btn = document.getElementById('btn-buscar');
            const resultsDiv = document.getElementById('results');
            document.getElementById('player-container').style.display = 'none';
            document.getElementById('player-container').innerHTML = '';
            
            btn.disabled = true;
            resultsDiv.innerHTML = "";
            
            fetch('/buscar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: query, pin: pin, source: source})
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    mostrarEstado("", "");
                    if (data.results.length === 0) {
                        mostrarEstado("❌ No se encontraron resultados.", "error");
                        return;
                    }
                    data.results.forEach(vid => {
                        const isYT = vid.source_type === 'youtube';
                        const badgeClass = isYT ? 'badge-yt' : 'badge-sc';
                        const badgeText = isYT ? '<i class="ph-fill ph-youtube-logo"></i> YouTube Music' : '<i class="ph-fill ph-soundcloud-logo"></i> SoundCloud';
                        
                        let actionButton = '';
                        if (isYT && vid.video_id) {
                            actionButton = `<button class="btn-action play" title="Reproducir Oficialmente" onclick="reproducir('${vid.video_id}')"><i class="ph-fill ph-play"></i></button>`;
                        } else if (!isYT) {
                            actionButton = `<button class="btn-action download" title="Descargar MP3" onclick="descargar('${vid.url}', this)"><i class="ph-bold ph-download-simple"></i></button>`;
                        }

                        // Optimización visual de portada en móviles
                        let thumbUrl = vid.thumbnail;
                        if(isYT && thumbUrl.includes('maxresdefault')) {
                            thumbUrl = thumbUrl.replace('maxresdefault', 'mqdefault');
                        } else if(isYT && thumbUrl.includes('hqdefault')) {
                            thumbUrl = thumbUrl.replace('hqdefault', 'mqdefault');
                        }

                        const div = document.createElement('div');
                        div.className = 'result-item';
                        div.innerHTML = `
                            <img src="${thumbUrl}" class="result-thumb" alt="Portada" onerror="this.src='https://via.placeholder.com/60?text=🎵'">
                            <div class="result-info">
                                <div class="result-title">${vid.title}</div>
                                <div class="result-meta">
                                    <span class="channel"><i class="ph-fill ph-user"></i> ${vid.channel}</span>
                                    <span class="duration"><i class="ph-fill ph-clock"></i> ${vid.duration}</span>
                                    <span class="badge ${badgeClass}">${badgeText}</span>
                                    <span class="badge" style="background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.2);"><i class="ph-fill ph-headphones"></i> Mejor MP3 disponible</span>
                                </div>
                            </div>
                            ${actionButton}
                        `;
                        resultsDiv.appendChild(div);
                    });
                } else {
                    mostrarEstado("❌ Error: " + data.error, "error");
                }
            })
            .catch(err => mostrarEstado("❌ Error de red.", "error"))
            .finally(() => {
                btn.disabled = false;
                isProcessing = false;
            });
        }

        function descargar(url_descarga, btnElement) {
            if(isProcessing) return;
            
            const pin = document.getElementById('pin').value.trim();
            const todosBotones = document.querySelectorAll('.btn-action');
            todosBotones.forEach(b => b.disabled = true);
            
            isProcessing = true;
            const originalIcon = btnElement.innerHTML;
            btnElement.innerHTML = '<i class="ph ph-spinner"></i>';
            btnElement.style.background = "#ff9800";
            btnElement.style.borderColor = "#ff9800";
            btnElement.style.color = "white";
            
            mostrarEstado('<i class="ph ph-spinner"></i> Extrayendo audio de fuente permitida... (Paciencia)', "loading");
            
            fetch('/descargar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: url_descarga, pin: pin})
            })
            .then(res => {
                if(res.ok) {
                    mostrarEstado('<i class="ph ph-spinner"></i> Procesando archivo y limpiando temporales...', "loading");
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
                    throw new Error("Servidor procesando otras descargas. Intenta en 15 segundos.");
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
                isProcessing = false;
            });
        }
    </script>
    <footer class="dev-signature">
        <div class="footer-divider"></div>
        <p>Music Hub Cloud</p>
        <p>Desarrollado por <span class="dev-name">HJC Web Studio</span></p>
    </footer>
</body>
</html>
"""

def is_download_permitted(url):
    """ Verifica de forma estricta que la fuente de descarga está explícitamente permitida """
    return any(domain in url.lower() for domain in FUENTES_PERMITIDAS)

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/buscar', methods=['POST'])
def buscar():
    data = request.json
    pin = data.get('pin', '')
    if pin != SECRET_PIN:
        return jsonify({"success": False, "error": "PIN incorrecto"}), 403

    query = data.get('query', '').strip()
    source = data.get('source', 'youtube') # youtube o soundcloud
    if not query:
        return jsonify({"success": False, "error": "Búsqueda vacía"}), 400
        
    # Extraemos solo metadatos de forma limpia y oficial. Cero spoofing.
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': FFMPEG_PATH
    }
    
    if source == 'youtube':
        ydl_opts['default_search'] = 'ytsearch5'
        search_query = f"ytsearch5:{query}" if "http" not in query else query
    else:
        ydl_opts['default_search'] = 'scsearch5'
        search_query = f"scsearch5:{query}" if "http" not in query else query
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
                
                url_resultado = entry.get('url', entry.get('webpage_url', ''))
                
                # Para YouTube, obtenemos el video_id para embeber el iframe oficial
                video_id = None
                if source == 'youtube' and 'youtube.com' in url_resultado or 'youtu.be' in url_resultado:
                    video_id = entry.get('id')
                
                videos.append({
                    "title": entry.get('title', 'Sin título'),
                    "channel": entry.get('uploader', 'Desconocido'),
                    "duration": duracion_str,
                    "thumbnail": thumb or '',
                    "url": url_resultado,
                    "source_type": source,
                    "video_id": video_id
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
    if pin != SECRET_PIN:
        return jsonify({"success": False, "error": "PIN incorrecto"}), 403

    query = data.get('query', '').strip()
    if not query:
        return jsonify({"success": False, "error": "URL vacía"}), 400
        
    # Validación ESTRICTA: Prohibido procesar descargas desde YouTube
    if 'youtube.com' in query or 'youtu.be' in query:
        return jsonify({"success": False, "error": "Operación denegada: La descarga desde YouTube no está permitida por políticas del servicio. Utilice el reproductor oficial."}), 403
        
    # Verificamos fuentes en la lista blanca
    if not is_download_permitted(query):
        return jsonify({"success": False, "error": f"Operación denegada: Fuente no autorizada explícitamente."}), 403
    
    if not semaforo_descargas.acquire(blocking=False):
        return jsonify({"success": False, "error": "Servidor muy ocupado. Intenta en unos segundos"}), 429
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Opciones limpias para extraer audio y metadatos sin alterar headers o evadir.
        ydl_opts = {
            'format': 'bestaudio/best',
            'writethumbnail': True,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '0',
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
            
            # Leemos el archivo en memoria (BytesIO) para poder limpiar el temporal ANTES de responder
            with open(archivo_final, 'rb') as f:
                datos_memoria = io.BytesIO(f.read())
                
            # Limpieza exhaustiva
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Retornamos el objeto en memoria
            datos_memoria.seek(0)
            return send_file(datos_memoria, as_attachment=True, download_name=nombre_archivo, mimetype="audio/mpeg")
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return jsonify({"success": False, "error": "No se generó el archivo de audio"}), 500
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        semaforo_descargas.release()

if __name__ == '__main__':
    print(f"==================================================")
    print(f" Inciando MUSIC HUB (Buscador YT + Descarga Externa)")
    print(f" - Reproductor oficial de YouTube Integrado")
    print(f" - Descargas autorizadas: {', '.join(FUENTES_PERMITIDAS)}")
    print(f"==================================================")
    puerto = int(os.environ.get("PORT", 5000))
    serve(app, host='0.0.0.0', port=puerto, threads=10)
