"""Normalisasi singkatan dan alias lembaga. Deterministik, tanpa LLM.

Kenapa bagian ini tidak diserahkan ke LLM: hasilnya harus sama persis tiap
kali. Kalau tidak, teks pertanyaan berubah-ubah, sidik jari cache embedding
ikut berubah, dan tiap pertanyaan yang sama dibayar berulang kali.

Kepanjangan **ditambahkan**, bukan menggantikan. Singkatannya tetap perlu ada
supaya BM25 bisa mencocokkannya secara harfiah — "NIB" muncul di pasal
sebagai "NIB", bukan sebagai kepanjangannya.

Nama lembaga berubah beberapa kali (BKPM, lalu Kementerian Investasi, lalu
Kementerian Investasi dan Hilirisasi). Pengguna menyebutnya dengan nama
tahun berapa pun, dan dokumennya memakai nama yang lain lagi.
"""

import re

# ditulis lowercase; pencocokan tidak peduli besar-kecil huruf
ALIAS: dict[str, str] = {
    "bkpm": "Badan Koordinasi Penanaman Modal (Kementerian Investasi dan Hilirisasi)",
    "kementerian investasi": "Kementerian Investasi dan Hilirisasi/BKPM",
    "oss": "OSS (Online Single Submission, Sistem Perizinan Berusaha Terintegrasi)",
    "nib": "NIB (Nomor Induk Berusaha)",
    "pb-umku": "PB UMKU (Perizinan Berusaha untuk Menunjang Kegiatan Usaha)",
    "pb umku": "PB UMKU (Perizinan Berusaha untuk Menunjang Kegiatan Usaha)",
    "pbbr": "PBBR (Perizinan Berusaha Berbasis Risiko)",
    "kkpr": "KKPR (Kesesuaian Kegiatan Pemanfaatan Ruang)",
    "pkkpr": "PKKPR (Persetujuan Kesesuaian Kegiatan Pemanfaatan Ruang)",
    "kkkpr": "KKKPR (Konfirmasi Kesesuaian Kegiatan Pemanfaatan Ruang)",
    "pbg": "PBG (Persetujuan Bangunan Gedung)",
    "slf": "SLF (Sertifikat Laik Fungsi)",
    "kbli": "KBLI (Klasifikasi Baku Lapangan Usaha Indonesia)",
    "umk": "UMK (Usaha Mikro dan Kecil)",
    "lkpm": "LKPM (Laporan Kegiatan Penanaman Modal)",
    "kek": "KEK (Kawasan Ekonomi Khusus)",
    "kpbpb": "KPBPB (Kawasan Perdagangan Bebas dan Pelabuhan Bebas)",
    "amdal": "Amdal (analisis mengenai dampak lingkungan hidup)",
    "ukl-upl": "UKL-UPL (upaya pengelolaan dan pemantauan lingkungan hidup)",
    "nspk": "NSPK (norma, standar, prosedur, dan kriteria)",
    "sppl": "SPPL (surat pernyataan kesanggupan pengelolaan lingkungan hidup)",
}

# Satu pola gabungan, istilah terpanjang lebih dulu supaya "pb umku" menang
# atas potongan yang lebih pendek.
_POLA = re.compile(
    r"(?<![\w-])("
    + "|".join(re.escape(a) for a in sorted(ALIAS, key=len, reverse=True))
    + r")(?![\w-])",
    re.IGNORECASE,
)


def normalisasi(teks: str) -> tuple[str, list[str]]:
    """Tambahkan kepanjangan untuk alias yang muncul. Kembalikan teks dan daftar yang kena.

    Penggantian dilakukan dalam satu kali jalan. Kalau dikerjakan alias per
    alias, kepanjangan yang baru disisipkan ikut terpindai lagi: "PB-UMKU"
    berubah jadi "PB UMKU (...)" lalu tertangkap alias "pb umku" dan diperluas
    dua kali.
    """
    kena: list[str] = []

    def ganti(m: re.Match[str]) -> str:
        alias = m.group(1).lower()
        if alias in kena:
            # cukup sekali per alias; sisanya biarkan apa adanya
            return m.group(0)
        kena.append(alias)
        return ALIAS[alias]

    return _POLA.sub(ganti, teks), kena
