-- Rujukan Recon & Discovery: scan yang memakai ulang hasil penemuan merujuk scan sumbernya, sehingga
-- topologi tetap dapat ditampilkan tanpa menyalin data recon.
ALTER TABLE `scans` ADD `recon_scan_id` bigint unsigned AFTER `approach`;--> statement-breakpoint
-- Isi untuk scan eksploratif lama tanpa fase penemuan: rujuk scan terakhir aplikasi yang sama yang
-- menjalankan penemuan sebelum scan tersebut. (Tabel turunan dimaterialisasi → aman untuk MySQL 1093.)
UPDATE `scans` s
JOIN (
  SELECT s2.`id` AS sid, MAX(p.`id`) AS rid
  FROM `scans` s2
  JOIN `scans` p ON p.`application_id` = s2.`application_id` AND p.`id` < s2.`id`
  JOIN `scan_tasks` tp ON tp.`scan_id` = p.`id` AND tp.`engine` = 'discovery'
  WHERE s2.`mode` = 'eksploratif'
    AND NOT EXISTS (SELECT 1 FROM `scan_tasks` t WHERE t.`scan_id` = s2.`id` AND t.`engine` = 'discovery')
  GROUP BY s2.`id`
) x ON x.sid = s.`id`
SET s.`recon_scan_id` = x.rid;
