-- Inventaris komponen per aplikasi (produk + versi) sebagai dasar pencocokan CVE.
-- Sumber: 'formulir' (field teknologi aset, disinkron otomatis), 'manual' (koreksi/tambahan pengguna),
-- dan hasil recon worker (banner, nuclei, bundle_js, tls). Satu baris per (aplikasi, produk, sumber).
CREATE TABLE `aplikasi_komponen` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`application_id` bigint unsigned NOT NULL,
	`kategori` enum('frontend','backend','database','server','library','os','lainnya') NOT NULL,
	`vendor` varchar(100),
	`produk` varchar(100) NOT NULL,
	`nama` varchar(100) NOT NULL,
	`versi` varchar(60),
	`cpe` varchar(255),
	`purl` varchar(255),
	`sumber` enum('formulir','manual','banner','nuclei','bundle_js','tls') NOT NULL,
	`keyakinan` enum('tinggi','sedang','rendah') NOT NULL,
	`bukti` varchar(255),
	`scan_id` bigint unsigned,
	`terakhir_terlihat` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `aplikasi_komponen_id` PRIMARY KEY(`id`),
	CONSTRAINT `aplikasi_komponen_unik` UNIQUE(`application_id`,`produk`,`sumber`)
);
--> statement-breakpoint
ALTER TABLE `aplikasi_komponen` ADD CONSTRAINT `aplikasi_komponen_application_id_fk` FOREIGN KEY (`application_id`) REFERENCES `applications`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `aplikasi_komponen` ADD CONSTRAINT `aplikasi_komponen_scan_id_fk` FOREIGN KEY (`scan_id`) REFERENCES `scans`(`id`) ON DELETE set null ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `aplikasi_komponen_vendor_produk_idx` ON `aplikasi_komponen` (`vendor`,`produk`);
