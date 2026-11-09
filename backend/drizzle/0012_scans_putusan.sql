-- Putusan kelaikan, skor kepatuhan, dan jumlah temuan per severity disimpan per scan saat selesai,
-- agar daftar aplikasi bisa disaring (putusan) dan diurutkan (skor/temuan) di DB dengan paginasi
-- server. Scan lama diisi bertahap saat daftar aplikasi dibuka (verdict.service.lengkapiYangKosong).
ALTER TABLE `scans` ADD `verdict` enum('laik','laik_bersyarat','tidak_laik');--> statement-breakpoint
ALTER TABLE `scans` ADD `score` smallint unsigned;--> statement-breakpoint
ALTER TABLE `scans` ADD `findings_critical` smallint unsigned;--> statement-breakpoint
ALTER TABLE `scans` ADD `findings_high` smallint unsigned;--> statement-breakpoint
ALTER TABLE `scans` ADD `findings_medium` smallint unsigned;--> statement-breakpoint
ALTER TABLE `scans` ADD `findings_low` smallint unsigned;--> statement-breakpoint
CREATE INDEX `scans_application_status_idx` ON `scans` (`application_id`,`status`);
