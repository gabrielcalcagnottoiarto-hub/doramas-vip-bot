"""
Módulo de Geração de Mídia para Novelas.
Gera áudio (narração), imagens de cenas e vídeos para as novelas.
Integra com:
- gTTS: Narração gratuita em português
- Pollinations.ai: Imagens de cenas gratuitas (sem API key)
- Pika Labs: Vídeos com pessoas em movimento (requer API key)
"""

import os
import logging
import tempfile
import asyncio
import urllib.parse
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────
PIKA_API_KEY = os.environ.get("PIKA_API_KEY", "")
MEDIA_DIR = Path(__file__).parent / "media"
MEDIA_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# ÁUDIO - NARRAÇÃO COM gTTS (GRATUITO)
# ─────────────────────────────────────────────
async def gerar_audio_narracao(texto: str, filename: str = None) -> str:
    """
    Gera áudio de narração usando gTTS (Google Text-to-Speech).
    Retorna o caminho do arquivo de áudio MP3.
    100% gratuito, sem limite de uso.
    """
    try:
        from gtts import gTTS

        if not filename:
            filename = f"narracao_{hash(texto) % 100000}.mp3"

        filepath = MEDIA_DIR / filename

        # Run gTTS in thread to not block async loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _create_audio, texto, str(filepath))

        if filepath.exists():
            logger.info(f"Áudio gerado: {filepath} ({filepath.stat().st_size} bytes)")
            return str(filepath)

    except Exception as e:
        logger.error(f"Erro ao gerar áudio: {e}")

    return ""


def _create_audio(texto: str, filepath: str) -> None:
    """Helper síncrono para gerar áudio."""
    from gtts import gTTS

    # Limitar texto para evitar áudios muito longos
    texto_limitado = texto[:2000]

    tts = gTTS(text=texto_limitado, lang="pt-br", slow=False)
    tts.save(filepath)


async def gerar_audio_episodio(titulo_novela: str, episodio_num: int,
                                sinopse: str, dialogo: str) -> str:
    """Gera narração completa de um episódio."""
    texto_narracao = (
        f"{titulo_novela}. Episódio {episodio_num}. "
        f"{sinopse} "
        f"{dialogo}"
    )

    filename = f"ep_{hash(titulo_novela) % 10000}_{episodio_num}.mp3"
    return await gerar_audio_narracao(texto_narracao, filename)


# ─────────────────────────────────────────────
# IMAGENS - POLLINATIONS.AI (GRATUITO)
# ─────────────────────────────────────────────
def gerar_url_imagem(prompt: str, width: int = 1024, height: int = 768) -> str:
    """
    Gera URL de imagem usando Pollinations.ai.
    100% gratuito, sem API key necessária.
    A URL retornada gera a imagem on-demand quando acessada.
    """
    # Pollinations.ai gera imagens direto na URL
    prompt_encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width={width}&height={height}&nologo=true"
    return url


def gerar_imagem_cena_novela(categoria: str, tipo_cena: str = "romantica") -> str:
    """Gera imagem de cena de novela."""
    prompts = {
        "turca": {
            "romantica": "Beautiful Turkish couple in romantic scene, Istanbul sunset, Bosphorus background, cinematic lighting, telenovela style, 4K",
            "drama": "Dramatic confrontation scene, Turkish mansion interior, elegant decor, tense atmosphere, cinematic, telenovela",
            "cidade": "Beautiful Istanbul cityscape, Hagia Sophia, sunset, romantic atmosphere, cinematic photography",
            "mansao": "Luxurious Turkish mansion interior, marble floors, chandelier, elegant, telenovela setting",
            "natureza": "Beautiful Cappadocia landscape, hot air balloons, sunset, romantic, cinematic",
        },
        "mexicana": {
            "romantica": "Beautiful Latin couple in romantic scene, Mexican hacienda, sunset, passionate, telenovela style, 4K",
            "drama": "Dramatic scene in Mexican mansion, family confrontation, elegant interior, tense atmosphere, telenovela",
            "cidade": "Mexico City skyline at night, colorful lights, romantic atmosphere, cinematic photography",
            "mansao": "Luxurious Mexican hacienda interior, colonial style, flowers, elegant, telenovela setting",
            "natureza": "Beautiful Mexican beach, Cancun turquoise water, sunset, romantic, paradise, cinematic",
        },
    }

    cat_prompts = prompts.get(categoria, prompts["mexicana"])
    prompt = cat_prompts.get(tipo_cena, cat_prompts["romantica"])

    return gerar_url_imagem(prompt)


def gerar_imagem_personagem(nome: str, categoria: str, genero: str = "feminino") -> str:
    """Gera imagem de personagem."""
    if categoria == "turca":
        if genero == "feminino":
            prompt = f"Portrait of beautiful Turkish woman named {nome}, elegant, dark hair, brown eyes, professional photo, telenovela actress style, 4K"
        else:
            prompt = f"Portrait of handsome Turkish man named {nome}, strong features, dark hair, charismatic, professional photo, telenovela actor style, 4K"
    else:
        if genero == "feminino":
            prompt = f"Portrait of beautiful Latin woman named {nome}, elegant, passionate eyes, professional photo, telenovela actress style, 4K"
        else:
            prompt = f"Portrait of handsome Latin man named {nome}, charismatic, strong jawline, professional photo, telenovela actor style, 4K"

    return gerar_url_imagem(prompt, 512, 512)


def gerar_capa_novela(titulo: str, categoria: str) -> str:
    """Gera imagem de capa para novela."""
    if categoria == "turca":
        prompt = f"Movie poster for Turkish telenovela '{titulo}', romantic drama, beautiful couple, Istanbul skyline background, dramatic lighting, cinematic, professional poster design, 4K"
    else:
        prompt = f"Movie poster for Mexican telenovela '{titulo}', passionate romance, beautiful couple, hacienda background, warm colors, dramatic lighting, cinematic, professional poster design, 4K"

    return gerar_url_imagem(prompt, 768, 1024)


# ─────────────────────────────────────────────
# VÍDEOS - PIKA LABS (REQUER API KEY)
# ─────────────────────────────────────────────
async def gerar_video_pika(prompt: str, duration: int = 4) -> str:
    """
    Gera vídeo usando Pika Labs API.
    Requer PIKA_API_KEY nas variáveis de ambiente.
    Retorna URL do vídeo gerado.

    Pika Labs gera vídeos de até 4 segundos com pessoas em movimento.
    """
    if not PIKA_API_KEY:
        logger.warning("PIKA_API_KEY não configurada. Vídeo não gerado.")
        return ""

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            # Pika Labs API - Create video generation
            resp = await client.post(
                "https://api.pika.art/v1/generate",
                headers={
                    "Authorization": f"Bearer {PIKA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": prompt,
                    "style": "cinematic",
                    "ratio": "16:9",
                    "duration": duration,
                },
            )

            if resp.status_code in (200, 201, 202):
                data = resp.json()
                video_id = data.get("id") or data.get("generation_id")

                if video_id:
                    # Poll for completion
                    video_url = await _poll_pika_video(client, video_id)
                    return video_url

            logger.error(f"Pika API erro: {resp.status_code} - {resp.text}")

    except Exception as e:
        logger.error(f"Erro ao gerar vídeo Pika: {e}")

    return ""


async def _poll_pika_video(client: httpx.AsyncClient, video_id: str,
                           max_attempts: int = 30) -> str:
    """Aguarda o vídeo ser processado no Pika Labs."""
    for _ in range(max_attempts):
        await asyncio.sleep(10)
        try:
            resp = await client.get(
                f"https://api.pika.art/v1/generate/{video_id}",
                headers={"Authorization": f"Bearer {PIKA_API_KEY}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "")
                if status == "completed":
                    return data.get("video_url", "")
                elif status == "failed":
                    logger.error(f"Pika video falhou: {data}")
                    return ""
        except Exception as e:
            logger.warning(f"Erro ao verificar vídeo Pika: {e}")

    return ""


async def gerar_video_cena_novela(categoria: str, tipo_cena: str = "romantica") -> str:
    """Gera vídeo de cena de novela com Pika Labs."""
    prompts = {
        "turca": {
            "romantica": "Beautiful Turkish couple walking together along the Bosphorus at sunset, romantic, cinematic, slow motion",
            "drama": "Turkish woman confronting a man in a luxurious mansion, dramatic, intense emotion, cinematic",
            "encontro": "Turkish man and woman meeting eyes for the first time in a bazaar, magical moment, cinematic",
        },
        "mexicana": {
            "romantica": "Beautiful Latin couple dancing together at a hacienda party, passionate, warm lights, cinematic",
            "drama": "Latin woman crying in a luxurious bedroom, rain outside the window, emotional, cinematic",
            "encontro": "Latin man arriving on horseback at a ranch, confident, sunset, cinematic western style",
        },
    }

    cat_prompts = prompts.get(categoria, prompts["mexicana"])
    prompt = cat_prompts.get(tipo_cena, cat_prompts["romantica"])

    return await gerar_video_pika(prompt)


# ─────────────────────────────────────────────
# GERADOR COMPLETO DE MÍDIA PARA EPISÓDIO
# ─────────────────────────────────────────────
async def gerar_midia_episodio(titulo_novela: str, categoria: str,
                                episodio_num: int, sinopse: str,
                                dialogo: str, tipo_cena: str = "romantica") -> dict:
    """
    Gera todo o pacote de mídia para um episódio:
    - Áudio de narração (sempre disponível - grátis)
    - Imagem da cena (sempre disponível - grátis)
    - Vídeo (se Pika API key disponível)
    """
    resultado = {
        "audio": "",
        "imagem": "",
        "video": "",
        "capa": "",
    }

    # Áudio (sempre funciona - grátis)
    resultado["audio"] = await gerar_audio_episodio(
        titulo_novela, episodio_num, sinopse, dialogo
    )

    # Imagem da cena (sempre funciona - grátis)
    resultado["imagem"] = gerar_imagem_cena_novela(categoria, tipo_cena)

    # Capa da novela (sempre funciona - grátis)
    resultado["capa"] = gerar_capa_novela(titulo_novela, categoria)

    # Vídeo (requer Pika API key)
    if PIKA_API_KEY:
        resultado["video"] = await gerar_video_cena_novela(categoria, tipo_cena)

    return resultado


# ─────────────────────────────────────────────
# LIMPEZA DE MÍDIA
# ─────────────────────────────────────────────
def limpar_media_antiga(max_files: int = 100) -> int:
    """Remove arquivos de mídia antigos para economizar espaço."""
    files = sorted(MEDIA_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime)
    removed = 0
    while len(files) > max_files:
        oldest = files.pop(0)
        oldest.unlink()
        removed += 1
    return removed
