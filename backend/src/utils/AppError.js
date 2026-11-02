export class AppError extends Error {
  /** `code`: kode mesin opsional untuk client (mis. 'LICENSE_REQUIRED'). */
  constructor(statusCode, message, details, code) {
    super(message);
    this.name = 'AppError';
    this.statusCode = statusCode;
    this.details = details;
    this.code = code;
  }

  static badRequest(message, details) {
    return new AppError(400, message, details);
  }

  static unauthorized(message = 'Tidak terautentikasi') {
    return new AppError(401, message);
  }

  static forbidden(message = 'Akses ditolak') {
    return new AppError(403, message);
  }

  static notFound(message = 'Data tidak ditemukan') {
    return new AppError(404, message);
  }

  static conflict(message, details) {
    return new AppError(409, message, details);
  }
}
