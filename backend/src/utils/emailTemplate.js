import { APP_NAME } from '../config/app.js';

// Template email transaksional SATRIA.
//
// HTML email ≠ HTML web: tata letak memakai <table> & style inline (Gmail/Outlook membuang <style>/CSS
// eksternal), lebar maks 600px, tanpa JavaScript/web font. Setiap email juga punya versi teks polos.
// SEMUA data dinamis (nama, tautan) wajib lewat escapeHtml() — nama pengguna adalah masukan bebas.

const WARNA = {
  latar: '#eef0ea',
  kop: '#0b0f0c',
  kartu: '#ffffff',
  teks: '#1d2419',
  redup: '#5f6b58',
  garis: '#e1e5da',
  aksen: '#4f6a2e', // hijau zaitun SATRIA (kontras teks putih ≥ 4.5:1)
  aksenTipis: '#f2f5ec',
};
const FONT = "Arial, 'Helvetica Neue', Helvetica, sans-serif";

export function escapeHtml(nilai) {
  return String(nilai ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Tombol "bulletproof" (tabel + <a> ber-padding) — tetap tampil di Outlook tanpa gambar. */
function tombol(teks, href) {
  return `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 4px;">
  <tr><td align="center" bgcolor="${WARNA.aksen}" style="border-radius:6px;">
    <a href="${escapeHtml(href)}" target="_blank" rel="noopener"
       style="display:inline-block;padding:13px 28px;font-family:${FONT};font-size:15px;font-weight:bold;line-height:1;color:#ffffff;text-decoration:none;border-radius:6px;">${escapeHtml(teks)}</a>
  </td></tr>
</table>`;
}

/**
 * Bingkai email: kop gelap (lambang + nama aplikasi), kartu isi, dan kaki.
 * @param {{ judul: string, pratinjau: string, isiHtml: string, appUrl: string }} p
 */
export function bingkaiEmail({ judul, pratinjau, isiHtml, appUrl }) {
  const lambang = `${appUrl}/satria-lambang.png`;
  return `<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>${escapeHtml(judul)}</title>
</head>
<body style="margin:0;padding:0;background:${WARNA.latar};">
<!-- Teks pratinjau di daftar kotak masuk (tidak tampil di isi email). -->
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">${escapeHtml(pratinjau)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:${WARNA.latar};">
  <tr><td align="center" style="padding:32px 16px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">
      <!-- Kop -->
      <tr><td style="background:${WARNA.kop};border-radius:10px 10px 0 0;padding:22px 32px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
          <td style="padding-right:14px;vertical-align:middle;">
            <img src="${escapeHtml(lambang)}" width="27" height="40" alt="" style="display:block;border:0;">
          </td>
          <td style="vertical-align:middle;font-family:${FONT};">
            <div style="font-size:20px;font-weight:bold;letter-spacing:4px;color:#ffffff;">${APP_NAME}</div>
            <div style="font-size:11px;letter-spacing:1px;color:#9fae8f;text-transform:uppercase;">Asesmen Kelaikan Keamanan Aplikasi</div>
          </td>
        </tr></table>
      </td></tr>
      <!-- Isi -->
      <tr><td style="background:${WARNA.kartu};padding:36px 32px 28px;border-radius:0 0 10px 10px;font-family:${FONT};font-size:15px;line-height:1.6;color:${WARNA.teks};">
        ${isiHtml}
      </td></tr>
      <!-- Kaki -->
      <tr><td style="padding:20px 32px 0;font-family:${FONT};font-size:12px;line-height:1.6;color:${WARNA.redup};text-align:center;">
        Email ini dikirim otomatis oleh ${APP_NAME}; mohon tidak membalas email ini.<br>
        Hasil asesmen bersifat terbatas, untuk kalangan sendiri.
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>`;
}

/**
 * Email atur ulang kata sandi.
 * @param {{ nama: string, tautan: string, menit: number, appUrl: string }} p
 * @returns {{ subject: string, text: string, html: string }}
 */
export function emailResetSandi({ nama, tautan, menit, appUrl }) {
  const subject = `Atur ulang kata sandi ${APP_NAME}`;
  const text = [
    `Halo ${nama},`,
    '',
    `Kami menerima permintaan untuk mengatur ulang kata sandi akun ${APP_NAME} Anda.`,
    `Buka tautan berikut dalam ${menit} menit (hanya bisa dipakai sekali):`,
    tautan,
    '',
    'Bila Anda tidak meminta atur ulang kata sandi, abaikan email ini — kata sandi Anda tidak berubah.',
    'Jangan teruskan email ini kepada siapa pun.',
    '',
    `— ${APP_NAME} · Asesmen Kelaikan Keamanan Aplikasi`,
  ].join('\n');

  const isiHtml = `
        <h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;color:${WARNA.teks};">Atur ulang kata sandi</h1>
        <p style="margin:0 0 14px;">Halo <strong>${escapeHtml(nama)}</strong>,</p>
        <p style="margin:0 0 22px;">Kami menerima permintaan untuk mengatur ulang kata sandi akun ${APP_NAME} Anda. Klik tombol di bawah untuk membuat kata sandi baru.</p>
        ${tombol('Atur ulang kata sandi', tautan)}
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:22px 0;">
          <tr><td style="background:${WARNA.aksenTipis};border-left:3px solid ${WARNA.aksen};padding:12px 16px;font-size:13px;line-height:1.55;color:${WARNA.teks};">
            Tautan berlaku <strong>${escapeHtml(menit)} menit</strong> dan hanya dapat dipakai <strong>satu kali</strong>. Setelah kata sandi diganti, semua sesi masuk yang lain akan diakhiri.
          </td></tr>
        </table>
        <p style="margin:0 0 6px;font-size:13px;color:${WARNA.redup};">Tombol tidak berfungsi? Salin tautan berikut ke peramban Anda:</p>
        <p style="margin:0 0 24px;font-size:13px;line-height:1.5;word-break:break-all;"><a href="${escapeHtml(tautan)}" target="_blank" rel="noopener" style="color:${WARNA.aksen};">${escapeHtml(tautan)}</a></p>
        <hr style="border:0;border-top:1px solid ${WARNA.garis};margin:0 0 18px;">
        <p style="margin:0;font-size:13px;line-height:1.55;color:${WARNA.redup};">Bila Anda tidak meminta atur ulang kata sandi, abaikan email ini — kata sandi Anda tidak berubah. Jangan teruskan email ini kepada siapa pun; petugas ${APP_NAME} tidak akan pernah meminta kata sandi Anda.</p>`;

  return {
    subject,
    text,
    html: bingkaiEmail({ judul: subject, pratinjau: `Tautan atur ulang kata sandi berlaku ${menit} menit.`, isiHtml, appUrl }),
  };
}

/**
 * Email verifikasi alamat email setelah pendaftaran.
 * @param {{ nama: string, tautan: string, jam: number, appUrl: string }} p
 * @returns {{ subject: string, text: string, html: string }}
 */
export function emailVerifikasi({ nama, tautan, jam, appUrl }) {
  const subject = `Verifikasi email akun ${APP_NAME}`;
  const text = [
    `Halo ${nama},`,
    '',
    `Terima kasih telah mendaftar di ${APP_NAME}. Untuk mengaktifkan akun Anda, buka tautan berikut dalam ${jam} jam:`,
    tautan,
    '',
    'Bila Anda tidak merasa mendaftar, abaikan email ini — akun tidak akan aktif tanpa verifikasi.',
    '',
    `— ${APP_NAME} · Asesmen Kelaikan Keamanan Aplikasi`,
  ].join('\n');

  const isiHtml = `
        <h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;color:${WARNA.teks};">Verifikasi email Anda</h1>
        <p style="margin:0 0 14px;">Halo <strong>${escapeHtml(nama)}</strong>,</p>
        <p style="margin:0 0 22px;">Terima kasih telah mendaftar di ${APP_NAME}. Klik tombol di bawah untuk memverifikasi alamat email dan mengaktifkan akun Anda.</p>
        ${tombol('Verifikasi email', tautan)}
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:22px 0;">
          <tr><td style="background:${WARNA.aksenTipis};border-left:3px solid ${WARNA.aksen};padding:12px 16px;font-size:13px;line-height:1.55;color:${WARNA.teks};">
            Tautan berlaku <strong>${escapeHtml(jam)} jam</strong> dan hanya dapat dipakai <strong>satu kali</strong>. Bila kedaluwarsa, minta tautan baru dari halaman masuk.
          </td></tr>
        </table>
        <p style="margin:0 0 6px;font-size:13px;color:${WARNA.redup};">Tombol tidak berfungsi? Salin tautan berikut ke peramban Anda:</p>
        <p style="margin:0 0 24px;font-size:13px;line-height:1.5;word-break:break-all;"><a href="${escapeHtml(tautan)}" target="_blank" rel="noopener" style="color:${WARNA.aksen};">${escapeHtml(tautan)}</a></p>
        <hr style="border:0;border-top:1px solid ${WARNA.garis};margin:0 0 18px;">
        <p style="margin:0;font-size:13px;line-height:1.55;color:${WARNA.redup};">Bila Anda tidak merasa mendaftar di ${APP_NAME}, abaikan email ini — akun tidak akan aktif tanpa verifikasi.</p>`;

  return {
    subject,
    text,
    html: bingkaiEmail({ judul: subject, pratinjau: `Tautan verifikasi email berlaku ${jam} jam.`, isiHtml, appUrl }),
  };
}
