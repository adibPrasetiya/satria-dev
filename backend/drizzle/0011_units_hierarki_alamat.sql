-- Satuan kerja menjadi hierarkis (induk → sub-satuan, mis. Mabes TNI → Kodam → Korem → Kodim) dan
-- punya jenis, alamat, provinsi, serta koordinat untuk peta sebaran sistem informasi di dasbor.
-- Satuan lama menjadi akar berjenis SATUAN tanpa alamat; admin melengkapinya lewat halaman Satuan Kerja.
ALTER TABLE `units` ADD `parent_id` bigint unsigned AFTER `id`;--> statement-breakpoint
ALTER TABLE `units` ADD `type` enum('MABES','KOTAMA','BALAKPUS','KOREM','KODIM','KORAMIL','SATUAN') NOT NULL DEFAULT 'SATUAN' AFTER `name`;--> statement-breakpoint
ALTER TABLE `units` ADD `address` varchar(255) AFTER `type`;--> statement-breakpoint
ALTER TABLE `units` ADD `city` varchar(100) AFTER `address`;--> statement-breakpoint
ALTER TABLE `units` ADD `province_code` char(2) AFTER `city`;--> statement-breakpoint
ALTER TABLE `units` ADD `latitude` decimal(9,6) AFTER `province_code`;--> statement-breakpoint
ALTER TABLE `units` ADD `longitude` decimal(9,6) AFTER `latitude`;--> statement-breakpoint
ALTER TABLE `units` ADD `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP;--> statement-breakpoint
ALTER TABLE `units` ADD CONSTRAINT `units_parent_id_units_id_fk` FOREIGN KEY (`parent_id`) REFERENCES `units`(`id`) ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `units_parent_id_idx` ON `units` (`parent_id`);--> statement-breakpoint
CREATE INDEX `units_province_code_idx` ON `units` (`province_code`);
