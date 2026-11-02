/**
 * Pesan galat yang bisa dibaca untuk CLI. Drizzle membungkus galat MySQL di `cause` ("Failed query: ..."),
 * dan koneksi yang ditolak ke `localhost` (IPv4 + IPv6) menjadi AggregateError dengan message kosong.
 */
export function errorMessage(error) {
  const root = error?.cause ?? error;
  const inner = root instanceof AggregateError ? root.errors[0] : root;
  if (inner?.code === 'ECONNREFUSED') {
    return `Tidak bisa terhubung ke MySQL (${inner.address ?? 'host'}:${inner.port ?? '?'}). Pastikan server MySQL sudah berjalan dan DATABASE_URL benar.`;
  }
  const detail = inner?.sqlMessage ?? inner?.message ?? inner?.code;
  return detail && detail !== error?.message ? `${error.message.split('\n')[0]}\n→ ${detail}` : error?.message || String(error);
}
