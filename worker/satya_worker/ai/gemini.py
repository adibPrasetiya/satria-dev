"""Provider AI: Google Gemini (utama).

SDK `google-genai` diimpor LAZY agar worker tetap jalan tanpa paket/kunci.
Env: GEMINI_API_KEY (atau AI_API_KEY), AI_MODEL (default gemini-3.8-flash).
"""

from __future__ import annotations

import os
from typing import Any, Optional

from . import penggunaan
from .base import bangun_prompt, bangun_prompt_atribusi, bangun_prompt_isi_payload, bangun_prompt_kandidat, bangun_prompt_klasifikasi, bangun_prompt_login, parse_json

MODEL_DEFAULT = "gemini-3.8-flash"


def _teks_respons(resp: Any) -> str:
    """Gabungkan bagian TEKS jawaban (abaikan bagian pemikiran/`thought_signature`).

    `resp.text` pada model berpikir mencetak peringatan "non-text parts" tiap panggilan; membaca
    `parts` langsung memberi hasil yang sama tanpa peringatan.
    """
    try:
        bagian = resp.candidates[0].content.parts or []
        teks = "".join(p.text for p in bagian if getattr(p, "text", None) and not getattr(p, "thought", False))
        if teks:
            return teks
    except (AttributeError, IndexError, TypeError):
        pass
    return getattr(resp, "text", "") or ""


class GeminiProvider:
    nama = "gemini"

    def __init__(self, api_key: str, model: Optional[str] = None, bahasa: str = "id") -> None:
        self.api_key = api_key
        self.model = model or os.environ.get("AI_MODEL") or MODEL_DEFAULT
        self.bahasa = bahasa

    @classmethod
    def dari_env(cls) -> Optional["GeminiProvider"]:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("AI_API_KEY") or ""
        if not key.strip():
            return None
        return cls(key.strip(), bahasa=os.environ.get("AI_BAHASA", "id"))

    def enrich(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            from google import genai  # lazy
        except Exception as e:  # paket belum terpasang
            return {"_galat": f"google-genai tak tersedia: {type(e).__name__}"}
        try:
            klien = genai.Client(api_key=self.api_key)
            resp = klien.models.generate_content(
                model=self.model,
                contents=bangun_prompt(payload, self.bahasa),
            )
            teks = _teks_respons(resp)
        except Exception as e:
            return {"_galat": f"Gemini gagal: {type(e).__name__}: {e}"}
        hasil = parse_json(teks)
        return hasil if hasil is not None else {"_galat": "Respons Gemini bukan JSON valid", "_mentah": teks[:2000]}

    def _tanya_json(self, prompt: str) -> dict[str, Any]:
        """Satu panggilan generate_content → JSON (dipakai arbiter login & kandidat)."""
        try:
            from google import genai  # lazy
        except Exception as e:
            return {"_galat": f"google-genai tak tersedia: {type(e).__name__}"}
        try:
            klien = genai.Client(api_key=self.api_key)
            resp = klien.models.generate_content(model=self.model, contents=prompt)
            teks = _teks_respons(resp)
            penggunaan.catat(prompt, teks, *penggunaan.usage_gemini(resp))
        except Exception as e:
            return {"_galat": f"Gemini gagal: {type(e).__name__}: {e}"}
        hasil = parse_json(teks)
        return hasil if hasil is not None else {"_galat": "Respons Gemini bukan JSON valid"}

    def tanya_json(self, prompt: str, max_tokens: int = 2000) -> dict[str, Any]:
        """Panggilan JSON umum (dipakai INPV). `max_tokens` diabaikan: batas output Gemini ikut
        menghitung token berpikir sehingga respons bisa terpotong; prompt sendiri meminta JSON ringkas."""
        return self._tanya_json(prompt)

    def putuskan_login(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Arbiter login dari metadata non-sensitif. Return {ok, keyakinan, alasan} | {_galat}."""
        return self._tanya_json(bangun_prompt_login(metadata, self.bahasa))

    def lengkapi_kandidat(self, metadata: list[Any]) -> dict[str, Any]:
        """Penyempurnaan kandidat uji dari metadata non-sensitif. Return {saran:[...]} | {_galat}."""
        return self._tanya_json(bangun_prompt_kandidat(metadata, self.bahasa))

    def atribusi_penolakan(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Penyebab penolakan uji sandi dari metadata tersamar. Return {penyebab, field, alasan} | {_galat}."""
        return self._tanya_json(bangun_prompt_atribusi(metadata, self.bahasa))

    def isi_payload(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Nilai dummy valid untuk field form. Return {nilai: {...}} | {_galat}."""
        return self._tanya_json(bangun_prompt_isi_payload(metadata, self.bahasa))

    def klasifikasi_endpoint(self, metadata: list[Any]) -> dict[str, Any]:
        """Penajaman lapisan endpoint ambigu dari metadata non-sensitif. Return {saran:[...]} | {_galat}."""
        return self._tanya_json(bangun_prompt_klasifikasi(metadata, self.bahasa))
