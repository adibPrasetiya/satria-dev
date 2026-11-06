-- Pendaftaran bertahap kini mengumpulkan status kepegawaian (TNI/PNS) & pangkat/golongan sebagai
-- kolom tersendiri. Nullable: akun lama menyimpan pangkat di dalam `name`.
ALTER TABLE `users` ADD `status_kepegawaian` enum('TNI','PNS');--> statement-breakpoint
ALTER TABLE `users` ADD `pangkat` varchar(60);
