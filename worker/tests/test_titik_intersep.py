"""Form SPA tanpa action → titik uji diambil dari endpoint yang terungkap lewat intersep."""

from satya_worker.discovery_browser import petakan_titik_intersep

_PERINGKAT = {"tinggi": 3, "sedang": 2, "rendah": 1}


def _pencatat():
    tp: dict = {}

    def catat(titik, url, metode_http, keyakinan, catatan):
        lama = tp.get(titik)
        if lama and _PERINGKAT[lama["keyakinan"]] >= _PERINGKAT[keyakinan]:
            return
        tp[titik] = {"url": url, "metode_http": metode_http, "keyakinan": keyakinan}

    return tp, catat


def test_form_spa_dipetakan_ke_endpoint_api():
    tp, catat = _pencatat()
    catat("login", "https://x.test/login", "POST", "rendah", "form tanpa action")
    hasil = [
        {"method": "POST", "url": "https://x.test/api/telemetry", "asal": "https://x.test/login"},
        {"method": "POST", "url": "https://x.test/api/users/login?next=1", "asal": "https://x.test/login"},
        {"method": "POST", "url": "https://x.test/api/users/register", "asal": "https://x.test/register"},
    ]
    petakan_titik_intersep(hasil, {"https://x.test/login": "login", "https://x.test/register": "registrasi"}, catat)
    assert tp["login"] == {"url": "https://x.test/api/users/login", "metode_http": "POST", "keyakinan": "tinggi"}
    assert tp["registrasi"]["url"] == "https://x.test/api/users/register"


def test_kandidat_tunggal_tak_terklasifikasi_bernilai_sedang():
    tp, catat = _pencatat()
    catat("reset_password", "https://x.test/forgot-password", "POST", "rendah", "form tanpa action")
    petakan_titik_intersep(
        [{"method": "POST", "url": "https://x.test/api/v1/auth/minta-tautan", "asal": "https://x.test/forgot-password"}],
        {"https://x.test/forgot-password": "reset_password"}, catat,
    )
    assert tp["reset_password"]["url"] == "https://x.test/api/v1/auth/minta-tautan"
    assert tp["reset_password"]["keyakinan"] == "sedang"


def test_kandidat_ambigu_tak_menimpa():
    tp, catat = _pencatat()
    catat("login", "https://x.test/login", "POST", "rendah", "form tanpa action")
    petakan_titik_intersep(
        [{"method": "POST", "url": "https://x.test/api/a", "asal": "https://x.test/login"},
         {"method": "PUT", "url": "https://x.test/api/b", "asal": "https://x.test/login"}],
        {"https://x.test/login": "login"}, catat,
    )
    assert tp["login"]["url"] == "https://x.test/login"
