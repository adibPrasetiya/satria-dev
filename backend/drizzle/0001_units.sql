-- Satuan/instansi menjadi daftar baku (tabel units); users.unit (teks bebas) diganti users.unit_id.
-- Data contoh — ganti/tambah daftar resmi lewat migrasi INSERT berikutnya.
CREATE TABLE `units` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`name` varchar(120) NOT NULL,
	`is_active` boolean NOT NULL DEFAULT true,
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `units_id` PRIMARY KEY(`id`),
	CONSTRAINT `units_name_unique` UNIQUE(`name`)
);
--> statement-breakpoint
INSERT INTO `units` (`name`) VALUES
	('Satuan Contoh A'),
	('Satuan Contoh B'),
	('Satuan Contoh C'),
	('Laboratorium Siber'),
	('Tim Asesor Keamanan Siber'),
	('Pengelola Platform');
--> statement-breakpoint
-- Satuan yang sudah diketik pengguna lama ikut menjadi entri agar datanya tidak hilang.
INSERT IGNORE INTO `units` (`name`) SELECT DISTINCT `unit` FROM `users`;
--> statement-breakpoint
ALTER TABLE `users` ADD `unit_id` bigint unsigned AFTER `nrp`;
--> statement-breakpoint
UPDATE `users` JOIN `units` ON `units`.`name` = `users`.`unit` SET `users`.`unit_id` = `units`.`id`;
--> statement-breakpoint
ALTER TABLE `users` MODIFY `unit_id` bigint unsigned NOT NULL;
--> statement-breakpoint
ALTER TABLE `users` DROP COLUMN `unit`;
--> statement-breakpoint
ALTER TABLE `users` ADD CONSTRAINT `users_unit_id_units_id_fk` FOREIGN KEY (`unit_id`) REFERENCES `units`(`id`) ON DELETE restrict ON UPDATE no action;
--> statement-breakpoint
CREATE INDEX `users_unit_id_idx` ON `users` (`unit_id`);
