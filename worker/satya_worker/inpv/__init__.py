"""Mesin sapuan Validasi Input (INPV).

Satu sapuan per scan menguji SELURUH endpoint inventaris discovery (`ctx.endpoints`):
tiap field body/query/path dikirimi varian tak valid (tipe/format/rentang/panjang/enum)
dan penanda injeksi inert, dengan field lain bernilai valid agar penolakan bisa
diatribusikan. Hasilnya — matriks cakupan + observasi per request — di-cache per
proses (kunci `scan_id`) dan dibaca semua check INPV (lihat `checks/input_validation.py`)
serta check ZAP aktif, sehingga target tidak disapu berulang untuk tiap metode.

Modul:
  cakupan.py       endpoint → diuji / tanpa_input / dilewati (+alasan), ID fiktif untuk mutasi
  profil_field.py  profil validasi per field (deterministik; AI hanya untuk yang ambigu)
  payload.py       varian tak valid per field sesuai profil
  vonis.py         observasi respons → kategori (ditolak_tepat, diterima, crash, indikasi_sqli, …)
  sapu.py          orkestrasi sapuan + cache
"""

from .sapu import Sapuan, sapuan  # noqa: F401
