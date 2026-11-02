CREATE TABLE `workers` (
	`id` varchar(100) NOT NULL,
	`engines` json NOT NULL,
	`status` enum('siaga','sibuk','berhenti') NOT NULL DEFAULT 'siaga',
	`task_id` bigint unsigned,
	`scan_id` bigint unsigned,
	`tahap` varchar(120),
	`versi` varchar(40),
	`host` varchar(120),
	`mulai_pada` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`terakhir_terlihat` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `workers_id` PRIMARY KEY(`id`)
);
