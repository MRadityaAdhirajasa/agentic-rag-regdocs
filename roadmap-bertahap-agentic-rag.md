# Roadmap Bertahap — Agentic RAG Regdocs

Pecahan dari Plan v3 menjadi 13 tahap inkremental. Tidak ada patokan waktu.
Naik tahap kalau tahap sekarang sudah jalan dan kamu paham kenapa dia jalan.

---

## Aturan Main

1. **Satu konsep baru per tahap.** Kalau satu tahap terasa berat, dia terlalu besar — pecah lagi.
2. **Tiap tahap harus bisa dijalanin.** Bukan setengah jadi yang baru nyala di tahap berikutnya.
3. **Commit di akhir tiap tahap**, dengan pesan yang jelas. Nanti `git log` kamu jadi cerita pembelajaran yang rapi — dan itu bagus dilihat di interview.
4. **Tag tiap tahap:** `git tag stage-03`. Kalau tahap berikutnya kacau, kamu bisa balik ke titik yang pasti jalan.
5. **Kalau macet lebih dari beberapa jam di satu hal**, catat di `docs/notes.md` dan cari jalan pintas sementara. Jangan berhenti total.

Tiga alat ini dipakai dari Tahap 0 dan seterusnya: **git, uv, Docker.**

---

## Korpus

Dua jenis sumber, satu collection, dibedakan lewat payload `source_type`.

### A. FAQ OSS BKPM — 353 item

Diambil manual dari `oss.go.id`, enam file JSON, satu per kategori.
Satu item (question + answer) = satu chunk. Tidak dipotong lagi.

| Kategori | Item | Sifat | Bisa ditelusuri ke pasal? |
|---|---|---|---|
| Proses Perizinan Berusaha | 147 | Hukum | Ya, kuat |
| Layanan Informasi dan Bantuan Pengguna | 97 | Meta/support | Tidak |
| Pelaporan, Pelacakan, Pengawasan, Sanksi | 51 | Hukum | Ya, kuat |
| Manajemen Akun dan Pendaftaran | 47 | Teknis | Jarang |
| Fasilitas, Kemitraan, Fitur Pendukung | 8 | Campuran | Sebagian |
| Sistem dan Kendala Teknis | 3 | Teknis murni | Tidak |

Dua kategori hukum (198 item) adalah jantung korpus. Di situ FAQ dan
regulasi membahas hal yang sama dari dua sisi.

Kategori Layanan Informasi (97 item) nilainya rendah tapi **tetap
dimasukkan** — dia berfungsi sebagai distractor. Korpus tanpa distractor
membuat `recall@5` terlihat bagus hanya karena tidak ada saingan.

Kategori Fasilitas (8 item) terlalu kecil untuk jadi kelas routing
tersendiri. Pilah manual per entri.

### B. Regulasi — 5 dokumen inti

Dari `jdih.bkpm.go.id`, status di-cross-check ke `peraturan.bpk.go.id`.

1. UU Cipta Kerja — payung hukum
2. PP 5/2021 tentang Perizinan Berusaha Berbasis Risiko
3. Perban BKPM 4/2021 tentang Pedoman dan Tata Cara Pelayanan Perizinan Berusaha Berbasis Risiko dan Fasilitas Penanaman Modal
4. Perban BKPM 5/2021 tentang Pengawasan Perizinan Berusaha Berbasis Risiko
5. Permen Investasi dan Hilirisasi/Kepala BKPM 5/2025 — versi terkini

Pasangan nomor 3 dan 5 adalah inti demo supersesi. Jangan sampai salah
satu tidak ada.

**Hitung dulu sebelum menyimpulkan korpus ini "kecil".** UU Cipta Kerja
dan PP 5/2021 itu dokumen besar. Setelah parsing, cetak jumlah chunk per
dokumen. Kalau totalnya di bawah 300 chunk, baru tambah 5-10 Permen
pendek.

### Skema payload gabungan

| Field | FAQ | Regulasi |
|---|---|---|
| `chunk_id`, `source_type`, `status`, `text`, `url_sumber` | ada | ada |
| `bab`, `pasal`, `ayat`, `halaman`, `tahun`, `nomor`, `jenis` | null | ada |
| `faq_category`, `question`, `confidence` | ada | null |

Bentuk sitasinya jadi dua: `PP 5/2021, Pasal 12 ayat 1, hal. 18` atau
`FAQ OSS — Proses Perizinan Berusaha, diakses [tanggal]`.

### Catatan lisensi dan kesegaran

- FAQ diambil dari halaman publik `oss.go.id`. Tulis sumber dan tanggal
  akses di README
- `last_updated` data FAQ adalah 2025-12-24. Cek sekilas apakah sudah
  berubah, dan catat tanggal akses yang jujur
- Jawaban FAQ teknis banyak menyebut elemen antarmuka ("klik ikon
  keranjang sampah"). Konten seperti ini cepat basi — sebutkan sebagai
  batasan yang disadari di README
- Peraturan perundang-undangan dikecualikan dari hak cipta berdasarkan
  UU 28/2014. Verifikasi pasalnya sendiri, tulis satu paragraf di README

---

## Peta Cepat

| Tahap | Kapabilitas baru | Alat/konsep baru |
|---|---|---|
| 0 | Kerangka kosong yang jalan | uv, Docker, git, ruff/pytest |
| 1 | RAG lamamu pindah ke Qdrant | qdrant-client, collection, payload |
| 2 | Korpus asli + sitasi | PyMuPDF, metadata.csv, quality gate |
| 3 | Ingestion yang tahan gagal | cache, backoff, checkpoint |
| 4 | **Alat ukur** | golden dataset, recall@5, MRR |
| 5 | Chunking berbasis pasal | regex parser + eksperimen #1 |
| 6 | Hybrid search | fastembed, sparse, RRF + eksperimen #2 |
| 7 | Reranking | cross-encoder + eksperimen #3 |
| 8 | Jadi API | FastAPI, Pydantic, Swagger |
| 9 | Jadi graph | LangGraph, state, routing |
| 10 | Verifikasi + retry | node verify, mutasi strategi |
| 11 | Tahan banting | degraded mode, rate limit, budget |
| 12 | Terpantau + terjaga | Langfuse, CI gate |
| 13 | Bisa dilihat orang | deploy, README, benchmark |

Tahap 0-3 fondasi. Tahap 4-7 retrieval yang terukur. Tahap 8-10 agentic.
Tahap 11-13 produksi.

---

# FONDASI

## Tahap 0 — Kerangka kosong yang jalan

**Yang baru:** uv, Docker Compose, struktur repo, CI kosong.

**Isi tahap ini:**
- `git init`, repo di GitHub, `.gitignore` (pastikan `.env` masuk)
- `uv init`, `pyproject.toml`, `uv add` beberapa dependency dasar
- Struktur folder: `app/{api,core,agents,retrieval,eval}`, `data/`, `docs/`
- `docker-compose.yml`: Qdrant + volume persist
- `.env.example` dan `.env` — **API key tidak pernah masuk ke kode**
- GitHub Actions: ruff + pytest kosong, biar pipeline-nya ada duluan
- `docs/adr/` dengan ADR-001 sampai ADR-005 disalin dari Plan v3

**Selesai kalau:**
- `docker compose up` → Qdrant hidup di `localhost:6333`
- Script Python bisa connect, bikin collection dummy, isi 1 vektor
- `docker compose down` lalu `up` lagi → collection masih ada
- Push ke GitHub, CI hijau

**Jangan dulu:** container untuk API. Tahap ini cuma Qdrant. Kode Python jalan di virtualenv lokal.

**Yang bikin bingung:** perbedaan `docker compose down` dan `down -v`. Coba dua-duanya sekali, sengaja, biar kamu paham konsekuensinya.

---

## Tahap 1 — RAG lamamu, pindah ke Qdrant

**Yang baru:** qdrant-client, konsep collection dan payload.

Ambil `rag_langchain_2.py` kamu. Ganti Chroma jadi Qdrant. Selesai. Jangan ubah apa pun yang lain.

- Masih 1-2 PDF
- Masih `RecursiveCharacterTextSplitter`
- Masih dense-only, k=3
- Masih chat loop CLI

**Kenapa tahap ini ada:** kamu belajar Qdrant secara terisolasi, tanpa variabel lain berubah. Kalau hasilnya beda dari versi Chroma, kamu tahu penyebabnya cuma satu.

**Selesai kalau:** jawaban yang keluar kurang lebih setara versi Chroma-mu, tapi datanya sekarang ada di Qdrant dan selamat setelah restart.

**Yang bikin bingung:** `collection_name`, `vector size` harus cocok dengan dimensi model embedding, dan `distance` metric. Salah satu saja tidak cocok, Qdrant menolak.

---

## Tahap 2 — Korpus asli dan sitasi

**Yang baru:** PyMuPDF, quality gate PDF, desain payload metadata.

- Download 5 dokumen inti dari `jdih.bkpm.go.id` (tabel di Bab 4 Plan v3)
- Jalankan quality gate: hitung karakter per halaman, buang yang hasil scan
- Susun `data/metadata.csv`: `doc_id, judul, jenis, nomor, tahun, status, url_sumber, file_path, tanggal_unduh`
- Ganti PyPDFLoader jadi PyMuPDF, **simpan nomor halaman per chunk**
- Payload tiap chunk minimal: `doc_id`, `halaman`, `judul`, `status`, `tahun`
- Cetak sitasi bersama jawaban: judul dokumen dan halaman

**Jalur kedua — FAQ JSON:**
- Loader terpisah untuk enam file JSON FAQ. Satu item = satu chunk,
  tanpa chunking
- Yang di-embed adalah **gabungan question dan answer**, bukan salah
  satu. Question mencocokkan cara user bertanya, answer membawa kata
  kunci substansinya
- Isi parameter `title` pada `embed_content` dengan question-nya —
  parameter yang sudah pernah kamu pakai di `rag_manual.py`
- Payload: `source_type: "faq"`, `faq_category`, `question`,
  `url_sumber` dari `reference_url`, `tanggal_akses`, `confidence`
- Buang field `notes`, `input_method`, `base_url`
- Rapikan dulu nama file `fasilitass_...` — ada dobel s. Perbaiki
  sekarang sebelum menyebar ke variabel dan key payload

**Selesai kalau:** kedua jenis sumber masuk ke satu collection, dan
`source_type` bisa dipakai untuk memfilter salah satunya.

**Kenapa tahap ini penting:** ini pertama kalinya jawabanmu bisa diverifikasi manual. Buka PDF, cek halaman, lihat sendiri benar atau tidak. Rasanya beda jauh dari sebelumnya.

**Selesai kalau:** ambil 5 jawaban acak, cek sitasinya satu-satu di PDF asli, semuanya nyambung.

**Jangan dulu:** parsing berbasis pasal. Masih character splitter.

**Yang bikin bingung:** `status` (berlaku/diubah/dicabut) diisi manual dengan referensi silang ke `peraturan.bpk.go.id`. Jangan tebak dari tahun terbit.

---

## Tahap 3 — Ingestion yang tahan gagal

**Yang baru:** disk cache, exponential backoff, checkpoint.

Naikkan korpus jadi 40-50 dokumen. Di titik ini ingestion naif kamu akan patah, dan itu memang tujuannya — kamu perlu merasakan masalahnya sebelum memasang solusinya.

- Batching sesuai limit provider
- Exponential backoff plus jitter untuk error 429
- **Disk cache embedding dikunci `content_hash`** — ini yang paling penting
- Checkpoint progress ke file, bukan cuma di memori
- Bungkus jadi `make ingest`

**Selesai kalau:** jalankan `make ingest`, matikan paksa di tengah (Ctrl+C), jalankan lagi — dia lanjut dari titik terakhir, tidak mengulang dari nol.

**Uji ini beneran.** Ini yang menyelamatkan kuota harianmu berkali-kali nanti.

**Yang bikin bingung:** `content_hash` dihitung dari teks chunk, bukan dari nama file. Chunk yang isinya sama persis tidak perlu di-embed dua kali meski beda dokumen.

---

# RETRIEVAL YANG TERUKUR

## Tahap 4 — Alat ukur (JANGAN DILEWAT)

**Yang baru:** golden dataset, metrik retrieval.

Ini tahap yang paling membosankan dan paling penting. Semua tahap setelah ini bergantung padanya.

- Tulis 10 pertanyaan golden dulu, tidak usah 50. Semuanya
  `lookup_faktual` dari kategori Proses Perizinan Berusaha
- Format lengkap ada di `golden-dataset-format.md` — skema, aturan
  parafrase, dan alur pengisian `relevant_chunk_ids`
- Implementasi metrik dengan Python murni: `recall@5`, `recall@10`, `MRR`, `nDCG@10`
- `make eval` mencetak tabel, dipecah per `expected_source_type`
- Simpan hasil pertama ke `eval/baseline.json`, sertakan jumlah
  pertanyaan di dalamnya
- Sisihkan 50 item FAQ ke `eval/holdout_routing.jsonl`, jangan dipakai
  di golden dataset

**Bahaya utama tahap ini: kebocoran evaluasi.**

FAQ ada di dalam korpus. Kalau pertanyaan golden disalin mentah dari
FAQ, retrieval akan menemukan entri FAQ itu sendiri karena kalimatnya
identik. `recall@5` jadi tinggi, dan angkanya bohong — yang terukur
bukan kualitas retrieval, tapi kemampuan mencocokkan kalimat yang sama.

Tiga pengaman:
1. Pertanyaan dari FAQ **wajib diparafrase**, ikuti lima aturan di
   `golden-dataset-format.md`
2. Untuk kategori hukum, `relevant_chunk_ids` menunjuk **chunk
   regulasi**, bukan entri FAQ
3. Metrik dilaporkan terpisah per `expected_source_type`

Simpan `origin.faq_id` di tiap entri, supaya kebocoran bisa diaudit
belakangan.

**Kenapa harus di sini, bukan nanti:** mulai Tahap 5 kamu akan mengubah-ubah retrieval. Tanpa angka, kamu cuma menebak apakah perubahanmu membantu. Dengan angka, tiap tahap berikutnya jadi eksperimen yang punya hasil.

**Selesai kalau:** `make eval` keluar angka, dan kamu tahu `recall@5` kamu sekarang berapa.

**Yang bikin bingung:** menentukan `relevant_chunk_ids` itu manual dan agak melelahkan. Tapi 10 pertanyaan cukup untuk mulai. Tambah 10 lagi tiap beberapa tahap.

---

## Tahap 5 — Chunking berbasis pasal

**Yang baru:** parser struktur dokumen, eksperimen terukur pertama.

- Regex untuk mendeteksi penanda Bab, Pasal, Ayat
- Fallback ke recursive splitter kalau struktur tidak terdeteksi
- Payload bertambah: `bab`, `pasal`, `ayat`
- **Jalankan `make eval` sebelum dan sesudah.** Catat kedua angka di `docs/experiments.md`

**Ini eksperimen #1 dari Plan v3.** Sitasi kamu juga naik kelas: dari "halaman 18" jadi "Pasal 12 ayat 1, halaman 18".

**Selesai kalau:** ada dua baris angka di `docs/experiments.md` dan kamu bisa bilang chunking pasal menang atau kalah, beserta selisihnya.

**Yang bikin bingung:** format penomoran pasal di PDF tidak selalu konsisten. Timebox usahamu. Dokumen yang gagal di-parse dicatat sebagai `parse_failed` dan dilewat — kegagalan yang tercatat itu fitur, bukan aib.

---

## Tahap 6 — Hybrid search

**Yang baru:** sparse vector, BM25, Reciprocal Rank Fusion.

- fastembed untuk sisi sparse
- Named vectors di Qdrant: dense dan sparse dalam satu collection
- RRF native lewat query API Qdrant
- `make eval` lagi, catat lagi

**Ini eksperimen #2.** Perhatikan pertanyaan yang menyebut nomor pasal atau nomor peraturan — di situ sparse biasanya menyelamatkan hasil yang dense-nya meleset.

**Selesai kalau:** angka vector-only vs hybrid ada di `docs/experiments.md`.

**Yang bikin bingung:** re-ingest diperlukan karena struktur collection berubah. Di sinilah disk cache dari Tahap 3 terbayar — embedding dense-nya tidak dihitung ulang.

---

## Tahap 7 — Reranking

**Yang baru:** cross-encoder.

- `BAAI/bge-reranker-v2-m3`, jalan lokal di CPU
- Ambil top-20 dari retrieval, rerank jadi top-5
- Ukur `recall@5` sebelum dan sesudah, plus tambahan latency-nya

**Ini eksperimen #3.**

**Selesai kalau:** kamu bisa menjawab "reranker menaikkan recall@5 sebesar sekian, dengan ongkos sekian milidetik".

**Yang bikin bingung:** model reranker di-download sekali dan lumayan besar. Di Docker, pastikan dia di-cache supaya tidak diunduh ulang tiap build.

**Catatan:** setelah tahap ini, kualitas retrieval kamu sudah mendekati final. Tahap-tahap berikutnya soal arsitektur dan keandalan, bukan soal kualitas pencarian.

---

# AGENTIC

## Tahap 8 — Jadi API

**Yang baru:** FastAPI, Pydantic response model, Swagger.

- `POST /api/v1/query`, `GET /health`, `GET /documents`
- Response terstruktur: `answer`, `citations`, `execution_time_seconds`
- Container kedua di `docker-compose.yml` untuk API
- Swagger hidup di `/docs`

**Kenapa API dulu sebelum LangGraph:** setelah ini permukaan API-mu tidak berubah lagi. Waktu isi dalamnya diganti jadi graph di Tahap 9, kamu bisa membandingkan hasil sebelum dan sesudah lewat endpoint yang sama. Perubahan besar jadi jauh lebih aman.

**Selesai kalau:** `docker compose up` di mesin bersih menyalakan Qdrant dan API sekaligus, dan Swagger bisa dipakai untuk query.

**Yang bikin bingung:** networking antar container. API memanggil Qdrant lewat nama service (`http://qdrant:6333`), bukan `localhost`.

---

## Tahap 9 — Jadi graph

**Yang baru:** LangGraph, state, percabangan.

Tidak ada fitur baru di tahap ini. Kamu cuma memindahkan yang sudah jalan ke struktur graph.

- Node: `rewrite_query`, `route_intent`, `retrieve`, `rerank`, `generate`
- State: `original_query`, `rewritten_query`, `intent`, `retrieved_chunks`, `reranked_chunks`, `answer`, `citations`
- `rewrite_query` menormalkan alias lembaga dari `app/core/entities.py` (deterministik, tanpa LLM) lalu ekspansi istilah hukum (pakai LLM)
- `route_intent` mengatur parameter retrieval berbeda per intent
- **Intent keempat: `troubleshooting`.** Pertanyaan seperti "kenapa ID
  izin saya hilang" harus dijawab FAQ, bukan pasal. Pertanyaan seperti
  "apa tingkat risiko untuk KBLI X" sebaliknya. Routing memfilter
  `source_type`
- **Evaluasi routing, gratis.** Tiap item FAQ sudah berlabel kategori,
  jadi `eval/holdout_routing.jsonl` adalah test set yang sudah jadi.
  Ukur akurasi klasifikasi `route_intent` di 50 item holdout, laporkan
  angkanya di README

Mengukur akurasi routing itu jarang ada di portofolio RAG orang lain —
kebanyakan berhenti di metrik retrieval.

**Selesai kalau:** `make eval` menghasilkan angka yang setara Tahap 7. Kalau turun, ada yang salah dalam pemindahan — perbaiki sebelum lanjut.

**Yang bikin bingung:** state di LangGraph itu satu objek yang mengalir dan diperbarui tiap node. Beda dari chain LangChain yang cuma meneruskan output. Ini yang memungkinkan Tahap 10.

---

## Tahap 10 — Verifikasi dan retry

**Yang baru:** LLM-as-a-Judge, loop dalam graph.

Sekarang baru mungkin, karena butuh struktur graph dari Tahap 9.

- Node `verify`, opt-in lewat parameter `verify: bool = false`
- Output terstruktur: `verdict`, `unsupported_claims`, `supporting_chunk_ids`, `reasoning`
- Node `mutate_strategy`: tiap retry **wajib** mengubah minimal satu parameter
- `max_retries = 2`, keras
- Catat `retry_count` dan `strategy_history` di response
- Kalau tetap gagal: kembalikan `verdict: "unsupported"` beserta chunk. Jangan halusinasi, jangan 500

**Selesai kalau:** ada satu pertanyaan yang kamu tahu jawabannya tidak ada di korpus, dan sistem menjawab "tidak didukung" dengan `strategy_history` yang menunjukkan dua percobaan berbeda.

**Yang bikin bingung:** conditional edge di LangGraph — bagaimana graph memutuskan ke node mana selanjutnya berdasarkan isi state.

---

# PRODUKSI

## Tahap 11 — Tahan banting

**Yang baru:** degraded mode, rate limiting, budget.

- **Degraded mode:** kalau kuota habis atau key tidak ada, kembalikan chunk hasil retrieval dengan `degraded_mode: true`. Jangan 500
- slowapi: rate limit per IP
- Budget harian di level aplikasi: setelah ambang tertentu, paksa degraded mode
- Cache jawaban untuk query identik
- Hard cap `max_output_tokens`
- Upload endpoint asynchronous, dilindungi API key header

**Selesai kalau:** cabut API key dari `.env`, restart, kirim query — sistem tetap mengembalikan pasal yang relevan tanpa error.

**Yang bikin bingung:** di degraded mode, embedding juga tidak bisa dipakai. Jadi jalur ini sparse-only. Reranker lokal tetap jalan.

---

## Tahap 12 — Terpantau dan terjaga

**Yang baru:** Langfuse, eval gate di CI.

- Langfuse callback handler, trace per node dengan latency dan token
- Eval Tier 1 masuk GitHub Actions, jalan di setiap PR
- Gate: turun lebih dari 5 persen dari `eval/baseline.json` → PR diblokir
- Eval Tier 2 (RAGAS) di workflow nightly terpisah
- **Bikin satu PR yang sengaja merusak retrieval, screenshot CI merah**

**Selesai kalau:** ada screenshot PR merah yang siap masuk README, dan trace muncul di dashboard Langfuse.

**Kenapa Langfuse di sini:** data trace inilah bahan tabel benchmark di Tahap 13. Pasang sekarang supaya sempat mengumpulkan cukup request untuk p95 yang berarti.

---

## Tahap 13 — Bisa dilihat orang

**Yang baru:** deploy, benchmark, dokumentasi.

- Golden dataset dilengkapi jadi 50 pertanyaan dengan komposisi dari Bab 6
- Kalibrasi verifier: 30 sampel dilabeli manual, laporkan agreement rate
- Eksperimen #4: Gemini embedding vs `multilingual-e5-base`
- **Tabel benchmark verify on/off**: p50, p95, token, estimasi biaya, faithfulness
- Deploy ke Render atau Hugging Face Spaces
- Rekam demo GIF 60 detik, taruh di paling atas README
- README final dengan semua angka dari Bab 11 Plan v3
- Bagian "Yang sengaja tidak dibangun"

**Selesai kalau:** sembilan kriteria DoD terpenuhi.

---

## Kalau Waktu Mepet

Urutan prioritas kalau harus memotong:

**Tidak boleh dipotong:** Tahap 4 (alat ukur), Tahap 12 (CI gate), tabel benchmark di Tahap 13. Tiga ini pembeda utama.

**Boleh dikurangi:** golden dataset 30 pertanyaan alih-alih 50. Eksperimen #4 dilewat. Deploy diganti demo GIF saja.

**Boleh dilewat sama sekali:** upload endpoint asynchronous, cache jawaban, `GET /documents`.
