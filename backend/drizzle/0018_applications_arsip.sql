-- Arsip aplikasi (pengganti hapus): aplikasi terarsip disembunyikan dari daftar & tidak bisa diuji,
-- tetapi riwayat scan, temuan, dan laporannya tetap tersimpan untuk audit.
ALTER TABLE `applications` ADD `archived_at` datetime;
