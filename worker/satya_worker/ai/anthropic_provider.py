"""Provider AI: Anthropic Claude (fallback).

SDK `anthropic` diimpor LAZY agar worker tetap jalan tanpa paket/kunci.
Env: ANTHROPIC_API_KEY (atau AI_API_KEY), AI_MODEL (default claude-opus-5-5).

Mengikuti panduan skill `claude-api`: panggil `messages.create` tanpa menyetel
`thinking`/`temperature` (model terbaru memakai adaptive thinking secara bawaan),
dan minta keluaran JSON lewat instruksi prompt (prefill asisten tidak didukung).
"""

from __future__ import annotations

import os
from typing import Any, Optional

from . import penggunaan
from .base import bangun_prompt, bangun_prompt_atribusi, bangun_prompt_isi_payload, bangun_prompt_kandidat, bangun_prompt_klasifikasi, bangun_prompt_login, parse_json

MODEL_DEFAULT = "claude-opus-5-5"


class AnthropicProvider:
    nama = "anthropic"

    def __init__(self, api_key: str, model: Optional[str] = None, bahasa: str = "id") -> None:
        self.api_key = api_key
        self.model = model or os.environ.get("AI_MODEL") or MODEL_DEFAULT
        self.bahasa = bahasa

    @classmethod
    def dari_env(cls) -> Optional["AnthropicProvider"]:
        key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("AI_API_KEY") or ""
        if not key.strip():
            return None
        return cls(key.strip(), bahasa=os.environ.get("AI_BAHASA", "id"))

    def enrich(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            from anthropic import Anthropic  # lazy
        except Exception as e:
            return {"_galat": f"anthropic SDK tak tersedia: {type(e).__name__}"}
        try:
            klien = Anthropic(api_key=self.api_key)
            resp = klien.messages.create(
                model=self.model,
                max_tokens=8000,
                messages=[{"role": "user", "content": bangun_prompt(payload, self.bahasa)}],
            )
            teks = "".join(
                getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
            )
        except Exception as e:
            return {"_galat": f"Anthropic gagal: {type(e).__name__}: {e}"}
        hasil = parse_json(teks)
        return hasil if hasil is not None else {"_galat": "Respons Anthropic bukan JSON valid", "_mentah": teks[:2000]}

    def _tanya_json(self, prompt: str, max_tokens: int = 1500) -> dict[str, Any]:
        """Satu panggilan messages.create → JSON (dipakai arbiter login & kandidat)."""
        try:
            from anthropic import Anthropic  # lazy
        except Exception as e:
            return {"_galat": f"anthropic SDK tak tersedia: {type(e).__name__}"}
        try:
            klien = Anthropic(api_key=self.api_key)
            resp = klien.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            teks = "".join(
                getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
            )
            penggunaan.catat(prompt, teks, *penggunaan.usage_anthropic(resp))
        except Exception as e:
            return {"_galat": f"Anthropic gagal: {type(e).__name__}: {e}"}
        hasil = parse_json(teks)
        return hasil if hasil is not None else {"_galat": "Respons Anthropic bukan JSON valid"}

    def tanya_json(self, prompt: str, max_tokens: int = 2000) -> dict[str, Any]:
        """Panggilan JSON umum (dipakai INPV) dengan batas token keluaran kecil."""
        return self._tanya_json(prompt, max_tokens=max_tokens)

    def putuskan_login(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Arbiter login dari metadata non-sensitif. Return {ok, keyakinan, alasan} | {_galat}."""
        return self._tanya_json(bangun_prompt_login(metadata, self.bahasa), max_tokens=1000)

    def lengkapi_kandidat(self, metadata: list[Any]) -> dict[str, Any]:
        """Penyempurnaan kandidat uji dari metadata non-sensitif. Return {saran:[...]} | {_galat}."""
        return self._tanya_json(bangun_prompt_kandidat(metadata, self.bahasa), max_tokens=4000)

    def atribusi_penolakan(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Penyebab penolakan uji sandi dari metadata tersamar. Return {penyebab, field, alasan} | {_galat}."""
        return self._tanya_json(bangun_prompt_atribusi(metadata, self.bahasa), max_tokens=1500)

    def isi_payload(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Nilai dummy valid untuk field form. Return {nilai: {...}} | {_galat}."""
        return self._tanya_json(bangun_prompt_isi_payload(metadata, self.bahasa), max_tokens=1500)

    def klasifikasi_endpoint(self, metadata: list[Any]) -> dict[str, Any]:
        """Penajaman lapisan endpoint ambigu dari metadata non-sensitif. Return {saran:[...]} | {_galat}."""
        return self._tanya_json(bangun_prompt_klasifikasi(metadata, self.bahasa), max_tokens=4000)
