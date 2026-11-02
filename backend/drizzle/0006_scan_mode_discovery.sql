ALTER TABLE `scans` ADD `mode` enum('terarah','eksploratif') NOT NULL DEFAULT 'terarah';--> statement-breakpoint
ALTER TABLE `scan_targets` ADD `discovery` json;--> statement-breakpoint
ALTER TABLE `scan_tasks` MODIFY COLUMN `engine` enum('custom','zap','nuclei','sslyze','playwright','manual','discovery') NOT NULL;--> statement-breakpoint
ALTER TABLE `catalog_methods` MODIFY COLUMN `engine` enum('custom','zap','nuclei','sslyze','playwright','manual','discovery') NOT NULL;