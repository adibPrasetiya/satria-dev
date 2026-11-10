import { Router } from 'express';
import {
  availabilityLimiter,
  changePasswordLimiter,
  emailVerificationLimiter,
  loginLimiter,
  passwordResetLimiter,
  registerLimiter,
} from '../../middleware/rateLimiter.js';
import { validate } from '../../middleware/validate.js';
import { authenticationController } from './authentication.controller.js';
import {
  availabilitySchema,
  changePasswordSchema,
  forgotPasswordSchema,
  loginSchema,
  logoutSchema,
  refreshSchema,
  registerSchema,
  resendVerificationSchema,
  resetPasswordSchema,
  verifyEmailSchema,
} from './authentication.validation.js';

export const authPublicRouter = Router();

authPublicRouter.post('/register', registerLimiter, validate(registerSchema), authenticationController.register);
authPublicRouter.post('/check-availability', availabilityLimiter, validate(availabilitySchema), authenticationController.checkAvailability);
authPublicRouter.post('/login', validate(loginSchema), loginLimiter, authenticationController.login);
authPublicRouter.post('/refresh', validate(refreshSchema), authenticationController.refresh);
authPublicRouter.post('/forgot-password', passwordResetLimiter, validate(forgotPasswordSchema), authenticationController.forgotPassword);
authPublicRouter.post('/reset-password', passwordResetLimiter, validate(resetPasswordSchema), authenticationController.resetPassword);
authPublicRouter.post('/verify-email', emailVerificationLimiter, validate(verifyEmailSchema), authenticationController.verifyEmail);
authPublicRouter.post(
  '/resend-verification',
  emailVerificationLimiter,
  validate(resendVerificationSchema),
  authenticationController.resendVerification,
);

export const authProtectedRouter = Router();

authProtectedRouter.post('/logout', validate(logoutSchema), authenticationController.logout);
authProtectedRouter.post('/change-password', changePasswordLimiter, validate(changePasswordSchema), authenticationController.changePassword);
authProtectedRouter.get('/me', authenticationController.me);
