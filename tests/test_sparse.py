from app.core.sparse import encode_dokumen, encode_query


def _skor(dok, kueri) -> float:  # type: ignore[no-untyped-def]
    d = dict(zip(dok.indices, dok.values, strict=True))
    return sum(d[i] for i in kueri.indices if i in d)


def test_penanda_harfiah_tertangkap() -> None:
    dok = encode_dokumen(["Pelaku Usaha wajib memiliki NIB sebagaimana dimaksud dalam Pasal 227"])[
        0
    ]
    assert _skor(dok, encode_query(["Pasal 227"])[0]) > 0
    assert _skor(dok, encode_query(["NIB"])[0]) > 0


def test_kata_asing_tidak_kena() -> None:
    dok = encode_dokumen(["Pelaku Usaha wajib memiliki NIB sesuai Pasal 227"])[0]
    assert _skor(dok, encode_query(["tarif pajak penghasilan"])[0]) == 0


def test_tanpa_stemming_bentuk_kata_berbeda_tidak_disamakan() -> None:
    a = encode_query(["perizinan"])[0]
    b = encode_query(["izin"])[0]
    assert set(a.indices) != set(b.indices)
