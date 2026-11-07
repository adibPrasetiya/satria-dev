import { createInterface } from 'node:readline/promises';
import { authenticationRepository } from '../features/authentication/authentication.repository.js';
import Joi from 'joi';
import { email as emailSchema, name as nameSchema, newPassword, nrp as nrpSchema } from '../features/authentication/authentication.validation.js';
import { unitsRepository } from '../features/units/units.repository.js';
import { hashPassword } from '../utils/password.js';

/** Tanya ulang sampai jawaban lolos validasi Joi. */
async function askValid(ask, question, schema) {
  for (;;) {
    const { value, error } = schema.validate(await ask(question));
    if (!error) return value;
    console.log(`  ✗ ${error.details[0].message.replace(/"/g, '')}`);
  }
}

/**
 * Membuat akun administrator pertama secara interaktif (langsung terverifikasi):
 * `npm run admin:create`. Admin inilah yang kemudian memverifikasi pendaftaran pengguna lain.
 */
export async function createAdmin({ repository = authenticationRepository, units = unitsRepository } = {}) {
  if (!(await units.searchActive({ limit: 1 })).length) {
    console.error('Daftar satuan masih kosong. Jalankan `npm run db:migrate` terlebih dahulu.');
    process.exitCode = 1;
    return;
  }

  const rl = createInterface({ input: process.stdin, output: process.stdout, terminal: true });

  // Sembunyikan ketikan kata sandi: setelah pertanyaan tampil, karakter yang diketik tidak di-echo.
  let muted = false;
  const write = rl._writeToOutput?.bind(rl);
  rl._writeToOutput = (text) => {
    if (!muted || text.includes('\n')) write?.(muted ? '\n' : text);
  };
  const ask = (question) => rl.question(question);
  const askHidden = async (question) => {
    process.stdout.write(question);
    muted = true;
    try {
      return await rl.question('');
    } finally {
      muted = false;
    }
  };

  try {
    console.log('== Buat akun administrator SATRIA ==');
    const name = await askValid(ask, 'Nama & pangkat : ', nameSchema);
    const nrp = await askValid(ask, 'NRP / NIP      : ', nrpSchema);
    // Daftar satuan bisa ribuan: cari dengan kata kunci, lalu pilih nomor dari hasilnya.
    let unitId;
    while (!unitId) {
      const found = await units.searchActive({ search: (await ask('Cari satuan    : ')).trim(), limit: 20 });
      if (!found.length) {
        console.log('  ✗ Tidak ada satuan yang cocok, coba kata lain.');
        continue;
      }
      found.forEach((u, i) => console.log(`  ${String(i + 1).padStart(3)}. ${u.name}`));
      const pick = Joi.number().integer().min(1).max(found.length).allow('').messages({ '*': `Pilih nomor 1–${found.length}` });
      const nomor = await askValid(ask, 'Nomor (kosong = cari lagi): ', pick);
      if (nomor) unitId = found[nomor - 1].id;
    }
    const email = await askValid(ask, 'Email dinas    : ', emailSchema);

    if (await repository.emailOrNrpExists(email, nrp)) {
      console.error('Email atau NRP/NIP sudah terdaftar. Batal.');
      process.exitCode = 1;
      return;
    }

    let password;
    for (;;) {
      password = await askValid(askHidden, 'Kata sandi     : ', newPassword);
      if ((await askHidden('Ulangi         : ')) === password) break;
      console.log('  ✗ Konfirmasi kata sandi tidak sama, ulangi.');
    }

    await repository.createUser({
      name,
      nrp,
      unitId,
      email,
      passwordHash: await hashPassword(password),
      role: 'admin',
      isVerified: true,
      verifiedAt: new Date(),
    });
    console.log(`Administrator "${email}" berhasil dibuat dan sudah terverifikasi.`);
  } finally {
    rl.close();
  }
}

