from app.ingestion import pasal


def test_nomor_pasal_membetulkan_huruf_yang_sebenarnya_angka() -> None:
    assert pasal.nomor_pasal("1O1") == 101
    assert pasal.nomor_pasal("2OO") == 200
    assert pasal.nomor_pasal("lI2") == 112
    assert pasal.nomor_pasal("Il4") == 114
    assert pasal.nomor_pasal("12") == 12
    assert pasal.nomor_pasal("abc") is None


def test_rujukan_berakhiran_titik_bukan_judul() -> None:
    halaman = ["Pasal 1\n" + "isi. " * 60 + "\nsebagaimana dimaksud dalam Pasal 138.\n" + "x " * 60]
    hasil = pasal.pecah(halaman * 25)
    assert all("138" not in str(h["pasal"]) for h in hasil)


def test_pasal_tidak_berurutan_tidak_digabung() -> None:
    teks = "".join(f"Pasal {n}\nisi pendek.\n" for n in [1, 2, 3, 50, 51])
    hasil = pasal.pecah([teks] * 10)
    for h in hasil:
        if h["pasal"] and "-" in str(h["pasal"]):
            a, b = (int(x) for x in str(h["pasal"]).split("-"))
            assert b - a == len(range(a, b)), f"rentang melompat: {h['pasal']}"


def test_penjelasan_tidak_ikut_bernomor_pasal() -> None:
    batang = "".join(f"Pasal {n}\nisi batang tubuh.\n" for n in range(1, 30))
    teks = batang + "\nPENJELASAN\n" + "".join(f"Pasal {n}\nCukup jelas.\n" for n in range(1, 30))
    hasil = pasal.pecah([teks])
    penjelasan = [h for h in hasil if h["bab"] == "PENJELASAN"]
    assert penjelasan, "bagian PENJELASAN hilang dari korpus"
    assert all(h["pasal"] is None for h in penjelasan)


def test_tanpa_struktur_kembalikan_none() -> None:
    assert pasal.pecah(["teks biasa tanpa penanda apa pun."] * 5) is None


def test_halaman_dilacak_per_potongan() -> None:
    halaman = [f"Pasal {n}\n" + "isi " * 200 for n in range(1, 31)]
    hasil = pasal.pecah(halaman)
    assert hasil
    for h in hasil:
        assert h["halaman"], "setiap potongan wajib punya halaman"
        assert all(1 <= x <= len(halaman) for x in h["halaman"])
