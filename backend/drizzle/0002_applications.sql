CREATE TABLE `applications` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`name` varchar(150) NOT NULL,
	`description` text,
	`unit_id` bigint unsigned NOT NULL,
	`owner_id` bigint unsigned,
	`pic_name` varchar(100) NOT NULL,
	`pic_contact` varchar(100) NOT NULL,
	`base_url` varchar(255) NOT NULL,
	`environment` enum('produksi','staging','pengembangan') NOT NULL,
	`data_classification` enum('biasa','terbatas','rahasia') NOT NULL,
	`tech_frontend` varchar(100),
	`tech_backend` varchar(100),
	`tech_database` varchar(100),
	`tech_server` varchar(100),
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `applications_id` PRIMARY KEY(`id`),
	CONSTRAINT `applications_base_url_unique` UNIQUE(`base_url`)
);
--> statement-breakpoint
ALTER TABLE `applications` ADD CONSTRAINT `applications_unit_id_units_id_fk` FOREIGN KEY (`unit_id`) REFERENCES `units`(`id`) ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `applications` ADD CONSTRAINT `applications_owner_id_users_id_fk` FOREIGN KEY (`owner_id`) REFERENCES `users`(`id`) ON DELETE set null ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `applications_unit_id_idx` ON `applications` (`unit_id`);