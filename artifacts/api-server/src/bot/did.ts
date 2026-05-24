import { logger } from "../lib/logger.js";

const DID_API_KEY = process.env["DID_API_KEY"] ?? "";
const DID_BASE = "https://api.d-id.com";

export type VideoQuality = "standard" | "hd";

export const YUNA_AVATAR_URL =
  "https://image.pollinations.ai/prompt/" +
  encodeURIComponent(
    "photorealistic beautiful sexy woman, very large expressive eyes with long lashes, " +
    "extremely long flowing purple-blue hair with natural shine, large prominent breasts visible in elegant low-cut outfit, " +
    "seductive gentle smile with glossy lips, soft glowing dewy skin with natural pores, " +
    "RAW photo DSLR quality, hyperrealistic, " +
    "detailed face portrait, sensual warm pose, " +
    "face and upper body portrait, professional studio lighting with rim light, high quality render, " +
    "8k ultra detailed, perfect anatomy, alluring expression, shallow depth of field, subsurface scattering"
  ) +
  "?width=1024&height=1024&seed=9999&nologo=true&model=flux-realism";

export const YUNA_VOICE_ID = "pt-BR-ThalitaMultilingualNeural";

// ─── Mapeamento de idioma para lang SSML ─────────────────────────────────────
const VOICE_LANG_MAP: Record<string, string> = {
  "pt-BR-ThalitaMultilingualNeural": "pt-BR",
  "pt-BR-AntonioNeural": "pt-BR",
  "en-US-AvaMultilingualNeural": "en-US",
  "es-ES-ElviraNeural": "es-ES",
  "ko-KR-SunHiNeural": "ko-KR",
  "ja-JP-NanamiNeural": "ja-JP",
  "fr-FR-DeniseNeural": "fr-FR",
  "it-IT-ElsaNeural": "it-IT",
  "de-DE-KatjaNeural": "de-DE",
  "zh-CN-XiaoxiaoNeural": "zh-CN",
};

function buildAuthKey(): string {
  const key = DID_API_KEY.trim();
  if (!key) return "";

  // Case 1: entire key is already base64(email:password)
  try {
    const decoded = Buffer.from(key, "base64").toString("utf8");
    if (decoded.includes(":") && decoded.includes("@")) {
      return key;
    }
  } catch {}

  // Case 2: key is in format base64(email):password — decode email first
  if (key.includes(":")) {
    const colonIdx = key.indexOf(":");
    const emailPart = key.slice(0, colonIdx);
    const passwordPart = key.slice(colonIdx + 1);
    try {
      const decodedEmail = Buffer.from(emailPart, "base64").toString("utf8");
      if (decodedEmail.includes("@")) {
        return Buffer.from(`${decodedEmail}:${passwordPart}`).toString("base64");
      }
    } catch {}
    // Plain email:password
    return Buffer.from(key).toString("base64");
  }

  return key;
}

/**
 * Gera video D-ID com voz 100% humana natural, zero robótico.
 *
 * Configuracoes chave para voz natural e feminina:
 * - SSML com <mstts:express-as style="chat"> = conversacional, humana
 * - <break> curtos e orgânicos = pausas naturais entre frases
 * - Prosody rate 82-85% = fala levemente lenta, natural
 * - Prosody pitch +4% a +6% = tom feminino equilibrado
 * - volume="medium" = volume natural de conversa
 * - driver_url "bank://natural" = movimentos faciais naturais
 * - fluent: true = lip-sync suave e continuo
 * - stitch: true = mantem contexto visual da imagem original
 */
export async function generateDIDVideo(
  text: string,
  imageUrl: string,
  voiceId: string = YUNA_VOICE_ID,
  quality: VideoQuality = "standard",
  expression: string = "warm",
): Promise<Buffer | null> {
  if (!DID_API_KEY) {
    logger.warn("DID_API_KEY nao configurada — video D-ID desativado");
    return null;
  }

  const authKey = buildAuthKey();
  const isHD = quality === "hd";
  const ssmlText = buildSSML(text, isHD, voiceId);

  try {
    const body: Record<string, unknown> = {
      source_url: imageUrl,
      script: {
        type: "text",
        input: ssmlText,
        ssml: true,
        provider: {
          type: "microsoft",
          voice_id: voiceId,
          voice_config: {
            style: "chat",
            rate: isHD ? "0.82" : "0.85",
            pitch: isHD ? "+6%" : "+4%",
          },
        },
      },
      config: {
        fluent: true,
        stitch: true,
        pad_audio: isHD ? 1.5 : 0.8,
        result_format: "mp4",
        driver_url: "bank://natural",
        motion_factor: 1.0,
        align_driver: true,
        auto_match: true,
        ...(isHD ? { sharpen: true } : {}),
      },
    };

    logger.info({ voiceId, quality, textLen: text.length, imageUrl: imageUrl.slice(0, 80) }, "D-ID criando talk...");

    const createRes = await fetch(`${DID_BASE}/talks`, {
      method: "POST",
      headers: {
        Authorization: `Basic ${authKey}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!createRes.ok) {
      const errBody = await createRes.text();
      logger.error({ status: createRes.status, errBody, voiceId }, "D-ID criacao falhou");
      return null;
    }

    const createData = (await createRes.json()) as { id?: string };
    const talkId = createData.id;
    if (!talkId) {
      logger.error({ createData }, "D-ID: nenhum talk ID retornado");
      return null;
    }

    logger.info({ talkId, quality }, "D-ID talk criado, aguardando resultado...");
    return pollResult(`${DID_BASE}/talks/${talkId}`, authKey);
  } catch (err) {
    logger.error({ err }, "D-ID excecao geral");
    return null;
  }
}

/**
 * Constroi SSML otimizado para voz 100% humana natural.
 *
 * Tecnicas usadas:
 * 1. <mstts:express-as style="chat"> = tom conversacional humano
 * 2. <break> curtos apos pontuacao = pausas naturais organicas
 * 3. <prosody> com rate levemente lento e pitch feminino = voz natural
 * 4. volume="medium" = volume natural de conversa
 * 5. Pausas curtas em reticencias = ritmo humano
 */
function buildSSML(text: string, isHD: boolean, voiceId: string): string {
  const trimmed = text.slice(0, 900);
  const lang = VOICE_LANG_MAP[voiceId] ?? "pt-BR";

  // Pausas naturais humanas — curtas e orgânicas
  let processed = trimmed
    .replace(/\.\.\./g, '<break time="500ms"/>')
    .replace(/—/g, '<break time="350ms"/>')
    .replace(/\.\s+/g, '.<break time="300ms"/> ')
    .replace(/!\s+/g, '!<break time="280ms"/> ')
    .replace(/\?\s+/g, '?<break time="300ms"/> ')
    .replace(/,\s+/g, ',<break time="150ms"/> ')
    .replace(/;\s+/g, ';<break time="220ms"/> ');

  // Escape caracteres XML
  processed = processed
    .replace(/&(?!amp;|lt;|gt;|quot;|apos;)/g, "&amp;")
    .replace(/<(?!break|\/break|prosody|\/prosody|mstts:|\/mstts:)/g, "&lt;");

  // Voz natural feminina: pitch moderado, rate levemente lento
  const rate = isHD ? "82%" : "85%";
  const pitch = isHD ? "+6%" : "+4%";

  return [
    `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="${lang}">`,
    `<mstts:express-as style="chat" styledegree="1.2">`,
    `<prosody rate="${rate}" pitch="${pitch}" volume="medium">`,
    processed,
    `</prosody>`,
    `</mstts:express-as>`,
    `</speak>`,
  ].join("");
}

async function pollResult(url: string, authKey: string): Promise<Buffer | null> {
  for (let i = 0; i < 90; i++) {
    await sleep(2000);
    try {
      const statusRes = await fetch(url, {
        headers: { Authorization: `Basic ${authKey}`, Accept: "application/json" },
      });
      if (!statusRes.ok) {
        logger.warn({ status: statusRes.status, attempt: i }, "D-ID poll status nao-OK");
        continue;
      }
      const data = (await statusRes.json()) as {
        status?: string;
        result_url?: string;
        error?: unknown;
      };

      if (i % 5 === 0) {
        logger.info({ status: data.status, attempt: i }, "D-ID poll...");
      }

      if (data.status === "done" && data.result_url) {
        const videoRes = await fetch(data.result_url);
        if (!videoRes.ok) {
          logger.error({ status: videoRes.status }, "D-ID download do video falhou");
          return null;
        }
        const buf = await videoRes.arrayBuffer();
        logger.info({ kb: Math.round(buf.byteLength / 1024) }, "D-ID video pronto!");
        return Buffer.from(buf);
      }

      if (data.status === "error" || data.status === "rejected") {
        logger.error({ data }, "D-ID erro de processamento");
        return null;
      }
    } catch (err) {
      logger.warn({ err, attempt: i }, "D-ID poll excecao");
    }
  }
  logger.error("D-ID timeout apos 180s de polling");
  return null;
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
