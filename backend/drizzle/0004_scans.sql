CREATE TABLE `scan_targets` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`application_id` bigint unsigned NOT NULL,
	`test_points` json,
	`forms` json,
	`updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `scan_targets_id` PRIMARY KEY(`id`),
	CONSTRAINT `scan_targets_application_id_unique` UNIQUE(`application_id`)
);
--> statement-breakpoint
CREATE TABLE `scans` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`application_id` bigint unsigned NOT NULL,
	`profile` enum('aman','intrusif') NOT NULL DEFAULT 'aman',
	`status` enum('antre','berjalan','selesai','dibatalkan') NOT NULL DEFAULT 'berjalan',
	`started_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`finished_at` datetime,
	CONSTRAINT `scans_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `scan_tasks` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`scan_id` bigint unsigned NOT NULL,
	`method_code` varchar(50) NOT NULL,
	`check_id` varchar(120) NOT NULL,
	`engine` enum('custom','zap','nuclei','sslyze','playwright','manual') NOT NULL,
	`status` enum('antre','berjalan','selesai') NOT NULL DEFAULT 'antre',
	`attempts` smallint unsigned NOT NULL DEFAULT 0,
	`locked_by` varchar(100),
	`locked_at` datetime,
	`result` json,
	`duration_ms` bigint unsigned,
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `scan_tasks_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `scan_logs` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`scan_id` bigint unsigned NOT NULL,
	`level` enum('info','peringatan','galat') NOT NULL DEFAULT 'info',
	`message` varchar(500) NOT NULL,
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `scan_logs_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
ALTER TABLE `scan_targets` ADD CONSTRAINT `scan_targets_application_id_applications_id_fk` FOREIGN KEY (`application_id`) REFERENCES `applications`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `scans` ADD CONSTRAINT `scans_application_id_applications_id_fk` FOREIGN KEY (`application_id`) REFERENCES `applications`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `scan_tasks` ADD CONSTRAINT `scan_tasks_scan_id_scans_id_fk` FOREIGN KEY (`scan_id`) REFERENCES `scans`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `scan_logs` ADD CONSTRAINT `scan_logs_scan_id_scans_id_fk` FOREIGN KEY (`scan_id`) REFERENCES `scans`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `scans_application_id_idx` ON `scans` (`application_id`);--> statement-breakpoint
CREATE INDEX `scan_tasks_scan_id_idx` ON `scan_tasks` (`scan_id`);--> statement-breakpoint
CREATE INDEX `scan_tasks_status_engine_idx` ON `scan_tasks` (`status`,`engine`);--> statement-breakpoint
CREATE INDEX `scan_logs_scan_id_idx` ON `scan_logs` (`scan_id`);