-- Verifikasi akun lewat tautan email (pengganti verifikasi manual admin) + alasan pencabutan sesi
-- saat admin mengubah peran pengguna.
CREATE TABLE `email_verification_tokens` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`user_id` bigint unsigned NOT NULL,
	`token_hash` char(64) NOT NULL,
	`expires_at` datetime NOT NULL,
	`used_at` datetime,
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `email_verification_tokens_id` PRIMARY KEY(`id`),
	CONSTRAINT `email_verification_tokens_token_hash_unique` UNIQUE(`token_hash`)
);
--> statement-breakpoint
ALTER TABLE `email_verification_tokens` ADD CONSTRAINT `email_verification_tokens_user_id_users_id_fk` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `email_verification_tokens_user_id_idx` ON `email_verification_tokens` (`user_id`);--> statement-breakpoint
ALTER TABLE `refresh_tokens` MODIFY COLUMN `revoked_reason` enum('rotated','logout','password_change','deactivated','reuse','role_change');
