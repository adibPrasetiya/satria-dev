-- Intel kerentanan (cache lokal NVD/CVE, CISA KEV, EPSS, OSV) + hasil pencocokan ke aset.
-- `cve.id` varchar(40): selain CVE-xxxx juga menampung ID GHSA/OSV untuk advisory paket tanpa CVE.
CREATE TABLE `cve` (
	`id` varchar(40) NOT NULL,
	`ringkasan` text,
	`dipublikasi_pada` datetime,
	`diubah_pada` datetime,
	`cvss_skor` decimal(3,1),
	`cvss_vektor` varchar(200),
	`severitas` enum('kritis','tinggi','sedang','rendah','info'),
	`cwe` json,
	`referensi` json,
	`status_analisis` enum('menunggu','dianalisis','ditolak') NOT NULL DEFAULT 'menunggu',
	`kev` boolean NOT NULL DEFAULT false,
	`kev_ditambahkan` date,
	`kev_tenggat` date,
	`kev_ransomware` boolean NOT NULL DEFAULT false,
	`epss` decimal(6,5),
	`epss_persentil` decimal(6,5),
	`sumber` enum('nvd','osv') NOT NULL DEFAULT 'nvd',
	`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `cve_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE INDEX `cve_kev_idx` ON `cve` (`kev`);--> statement-breakpoint
-- Rentang versi rentan per produk (dari konfigurasi CPE NVD; hanya cpeMatch `vulnerable: true`).
CREATE TABLE `cve_cpe` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`cve_id` varchar(40) NOT NULL,
	`vendor` varchar(100) NOT NULL,
	`produk` varchar(100) NOT NULL,
	`versi` varchar(60),
	`versi_mulai_incl` varchar(60),
	`versi_mulai_excl` varchar(60),
	`versi_akhir_incl` varchar(60),
	`versi_akhir_excl` varchar(60),
	CONSTRAINT `cve_cpe_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
ALTER TABLE `cve_cpe` ADD CONSTRAINT `cve_cpe_cve_id_fk` FOREIGN KEY (`cve_id`) REFERENCES `cve`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `cve_cpe_vendor_produk_idx` ON `cve_cpe` (`vendor`,`produk`);--> statement-breakpoint
-- Hasil OSV yang positif (paket@versi terdampak advisory); evaluasi versinya dikerjakan OSV sendiri.
CREATE TABLE `cve_paket` (
	`cve_id` varchar(40) NOT NULL,
	`purl` varchar(255) NOT NULL,
	`versi` varchar(60) NOT NULL,
	CONSTRAINT `cve_paket_pk` PRIMARY KEY(`cve_id`,`purl`,`versi`)
);
--> statement-breakpoint
ALTER TABLE `cve_paket` ADD CONSTRAINT `cve_paket_cve_id_fk` FOREIGN KEY (`cve_id`) REFERENCES `cve`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `cve_paket_purl_idx` ON `cve_paket` (`purl`,`versi`);--> statement-breakpoint
-- Status sinkron per kunci (mis. nvd:inkremental, nvd:produk:f5:nginx, kev, osv:pkg:npm/jquery@3.4.1).
CREATE TABLE `sinkron_intel` (
	`kunci` varchar(255) NOT NULL,
	`kursor` datetime,
	`status` enum('berhasil','gagal','berjalan') NOT NULL,
	`pesan` text,
	`updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `sinkron_intel_kunci` PRIMARY KEY(`kunci`)
);
--> statement-breakpoint
-- Hasil pencocokan CVE <-> aset. Identitas komponen didenormalisasi (komponen dibentuk ulang tiap sinkron/recon,
-- id-nya tidak stabil). Status ditangani/dikecualikan diisi manusia dan tidak pernah ditimpa pencocokan.
CREATE TABLE `aset_kerentanan` (
	`id` bigint unsigned AUTO_INCREMENT NOT NULL,
	`application_id` bigint unsigned NOT NULL,
	`cve_id` varchar(40) NOT NULL,
	`vendor` varchar(100),
	`produk` varchar(100) NOT NULL,
	`nama_komponen` varchar(100) NOT NULL,
	`versi` varchar(60),
	`sumber_komponen` varchar(20) NOT NULL,
	`status` enum('terdampak','kemungkinan','ditangani','dikecualikan','kedaluwarsa') NOT NULL,
	`alasan` varchar(500) NOT NULL,
	`prioritas` smallint unsigned NOT NULL DEFAULT 0,
	`catatan` varchar(1000),
	`ditangani_oleh` bigint unsigned,
	`ditangani_pada` datetime,
	`diberitahu_pada` datetime,
	`pertama_ditemukan` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`terakhir_dievaluasi` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT `aset_kerentanan_id` PRIMARY KEY(`id`),
	CONSTRAINT `aset_kerentanan_unik` UNIQUE(`application_id`,`cve_id`,`produk`)
);
--> statement-breakpoint
ALTER TABLE `aset_kerentanan` ADD CONSTRAINT `aset_kerentanan_application_id_fk` FOREIGN KEY (`application_id`) REFERENCES `applications`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `aset_kerentanan` ADD CONSTRAINT `aset_kerentanan_cve_id_fk` FOREIGN KEY (`cve_id`) REFERENCES `cve`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `aset_kerentanan` ADD CONSTRAINT `aset_kerentanan_ditangani_oleh_fk` FOREIGN KEY (`ditangani_oleh`) REFERENCES `users`(`id`) ON DELETE set null ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `aset_kerentanan_status_idx` ON `aset_kerentanan` (`status`,`prioritas`);
