import { EventEmitter } from 'node:events';

// Sinyal "status worker/antrean mungkin berubah" (satu proses backend; lihat ecosystem.config.cjs instances: 1).
// Produsen: heartbeat/klaim/selesai worker & scan dimulai/dibatalkan. Konsumen: hub SSE di workers.stream.js.
// Sinyal beruntun digabung (debounce) agar satu ledakan perubahan cukup dihitung sekali.
const bus = new EventEmitter();
bus.setMaxListeners(0);

const JEDA_MS = 300;
let tunda = null;

export function beriTahu() {
  if (tunda) return;
  tunda = setTimeout(() => {
    tunda = null;
    bus.emit('berubah');
  }, JEDA_MS);
  tunda.unref?.();
}

/** @returns fungsi berhenti berlangganan */
export function berlangganan(handler) {
  bus.on('berubah', handler);
  return () => bus.off('berubah', handler);
}
