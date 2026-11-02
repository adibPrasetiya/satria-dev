import cors from 'cors';
import express from 'express';
import helmet from 'helmet';
import { env } from '../config/env.js';
import { authenticateWorker } from '../middleware/authenticateWorker.js';
import { errorHandler } from '../middleware/errorHandler.js';
import { notFound } from '../middleware/notFound.js';
import { requestLogger } from '../middleware/requestLogger.js';
import { internalRouter } from '../features/internal/internal.route.js';
import protectedRoutes from '../router/protected.routes.js';
import publicRoutes from '../router/public.routes.js';

export const app = express();

app.disable('x-powered-by');
// Di belakang reverse proxy (nginx), set 'trust proxy' agar req.ip & rate limit memakai IP klien asli.
app.set('trust proxy', 'loopback');
app.use(helmet());
app.use(cors({ origin: env.corsOrigin, exposedHeaders: ['X-Request-Id'] }));
// Kode request (X-Request-Id) & log ringkasan setiap request; dipasang sebelum route agar semua tercatat.
app.use(requestLogger);
// Hasil penemuan dari worker (inventaris endpoint, alert ZAP, analisis AI) bisa ratusan KB;
// batas besar hanya untuk /internal dan token worker diperiksa SEBELUM body diurai.
app.use('/api/v1/internal', authenticateWorker, express.json({ limit: '10mb' }));
app.use(express.json({ limit: '100kb' }));

app.get('/health', (req, res) => res.json({ status: 'ok' }));

// Endpoint worker pengujian (token layanan, bukan JWT pengguna); dipasang sebelum route pengguna.
app.use('/api/v1/internal', internalRouter);

app.use('/api/v1', publicRoutes);
app.use('/api/v1', protectedRoutes);

app.use(notFound);
app.use(errorHandler);
