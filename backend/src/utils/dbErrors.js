// Drizzle membungkus galat MySQL di `cause`.
const mysqlCode = (error) => (error?.cause ?? error)?.code;

/** Pelanggaran kolom UNIQUE (mis. nama satuan / URL aplikasi yang sudah ada). */
export const isDuplicateEntry = (error) => mysqlCode(error) === 'ER_DUP_ENTRY';
