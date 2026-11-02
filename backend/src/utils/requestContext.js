import { AsyncLocalStorage } from 'node:async_hooks';

// Konteks per request (kode request & user yang login), dibaca logger agar setiap baris log
// yang ditulis selama request tersebut otomatis membawa kodenya, tanpa perlu dioper manual.
const storage = new AsyncLocalStorage();

/** Jalankan `callback` di dalam konteks baru, mis. `{ requestId }`. */
export const runWithContext = (context, callback) => storage.run(context, callback);

/** Konteks request yang sedang berjalan, atau undefined di luar request (scheduler, startup). */
export const getContext = () => storage.getStore();
