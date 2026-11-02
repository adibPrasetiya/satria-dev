"""Ketajaman uji AUTH: payload valid, atribusi penolakan, pemulihan sandi, kebocoran hash."""

from __future__ import annotations

import json

import pytest

import satya_worker.ai as ai_mod
from satya_worker import atribusi_sandi as asd
from satya_worker.models import FormTitikUji
from satya_worker.runner import jalankan_metode
from tests.target_palsu import AKUN_UTAMA, TargetPalsu
from tests.test_auth_checks import ctx_for, metode

SKEMA_REG = {
    "nama": {"type": "string", "required": True},
    "nip": {"type": "string", "pattern": "^\\d{18}$", "required": True},
    "email": {"type": "string", "format": "email", "required": True},
}


@pytest.fixture(autouse=True)
def _tanpa_ai(monkeypatch):
    # Uji deterministik: AI eksternal tak dipakai.
    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: None)


class _Resp:
    def __init__(self, status: int, body: object):
        self.status_code = status
        self.text = json.dumps(body) if not isinstance(body, str) else body
        self.headers: dict[str, str] = {}


def _ctx_reg(base: str, skema: dict | None = SKEMA_REG):
    ctx = ctx_for(base)
    ctx.form["registrasi"] = FormTitikUji(
        field_dasar={k: "" for k in (skema or {})}, field_sandi="password", field_unik=["email", "nip"], skema_field=dict(skema or {})
    )
    return ctx


# ------------------------------------------------------------------ unit: payload & atribusi


def test_nilai_dummy_mengikuti_skema():
    assert len(asd.nilai_dummy("nip", {"pattern": "^\\d{18}$"})[0]) == 18
    assert asd.nilai_dummy("email", {"format": "email"})[0].endswith("@contoh.go.id")
    assert asd.nilai_dummy("peran", {"enum": ["pegawai", "admin"]})[0] == "pegawai"
    assert asd.nilai_dummy("nama", {"type": "string"})[0].startswith("Satya Uji")


def test_payload_valid_tak_mengisi_sandi_dan_unik_baru():
    f = FormTitikUji(field_dasar={"nama": "", "nip": "", "email": ""}, field_sandi="password", field_unik=["email"], skema_field=SKEMA_REG)
    p1, _ = asd.payload_valid(f)
    p2 = asd.segarkan_unik(p1, f)
    assert "password" not in p1 and p1["nama"] and len(p1["nip"]) == 18
    assert p1["email"] != p2["email"]


def test_analisis_body_error_terstruktur():
    p = {"nama": "", "email": "x", "password": "ab"}
    assert asd.analisis_body(_Resp(400, {"errors": [{"field": "password", "message": "terlalu pendek"}]}), "password", p)["penyebab"] == "kebijakan_sandi"
    a = asd.analisis_body(_Resp(400, {"errors": [{"field": "nama", "message": "wajib"}]}), "password", p)
    assert a["penyebab"] == "field_lain" and a["field"] == ["nama"]
    assert asd.analisis_body(_Resp(409, {"message": "Email sudah terdaftar"}), "password", p)["penyebab"] == "duplikasi"
    assert asd.analisis_body(_Resp(400, "Bad Request"), "password", p)["penyebab"] == "tidak_jelas"


def test_atribusi_pembanding_dan_vonis():
    lemah, kuat = _Resp(400, "Bad Request"), _Resp(201, {"ok": True})
    a = asd.atribusikan(lemah, field_sandi="password", payload={"password": "ab"}, sandi_lemah="ab", resp_kuat=kuat, pakai_ai=False)
    assert a["penyebab"] == "kebijakan_sandi" and a["sumber"] == "pembanding" and asd.vonis(a) == "lulus"
    # 400 tanpa penjelasan & pembanding juga ditolak → BUKAN lulus.
    a2 = asd.atribusikan(lemah, field_sandi="password", payload={"password": "ab"}, sandi_lemah="ab", resp_kuat=_Resp(400, "Bad Request"), pakai_ai=False)
    assert asd.vonis(a2) == "tidak_dapat_diverifikasi"
    assert asd.vonis(asd.atribusikan(_Resp(201, {}), field_sandi="password", payload={}, sandi_lemah="ab", pakai_ai=False)) == "gagal"


def test_atribusi_ai_dipakai_saat_ambigu(monkeypatch):
    class _Palsu:
        nama, model = "palsu", "m"

        def atribusi_penolakan(self, meta):
            assert "ab" not in json.dumps(meta)  # sandi lemah tak dikirim ke AI
            return {"penyebab": "kebijakan_sandi", "alasan": "pesan menyebut syarat kekuatan"}

    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: _Palsu())
    a = asd.atribusikan(_Resp(400, "Input ditolak: ab"), field_sandi="password", payload={"password": "ab"}, sandi_lemah="ab")
    assert a["sumber"] == "ai" and asd.vonis(a) == "lulus"


# ------------------------------------------------------------------ integrasi: registrasi


@pytest.mark.parametrize("mid,check_id", [("AUTH-1.3-T01", "auth.password_policy.min_length"), ("AUTH-1.3-T02", "auth.password_policy.complexity")])
def test_registrasi_payload_valid_lulus_karena_kebijakan(mid, check_id):
    with TargetPalsu("aman", validasi_ketat=True) as t:
        h = jalankan_metode(_ctx_reg(t.base_url), metode(mid, check_id, "registrasi"))
    assert h.status == "lulus", h.ringkasan
    assert "kebijakan kata sandi" in h.ringkasan


def test_registrasi_ditolak_field_lain_bukan_lulus():
    # Form tanpa field `nama`/`nip` → server menolak karena field lain, termasuk pembanding sandi kuat.
    with TargetPalsu("aman", validasi_ketat=True) as t:
        ctx = _ctx_reg(t.base_url, skema={"email": {"format": "email", "required": True}})
        h = jalankan_metode(ctx, metode("AUTH-1.2-T02", "auth.password_policy.server_side", "registrasi"))
    assert h.status == "tidak_dapat_diverifikasi", h.ringkasan
    assert "nama" in h.ringkasan or "field" in h.ringkasan


def test_registrasi_sandi_lemah_diterima_gagal():
    with TargetPalsu("rentan", validasi_ketat=True) as t:
        h = jalankan_metode(_ctx_reg(t.base_url), metode("AUTH-1.3-T01", "auth.password_policy.min_length", "registrasi"))
    assert h.status == "gagal"


# ------------------------------------------------------------------ ubah sandi + pemulihan


def test_ubah_sandi_lemah_diterima_lalu_dipulihkan():
    with TargetPalsu("rentan") as t:
        h = jalankan_metode(ctx_for(t.base_url), metode("AUTH-1.3-T04", "auth.password_policy.min_length+complexity", "ubah_password", butuh_autentikasi=True))
        sandi_akhir = t.sandi[AKUN_UTAMA[0]]
    assert h.status == "gagal"
    assert "dipulihkan" in h.ringkasan
    assert sandi_akhir == AKUN_UTAMA[1]  # akun uji kembali ke sandi asli


def test_ubah_sandi_ditolak_kebijakan_lulus_tanpa_mengubah_sandi():
    with TargetPalsu("aman") as t:
        h = jalankan_metode(ctx_for(t.base_url), metode("AUTH-1.3-T04", "auth.password_policy.min_length+complexity", "ubah_password", butuh_autentikasi=True))
        sandi_akhir = t.sandi[AKUN_UTAMA[0]]
    assert h.status == "lulus", h.ringkasan
    assert sandi_akhir == AKUN_UTAMA[1]


# ------------------------------------------------------------------ lainnya


def test_hash_sandi_terekspos_gagal():
    with TargetPalsu("aman", bocor_hash=True) as t:
        h = jalankan_metode(ctx_for(t.base_url), metode("AUTH-1.6-T01", "auth.password_not_echoed", "area_terautentikasi"))
    assert h.status == "gagal" and "Hash" in h.ringkasan


def test_validasi_server_kontrol_positif():
    with TargetPalsu("aman") as t:
        h = jalankan_metode(ctx_for(t.base_url), metode("AUTH-1.2-T01", "auth.server_side_validation", "login"))
    assert h.status == "lulus" and "kontrol positif" in h.ringkasan


def test_enumerasi_reset_pakai_email_akun_uji():
    with TargetPalsu("rentan") as t:
        ctx = ctx_for(t.base_url)
        ctx.form["reset_password"].email = ""  # tanpa email dikonfigurasi → pakai username akun uji
        h = jalankan_metode(ctx, metode("AUTH-1.5-T01", "auth.reset.no_user_enumeration", "reset_password"))
    assert h.status == "gagal"


def test_reset_enumerasi_tolak_metode_bukan_lulus():
    # Titik uji menunjuk halaman frontend (bukan API) → server menolak (404/405) untuk kedua akun;
    # respons "identik" tak boleh dianggap lulus.
    with TargetPalsu("aman") as t:
        ctx = ctx_for(t.base_url)
        ctx.titik_uji["reset_password"].url = f"{t.base_url}/halaman-spa-lupa-sandi"
        h = jalankan_metode(ctx, metode("AUTH-1.5-T01", "auth.reset.no_user_enumeration", "reset_password"))
    assert h.status == "tidak_dapat_diverifikasi"
    assert "frontend" in h.ringkasan
