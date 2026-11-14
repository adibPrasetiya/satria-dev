import { Router } from 'express';
import { authenticateWorker } from '../../middleware/authenticateWorker.js';
import { validate } from '../../middleware/validate.js';
import { internalController } from './internal.controller.js';
import {
  berhentiSchema,
  claimSchema,
  discoverySchema,
  evidenceUploadSchema,
  heartbeatSchema,
  komponenSchema,
  logSchema,
  resultSchema,
  taskIdSchema,
} from './internal.validation.js';

// Dipakai HANYA oleh worker pengujian (bukan JWT pengguna). Dilindungi X-Worker-Token.
export const internalRouter = Router();
internalRouter.use(authenticateWorker);

internalRouter.post('/tasks/claim', validate(claimSchema), internalController.claim);
internalRouter.post('/workers/heartbeat', validate(heartbeatSchema), internalController.heartbeat);
internalRouter.post('/workers/berhenti', validate(berhentiSchema), internalController.berhenti);
internalRouter.post('/tasks/:id/result', validate(taskIdSchema, 'params'), validate(resultSchema), internalController.result);
internalRouter.post('/tasks/:id/log', validate(taskIdSchema, 'params'), validate(logSchema), internalController.log);
internalRouter.post(
  '/scans/:id/discovery',
  validate(taskIdSchema, 'params'),
  validate(discoverySchema),
  internalController.discovery,
);
internalRouter.post(
  '/scans/:id/komponen',
  validate(taskIdSchema, 'params'),
  validate(komponenSchema),
  internalController.komponen,
);
internalRouter.post(
  '/scans/:id/evidence',
  validate(taskIdSchema, 'params'),
  validate(evidenceUploadSchema),
  internalController.evidence,
);
