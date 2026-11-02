// Pola LIKE "mengandung": wildcard dari input di-escape agar "50%" dicari apa adanya.
export const likePattern = (value) => `%${value.replace(/[\%_]/g, (char) => `\${char}`)}%`;
