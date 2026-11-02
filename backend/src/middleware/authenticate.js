import { authenticationService } from '../features/authentication/authentication.service.js';
import { AppError } from '../utils/AppError.js';
import { getContext } from '../utils/requestContext.js';

export async function authenticate(req, res, next) {
  const [scheme, token] = req.get('authorization')?.split(' ') ?? [];
  if (scheme !== 'Bearer' || !token) {
    return next(AppError.unauthorized('Access token wajib dikirim melalui header Authorization: Bearer'));
  }

  req.user = await authenticationService.authenticate(token);
  // Log selama request ini (termasuk log ringkasan request) ikut mencatat siapa user-nya.
  const context = getContext();
  if (context) {
    context.userId = req.user.id;
    context.username = req.user.email;
  }
  return next();
}
