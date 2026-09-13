# Agentic RAG untuk Dokumen Regulasi Indonesia

Sistem tanya-jawab atas peraturan perizinan berusaha berbasis risiko,
dengan sitasi tingkat pasal dan evaluasi retrieval yang terukur.

> Status: dalam pengembangan. Tahap 6 dari 13.

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
prefix `query:` / `document:`. Sisi sparse: BM25 lewat fastembed, dihitung
lokal tanpa API. Keduanya digabung Qdrant dengan RRF.

```bash
uv run python -m scripts.eval --mode dense    # bandingkan satu sisi saja
```

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

## Eksperimen

Perbandingan sebelum/sesudah tiap perubahan retrieval ada di
[`docs/experiments.md`](docs/experiments.md). Eksperimen #1 (pemotongan per
pasal) menaikkan recall@10 sebesar 0,100 tapi menurunkan MRR sebesar 0,074.
Eksperimen #2 (hybrid dense + BM25 lewat RRF) menaikkan MRR sebesar 0,189 —
lebih dari cukup untuk menebus kemunduran itu.

## Evaluasi

```bash
make eval
```

| Metrik (10 pertanyaan, `expected_source_type=regulasi`) | |
|---|---|
| recall@5 | **0,550** |
| recall@10 | 0,650 |
| MRR | **0,535** |
| nDCG@10 | **0,537** |

Ground truth memakai **nomor halaman**, bukan `chunk_id`. `chunk_id` berubah
setiap cara memotong berubah — dan Tahap 5 memang mengubahnya — sehingga
golden dataset akan rusak. Halaman tetap, dan tetap bisa diverifikasi manual
dengan membuka PDF. Patokan ini sedikit longgar: satu halaman berisi sekitar
dua chunk.

Pertanyaan yang berasal dari FAQ **wajib diparafrase** dengan struktur dan
kosakata berbeda. `origin.faq_id` disimpan supaya kebocoran bisa diaudit
belakangan. Semua pertanyaan di-embed dalam satu request, bukan satu per
satu — 50 pertanyaan berarti 1 request, bukan 50.

## Korpus

829 chunk dalam satu collection, dibedakan lewat payload `source_type`:

| Sumber | Chunk | Sitasi |
|---|---|---|
| `regulasi` — PP 28/2025 | 503 | jenis, nomor/tahun, **pasal**, halaman |
| `faq` — 6 file JSON OSS | 326 | kategori, tanggal akses |

Identitas dokumen ada di `data/metadata.csv`, bukan diambil dari nama file.

## Batasan korpus yang disadari

- **Nama berkas PDF-nya menyesatkan dan sempat menyesatkan proyek ini.**
  Berkas bernama `UU 28 2025 - ...pdf`, tetapi halaman judulnya berbunyi
  *Peraturan Pemerintah Republik Indonesia Nomor 28 Tahun 2025* — dan di
  dalamnya "Peraturan Pemerintah ini" muncul 42 kali, "Undang-Undang ini"
  nol kali. Sampai Tahap 5 seluruh sitasi tertulis `UU 28/2025` dan itu
  salah. Identitas di `data/metadata.csv` sekarang diambil dari halaman
  judul dokumen, bukan dari nama berkas. Berkasnya sendiri sengaja tidak
  diganti nama supaya jejak kesalahannya tetap terlihat.

- **Lapisan teks PP 28/2025 salah membaca huruf kapital I sebagai l** — 70 dari
  95 kata "Izin" tertulis "lzin". Dikoreksi lewat daftar eksplisit di
  `app/ingestion/pdf.py`; kalimat lain tidak terdampak.
- **Korpus regulasi sengaja dibatasi satu dokumen: PP 28/2025.** Ini proyek
  belajar; korpus besar tidak menambah pelajaran, hanya memperlambat siklus
  coba-ukur-perbaiki dan menghabiskan kuota embedding. PP 28/2025 dipilih
  karena topiknya paling bertemu dengan FAQ OSS (243 sebutan "OSS", 441
  "Pelaku Usaha") dan strukturnya rapi per pasal.
- **Ke-97 item FAQ "Layanan Informasi" sengaja dipertahankan** meski nilainya
  rendah. Mereka berfungsi sebagai pengecoh; korpus tanpa pengecoh membuat
  recall@5 terlihat bagus hanya karena tidak ada saingan.
- **Permen 5/2025 dan UU 6/2023 masih ada di `dokumen/PDF/`**, tinggal tambah
  barisnya di `data/metadata.csv` kalau suatu saat diperlukan. PDF UU 6/2023
  ternyata nyaris tidak menyebut OSS, NIB, atau tingkat risiko sama sekali.
- **Kolom `url_sumber` di `data/metadata.csv` belum diisi**, jadi sitasi belum
  bisa ditautkan langsung ke JDIH.
- **Jawaban FAQ teknis cepat basi** — banyak yang menyebut elemen antarmuka
  ("klik ikon keranjang sampah"). Tanggal akses ikut disimpan di payload.

## Batasan yang disengaja

Bagian ini diisi di Tahap 13.

## Sumber data

- FAQ OSS BKPM, diambil dari https://oss.go.id (`last_updated` file: 2025-12-22 s.d. 2025-12-24)
- Peraturan dari https://jdih.bkpm.go.id