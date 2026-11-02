import { EventEmitter } from 'node:events';

// Bus event SSE per-scan (satu instance proses backend; cukup untuk tahap ini).
// Produsen: internal.service saat hasil/log masuk & scans.service saat status berubah.
// Konsumen: SSE handler di scans.controller.
const bus = new EventEmitter();
// Bisa banyak pelanggan SSE per scan.
bus.setMaxListeners(0);

const topik = (scanId) => `scan:${scanId}`;

/** Siarkan satu EventScan (bentuk sesuai frontend: {tipe:'metode'|'log'|'status', ...}). */
export function siarkan(scanId, event) {
  bus.emit(topik(scanId), event);
}

/** Berlangganan event sebuah scan; mengembalikan fungsi berhenti. */
export function berlangganan(scanId, handler) {
  const t = topik(scanId);
  bus.on(t, handler);
  return () => bus.off(t, handler);
}
