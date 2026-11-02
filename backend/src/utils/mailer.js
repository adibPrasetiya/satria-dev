import { env } from '../config/env.js';
import { AppError } from './AppError.js';
import { logger } from './logger.js';

const RESEND_URL = 'https://api.resend.com/emails';

/**
 * Kirim email lewat Resend (REST API, https://resend.com/docs/api-reference/emails/send-email).
 * Tanpa RESEND_API_KEY: di development isi email dicatat di log agar alur (mis. tautan reset kata sandi)
 * tetap bisa diuji; di production dicatat sebagai error tanpa isinya.
 */
export async function sendMail({ to, subject, text, html }) {
  if (!env.mail.resendApiKey) {
    if (env.isProduction) {
      logger.error(`RESEND_API_KEY belum diatur, email "${subject}" tidak terkirim`);
      return;
    }
    logger.info(`[email belum dikirim: RESEND_API_KEY kosong] Kepada: ${to} | ${subject}\n${text}`);
    return;
  }

  const response = await fetch(RESEND_URL, {
    method: 'POST',
    headers: { Authorization: `Bearer ${env.mail.resendApiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ from: env.mail.from, to: [to], subject, text, html }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new AppError(502, `Resend menolak pengiriman email (${response.status}): ${detail.slice(0, 200)}`);
  }
  const { id } = await response.json().catch(() => ({}));
  logger.info(`Email terkirim: ${subject}`, { kepada: to, resendId: id });
}
