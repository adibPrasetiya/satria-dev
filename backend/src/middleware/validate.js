import { AppError } from '../utils/AppError.js';

export function validate(schema, source = 'body') {
  return (req, res, next) => {
    const { value, error } = schema.validate(req[source] ?? {}, {
      abortEarly: false,
      stripUnknown: true,
    });

    if (error) {
      const details = error.details.map((detail) => ({
        field: detail.path.join('.'),
        message: detail.message.replace(/"/g, ''),
      }));
      return next(AppError.badRequest('Data yang dikirim tidak valid', details));
    }

    // Express 5: req.query hanya getter, jadi ditimpa lewat defineProperty.
    Object.defineProperty(req, source, { value, writable: true, configurable: true, enumerable: true });
    return next();
  };
}
