# Agentic RAG untuk Dokumen Regulasi Indonesia

Sistem tanya-jawab atas peraturan perizinan berusaha berbasis risiko,
dengan sitasi tingkat pasal dan evaluasi retrieval yang terukur.

> Status: dalam pengembangan. Tahap 3 dari 13.

## Menjalankan

```bash
docker compose up -d                      # Qdrant
make ingest                               # regulasi + FAQ -> Qdrant
make chat                                 # tanya-jawab CLI dengan sitasi
```

Ingest per bagian, berguna karena kuota embedding harian terbatas:

```bash
uv run python -m scripts.ingest --faq
uv run python -m scripts.ingest --doc uu-6-2023
```

Butuh `.env` berisi `OPENROUTER_API_KEY` (embedding) dan `GOOGLE_API_KEY`
(LLM). Contohnya ada di `.env.example`.

Embedding: `nvidia/nemotron-3-embed-1b:free` lewat OpenRouter, 2048 dimensi,
prefix `query:` / `document:`. Retrieval masih dense-only, k=3.

## Ingestion

Embedding di-cache di `data/embed_cache.sqlite`, dikunci hash dari isi teks
plus nama model. Akibatnya ingest ulang seluruh korpus **tidak memanggil API
sama sekali**: 7 detik, nol request, bahkan saat kuota harian habis.

Cache ditulis dan di-commit per batch, jadi proses yang mati di tengah —
Ctrl+C, koneksi putus, kuota habis — melanjutkan dari titik terakhir, bukan
mengulang dari nol. Itu sekaligus checkpoint-nya; tidak ada file progress
terpisah.

Dua jenis rate limit ditangani berbeda: limit per-menit ditunggu dengan
exponential backoff plus jitter, limit per-hari langsung dihentikan dengan
pesan yang menyebut kapan pulih. Menunggu limit harian berarti menggantung
berjam-jam sambil pura-pura bekerja.

## Korpus

2.903 chunk dalam satu collection, dibedakan lewat payload `source_type`:

| Sumber | Chunk | Sitasi |
|---|---|---|
| `regulasi` — 3 PDF | 2.550 | jenis, nomor/tahun, halaman |
| `faq` — 6 file JSON OSS | 353 | kategori, tanggal akses |

Identitas dokumen ada di `data/metadata.csv`, bukan diambil dari nama file.

## Batasan korpus yang disadari

- **Lapisan teks UU 28/2025 salah membaca huruf kapital I sebagai l** — 70 dari
  95 kata "Izin" tertulis "lzin". Dikoreksi lewat daftar eksplisit di
  `app/ingestion/pdf.py`; kalimat lain tidak terdampak.
- **Korpus regulasi sengaja berhenti di 3 dokumen ini.** Ketiganya berstatus
  berlaku. Beberapa peraturan yang disebut di rencana awal (PP 5/2021, Perban
  BKPM 4/2021 & 5/2021) sudah tidak berlaku dan sengaja tidak dimasukkan.
- **Kolom `url_sumber` di `data/metadata.csv` belum diisi**, jadi sitasi belum
  bisa ditautkan langsung ke JDIH.
- **Jawaban FAQ teknis cepat basi** — banyak yang menyebut elemen antarmuka
  ("klik ikon keranjang sampah"). Tanggal akses ikut disimpan di payload.

## Batasan yang disengaja

Bagian ini diisi di Tahap 13.

## Sumber data

- FAQ OSS BKPM, diambil dari https://oss.go.id (`last_updated` file: 2025-12-22 s.d. 2025-12-24)
- Peraturan dari https://jdih.bkpm.go.id