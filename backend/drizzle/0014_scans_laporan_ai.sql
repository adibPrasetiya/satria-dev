-- Laporan hasil generate AI (ringkasan eksekutif + rekomendasi temuan). Hanya scan SELESAI terakhir
-- per aplikasi yang menyimpannya; scan riwayat lama di-generate ulang tiap diminta tanpa disimpan.
ALTER TABLE `scans` ADD `ai_analysis` json;
