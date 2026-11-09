-- Pendekatan pengujian per scan: grey box (memakai akun uji terbatas) atau black box (tanpa akun/
-- pengetahuan internal). Scan lama memakai akun uji → greybox.
ALTER TABLE `scans` ADD `approach` enum('greybox','blackbox') DEFAULT 'greybox' NOT NULL AFTER `mode`;
