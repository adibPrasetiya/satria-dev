CREATE TABLE `catalog_controls` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`code` varchar(40) NOT NULL,
	`function_id` bigint unsigned NOT NULL,
	`ref_number` varchar(20) NOT NULL,
	`description` text NOT NULL,
	`verifiability` enum('otomatis','sebagian','manual') NOT NULL,
	`default_severity` enum('kritis','tinggi','sedang','rendah','info') NOT NULL,
	`aggregation` enum('semua_lulus','minimal_satu') NOT NULL DEFAULT 'semua_lulus',
	`refs` json,
	`parameters` json,
	`is_active` boolean NOT NULL DEFAULT true,
	`sort` smallint unsigned NOT NULL DEFAULT 0,
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `catalog_controls_id` PRIMARY KEY(`id`),
	CONSTRAINT `catalog_controls_code_unique` UNIQUE(`code`)
);
--> statement-breakpoint
CREATE TABLE `catalog_functions` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`code` varchar(20) NOT NULL,
	`number` smallint unsigned NOT NULL,
	`name` varchar(150) NOT NULL,
	`sort` smallint unsigned NOT NULL DEFAULT 0,
	CONSTRAINT `catalog_functions_id` PRIMARY KEY(`id`),
	CONSTRAINT `catalog_functions_code_unique` UNIQUE(`code`)
);
--> statement-breakpoint
CREATE TABLE `catalog_meta` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`schema_version` smallint unsigned NOT NULL,
	`regulation` varchar(255) NOT NULL,
	`section` varchar(255) NOT NULL,
	`notes` json,
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `catalog_meta_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `catalog_methods` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`code` varchar(50) NOT NULL,
	`control_id` bigint unsigned NOT NULL,
	`name` varchar(255) NOT NULL,
	`test_point` varchar(40) NOT NULL,
	`check_id` varchar(120) NOT NULL,
	`kind` enum('otomatis','semi_otomatis','manual') NOT NULL,
	`engine` enum('custom','zap','nuclei','sslyze','playwright','manual') NOT NULL,
	`profile` enum('aman','intrusif') NOT NULL,
	`requires_auth` boolean NOT NULL DEFAULT false,
	`evidence` json,
	`pass_criteria` text NOT NULL,
	`side_effect` text,
	`parameters` json,
	`severity` enum('kritis','tinggi','sedang','rendah','info') NOT NULL,
	`is_active` boolean NOT NULL DEFAULT true,
	`sort` smallint unsigned NOT NULL DEFAULT 0,
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `catalog_methods_id` PRIMARY KEY(`id`),
	CONSTRAINT `catalog_methods_code_unique` UNIQUE(`code`)
);
--> statement-breakpoint
CREATE TABLE `catalog_test_points` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`code` varchar(40) NOT NULL,
	`name` varchar(150) NOT NULL,
	`sort` smallint unsigned NOT NULL DEFAULT 0,
	CONSTRAINT `catalog_test_points_id` PRIMARY KEY(`id`),
	CONSTRAINT `catalog_test_points_code_unique` UNIQUE(`code`)
);
--> statement-breakpoint
ALTER TABLE `catalog_controls` ADD CONSTRAINT `catalog_controls_function_id_catalog_functions_id_fk` FOREIGN KEY (`function_id`) REFERENCES `catalog_functions`(`id`) ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `catalog_methods` ADD CONSTRAINT `catalog_methods_control_id_catalog_controls_id_fk` FOREIGN KEY (`control_id`) REFERENCES `catalog_controls`(`id`) ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `catalog_controls_function_id_idx` ON `catalog_controls` (`function_id`);--> statement-breakpoint
CREATE INDEX `catalog_methods_control_id_idx` ON `catalog_methods` (`control_id`);