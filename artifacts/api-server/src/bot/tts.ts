import { logger } from "../lib/logger.js";
import https from "https";
import http from "http";

/**
 * TTS Module — Fish.audio (primary) + ElevenLabs (fallback) + Google TTS (last resort)
 *
 * Priority order:
 *   1. Fish.audio  — high-quality multilingual TTS (requires FISH_AUDIO_API_KEY)
 *   2. ElevenLabs  — fallback neural TTS (requires ELEVENLABS_API_KEY)
 *   3. Google TTS  — free fallback, lower quality, no API key needed
 */

const FISH_AUDIO_API_KEY = process.env["FISH_AUDIO_API_KEY"] ?? "";
const ELEVENLABS_API_KEY = process.env["ELEVENLABS_API_KEY"] ?? "";

/**
 * Fish.audio voice model IDs (reference_id)
 * Browse available voices at https://fish.audio/discovery
 *
 * You can override any voice via environment variables:
 *   FISH_VOICE_PT_BR_F=<reference_id>
 *   FISH_VOICE_PT_BR_M=<reference_id>
 *   FISH_VOICE_EN=<reference_id>
 *   FISH_VOICE_ES=<reference_id>
 *   FISH_VOICE_KO=<reference_id>
 *   FISH_VOICE_JA=<reference_id>
 *   FISH_VOICE_FR=<reference_id>
 *   FISH_VOICE_IT=<reference_id>
 *   FISH_VOICE_DE=<reference_id>
 *   FISH_VOICE_ZH=<reference_id>
 *
 * Default reference_id uses Fish.audio's built-in multilingual model.
 */
const DEFAULT_FISH_VOICE = "7f92f8afb8ec43bf81429cc1c9199cb1";

const FISH_VOICES: Record<string, { referenceId: string; name: string }> = {
  "pt-BR-ThalitaMultilingualNeural": { referenceId: process.env["FISH_VOICE_PT_BR_F"] ?? DEFAULT_FISH_VOICE, name: "Fish-PT-BR-F" },
  "pt-BR-AntonioNeural":            { referenceId: process.env["FISH_VOICE_PT_BR_M"] ?? DEFAULT_FISH_VOICE, name: "Fish-PT-BR-M" },
  "en-US-AvaMultilingualNeural":     { referenceId: process.env["FISH_VOICE_EN"] ?? DEFAULT_FISH_VOICE, name: "Fish-EN-US" },
  "es-ES-ElviraNeural":              { referenceId: process.env["FISH_VOICE_ES"] ?? DEFAULT_FISH_VOICE, name: "Fish-ES" },
  "ko-KR-SunHiNeural":              { referenceId: process.env["FISH_VOICE_KO"] ?? DEFAULT_FISH_VOICE, name: "Fish-KO" },
  "ja-JP-NanamiNeural":              { referenceId: process.env["FISH_VOICE_JA"] ?? DEFAULT_FISH_VOICE, name: "Fish-JA" },
  "fr-FR-DeniseNeural":              { referenceId: process.env["FISH_VOICE_FR"] ?? DEFAULT_FISH_VOICE, name: "Fish-FR" },
  "it-IT-ElsaNeural":                { referenceId: process.env["FISH_VOICE_IT"] ?? DEFAULT_FISH_VOICE, name: "Fish-IT" },
  "de-DE-KatjaNeural":               { referenceId: process.env["FISH_VOICE_DE"] ?? DEFAULT_FISH_VOICE, name: "Fish-DE" },
  "zh-CN-XiaoxiaoNeural":            { referenceId: process.env["FISH_VOICE_ZH"] ?? DEFAULT_FISH_VOICE, name: "Fish-ZH" },
};

/**
 * ElevenLabs voice IDs — high-quality neural voices (fallback)
 * Map from our internal voice identifiers to ElevenLabs voice IDs
 */
const ELEVENLABS_VOICES: Record<string, { voiceId: string; name: string }> = {
  "pt-BR-ThalitaMultilingualNeural": { voiceId: "EXAVITQu4vr4xnSDxMaL", name: "Sarah" },
  "pt-BR-AntonioNeural": { voiceId: "TX3LPaxmHKxFdv7VOQHJ", name: "Liam" },
  "en-US-AvaMultilingualNeural": { voiceId: "EXAVITQu4vr4xnSDxMaL", name: "Sarah" },
  "es-ES-ElviraNeural": { voiceId: "EXAVITQu4vr4xnSDxMaL", name: "Sarah" },
  "ko-KR-SunHiNeural": { voiceId: "EXAVITQu4vr4xnSDxMaL", name: "Sarah" },
  "ja-JP-NanamiNeural": { voiceId: "EXAVITQu4vr4xnSDxMaL", name: "Sarah" },
  "fr-FR-DeniseNeural": { voiceId: "EXAVITQu4vr4xnSDxMaL", name: "Sarah" },
  "it-IT-ElsaNeural": { voiceId: "EXAVITQu4vr4xnSDxMaL", name: "Sarah" },
  "de-DE-KatjaNeural": { voiceId: "EXAVITQu4vr4xnSDxMaL", name: "Sarah" },
  "zh-CN-XiaoxiaoNeural": { voiceId: "EXAVITQu4vr4xnSDxMaL", name: "Sarah" },
};

/** Map voice IDs to Google TTS language codes (fallback) */
const VOICE_TO_GTTS_LANG: Record<string, string> = {
  "pt-BR-ThalitaMultilingualNeural": "pt",
  "pt-BR-AntonioNeural": "pt",
  "en-US-AvaMultilingualNeural": "en",
  "es-ES-ElviraNeural": "es",
  "ko-KR-SunHiNeural": "ko",
  "ja-JP-NanamiNeural": "ja",
  "fr-FR-DeniseNeural": "fr",
  "it-IT-ElsaNeural": "it",
  "de-DE-KatjaNeural": "de",
  "zh-CN-XiaoxiaoNeural": "zh-CN",
};

/**
 * Generate TTS audio.
 * Priority: Fish.audio → ElevenLabs → Google TTS
 */
export async function generateTTSAudio(
  text: string,
  voiceId: string,
  rate: string = "-12%",
  pitch: string = "+6%",
): Promise<Buffer | null> {
  if (!text || text.trim().length === 0) {
    logger.warn("TTS: texto vazio, ignorando");
    return null;
  }

  // 1. Try Fish.audio (primary)
  if (FISH_AUDIO_API_KEY) {
    const result = await _attemptFishAudio(text, voiceId);
    if (result) return result;
    logger.warn("Fish.audio TTS failed, trying ElevenLabs fallback");
  } else {
    logger.info("FISH_AUDIO_API_KEY not set, skipping Fish.audio");
  }

  // 2. Try ElevenLabs (fallback)
  if (ELEVENLABS_API_KEY) {
    const result = await _attemptElevenLabs(text, voiceId);
    if (result) return result;
    logger.warn("ElevenLabs TTS failed, trying Google TTS fallback");
  } else {
    logger.info("ELEVENLABS_API_KEY not set, skipping ElevenLabs");
  }

  // 3. Fallback: Google Translate TTS
  const gttsResult = await _attemptGoogleTTS(text, voiceId);
  if (gttsResult) return gttsResult;

  logger.error("TTS: all providers failed");
  return null;
}

// ─── Fish.audio TTS (primary) ───────────────────────────────────────────────

async function _attemptFishAudio(
  text: string,
  voiceId: string,
): Promise<Buffer | null> {
  const voice = FISH_VOICES[voiceId] ?? FISH_VOICES["pt-BR-ThalitaMultilingualNeural"]!;
  const cleanText = text.slice(0, 5000); // Fish.audio supports long text

  logger.info(
    { voice: voice.name, referenceId: voice.referenceId, textLen: cleanText.length },
    "Fish.audio TTS: generating audio...",
  );

  return new Promise<Buffer | null>((resolve) => {
    const postData = JSON.stringify({
      text: cleanText,
      reference_id: voice.referenceId,
      format: "mp3",
      mp3_bitrate: 128,
      chunk_length: 300,
      normalize: true,
      latency: "balanced",
      temperature: 0.7,
      top_p: 0.7,
      prosody: {
        speed: 1,
        volume: 0,
        normalize_loudness: true,
      },
    });

    const req = https.request(
      {
        hostname: "api.fish.audio",
        path: "/v1/tts",
        method: "POST",
        headers: {
          "Authorization": `Bearer ${FISH_AUDIO_API_KEY}`,
          "Content-Type": "application/json",
          "model": "s2-pro",
          "Content-Length": Buffer.byteLength(postData),
        },
        timeout: 45000,
      },
      (res: http.IncomingMessage) => {
        if (res.statusCode !== 200) {
          const chunks: Buffer[] = [];
          res.on("data", (c: Buffer) => chunks.push(c));
          res.on("end", () => {
            const body = Buffer.concat(chunks).toString();
            logger.error(
              { status: res.statusCode, body: body.slice(0, 300) },
              "Fish.audio TTS: API error",
            );
            resolve(null);
          });
          return;
        }

        const audioChunks: Buffer[] = [];
        res.on("data", (chunk: Buffer) => audioChunks.push(chunk));
        res.on("end", () => {
          if (audioChunks.length > 0) {
            const result = Buffer.concat(audioChunks);
            logger.info(
              { kb: Math.round(result.length / 1024) },
              "Fish.audio TTS: audio gerado com sucesso",
            );
            resolve(result);
          } else {
            resolve(null);
          }
        });
        res.on("error", () => resolve(null));
      },
    );

    req.on("error", (err) => {
      logger.error({ err }, "Fish.audio TTS: request error");
      resolve(null);
    });

    req.on("timeout", () => {
      logger.error("Fish.audio TTS: timeout after 45s");
      req.destroy();
      resolve(null);
    });

    req.write(postData);
    req.end();
  });
}

// ─── ElevenLabs TTS ──────────────────────────────────────────────────────────

async function _attemptElevenLabs(
  text: string,
  voiceId: string,
): Promise<Buffer | null> {
  const voice = ELEVENLABS_VOICES[voiceId] ?? { voiceId: "EXAVITQu4vr4xnSDxMaL", name: "Sarah" };
  const cleanText = text.slice(0, 2500); // ElevenLabs supports longer text

  logger.info(
    { voice: voice.name, voiceId: voice.voiceId, textLen: cleanText.length },
    "ElevenLabs TTS: generating audio...",
  );

  return new Promise<Buffer | null>((resolve) => {
    const postData = JSON.stringify({
      text: cleanText,
      model_id: "eleven_multilingual_v2",
      voice_settings: {
        stability: 0.5,
        similarity_boost: 0.75,
        style: 0.4,
        use_speaker_boost: true,
      },
    });

    const req = https.request(
      {
        hostname: "api.elevenlabs.io",
        path: `/v1/text-to-speech/${voice.voiceId}`,
        method: "POST",
        headers: {
          "Accept": "audio/mpeg",
          "Content-Type": "application/json",
          "xi-api-key": ELEVENLABS_API_KEY,
          "Content-Length": Buffer.byteLength(postData),
        },
        timeout: 30000,
      },
      (res: http.IncomingMessage) => {
        if (res.statusCode !== 200) {
          const chunks: Buffer[] = [];
          res.on("data", (c: Buffer) => chunks.push(c));
          res.on("end", () => {
            const body = Buffer.concat(chunks).toString();
            logger.error(
              { status: res.statusCode, body: body.slice(0, 200) },
              "ElevenLabs TTS: API error",
            );
            resolve(null);
          });
          return;
        }

        const audioChunks: Buffer[] = [];
        res.on("data", (chunk: Buffer) => audioChunks.push(chunk));
        res.on("end", () => {
          if (audioChunks.length > 0) {
            const result = Buffer.concat(audioChunks);
            logger.info(
              { kb: Math.round(result.length / 1024) },
              "ElevenLabs TTS: audio gerado com sucesso",
            );
            resolve(result);
          } else {
            resolve(null);
          }
        });
        res.on("error", () => resolve(null));
      },
    );

    req.on("error", (err) => {
      logger.error({ err }, "ElevenLabs TTS: request error");
      resolve(null);
    });

    req.on("timeout", () => {
      logger.error("ElevenLabs TTS: timeout after 30s");
      req.destroy();
      resolve(null);
    });

    req.write(postData);
    req.end();
  });
}

// ─── Google Translate TTS (fallback) ─────────────────────────────────────────

async function _attemptGoogleTTS(
  text: string,
  voiceId: string,
): Promise<Buffer | null> {
  const lang = VOICE_TO_GTTS_LANG[voiceId] ?? "pt";
  const cleanText = text.slice(0, 900).replace(/[<>]/g, "");
  const chunks = splitTextForGTTS(cleanText);

  logger.info(
    { lang, chunks: chunks.length, textLen: cleanText.length },
    "Google TTS: generating audio",
  );

  const audioBuffers: Buffer[] = [];

  for (let i = 0; i < chunks.length; i++) {
    const chunk = chunks[i];
    if (!chunk || chunk.trim().length === 0) continue;

    try {
      const buf = await fetchGoogleTTSChunk(chunk, lang, i, chunks.length);
      if (buf && buf.length > 0) {
        audioBuffers.push(buf);
      }
    } catch (err) {
      logger.warn({ err, chunkIndex: i }, "Google TTS: chunk failed");
    }

    if (i < chunks.length - 1) {
      await new Promise((r) => setTimeout(r, 300));
    }
  }

  if (audioBuffers.length === 0) {
    logger.error("Google TTS: no audio chunks generated");
    return null;
  }

  const result = Buffer.concat(audioBuffers);
  logger.info({ kb: Math.round(result.length / 1024) }, "Google TTS: audio gerado com sucesso");
  return result;
}

function splitTextForGTTS(text: string): string[] {
  const maxLen = 190;
  const chunks: string[] = [];
  let remaining = text;

  while (remaining.length > 0) {
    if (remaining.length <= maxLen) {
      chunks.push(remaining.trim());
      break;
    }

    let splitIdx = -1;
    for (const sep of [". ", "! ", "? ", "; ", ", "]) {
      const idx = remaining.lastIndexOf(sep, maxLen);
      if (idx > 0) {
        splitIdx = idx + sep.length;
        break;
      }
    }

    if (splitIdx <= 0) {
      const spaceIdx = remaining.lastIndexOf(" ", maxLen);
      splitIdx = spaceIdx > 0 ? spaceIdx + 1 : maxLen;
    }

    chunks.push(remaining.slice(0, splitIdx).trim());
    remaining = remaining.slice(splitIdx);
  }

  return chunks.filter((c) => c.length > 0);
}

function fetchGoogleTTSChunk(
  text: string,
  lang: string,
  idx: number,
  total: number,
): Promise<Buffer | null> {
  return new Promise((resolve) => {
    const encodedText = encodeURIComponent(text);
    const url = `https://translate.google.com/translate_tts?ie=UTF-8&tl=${lang}&client=tw-ob&q=${encodedText}&idx=${idx}&total=${total}&textlen=${text.length}`;

    const req = https.get(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://translate.google.com/",
      },
      timeout: 15000,
    }, (res: http.IncomingMessage) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        https.get(res.headers.location, {
          headers: { "User-Agent": "Mozilla/5.0" },
          timeout: 15000,
        }, (redirectRes: http.IncomingMessage) => {
          collectResponse(redirectRes, resolve);
        }).on("error", () => resolve(null));
        return;
      }

      if (res.statusCode !== 200) {
        logger.warn({ status: res.statusCode, idx }, "Google TTS: non-200 response");
        resolve(null);
        return;
      }

      collectResponse(res, resolve);
    });

    req.on("error", (err) => {
      logger.warn({ err }, "Google TTS: request error");
      resolve(null);
    });

    req.on("timeout", () => {
      req.destroy();
      resolve(null);
    });
  });
}

function collectResponse(
  res: http.IncomingMessage,
  resolve: (val: Buffer | null) => void,
): void {
  const chunks: Buffer[] = [];
  res.on("data", (chunk: Buffer) => chunks.push(chunk));
  res.on("end", () => {
    if (chunks.length > 0) {
      resolve(Buffer.concat(chunks));
    } else {
      resolve(null);
    }
  });
  res.on("error", () => resolve(null));
}
