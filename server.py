"""
NaPista Video — Web Server
Formulário simples para gerar vídeos personalizados.
"""
import io
import json
import os
import requests
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, Response, JSONResponse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

app = FastAPI()

ELEVENLABS_API_KEY      = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID     = os.getenv("ELEVENLABS_VOICE_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_DRIVE_VIDEO_ID   = os.getenv("GOOGLE_DRIVE_VIDEO_ID", "")
FFMPEG_SERVICE_URL      = os.getenv("FFMPEG_SERVICE_URL", "")

VOICE_SETTINGS = {
    "stability": 0.35,
    "similarity_boost": 0.75,
    "style": 0.35,
    "use_speaker_boost": True,
    "speed": 0.97,
}

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NaPista — Gerador de Vídeo</title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Work+Sans:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Work Sans', sans-serif;
      background: #F4F6FA;
      color: #252626;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }
    header {
      width: 100%;
      background: #fff;
      border-bottom: 1px solid #E9EDF2;
      padding: 18px 32px;
      display: flex;
      align-items: center;
      position: fixed;
      top: 0;
    }
    .logo-text {
      font-family: 'DM Sans', sans-serif;
      font-weight: 700;
      font-size: 20px;
      color: #223DFF;
      letter-spacing: -0.5px;
    }
    .card {
      background: #fff;
      border-radius: 16px;
      padding: 48px;
      width: 100%;
      max-width: 480px;
      box-shadow: 0px 2px 4px rgba(0,0,0,0.08), 0px 8px 24px rgba(0,0,0,0.06);
      margin-top: 80px;
    }
    h1 {
      font-family: 'DM Sans', sans-serif;
      font-size: 28px;
      font-weight: 700;
      margin-bottom: 8px;
      color: #091868;
    }
    .subtitle {
      font-size: 14px;
      color: #67696B;
      margin-bottom: 32px;
    }
    label {
      display: block;
      font-size: 13px;
      font-weight: 500;
      color: #67696B;
      margin-bottom: 8px;
    }
    input {
      width: 100%;
      background: #fff;
      border: 1.5px solid #E9EDF2;
      border-radius: 99px;
      padding: 14px 20px;
      font-size: 15px;
      font-family: 'Work Sans', sans-serif;
      color: #252626;
      margin-bottom: 20px;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    input:focus {
      border-color: #223DFF;
      box-shadow: 0px 4px 8px rgba(0, 49, 188, 0.16);
    }
    button {
      width: 100%;
      background: #223DFF;
      color: #fff;
      border: none;
      border-radius: 99px;
      padding: 16px;
      font-size: 15px;
      font-family: 'DM Sans', sans-serif;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.2s, box-shadow 0.2s;
      letter-spacing: 0.2px;
    }
    button:hover { background: #091868; box-shadow: 0px 4px 12px rgba(34,61,255,0.3); }
    button:disabled { background: #A5AAAF; cursor: not-allowed; box-shadow: none; }
    .status {
      margin-top: 20px;
      padding: 14px 18px;
      border-radius: 12px;
      font-size: 14px;
      display: none;
      line-height: 1.5;
    }
    .status.loading { background: #EEF1FF; color: #223DFF; border: 1px solid #C7CFFE; }
    .status.success { background: #EEFAF3; color: #1a7a45; border: 1px solid #B0E8C8; }
    .status.error   { background: #FFF0EE; color: #C0392B; border: 1px solid #F5C0BA; }
  </style>
</head>
<body>
  <header>
    <span class="logo-text">napista</span>
  </header>
  <div class="card">
    <h1>Gerador de Vídeo</h1>
    <p class="subtitle">Preencha os dados para gerar um vídeo personalizado.</p>
    <form id="form">
      <label>Nome</label>
      <input type="text" id="nome" placeholder="Ex: Guilherme" required>
      <label>Empresa</label>
      <input type="text" id="empresa" placeholder="Ex: Car Drive" required>
      <button type="submit" id="btn">Gerar Vídeo</button>
    </form>
    <div class="status" id="status"></div>
  </div>
  <script>
    const form = document.getElementById('form');
    const btn = document.getElementById('btn');
    const status = document.getElementById('status');

    function showStatus(msg, type) {
      status.innerHTML = msg;
      status.className = 'status ' + type;
      status.style.display = 'block';
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const nome = document.getElementById('nome').value.trim();
      const empresa = document.getElementById('empresa').value.trim();
      if (!nome || !empresa) return;

      btn.disabled = true;
      btn.textContent = 'Gerando...';
      showStatus('⏳ Gerando áudios e renderizando vídeo...<br>Isso leva cerca de 30–60 segundos.', 'loading');

      try {
        const fd = new FormData();
        fd.append('nome', nome);
        fd.append('empresa', empresa);

        const res = await fetch('/gerar', { method: 'POST', body: fd });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Erro desconhecido');
        }

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `napista_${nome.replace(/\\s+/g, '_')}.mp4`;
        a.click();
        URL.revokeObjectURL(url);

        showStatus('✅ Vídeo gerado e baixado com sucesso!', 'success');
      } catch (err) {
        showStatus('❌ Erro: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Gerar Vídeo';
      }
    });
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML


@app.post("/gerar")
async def gerar(nome: str = Form(...), empresa: str = Form(...)):
    # 1. Gera áudios
    audio_nome    = _gerar_audio(f"Oi {nome}, bem-vindo ao NaPista.")
    audio_empresa = _gerar_audio(f"Aqui a {empresa}")

    # 2. Baixa vídeo base do Drive
    video_base = _baixar_drive(GOOGLE_DRIVE_VIDEO_ID)

    # 3. Monta timeline
    timeline = [
        {"type": "audio", "file_field": "audio_nome",    "start": 0},
        {"type": "audio", "file_field": "audio_empresa", "start": 7.7},
        {
            "type": "text", "text": empresa,
            "start": 7.7, "end": 20,
            "font_size": 80, "font_color": "#E93925",
            "font_family": "Gravitas One", "bold": False,
            "position": "baixo_esquerda",
        },
    ]

    # 4. Renderiza via FFmpeg Service
    files = {
        "audio_nome":    ("audio_nome.mp3",    audio_nome,    "audio/mpeg"),
        "audio_empresa": ("audio_empresa.mp3",  audio_empresa, "audio/mpeg"),
        "video_base":    ("video_base.mp4",     video_base,    "video/mp4"),
    }
    r = requests.post(
        f"{FFMPEG_SERVICE_URL}/render",
        files=files,
        data={"timeline_json": json.dumps(timeline)},
        timeout=180,
    )
    if r.status_code != 200:
        return JSONResponse(status_code=500, content={"detail": f"FFmpeg erro: {r.text[:300]}"})

    return Response(
        content=r.content,
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="napista_{nome}.mp4"'},
    )


def _gerar_audio(texto: str) -> bytes:
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
        headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        json={"text": texto, "model_id": "eleven_turbo_v2_5", "language_code": "pt", "voice_settings": VOICE_SETTINGS},
        timeout=30,
    )
    if r.status_code != 200:
        raise Exception(f"ElevenLabs erro {r.status_code}: {r.text[:200]}")
    return r.content


def _baixar_drive(drive_id: str) -> bytes:
    sa_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=creds)
    request = service.files().get_media(fileId=drive_id, supportsAllDrives=True)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()
