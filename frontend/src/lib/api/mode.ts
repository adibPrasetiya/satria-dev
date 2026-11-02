/** VITE_USE_MOCK=false untuk memakai backend Express sungguhan (fitur yang belum ada tetap memakai mock). */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';
