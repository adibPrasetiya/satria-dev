import { EventEmitter } from 'node:events';

/**
 * Peristiwa inventaris komponen: `berubah` (applicationId) setiap komponen aplikasi dibentuk ulang atau
 * dikoreksi. Modul kerentanan berlangganan saat server start untuk mencocokkan ulang CVE aplikasi tersebut.
 */
export const peristiwaKomponen = new EventEmitter();
