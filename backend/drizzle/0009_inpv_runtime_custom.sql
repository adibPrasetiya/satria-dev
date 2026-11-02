-- INPV-4.3-T01 (versi runtime/kerangka kerja rentan) kini dijalankan worker engine custom
-- (header versi + pustaka JS rentan dari ZAP), bukan nuclei yang belum didukung.
UPDATE `catalog_methods` SET `engine` = 'custom' WHERE `code` = 'INPV-4.3-T01' AND `engine` = 'nuclei';
