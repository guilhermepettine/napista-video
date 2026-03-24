"""
NaPista Video — Teste de Pipeline
Gera 2 áudios via ElevenLabs + renderiza vídeo via FFmpeg Service no Railway.
Salva video_final.mp4 localmente.
"""
__version__ = "1.0.0"

import json
import os
import io
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_DRIVE_VIDEO_ID = os.getenv("GOOGLE_DRIVE_VIDEO_ID")
FFMPEG_SERVICE_URL = os.getenv("FFMPEG_SERVICE_URL", "https://ffmpeg-video-service-production-bcac.up.railway.app")
TEST_NOME = os.getenv("TEST_NOME", "Guilherme")
TEST_EMPRESA = os.getenv("TEST_EMPRESA", "Grestar")
TEST_TEXTO = os.getenv("TEST_TEXTO", "Guilherme")

# Configurações do texto na tela
TEXTO_CONFIG = {
    "text": TEST_TEXTO,
    "start": 7.7,
    "end": 20,
    "font_size": 80,
    "font_color": "#E93925",   # RGB 233, 57, 37
    "font_family": "Gravitas One",
    "bold": False,
    "position": "baixo_esquerda",
}

# Configurações de voz ElevenLabs
VOICE_SETTINGS = {
    "stability": 0.35,
    "similarity_boost": 0.75,
    "style": 0.35,
    "use_speaker_boost": True,
    "speed": 0.97,   # slider ~60% do range 0.7–1.2
}


def checar_config():
    obrigatorios = {
        "ELEVENLABS_API_KEY": ELEVENLABS_API_KEY,
        "ELEVENLABS_VOICE_ID": ELEVENLABS_VOICE_ID,
        "GOOGLE_SERVICE_ACCOUNT_JSON": GOOGLE_SERVICE_ACCOUNT_JSON,
        "GOOGLE_DRIVE_VIDEO_ID": GOOGLE_DRIVE_VIDEO_ID,
    }
    faltando = [k for k, v in obrigatorios.items() if not v]
    if faltando:
        print(f"❌ Variáveis faltando no .env: {', '.join(faltando)}")
        sys.exit(1)
    print("✅ Config OK")


def checar_ffmpeg():
    """Verifica se o FFmpeg Service está no ar."""
    try:
        r = requests.get(f"{FFMPEG_SERVICE_URL}/health", timeout=10)
        r.raise_for_status()
        print(f"✅ FFmpeg Service OK — {r.json()}")
    except Exception as e:
        print(f"❌ FFmpeg Service inacessível: {e}")
        sys.exit(1)


def gerar_audio(texto: str, label: str) -> bytes:
    """Gera áudio via ElevenLabs e retorna bytes MP3."""
    print(f"🎙️  Gerando áudio '{label}': \"{texto}\"")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": texto,
        "model_id": "eleven_turbo_v2_5",
        "language_code": "pt",
        "voice_settings": VOICE_SETTINGS,
    }
    r = requests.post(url, headers=headers, json=body, timeout=30)
    if r.status_code != 200:
        print(f"❌ ElevenLabs erro {r.status_code}: {r.text[:200]}")
        sys.exit(1)
    print(f"   ✅ {len(r.content) / 1024:.1f} KB")
    return r.content


def baixar_video_drive(drive_id: str) -> bytes:
    """Baixa o vídeo base do Google Drive via service account."""
    print(f"📥 Baixando vídeo base do Drive...")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

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
        status, done = downloader.next_chunk()
        if status:
            print(f"   {int(status.progress() * 100)}%", end="\r")
    video_bytes = buffer.getvalue()
    print(f"   ✅ {len(video_bytes) / (1024*1024):.1f} MB")
    return video_bytes


def renderizar_video(audio_nome: bytes, audio_empresa: bytes, video_base: bytes) -> bytes:
    """Envia os áudios + vídeo base + timeline para o FFmpeg Service."""
    print("🎬 Renderizando vídeo no FFmpeg Service...")

    timeline = [
        {"type": "audio", "file_field": "audio_nome", "start": 0},
        {"type": "audio", "file_field": "audio_empresa", "start": 7.7},
        {
            "type": "text",
            "text": TEXTO_CONFIG["text"],
            "start": TEXTO_CONFIG["start"],
            "end": TEXTO_CONFIG["end"],
            "font_size": TEXTO_CONFIG["font_size"],
            "font_color": TEXTO_CONFIG["font_color"],
            "font_family": TEXTO_CONFIG["font_family"],
            "bold": TEXTO_CONFIG["bold"],
            "position": TEXTO_CONFIG["position"],
        },
    ]

    files = {
        "audio_nome": ("audio_nome.mp3", audio_nome, "audio/mpeg"),
        "audio_empresa": ("audio_empresa.mp3", audio_empresa, "audio/mpeg"),
        "video_base": ("video_base.mp4", video_base, "video/mp4"),
    }
    data = {"timeline_json": json.dumps(timeline)}

    r = requests.post(
        f"{FFMPEG_SERVICE_URL}/render",
        files=files,
        data=data,
        timeout=120,
    )
    if r.status_code != 200:
        print(f"❌ FFmpeg Service erro {r.status_code}: {r.text[:300]}")
        sys.exit(1)

    print(f"   ✅ Vídeo recebido: {len(r.content) / (1024*1024):.1f} MB")
    return r.content


def salvar_video(video_bytes: bytes, nome_arquivo: str = "video_final.mp4"):
    with open(nome_arquivo, "wb") as f:
        f.write(video_bytes)
    print(f"💾 Vídeo salvo: {nome_arquivo} ({len(video_bytes) / (1024*1024):.1f} MB)")


def main():
    print(f"\n🎬 NaPista Video — Teste de Pipeline v{__version__}")
    print(f"   Nome: {TEST_NOME} | Empresa: {TEST_EMPRESA}\n")

    checar_config()
    checar_ffmpeg()

    audio_nome = gerar_audio(TEST_NOME, "audio_nome")
    audio_empresa = gerar_audio(TEST_EMPRESA, "audio_empresa")
    video_base = baixar_video_drive(GOOGLE_DRIVE_VIDEO_ID)
    video_final = renderizar_video(audio_nome, audio_empresa, video_base)
    salvar_video(video_final)

    print("\n✅ Pipeline completo! Abra video_final.mp4 para conferir.")


if __name__ == "__main__":
    main()
