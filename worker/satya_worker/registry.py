"""Registry check: satu plugin per (check_id, engine) katalog.

Satu check_id bisa punya varian engine berbeda (mis. auth.password_policy.min_length+complexity
ada versi custom [ubah_password] dan playwright [reset]). Karena itu kuncinya pasangan
(check_id, engine). Mendaftarkan plugin cukup dengan dekorator `@check("<check_id>")`
(engine default 'custom') atau `@check("<check_id>", engine="playwright")`.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from .models import HasilMetode, MetodeSpec, ScanContext


@runtime_checkable
class Check(Protocol):
    check_id: str
    engine: str

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode: ...


_REGISTRY: dict[tuple[str, str], "Check"] = {}


def check(check_id: str, engine: str = "custom") -> Callable[[type], type]:
    """Dekorator kelas: daftarkan instance tunggal untuk (check_id, engine)."""

    def bungkus(kelas: type) -> type:
        instance = kelas()
        instance.check_id = check_id  # type: ignore[attr-defined]
        instance.engine = engine  # type: ignore[attr-defined]
        _REGISTRY[(check_id, engine)] = instance  # type: ignore[assignment]
        return kelas

    return bungkus


def cari_check(check_id: str, engine: str = "custom") -> "Check | None":
    return _REGISTRY.get((check_id, engine))


def daftar_check() -> list[tuple[str, str]]:
    return sorted(_REGISTRY)
