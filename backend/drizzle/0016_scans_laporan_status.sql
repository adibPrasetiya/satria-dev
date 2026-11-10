-- Status penyusunan laporan AI (auto-generate saat scan selesai): dasar tombol Lihat/Generate di UI.
ALTER TABLE `scans` ADD `laporan_status` enum('belum','proses','siap','gagal') NOT NULL DEFAULT 'belum';
