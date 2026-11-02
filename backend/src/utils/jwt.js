import jwt from 'jsonwebtoken';
import { env } from '../config/env.js';

const ALGORITHM = 'HS256';

export function signAccessToken(user) {
  return jwt.sign({ role: user.role }, env.jwt.accessSecret, {
    algorithm: ALGORITHM,
    expiresIn: env.jwt.accessExpiresIn,
    subject: String(user.id),
  });
}

export function verifyAccessToken(token) {
  return jwt.verify(token, env.jwt.accessSecret, { algorithms: [ALGORITHM] });
}
