import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { emailResetSandi, escapeHtml } = await import('../src/utils/emailTemplate.js');

describe('template email atur ulang kata sandi', () => {
  const tautan = 'https://dev.satria.pro/reset-sandi?token=abc%2Bdef&x=1';
  const email = emailResetSandi({ nama: 'Budi <script>alert(1)</script>', tautan, menit: 30, appUrl: 'https://dev.satria.pro' });

  it('memakai nama aplikasi SATRIA pada subjek, teks, dan HTML', () => {
    assert.equal(email.subject, 'Atur ulang kata sandi SATRIA');
    assert.match(email.text, /akun SATRIA Anda/);
    assert.match(email.html, /SATRIA/);
    assert.doesNotMatch(email.html + email.text, /SATYA/);
  });

  it('nama pengguna di-escape (tidak bisa menyisipkan HTML), versi teks tetap apa adanya', () => {
    assert.doesNotMatch(email.html, /<script>/);
    assert.match(email.html, /Budi &lt;script&gt;alert\(1\)&lt;\/script&gt;/);
    assert.match(email.text, /Halo Budi <script>/);
  });

  it('tautan ada di tombol & tautan cadangan (atribut di-escape), plus masa berlaku', () => {
    const href = `href="${escapeHtml(tautan)}"`;
    assert.equal(email.html.split(href).length - 1, 2);
    assert.match(email.text, new RegExp(tautan.replace(/[?.+]/g, '\\$&')));
    assert.match(email.html, /30 menit/);
    assert.match(email.html, /src="https:\/\/dev\.satria\.pro\/satria-lambang\.png"/);
  });
});
