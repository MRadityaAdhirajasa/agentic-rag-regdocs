import re

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

_POLA = re.compile(
    r"(?<![\w-])("
    + "|".join(re.escape(a) for a in sorted(ALIAS, key=len, reverse=True))
    + r")(?![\w-])",
    re.IGNORECASE,
)


def normalisasi(teks: str) -> tuple[str, list[str]]:
    kena: list[str] = []

    def ganti(m: re.Match[str]) -> str:
        alias = m.group(1).lower()
        if alias in kena:
            return m.group(0)
        kena.append(alias)
        return ALIAS[alias]

    # Satu kali sapu, bukan ganti berulang: hasil perluasan memuat aliasnya sendiri
    # dan akan cocok lagi kalau dijalankan dua kali.
    return _POLA.sub(ganti, teks), kena
