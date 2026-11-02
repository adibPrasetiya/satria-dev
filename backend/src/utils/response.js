export function success(res, { statusCode = 200, message = 'OK', data = null } = {}) {
  return res.status(statusCode).json({ success: true, message, data });
}

export function failure(res, { statusCode = 500, message = 'Terjadi kesalahan', errors, code } = {}) {
  const body = { success: false, message };
  if (code) body.code = code;
  if (errors) body.errors = errors;
  return res.status(statusCode).json(body);
}
