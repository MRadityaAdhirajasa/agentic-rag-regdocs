import os
import threading
from datetime import date

BATAS_HARIAN = int(os.getenv("BUDGET_LLM_HARIAN", "200"))

_kunci = threading.Lock()
_hari: date | None = None
_terpakai = 0


def pakai(jumlah: int = 1) -> None:
    global _hari, _terpakai
    with _kunci:
        hari_ini = date.today()
        if _hari != hari_ini:
            _hari, _terpakai = hari_ini, 0
        _terpakai += jumlah


def tersisa() -> int:
    with _kunci:
        if _hari != date.today():
            return BATAS_HARIAN
        return max(BATAS_HARIAN - _terpakai, 0)


def habis() -> bool:
    return tersisa() <= 0


def status() -> dict[str, int | str]:
    return {"batas_harian": BATAS_HARIAN, "tersisa": tersisa(), "hari": str(_hari or date.today())}


def reset() -> None:
    global _hari, _terpakai
    with _kunci:
        _hari, _terpakai = None, 0
