import bcrypt from 'bcryptjs';

const SALT_ROUNDS = 12;

// Dipakai saat email tidak ditemukan agar waktu respons login tetap sama (cegah user enumeration).
const DUMMY_HASH = bcrypt.hashSync('dummy-password-for-timing', SALT_ROUNDS);

export function hashPassword(plain) {
  return bcrypt.hash(plain, SALT_ROUNDS);
}

export function verifyPassword(plain, hash) {
  return bcrypt.compare(plain, hash ?? DUMMY_HASH);
}
