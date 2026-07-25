import os
import tempfile
from flask import Flask, render_template, request, jsonify, send_file, after_this_request
import yt_dlp

app = Flask(__name__)

# --- CONFIGURAÇÃO DE COOKIES PARA O RENDER ---
COOKIES_PATH = '/tmp/cookies.txt'

def setup_cookies():
    """Verifica se os cookies do Render existem e salva em um arquivo temporário."""
    cookies_content = os.environ.get('YOUTUBE_COOKIES')
    if cookies_content:
        try:
            with open(COOKIES_PATH, 'w', encoding='utf-8') as f:
                f.write(cookies_content)
            return COOKIES_PATH
        except Exception as e:
            app.logger.error(f"Erro ao salvar arquivo de cookies: {e}")
    return None


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
    
    # Adiciona os cookies se estiverem configurados no Render
    cookie_file = setup_cookies()
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

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

    # Adiciona os cookies se estiverem configurados no Render
    cookie_file = setup_cookies()
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
