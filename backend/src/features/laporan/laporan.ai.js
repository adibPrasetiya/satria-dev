import { env } from '../../config/env.js';

// Provider AI penyusun laporan. Pemilihan sama dengan worker (worker/satya_worker/ai):
//   AI_PROVIDER=gemini     → Google Gemini (SDK @google/genai)
//   AI_PROVIDER=anthropic  → Anthropic Claude (SDK @anthropic-ai/sdk)
//   AI_PROVIDER=none       → nonaktif
//   kosong                 → otomatis: Gemini bila kuncinya ada, lalu Anthropic.
// SDK diimpor lazy agar backend tetap jalan tanpa AI. Tiap provider: tanyaJson(prompt) → objek JSON
// atau melempar Error bermakna.

const MODEL_GEMINI = 'gemini-3.8-flash';
const MODEL_ANTHROPIC = 'claude-opus-5-5';

/** Ambil objek JSON dari teks jawaban model (toleran terhadap pagar ```json). */
export function parseJson(teks) {
  if (!teks) return null;
  const bersih = teks.trim().replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/, '');
  try {
    return JSON.parse(bersih);
  } catch {
    const a = bersih.indexOf('{');
    const b = bersih.lastIndexOf('}');
    if (a < 0 || b <= a) return null;
    try {
      return JSON.parse(bersih.slice(a, b + 1));
    } catch {
      return null;
    }
  }
}

function geminiProvider(apiKey, model) {
  return {
    nama: 'gemini',
    model,
    async tanyaJson(prompt) {
      const { GoogleGenAI } = await import('@google/genai');
      const klien = new GoogleGenAI({ apiKey });
      const resp = await klien.models.generateContent({
        model,
        contents: prompt,
        config: { responseMimeType: 'application/json' },
      });
      const hasil = parseJson(resp.text);
      if (!hasil) throw new Error('Respons Gemini bukan JSON valid');
      return hasil;
    },
  };
}

function anthropicProvider(apiKey, model) {
  return {
    nama: 'anthropic',
    model,
    async tanyaJson(prompt) {
      const { default: Anthropic } = await import('@anthropic-ai/sdk');
      const klien = new Anthropic({ apiKey });
      // Fallback sisi server bila model menolak karena kebijakan (refusal) — dirutekan otomatis.
      const resp = await klien.beta.messages.create({
        model,
        max_tokens: 16000,
        betas: ['server-side-fallback-2026-07-01'],
        fallbacks: 'default',
        messages: [{ role: 'user', content: prompt }],
      });
      if (resp.stop_reason === 'refusal') throw new Error('Model menolak menyusun laporan (refusal)');
      const teks = resp.content
        .filter((b) => b.type === 'text')
        .map((b) => b.text)
        .join('');
      const hasil = parseJson(teks);
      if (!hasil) throw new Error('Respons Anthropic bukan JSON valid');
      return hasil;
    },
  };
}

/** Provider sesuai konfigurasi; null bila AI dinonaktifkan atau tidak ada kunci. */
export function muatProvider(cfg = env.ai) {
  const pilih = (cfg.provider || '').toLowerCase();
  if (pilih === 'none') return null;
  const gemini = cfg.geminiKey ? geminiProvider(cfg.geminiKey, cfg.model || MODEL_GEMINI) : null;
  const anthropic = cfg.anthropicKey ? anthropicProvider(cfg.anthropicKey, cfg.model || MODEL_ANTHROPIC) : null;
  if (pilih === 'gemini') return gemini;
  if (pilih === 'anthropic') return anthropic;
  return gemini ?? anthropic;
}
