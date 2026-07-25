import os
import tempfile
from flask import Flask, render_template, request, jsonify, send_file, after_this_request
import yt_dlp

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.json or {}
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL inválida'}), 400

    ydl_opts = {'quiet': True}
    if 'tiktok.com' in url.lower():
        ydl_opts['extractor_args'] = {'tiktok': {'app_version': 'latest'}}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = info.get('formats', [])
            resolutions = set()
            for f in formats:
                if f.get('vcodec') != 'none' and f.get('height'):
                    resolutions.add(f['height'])
            
            sorted_res = sorted(list(resolutions), reverse=True)
            
            return jsonify({
                'title': info.get('title', 'Vídeo sem título'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration_string', 'N/A'),
                'uploader': info.get('uploader', 'Desconhecido'),
                'resolutions': sorted_res
            })
    except Exception as e:
        return jsonify({'error': f'Não foi possível analisar este link: {str(e)}'}), 500

@app.route('/api/download', methods=['POST'])
def process_download():
    data = request.json or {}
    url = data.get('url')
    format_type = data.get('format_type')
    quality = data.get('quality')

    if not url:
        return jsonify({'error': 'URL ausente'}), 400

    # Cria uma pasta temporária para salvar o arquivo com segurança
    temp_dir = tempfile.mkdtemp()
    filename_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
    
    ydl_opts = {
        'outtmpl': filename_template,
        'quiet': True,
    }

    if 'tiktok.com' in url.lower():
        ydl_opts['extractor_args'] = {'tiktok': {'app_version': 'latest'}}

    if format_type == 'mp3':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        if quality and quality != 'max':
            ydl_opts['format'] = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/b[height<={quality}]/best'
        else:
            ydl_opts['format'] = 'bestvideo+bestaudio/b/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if format_type == 'mp3':
                base, _ = os.path.splitext(filename)
                filename = base + '.mp3'

        @after_this_request
        def remove_file(response):
            # Limpa o arquivo e a pasta temporária após enviar ao usuário
            try:
                if os.path.exists(filename):
                    os.remove(filename)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except Exception as e:
                app.logger.error(f"Erro ao deletar arquivo temporário: {e}")
            return response

        return send_file(filename, as_attachment=True)

    except Exception as e:
        return jsonify({'error': f'Erro no processamento: {str(e)}'}), 500

if __name__ == '__main__':
    # Usa a porta dinâmica do ambiente ou 5000 por padrão
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
