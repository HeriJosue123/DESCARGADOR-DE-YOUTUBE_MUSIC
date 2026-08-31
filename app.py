import os
import tempfile
import glob
import json
from flask import Flask, request, render_template_string, jsonify, send_file
import yt_dlp

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Descargador de Música - Búsqueda Inteligente</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #121212; 
            color: #ffffff; 
            text-align: center; 
            padding: 50px 20px; 
            margin: 0;
        }
        .container {
            max-width: 650px;
            margin: 0 auto;
            background-color: #1e1e1e;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.5);
        }
        h1 { margin-top: 0; color: #1DB954; }
        p { color: #b3b3b3; line-height: 1.5; margin-bottom: 25px; }
        
        .search-box {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        input { 
            flex: 1;
            padding: 14px; 
            border-radius: 8px; 
            border: 1px solid #333; 
            background-color: #2a2a2a;
            color: white;
            font-size: 16px;
        }
        input:focus { outline: none; border-color: #1DB954; }
        
        button { 
            padding: 14px 24px; 
            border-radius: 8px; 
            border: none; 
            background-color: #1DB954; 
            color: black; 
            font-size: 16px;
            cursor: pointer; 
            font-weight: bold; 
            transition: background-color 0.2s, transform 0.1s;
        }
        button:hover { background-color: #1ed760; }
        button:active { transform: scale(0.98); }
        button:disabled { background-color: #555; cursor: not-allowed; color: #999; }
        
        #results {
            text-align: left;
            margin-top: 20px;
        }
        
        .result-item {
            background-color: #2a2a2a;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid transparent;
            transition: border-color 0.2s;
        }
        .result-item:hover {
            border-color: #1DB954;
            background-color: #333;
        }
        .result-info {
            flex: 1;
            padding-right: 15px;
        }
        .result-title { font-weight: bold; font-size: 16px; margin-bottom: 5px; }
        .result-channel { color: #b3b3b3; font-size: 14px; }
        .result-duration { color: #1DB954; font-size: 12px; margin-left: 10px; }
        
        .btn-download-small {
            background-color: transparent;
            border: 1px solid #1DB954;
            color: #1DB954;
            padding: 8px 16px;
            border-radius: 20px;
        }
        .btn-download-small:hover {
            background-color: #1DB954;
            color: black;
        }
        
        #status { 
            margin-top: 25px; 
            font-size: 1.1em; 
            padding: 15px;
            border-radius: 8px;
            display: none;
        }
        .success { background-color: rgba(29, 185, 84, 0.2); color: #1DB954; display: block !important; }
        .error { background-color: rgba(226, 33, 52, 0.2); color: #e22134; display: block !important; }
        .loading { background-color: rgba(255, 255, 255, 0.1); color: #ffffff; display: block !important; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Descargador Avanzado 🎵</h1>
        <p>Busca tu canción. Selecciona la versión correcta de la lista para descargarla.</p>
        
        <div class="search-box">
            <input type="text" id="query" placeholder="Ej: Feid Luna, Bad Bunny...">
            <button id="btn-buscar" onclick="buscar()">Buscar</button>
        </div>
        
        <div id="status"></div>
        <div id="results"></div>
    </div>

    <script>
        document.getElementById('query').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                buscar();
            }
        });

        function mostrarEstado(mensaje, tipo) {
            const status = document.getElementById('status');
            status.className = tipo;
            status.innerHTML = mensaje;
        }

        function buscar() {
            const query = document.getElementById('query').value.trim();
            if(!query) return;
            
            mostrarEstado("🔍 Buscando resultados...", "loading");
            const btn = document.getElementById('btn-buscar');
            const resultsDiv = document.getElementById('results');
            
            btn.disabled = true;
            resultsDiv.innerHTML = "";
            
            fetch('/buscar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: query})
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
                            <div class="result-info">
                                <div class="result-title">${vid.title} <span class="result-duration">⏱ ${vid.duration}</span></div>
                                <div class="result-channel">👤 ${vid.channel}</div>
                            </div>
                            <button class="btn-download-small" onclick="descargar('${vid.url}', this)">Descargar</button>
                        `;
                        resultsDiv.appendChild(div);
                    });
                } else {
                    mostrarEstado("❌ Error al buscar: " + data.error, "error");
                }
            })
            .catch(err => {
                mostrarEstado("❌ Error de conexión al buscar.", "error");
            })
            .finally(() => {
                btn.disabled = false;
            });
        }

        function descargar(url_descarga, btnElement) {
            const todosBotones = document.querySelectorAll('.btn-download-small');
            todosBotones.forEach(b => b.disabled = true);
            
            const originalText = btnElement.innerText;
            btnElement.innerText = "⏳ Bajando...";
            btnElement.style.backgroundColor = "#ff9800";
            btnElement.style.borderColor = "#ff9800";
            btnElement.style.color = "black";
            
            mostrarEstado("⏳ Descargando y convirtiendo a MP3... (No cierres la pestaña)", "loading");
            
            fetch('/descargar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: url_descarga})
            })
            .then(res => {
                if(res.ok) {
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
                
                mostrarEstado("✅ ¡Canción descargada con éxito!", "success");
                btnElement.innerText = "✅ Listo";
                btnElement.style.backgroundColor = "#1DB954";
                btnElement.style.borderColor = "#1DB954";
            })
            .catch(err => {
                mostrarEstado("❌ Error al descargar: " + err.message, "error");
                btnElement.innerText = "❌ Falló";
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
    query = data.get('query', '').strip()
    if not query:
        return jsonify({"success": False, "error": "Búsqueda vacía"}), 400
        
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch5'
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # ytsearch5:query
            search_query = f"ytsearch5:{query}"
            info = ydl.extract_info(search_query, download=False)
            
            videos = []
            if 'entries' in info:
                for entry in info['entries']:
                    duracion_seg = entry.get('duration', 0)
                    if duracion_seg:
                        mins = duracion_seg // 60
                        secs = duracion_seg % 60
                        duracion_str = f"{mins}:{secs:02d}"
                    else:
                        duracion_str = "?:??"
                        
                    videos.append({
                        "title": entry.get('title', 'Sin título'),
                        "channel": entry.get('uploader', 'Canal desconocido'),
                        "duration": duracion_str,
                        "url": entry.get('url', entry.get('webpage_url', ''))
                    })
            return jsonify({"success": True, "results": videos})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/descargar', methods=['POST'])
def descargar():
    data = request.json
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({"success": False, "error": "URL vacía"}), 400
    
    temp_dir = tempfile.mkdtemp()
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([query])
            
        archivos = glob.glob(os.path.join(temp_dir, "*.mp3"))
        if archivos:
            archivo_final = archivos[0]
            nombre_archivo = os.path.basename(archivo_final)
            return send_file(archivo_final, as_attachment=True, download_name=nombre_archivo, mimetype="audio/mpeg")
        else:
            return jsonify({"success": False, "error": "No se pudo generar el archivo MP3"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": "Fallo al descargar la cancion: " + str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
