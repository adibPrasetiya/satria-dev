"""Aplikasi target palsu untuk menguji check AUTH & SESS tanpa aplikasi nyata.

Mode 'aman' menegakkan kontrol; 'rentan' melanggarnya. Sesi berbasis token (JWT-like)
dengan opsi cookie sesi. Target stateful: token yang diterbitkan di-ACK pada endpoint
terautentikasi.

  GET  /login                 halaman login (HTML; input sandi type=password | text)
  POST /auth/register         registrasi (tolak sandi lemah)
  POST /auth/login            login (token unik per login; kunci akun setelah N gagal)
  POST /auth/change-password  ubah sandi (butuh Bearer; tolak sandi lemah)
  POST /auth/forgot-password  reset (respons identik utk akun ada/tidak)
  POST /auth/logout           logout
  GET  /auth/me               profil (butuh Bearer token yang diterbitkan)

Opsi: cookie=True menambah Set-Cookie sesi. token_tetap=True → token sama tiap login (rentan rotasi).
validasi_ketat=True → registrasi mewajibkan `nama` terisi & `nip` 18 digit (400 error terstruktur per
field) dan email unik (409) — untuk menguji atribusi penolakan. bocor_hash=True → /auth/me memuat hash
sandi. Endpoint tambahan: POST /auth/reset-password {token, password} (token valid: "tok-reset-uji").
"""

from __future__ import annotations

import base64
import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_BESAR = re.compile(r"[A-Z]")
_KECIL = re.compile(r"[a-z]")
_ANGKA = re.compile(r"\d")
_SIMBOL = re.compile(r"[^A-Za-z0-9]")

AKUN_UTAMA = ("uji@satya.local", "Rahasia#2026Uji")
AKUN_KUNCI = ("kunci@satya.local", "Rahasia#2026Kunci")

# Identitas objek per akun (dipakai uji akses horizontal/IDOR).
_UID = {AKUN_UTAMA[0]: "1001", AKUN_KUNCI[0]: "2002"}


def _uid(email: str) -> str:
    return _UID.get(email, "9")


def _kuat(s: str, minimal: int = 8) -> bool:
    return len(s) >= minimal and _BESAR.search(s) and _KECIL.search(s) and _ANGKA.search(s) and _SIMBOL.search(s)


def _b64(d: bytes) -> str:
    return base64.urlsafe_b64encode(d).decode().rstrip("=")


def _jwt_acak(exp_detik: int | None = None) -> str:
    head = _b64(b'{"alg":"HS256","typ":"JWT"}')
    isi = {"sub": "1", "jti": secrets.token_hex(8)}
    if exp_detik is not None:
        import time as _t

        now = int(_t.time())
        isi["iat"] = now
        isi["exp"] = now + exp_detik
    payload = _b64(json.dumps(isi).encode())
    sig = _b64(secrets.token_bytes(32))
    return f"{head}.{payload}.{sig}"


def buat_handler(mode: str, *, cookie: bool = False, token_tetap: bool = False, jwt: bool = False,
                 rekam_post: list[str] | None = None, validasi_ketat: bool = False, bocor_hash: bool = False,
                 sandi_akun: dict[str, str] | None = None, jwt_exp: int | None = None,
                 sesi_tunggal: bool = False, rate_limit: bool = False, rate_batas: int = 5):
    aman = mode == "aman"
    gagal: dict[str, int] = {}
    diterbitkan: set[str] = set()
    pemilik_token: dict[str, str] = {}
    # Sandi akun saat ini (berubah lewat change-password) — memungkinkan uji pemulihan sandi.
    sandi = sandi_akun if sandi_akun is not None else {}
    sandi.setdefault(AKUN_UTAMA[0], AKUN_UTAMA[1])
    sandi.setdefault(AKUN_KUNCI[0], AKUN_KUNCI[1])
    terdaftar: set[str] = set()
    counter = {"n": 0}
    tetap_val = secrets.token_urlsafe(32)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _kirim(self, status, body, ctype="application/json", set_cookie: str | None = None):
            data = json.dumps(body).encode() if isinstance(body, (dict, list)) else str(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if set_cookie:
                self.send_header("Set-Cookie", set_cookie)
            self.end_headers()
            self.wfile.write(data)

        def _baca(self):
            n = int(self.headers.get("Content-Length", "0"))
            try:
                return json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return {}

        def _issued(self) -> bool:
            """Bearer dengan token yang pernah diterbitkan (berlaku di kedua mode)."""
            auth = self.headers.get("Authorization", "")
            return auth.startswith("Bearer ") and auth[7:] in diterbitkan

        def do_GET(self):
            if self.path == "/" or self.path == "":
                html = (
                    "<!doctype html><html><head><title>SATYA Uji</title></head><body>"
                    "<a href=/login>Masuk</a> <a href=/register>Daftar</a> "
                    "<a href=/forgot-password>Lupa sandi</a> <a href=/profil>Profil</a>"
                    "</body></html>"
                )
                self._kirim(200, html, "text/html; charset=utf-8")
                return
            if self.path.startswith("/register"):
                html = (
                    "<!doctype html><html><body><form method=post action=/auth/register>"
                    "<input name=nama type=text><input name=email type=email>"
                    "<input name=nrp type=text><input name=password type=password>"
                    "</form></body></html>"
                )
                self._kirim(200, html, "text/html; charset=utf-8")
                return
            if self.path.startswith("/forgot-password"):
                html = (
                    "<!doctype html><html><body><form method=post action=/auth/forgot-password>"
                    "<input name=email type=email></form></body></html>"
                )
                self._kirim(200, html, "text/html; charset=utf-8")
                return
            if self.path.startswith("/login"):
                tipe = "password" if aman else "text"
                html = f"<!doctype html><html><body><form method=post action=/auth/login><input name=email type=email><input name=password type={tipe}></form></body></html>"
                self._kirim(200, html, "text/html; charset=utf-8")
                return
            if self.path.startswith("/auth/me") or self.path.startswith("/profil"):
                # aman: hanya token terbit yang diterima (token asing/kosong → 401).
                # rentan: selalu 200 & membocorkan kata sandi (langgar 1.1-T01, 1.6-T01, 2.5-T02).
                if aman and not self._issued():
                    self._kirim(401, {"success": False, "message": "perlu login"})
                    return
                email = pemilik_token.get(self.headers.get("Authorization", "")[7:], AKUN_UTAMA[0])
                prof = {"id": _uid(email), "email": email, "nama": "Akun Uji"}
                if not aman:
                    prof["password"] = AKUN_UTAMA[1]
                if bocor_hash:
                    prof["password_hash"] = "$2b$12$abcdefghijklmnopqrstuuJ8k1y4YyQf0r9a1t2Zx3Wq4Er5Ty6Ui"
                self._kirim(200, {"success": True, "data": prof})
                return
            # --- Kontrol Akses (ACCS) ---
            mobj = re.match(r"^/orders/([^/?]+)", self.path)
            if mobj:
                oid = mobj.group(1)
                if not aman:  # IDOR: siapa pun bisa baca objek siapa pun
                    self._kirim(200, {"success": True, "data": {"id": oid, "pemilik": oid, "rahasia": f"data-{oid}"}})
                    return
                tok = self.headers.get("Authorization", "")[7:] if self.headers.get("Authorization", "").startswith("Bearer ") else ""
                if tok not in diterbitkan:
                    self._kirim(401, {"success": False, "message": "perlu login"})
                elif _uid(pemilik_token.get(tok, "")) != oid:
                    self._kirim(403, {"success": False, "message": "Dilarang mengakses objek pengguna lain"})
                else:
                    self._kirim(200, {"success": True, "data": {"id": oid, "pemilik": oid, "rahasia": f"data-{oid}"}})
                return
            if self.path.startswith("/admin"):
                if not aman:  # panel admin terbuka untuk siapa pun
                    self._kirim(200, {"success": True, "data": {"panel": "admin", "pengguna": ["a", "b"]}})
                    return
                tok = self.headers.get("Authorization", "")[7:] if self.headers.get("Authorization", "").startswith("Bearer ") else ""
                if tok not in diterbitkan:
                    self._kirim(401, {"success": False, "message": "perlu login"})
                else:  # akun uji berperan biasa → ditolak
                    self._kirim(403, {"success": False, "message": "Khusus administrator"})
                return
            if self.path.startswith("/api/cari"):
                if rate_limit:
                    counter["rl"] = counter.get("rl", 0) + 1
                    if counter["rl"] > rate_batas:
                        self._kirim(429, {"success": False, "message": "Terlalu banyak permintaan"})
                        return
                self._kirim(200, {"success": True, "data": []})
                return
            self._kirim(404, {"success": False})

        def do_POST(self):
            path, body = self.path, self._baca()
            if rekam_post is not None:
                rekam_post.append(path)

            if path == "/auth/register":
                if validasi_ketat:
                    galat = []
                    if not str(body.get("nama", "")).strip():
                        galat.append({"field": "nama", "message": "nama wajib diisi"})
                    if not re.fullmatch(r"\d{18}", str(body.get("nip", ""))):
                        galat.append({"field": "nip", "message": "NIP harus 18 digit angka"})
                    if galat:
                        self._kirim(400, {"success": False, "errors": galat})
                        return
                    if str(body.get("email", "")) in terdaftar:
                        self._kirim(409, {"success": False, "message": "Email sudah terdaftar"})
                        return
                if aman and not _kuat(str(body.get("password", ""))):
                    self._kirim(400, {"success": False, "errors": [{"field": "password", "message": "Kata sandi minimal 8 karakter dengan huruf besar, kecil, angka, simbol"}]})
                    return
                terdaftar.add(str(body.get("email", "")))
                self._kirim(201, {"success": True, "message": "akun dibuat"})
                return

            if path == "/auth/reset-password":
                if body.get("token") != "tok-reset-uji":
                    self._kirim(400, {"success": False, "errors": [{"field": "token", "message": "token tidak valid"}]})
                    return
                if aman and not _kuat(str(body.get("password", ""))):
                    self._kirim(400, {"success": False, "errors": [{"field": "password", "message": "Kata sandi terlalu lemah"}]})
                    return
                self._kirim(200, {"success": True})
                return

            if path == "/auth/login":
                email, sandi_kirim = str(body.get("email", "")), str(body.get("password", ""))
                if email in sandi and sandi[email] == sandi_kirim:
                    gagal[email] = 0
                    if sesi_tunggal:  # sesi tunggal: invalidasi sesi akun ini sebelumnya
                        for t in [t for t, o in pemilik_token.items() if o == email]:
                            diterbitkan.discard(t)
                            pemilik_token.pop(t, None)
                    if token_tetap:
                        tok = tetap_val
                    elif aman:
                        tok = _jwt_acak(jwt_exp) if jwt else secrets.token_urlsafe(32)
                    else:
                        counter["n"] += 1
                        tok = f"sess-{counter['n']}"  # berurutan (rentan entropi)
                    diterbitkan.add(tok)
                    pemilik_token[tok] = email
                    sc = None
                    if cookie:
                        flags = "; Secure; HttpOnly; SameSite=Lax" if aman else ""
                        sc = f"sessionid={secrets.token_hex(8) if aman else counter['n']}{flags}"
                    self._kirim(200, {"success": True, "accessToken": tok, "user": {"email": email}}, set_cookie=sc)
                    return
                gagal[email] = gagal.get(email, 0) + 1
                if aman and gagal[email] > 5:
                    self._kirim(423, {"success": False, "message": "Akun terkunci sementara"})
                    return
                self._kirim(401, {"success": False, "message": "Email atau kata sandi salah"})
                return

            if path == "/auth/change-password":
                if not self._issued():
                    self._kirim(401, {"success": False, "message": "perlu login"})
                    return
                email = pemilik_token.get(self.headers.get("Authorization", "")[7:], "")
                if str(body.get("current_password", "")) != sandi.get(email):
                    self._kirim(400, {"success": False, "errors": [{"field": "current_password", "message": "sandi lama salah"}]})
                    return
                if aman and not _kuat(str(body.get("new_password", ""))):
                    self._kirim(400, {"success": False, "errors": [{"field": "new_password", "message": "Kata sandi baru tidak memenuhi kebijakan"}]})
                    return
                sandi[email] = str(body.get("new_password", ""))
                self._kirim(200, {"success": True})
                return

            if path == "/auth/logout":
                auth = self.headers.get("Authorization", "")
                if auth.startswith("Bearer "):
                    tok = auth[7:]
                    diterbitkan.discard(tok)  # invalidasi sesi di server
                    pemilik_token.pop(tok, None)
                sc = "sessionid=; Max-Age=0" if cookie else None
                self._kirim(200, {"success": True}, set_cookie=sc)
                return

            if path == "/auth/forgot-password":
                email = str(body.get("email", ""))
                if aman:
                    self._kirim(202, {"success": True, "message": "Bila email terdaftar, tautan reset dikirim."})
                elif email == AKUN_UTAMA[0]:
                    self._kirim(200, {"success": True, "message": "Tautan reset dikirim ke email Anda."})
                else:
                    self._kirim(404, {"success": False, "message": "Email tidak terdaftar."})
                return

            self._kirim(404, {"success": False})

    return H


class TargetPalsu:
    def __init__(self, mode: str = "aman", *, cookie: bool = False, token_tetap: bool = False, jwt: bool = False,
                 validasi_ketat: bool = False, bocor_hash: bool = False, jwt_exp: int | None = None,
                 sesi_tunggal: bool = False, rate_limit: bool = False, rate_batas: int = 5) -> None:
        self.mode = mode
        self.post_masuk: list[str] = []  # path setiap POST yang benar-benar diterima server
        self.sandi: dict[str, str] = {}  # sandi akun saat ini (diperbarui change-password)
        self._srv = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            buat_handler(mode, cookie=cookie, token_tetap=token_tetap, jwt=jwt, rekam_post=self.post_masuk,
                         validasi_ketat=validasi_ketat, bocor_hash=bocor_hash, sandi_akun=self.sandi,
                         jwt_exp=jwt_exp, sesi_tunggal=sesi_tunggal, rate_limit=rate_limit, rate_batas=rate_batas),
        )
        self.port = self._srv.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> "TargetPalsu":
        self._t = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._srv.shutdown()
        self._srv.server_close()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["aman", "rentan"], default="aman")
    p.add_argument("--port", type=int, default=8081)
    a = p.parse_args()
    ThreadingHTTPServer(("127.0.0.1", a.port), buat_handler(a.mode)).serve_forever()
