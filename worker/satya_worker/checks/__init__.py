"""Paket check. Impor modul agar dekorator @check mendaftarkan plugin (efek samping impor)."""

from . import akses  # noqa: F401
from . import api_web  # noqa: F401
from . import berkas  # noqa: F401
from . import field_sandi  # noqa: F401
from . import https  # noqa: F401
from . import input_validation  # noqa: F401
from . import kode_berbahaya  # noqa: F401
from . import komunikasi  # noqa: F401
from . import konfigurasi  # noqa: F401
from . import kontrol_akses  # noqa: F401
from . import kriptografi  # noqa: F401
from . import lockout  # noqa: F401
from . import manajemen_sesi  # noqa: F401
from . import password_policy  # noqa: F401
from . import penanganan_error  # noqa: F401
from . import proteksi_data  # noqa: F401
from . import reset_enumerasi  # noqa: F401
from . import sandi_tak_echo  # noqa: F401
from . import validasi_server  # noqa: F401
from . import zap_scan  # noqa: F401
from . import playwright_scan  # noqa: F401
