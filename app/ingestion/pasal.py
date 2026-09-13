"""Pemotong berbasis struktur dokumen: BAB dan Pasal.

Kenapa tidak sekadar memotong tiap pasal jadi satu chunk: median isi satu
pasal di UU 28/2025 cuma 193 karakter. Chunk sekecil itu kehilangan konteks
dan justru menurunkan kualitas pencarian. Jadi pasal-pasal pendek yang
berurutan digabung sampai mendekati ukuran yang sebanding dengan pemotongan
lama, tapi batas antar pasal tidak pernah dilanggar di tengah.

Pasal yang kepanjangan (lebih dari 1800 karakter, ada 37 dari 1038) dipotong
lagi memakai pemotong karakter biasa — itu jalur cadangannya.

Soal nomor yang rusak: lapisan teks PDF ini membaca 0 sebagai O dan 1 sebagai
l, I, atau L. Dari 1125 penanda pasal, 144 tertulis seperti `1O1` atau `lI2`.
Perbaikan hanya diterapkan di posisi nomor pasal — tidak di seluruh teks,
karena "O" dan "l" jelas sah di kata biasa.
"""

import bisect
import re
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

GABUNG_SAMPAI = 900  # pasal pendek berurutan digabung sampai sekitar ukuran ini
POTONG_KALAU_LEBIH = 1800  # pasal raksasa dipotong lagi
MINIMAL_PASAL = 20  # di bawah ini dokumen dianggap gagal diparse

# Penanda pasal harus berdiri sendiri di satu baris. Nomor boleh mengandung
# huruf yang sebenarnya angka.
POLA_PASAL = re.compile(r"(?m)^[ 	]*Pasal[ 	]+([0-9OoIlL]{1,4})[ 	]*$")
POLA_BAB = re.compile(r"(?m)^[ \t]*(BAB[ \t]+[IVXL]+)[ \t]*$")

# Bagian PENJELASAN di akhir dokumen mengulang penomoran pasal dari 1, dan
# sebagian besar isinya cuma "Cukup jelas". Kalau ikut diparse, nomornya
# bentrok dengan batang tubuh dan sitasinya jadi salah. Bagian ini tetap
# masuk korpus, tapi lewat pemotong karakter tanpa nomor pasal.
POLA_PENJELASAN = re.compile(r"(?m)^[ 	]*PENJELASAN[ 	]*$")

SAMARAN = {"O": "0", "o": "0", "I": "1", "l": "1", "L": "1"}


def nomor_pasal(mentah: str) -> int | None:
    angka = "".join(SAMARAN.get(c, c) for c in mentah)
    return int(angka) if angka.isdigit() else None


def _peta_halaman(pages: list[str]) -> tuple[str, list[int]]:
    """Gabung halaman jadi satu teks, simpan offset awal tiap halaman."""
    teks, mulai, jalan = [], [], 0
    for p in pages:
        mulai.append(jalan)
        teks.append(p)
        jalan += len(p) + 1
    return "\n".join(teks), mulai


def _halaman_dari(mulai: list[int], awal: int, akhir: int) -> list[int]:
    a = bisect.bisect_right(mulai, awal) - 1
    b = bisect.bisect_right(mulai, max(akhir - 1, awal)) - 1
    return list(range(a + 1, b + 2))


def pecah(pages: list[str]) -> list[dict[str, Any]] | None:
    """Pecah dokumen jadi potongan berbasis pasal.

    Kembalikan None kalau strukturnya tidak terdeteksi — pemanggil yang
    memutuskan memakai jalur cadangan dan menandainya `parse_failed`.
    """
    teks, mulai_hal = _peta_halaman(pages)

    batas = POLA_PENJELASAN.search(teks)
    batas_akhir = batas.start() if batas else len(teks)

    penanda = []
    for m in POLA_PASAL.finditer(teks):
        if m.start() >= batas_akhir:
            break
        n = nomor_pasal(m.group(1))
        if n is not None:
            penanda.append((m.start(), m.end(), n))
    if len(penanda) < MINIMAL_PASAL:
        return None

    bab_di = [(m.start(), m.group(1)) for m in POLA_BAB.finditer(teks)]

    def bab_untuk(posisi: int) -> str | None:
        i = bisect.bisect_right([p for p, _ in bab_di], posisi) - 1
        return bab_di[i][1] if i >= 0 else None

    # satu blok = judul pasal + isinya sampai pasal berikutnya
    blok: list[dict[str, Any]] = []
    for i, (awal, _, n) in enumerate(penanda):
        akhir = penanda[i + 1][0] if i + 1 < len(penanda) else batas_akhir
        isi = teks[awal:akhir].strip()
        if isi:
            blok.append({"pasal": n, "awal": awal, "akhir": akhir, "teks": isi})

    pemotong = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
    keluar: list[dict[str, Any]] = []

    # Halaman judul, Menimbang, dan Mengingat berada SEBELUM penanda Pasal
    # pertama. Tanpa ini, judul peraturannya sendiri tidak ada di korpus dan
    # pertanyaan "peraturan apa yang mengatur ini" tidak menemukan apa pun.
    pembukaan = teks[: penanda[0][0]].strip()
    if pembukaan:
        for bagian in pemotong.split_text(pembukaan):
            if not bagian.strip():
                continue
            pos = teks.find(bagian[:60], 0, penanda[0][0])
            pos = pos if pos >= 0 else 0
            keluar.append(
                {
                    "teks": bagian,
                    "pasal": None,
                    "bab": "PEMBUKAAN",
                    "halaman": _halaman_dari(mulai_hal, pos, pos + len(bagian)),
                }
            )
    tumpuk: list[dict[str, Any]] = []

    def buang_tumpukan() -> None:
        if not tumpuk:
            return
        gabung = "\n\n".join(b["teks"] for b in tumpuk)
        awal, akhir = tumpuk[0]["awal"], tumpuk[-1]["akhir"]
        nomor = [b["pasal"] for b in tumpuk]
        keluar.append(
            {
                "teks": gabung,
                "pasal": str(nomor[0]) if len(nomor) == 1 else f"{nomor[0]}-{nomor[-1]}",
                "bab": bab_untuk(awal),
                "halaman": _halaman_dari(mulai_hal, awal, akhir),
            }
        )
        tumpuk.clear()

    for b in blok:
        if len(b["teks"]) > POTONG_KALAU_LEBIH:
            buang_tumpukan()
            # jalur cadangan: pasal raksasa dipotong pemotong karakter.
            # Tiap potongan dicari posisinya sendiri — kalau tidak, semuanya
            # mewarisi rentang halaman pasal utuhnya dan sitasinya jadi palsu.
            jejak = b["awal"]
            for bagian in pemotong.split_text(b["teks"]):
                if not bagian.strip():
                    continue
                pos = teks.find(bagian[:60], jejak, b["akhir"])
                if pos < 0:
                    pos = jejak
                jejak = pos + max(len(bagian) - 150, 1)
                keluar.append(
                    {
                        "teks": bagian,
                        "pasal": str(b["pasal"]),
                        "bab": bab_untuk(b["awal"]),
                        "halaman": _halaman_dari(mulai_hal, pos, pos + len(bagian)),
                    }
                )
            continue

        # hanya pasal berurutan yang boleh digabung; kalau melompat, sitasi
        # gabungannya ("Pasal 138-209") jadi bohong
        if tumpuk and b["pasal"] != tumpuk[-1]["pasal"] + 1:
            buang_tumpukan()
        tumpuk.append(b)
        if sum(len(x["teks"]) for x in tumpuk) >= GABUNG_SAMPAI:
            buang_tumpukan()
    buang_tumpukan()

    if batas:
        # PENJELASAN lewat jalur cadangan, tanpa nomor pasal
        for bagian in pemotong.split_text(teks[batas.start() :]):
            if not bagian.strip():
                continue
            pos = teks.find(bagian[:60], batas.start())
            pos = pos if pos >= 0 else batas.start()
            keluar.append(
                {
                    "teks": bagian,
                    "pasal": None,
                    "bab": "PENJELASAN",
                    "halaman": _halaman_dari(mulai_hal, pos, pos + len(bagian)),
                }
            )

    return keluar
