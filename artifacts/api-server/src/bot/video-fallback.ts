import { logger } from "../lib/logger.js";
import { generateTTSAudio } from "./tts.js";
import { execFile } from "node:child_process";
import { writeFile, unlink, mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

/**
 * Gera um vídeo MP4 real combinando uma imagem estática + áudio TTS via ffmpeg.
 *
 * Fluxo:
 * 1. Baixa a imagem da URL (Pollinations AI)
 * 2. Gera o áudio TTS via Edge TTS (gratuito)
 * 3. Combina imagem + áudio em vídeo MP4 com ffmpeg
 * 4. Retorna o Buffer do vídeo pronto
 *
 * O vídeo resultante mostra a imagem durante toda a duração do áudio,
 * com um leve efeito de zoom lento (Ken Burns) para dar vida à imagem.
 */
export async function generateFallbackVideo(
  text: string,
  imageUrl: string,
  voiceId: string,
  rate: string = "-18%",
  pitch: string = "+6%",
): Promise<Buffer | null> {
  let tempDir: string | null = null;

  try {
    // 1. Criar diretório temporário
    tempDir = await mkdtemp(join(tmpdir(), "dorama-vid-"));
    const imgPath = join(tempDir, "input.jpg");
    const audioPath = join(tempDir, "audio.mp3");
    const outputPath = join(tempDir, "output.mp4");

    logger.info({ voiceId, textLen: text.length, imageUrl: imageUrl.slice(0, 80) }, "Fallback video: iniciando...");

    // 2. Baixar imagem e gerar TTS em paralelo
    const [imageBuffer, ttsBuffer] = await Promise.all([
      downloadImage(imageUrl),
      generateTTSAudio(text, voiceId, rate, pitch),
    ]);

    if (!imageBuffer) {
      logger.error("Fallback video: falha ao baixar imagem");
      return null;
    }

    if (!ttsBuffer || ttsBuffer.length === 0) {
      logger.error("Fallback video: falha ao gerar áudio TTS");
      return null;
    }

    // 3. Salvar arquivos temporários
    await Promise.all([
      writeFile(imgPath, imageBuffer),
      writeFile(audioPath, ttsBuffer),
    ]);

    logger.info(
      { imgKb: Math.round(imageBuffer.length / 1024), audioKb: Math.round(ttsBuffer.length / 1024) },
      "Fallback video: imagem e áudio prontos, gerando MP4...",
    );

    // 4. Combinar com ffmpeg
    // - loop da imagem com duração do áudio
    // - efeito Ken Burns (zoom lento de 1.0x a 1.08x) para dar vida
    // - codec H.264 compatível com Telegram
    // - resolução 720x720 (quadrado, ideal para mobile/Telegram)
    const videoBuffer = await runFfmpeg(imgPath, audioPath, outputPath);

    if (!videoBuffer) {
      logger.error("Fallback video: ffmpeg falhou");
      return null;
    }

    logger.info(
      { kb: Math.round(videoBuffer.length / 1024) },
      "Fallback video: MP4 gerado com sucesso!",
    );

    return videoBuffer;
  } catch (err) {
    logger.error({ err }, "Fallback video: erro geral");
    return null;
  } finally {
    // Limpeza dos arquivos temporários
    if (tempDir) {
      try {
        await Promise.all([
          unlink(join(tempDir, "input.jpg")).catch(() => {}),
          unlink(join(tempDir, "audio.mp3")).catch(() => {}),
          unlink(join(tempDir, "output.mp4")).catch(() => {}),
        ]);
        const { rmdir } = await import("node:fs/promises");
        await rmdir(tempDir).catch(() => {});
      } catch {}
    }
  }
}

async function downloadImage(url: string): Promise<Buffer | null> {
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      },
    });
    if (!res.ok) {
      logger.error({ status: res.status, url: url.slice(0, 80) }, "Falha ao baixar imagem");
      return null;
    }
    const buf = await res.arrayBuffer();
    return Buffer.from(buf);
  } catch (err) {
    logger.error({ err }, "Erro ao baixar imagem");
    return null;
  }
}

function runFfmpeg(imgPath: string, audioPath: string, outputPath: string): Promise<Buffer | null> {
  return new Promise((resolve) => {
    const args = [
      // Input: imagem em loop
      "-loop", "1",
      "-i", imgPath,
      // Input: áudio TTS
      "-i", audioPath,
      // Filtro de vídeo: escala + Ken Burns dinâmico (zoom oscilante + pan)
      // zoom: oscila entre 1.0x-1.35x usando onda senoidal (~10s por ciclo a 24fps)
      // x/y: paneia suavemente pela imagem com padrão senoidal para movimento constante
      "-vf", "scale=1280:1280:force_original_aspect_ratio=increase,crop=1280:1280,zoompan=z='1.0+0.35*abs(sin(on/240*PI))':d=3120:x='(iw-iw/zoom)/2+30*sin(on/180*PI)':y='(ih-ih/zoom)/2+20*cos(on/220*PI)':s=720x720:fps=24",
      // Codec de vídeo H.264 (máxima compatibilidade com Telegram)
      "-c:v", "libx264",
      "-preset", "fast",
      "-crf", "28",
      "-pix_fmt", "yuv420p",
      // Codec de áudio AAC
      "-c:a", "aac",
      "-b:a", "96k",
      // Duração = duração do áudio (encerra quando o áudio termina)
      "-shortest",
      // Metadados mínimos para compatibilidade
      "-movflags", "+faststart",
      // Limitar duração máxima a 120 segundos
      "-t", "120",
      // Sobrescrever output
      "-y",
      outputPath,
    ];

    const timeout = setTimeout(() => {
      logger.error("ffmpeg: timeout após 90 segundos");
      try { proc.kill("SIGKILL"); } catch {}
      resolve(null);
    }, 90_000);

    const proc = execFile("ffmpeg", args, { maxBuffer: 50 * 1024 * 1024 }, async (error, _stdout, stderr) => {
      clearTimeout(timeout);

      if (error) {
        logger.error({ error: error.message, stderr: stderr?.slice(0, 500) }, "ffmpeg erro");
        resolve(null);
        return;
      }

      try {
        const { readFile } = await import("node:fs/promises");
        const buf = await readFile(outputPath);
        resolve(buf);
      } catch (readErr) {
        logger.error({ readErr }, "Erro ao ler output do ffmpeg");
        resolve(null);
      }
    });
  });
}

/**
 * Generate a fallback video WITHOUT narration — image + ambient music only.
 */
export async function generateFallbackVideoNoNarration(
  imageUrl: string,
  durationSeconds: number = 30,
): Promise<Buffer | null> {
  let tempDir: string | null = null;

  try {
    tempDir = await mkdtemp(join(tmpdir(), "dorama-nonarr-fb-"));
    const imgPath = join(tempDir, "input.jpg");
    const outputPath = join(tempDir, "output_nonarr.mp4");

    logger.info({ imageUrl: imageUrl.slice(0, 80), duration: durationSeconds }, "Fallback no-narration video: iniciando...");

    const imageBuffer = await downloadImage(imageUrl);
    if (!imageBuffer) {
      logger.error("Fallback no-narration: falha ao baixar imagem");
      return null;
    }

    await writeFile(imgPath, imageBuffer);

    // Generate ambient music via ffmpeg sine waves
    const ambientPath = join(tempDir, "ambient.mp3");
    const fadeOut = String(durationSeconds - 3);
    const ambientArgs = [
      "-f", "lavfi", "-i", `sine=f=174:d=${durationSeconds}`,
      "-f", "lavfi", "-i", `sine=f=220:d=${durationSeconds}`,
      "-f", "lavfi", "-i", `sine=f=261:d=${durationSeconds}`,
      "-filter_complex",
      `[0][1][2]amix=inputs=3,volume=0.03,lowpass=f=600,aecho=0.8:0.88:500:0.4,afade=t=in:d=2,afade=t=out:st=${fadeOut}:d=3`,
      "-c:a", "libmp3lame",
      "-b:a", "64k",
      "-y",
      ambientPath,
    ];

    await new Promise<void>((resolve) => {
      const proc = execFile("ffmpeg", ambientArgs, { maxBuffer: 20 * 1024 * 1024 }, () => resolve());
    });

    // Compose: Ken Burns image + ambient music
    const videoArgs = [
      "-loop", "1",
      "-i", imgPath,
      "-i", ambientPath,
      "-filter_complex",
      `[0:v]scale=1280:1280:force_original_aspect_ratio=increase,crop=1280:1280,zoompan=z='1.0+0.35*abs(sin(on/240*PI))':d=3120:x='(iw-iw/zoom)/2+30*sin(on/180*PI)':y='(ih-ih/zoom)/2+20*cos(on/220*PI)':s=720x720:fps=24[vid];[1:a]volume=0.6[audio]`,
      "-map", "[vid]",
      "-map", "[audio]",
      "-c:v", "libx264",
      "-preset", "fast",
      "-crf", "28",
      "-pix_fmt", "yuv420p",
      "-c:a", "aac",
      "-b:a", "96k",
      "-t", String(durationSeconds),
      "-movflags", "+faststart",
      "-y",
      outputPath,
    ];

    const videoBuffer = await new Promise<Buffer | null>((resolve) => {
      const timeout = setTimeout(() => {
        logger.error("ffmpeg no-narration: timeout");
        try { proc.kill("SIGKILL"); } catch {}
        resolve(null);
      }, 90_000);

      const proc = execFile("ffmpeg", videoArgs, { maxBuffer: 50 * 1024 * 1024 }, async (error, _stdout, stderr) => {
        clearTimeout(timeout);
        if (error) {
          logger.error({ error: error.message, stderr: stderr?.slice(0, 500) }, "ffmpeg no-narration erro");
          resolve(null);
          return;
        }
        try {
          const { readFile } = await import("node:fs/promises");
          const buf = await readFile(outputPath);
          resolve(buf);
        } catch (readErr) {
          logger.error({ readErr }, "Erro ao ler output no-narration");
          resolve(null);
        }
      });
    });

    return videoBuffer;
  } catch (err) {
    logger.error({ err }, "Fallback no-narration: erro geral");
    return null;
  } finally {
    if (tempDir) {
      try {
        const { readdir, rmdir: rmdirFs } = await import("node:fs/promises");
        const files = await readdir(tempDir);
        await Promise.all(files.map((f) => unlink(join(tempDir!, f)).catch(() => {})));
        await rmdirFs(tempDir).catch(() => {});
      } catch {}
    }
  }
}
