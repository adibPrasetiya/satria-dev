import { createHash, randomBytes } from 'node:crypto';

export function generateToken(bytes = 32) {
  return randomBytes(bytes).toString('base64url');
}

export function hashToken(token) {
  return createHash('sha256').update(token).digest('hex');
}
