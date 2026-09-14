"""Satu jenis error untuk semua penyedia luar yang sedang tidak bisa dipakai.

Sebelum Tahap 11, kuota embedding yang habis melempar `SystemExit`. Di CLI itu
wajar — prosesnya memang harus berhenti. Di dalam server, `SystemExit` berubah
jadi 500, dan 500 adalah hal yang justru dilarang roadmap di tahap ini.

Dipisahkan jadi jenis sendiri supaya pemanggil bisa membedakan "layanan luar
sedang mati" dari "ada bug di kode kita". Yang pertama harus diturunkan
mutunya dengan anggun; yang kedua harus berisik.
"""


class LayananTidakTersedia(RuntimeError):
    """Penyedia luar tidak bisa dipakai: key kosong, kuota habis, atau layanan mati."""

    def __init__(self, layanan: str, sebab: str) -> None:
        self.layanan = layanan
        self.sebab = sebab
        super().__init__(f"{layanan} tidak tersedia: {sebab}")
