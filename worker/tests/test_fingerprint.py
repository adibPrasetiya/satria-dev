"""Uji fingerprint teknologi (fungsi murni: header/HTML/JS/nuclei → item komponen), tanpa jaringan."""

from __future__ import annotations

import json

from satya_worker import fingerprint as fp


def teks(items):
    return [(i["sumber"], i["kategori"], i["teks"], i["keyakinan"]) for i in items]


def test_header_server_dan_powered_by():
    items = fp.dari_respons({"Server": "Apache/2.4.41 (Ubuntu)", "X-Powered-By": "PHP/7.4.3"}, "", [])
    assert teks(items) == [
        ("banner", "server", "Apache/2.4.41 (Ubuntu)", "tinggi"),
        ("banner", "backend", "PHP/7.4.3", "tinggi"),
    ]
    assert items[0]["bukti"] == "Server: Apache/2.4.41 (Ubuntu)"


def test_banner_tanpa_versi_keyakinan_sedang():
    assert teks(fp.dari_respons({"server": "nginx"}, "", [])) == [("banner", "server", "nginx", "sedang")]


def test_halaman_galat_bawaan_dan_meta_generator():
    html = (
        '<html><head><meta name="generator" content="WordPress 6.4.2"></head>'
        "<body><address>Apache/2.4.29 (Ubuntu) Server at app.test Port 443</address>"
        "<hr><center>nginx/1.18.0</center></body></html>"
    )
    hasil = teks(fp.dari_respons({}, html, []))
    assert ("banner", "backend", "WordPress 6.4.2", "tinggi") in hasil
    assert ("banner", "server", "Apache/2.4.29 (Ubuntu)", "tinggi") in hasil
    assert ("banner", "server", "nginx/1.18.0", "tinggi") in hasil


def test_cookie_sesi_kerangka_kerja():
    hasil = teks(fp.dari_respons({}, "", ["laravel_session", "XSRF-TOKEN", "PHPSESSID"]))
    assert ("banner", "backend", "Laravel", "rendah") in hasil
    assert ("banner", "backend", "PHP", "rendah") in hasil
    assert len(hasil) == 2


def test_versi_library_dari_url_skrip():
    html = (
        '<script src="https://code.jquery.com/jquery-3.4.1.min.js"></script>'
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">'
        '<script src="/static/app.js"></script>'
    )
    hasil = [i["teks"] for i in fp.dari_respons({}, html, [])]
    assert hasil == ["jQuery 3.4.1", "Bootstrap 5.1.3"]


def test_banner_di_isi_js():
    js = (
        "/*! jQuery v3.6.0 | (c) OpenJS Foundation */ var x=1;"
        '/*! Bootstrap v5.2.3 (https://getbootstrap.com/) */'
        'X.injectIntoDevTools({bundleType:0,version:"18.2.0",rendererPackageName:"react-dom"});'
    )
    hasil = [i["teks"] for i in fp.dari_js(js, "vendor.js")]
    assert "jQuery 3.6.0" in hasil
    assert "Bootstrap 5.2.3" in hasil
    assert "React 18.2.0" in hasil


def test_keluaran_nuclei():
    baris = "\n".join(
        json.dumps(o)
        for o in [
            {"template-id": "tech-detect", "matcher-name": "nginx"},
            {"template-id": "nginx-version", "extracted-results": ["nginx/1.18.0"]},
            {"template-id": "php-detect", "extracted-results": ["7.4.3"]},
            {"template-id": "waf-detect", "matcher-name": "cloudflare"},
        ]
    )
    hasil = teks(fp.dari_nuclei(baris + "\nbukan json"))
    assert ("nuclei", "lainnya", "nginx", "sedang") in hasil
    assert ("nuclei", "lainnya", "nginx/1.18.0", "tinggi") in hasil
    assert ("nuclei", "lainnya", "php 7.4.3", "tinggi") in hasil
    assert ("nuclei", "lainnya", "cloudflare", "sedang") in hasil


def test_unik_dan_batas():
    it = fp._item("banner", "server", "nginx", "sedang")
    assert len(fp._unik([it, dict(it), {**it, "teks": "NGINX"}])) == 1
