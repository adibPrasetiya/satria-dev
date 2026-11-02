CREATE TABLE `password_reset_tokens` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`user_id` bigint unsigned NOT NULL,
	`token_hash` char(64) NOT NULL,
	`expires_at` datetime NOT NULL,
	`used_at` datetime,
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `password_reset_tokens_id` PRIMARY KEY(`id`),
	CONSTRAINT `password_reset_tokens_token_hash_unique` UNIQUE(`token_hash`)
);
--> statement-breakpoint
CREATE TABLE `refresh_tokens` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`user_id` bigint unsigned NOT NULL,
	`token_hash` char(64) NOT NULL,
	`expires_at` datetime NOT NULL,
	`revoked_at` datetime,
	`revoked_reason` enum('rotated','logout','password_change','deactivated','reuse'),
	`user_agent` varchar(255),
	`ip` varchar(45),
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `refresh_tokens_id` PRIMARY KEY(`id`),
	CONSTRAINT `refresh_tokens_token_hash_unique` UNIQUE(`token_hash`)
);
--> statement-breakpoint
CREATE TABLE `users` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`name` varchar(100) NOT NULL,
	`nrp` varchar(20) NOT NULL,
	`unit` varchar(120) NOT NULL,
	`email` varchar(160) NOT NULL,
	`password_hash` varchar(255) NOT NULL,
	`role` enum('pemilik','asesor','admin') NOT NULL DEFAULT 'pemilik',
	`is_verified` boolean NOT NULL DEFAULT false,
	`verified_at` datetime,
	`verified_by` bigint unsigned,
	`is_active` boolean NOT NULL DEFAULT true,
	`failed_login_count` smallint unsigned NOT NULL DEFAULT 0,
	`locked_until` datetime,
	`password_changed_at` datetime,
	`last_login_at` datetime,
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `users_id` PRIMARY KEY(`id`),
	CONSTRAINT `users_nrp_unique` UNIQUE(`nrp`),
	CONSTRAINT `users_email_unique` UNIQUE(`email`)
);
--> statement-breakpoint
ALTER TABLE `password_reset_tokens` ADD CONSTRAINT `password_reset_tokens_user_id_users_id_fk` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `refresh_tokens` ADD CONSTRAINT `refresh_tokens_user_id_users_id_fk` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `users` ADD CONSTRAINT `users_verified_by_users_id_fk` FOREIGN KEY (`verified_by`) REFERENCES `users`(`id`) ON DELETE set null ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `password_reset_tokens_user_id_idx` ON `password_reset_tokens` (`user_id`);--> statement-breakpoint
CREATE INDEX `refresh_tokens_user_id_idx` ON `refresh_tokens` (`user_id`);