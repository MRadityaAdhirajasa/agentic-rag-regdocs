# Agentic RAG — Regulasi Perizinan Berusaha

Mencari satu ketentuan di PP 28/2025 berarti menyisir lebih dari 300 halaman, dan
jawaban dari chatbot biasa tidak bisa dipakai kalau tidak jelas pasalnya yang mana.
Sistem ini menjawab pertanyaan dalam Bahasa Indonesia, lalu menyertakan **sitasi
sampai nomor pasal dan halaman** supaya pembaca bisa membuka PDF aslinya dan
memeriksa sendiri.

---

![Dashboard regdocs](ScreenShot/dashboard.png)

Jalur graph, lama tiap node, dan jumlah panggilan LLM ikut di setiap jawaban,
terlipat di bawah daftar sumber.

![Alur LangGraph](docs/graph.svg)

Graph-nya **berputar**: `verify` menilai jawaban yang baru dibuat, dan kalau
tidak didukung konteks, alurnya kembali ke `retrieve` dengan parameter yang
wajib berbeda. Bentuk di atas diambil dari graph yang dikompilasi, bukan
digambar tangan.

---

## Stack

| Teknologi | Perannya di sini |
|---|---|
| **LangGraph** | Orkestrasi 7 node dengan *conditional edge*, sehingga alurnya bisa mengulang, bukan cuma lurus |
| **Qdrant** | Basis data vektor. Satu titik membawa dua vektor bernama (`dense` + `sparse`) supaya penggabungan RRF dikerjakan servernya |
| **OpenRouter** · `nemotron-3-embed-1b` | Embedding dense 2.048 dimensi untuk pencarian berbasis makna |
| **fastembed** | BM25 sparse + reranker cross-encoder. Keduanya jalan di CPU sendiri, tanpa API |
| **Gemini 3.1 Flash Lite** | Tiga tugas terpisah: menentukan maksud pertanyaan, menyusun jawaban, dan menilai jawaban itu |
| **FastAPI** + **Pydantic** | HTTP API, validasi, dan Swagger otomatis |
| **PyMuPDF** | Membaca lapisan teks PDF per halaman, yang membuat sitasi "hal. 83" mungkin |
| **Langfuse** | Pemantauan: tiap node jadi span bersarang dengan durasi, token, dan biaya |
| **Docker Compose** | Qdrant + API + dashboard menyala dengan satu perintah |
| **GitHub Actions** · ruff · mypy · pytest | Lint, tipe, 74 test, dan gerbang mutu retrieval di tiap PR |
| **HTML/CSS/JS statis** | Dashboard. Satu berkas, tanpa npm dan tanpa build |

---

## Cara kerja

**Korpus** 829 potongan: PP 28/2025 dipotong **per pasal** (bukan per sekian
karakter, supaya batas potongan sama dengan batas hukumnya) dan 6 berkas FAQ OSS.

**Pencarian hybrid.** Sisi dense menangkap maksud; sisi BM25 menangkap penanda
yang harus persis seperti `Pasal 227`, `NIB`, atau `KBLI 47111`. Qdrant
menggabungkan keduanya lewat RRF, lalu cross-encoder membaca ulang 20 kandidat
teratas dan menyusunnya kembali.

**Routing.** Pertanyaan diklasifikasi lebih dulu. Keluhan seperti *"kenapa NIB
saya belum terbit?"* disaring ke FAQ saja, karena pertanyaan seperti itu tidak
akan pernah terjawab oleh pasal.

**Verifikasi.** Opsional. Jawaban dinilai LLM lain terhadap potongan yang
dipakai menyusunnya, dan percobaan ulang **wajib mengubah minimal satu
parameter** atau kodenya melempar error.

---

## Hasil, gambaran besar

| | |
|---|---|
| Mutu retrieval | recall@5 **0,58**, recall@10 **0,73** pada 30 pertanyaan golden |
| Dampak reranking | recall@10 naik **0,117**, ongkosnya ~4,5 detik per pertanyaan |
| Akurasi routing | **70%** pada 50 item holdout yang tidak pernah dipakai melatih apa pun |
| Kalibrasi verifier | **92,3%** setuju dengan label yang dibangun, bukan dilabeli tangan |
| Biaya | **USD 0,43** per 1.000 pertanyaan pada harga tier berbayar |
| Pertanyaan di luar korpus | **4/4** dijawab "tidak tahu", bukan dikarang |

Angka sisi FAQ sengaja dilaporkan terpisah karena optimistis secara struktural,
dan temuan yang paling tidak disangka justru negatif: **sistem sudah menolak
pertanyaan di luar korpus tanpa perlu verifikasi**, jadi yang ditambahkan
verifikasi bukan penolakan yang lebih baik, melainkan `verdict` yang bisa dibaca
mesin.

Rinciannya, lengkap dengan cara mengukurnya, ada di
[`docs/README-teknis.md`](docs/README-teknis.md) dan
[`docs/experiments.md`](docs/experiments.md).

---

## Yang membedakan

**Sitasi bisa diperiksa.** Bukan "menurut peraturan", melainkan
`PP 28/2025, Pasal 138, hal. 83`. Buka PDF-nya di halaman itu, pasalnya ada di
sana.

**Tiap perubahan diukur.** Golden dataset dan metrik dibangun di Tahap 4,
sebelum satu pun perbaikan retrieval dikerjakan, supaya sembilan tahap
berikutnya jadi eksperimen yang punya hasil, bukan "kayaknya lebih bagus".

**Tidak mati saat layanan luar mati.** Embedding, routing, dan penyusun jawaban
punya jalur mundur masing-masing. Diuji dengan mengosongkan kedua API key lalu
membuat ulang container: jawabannya tetap `HTTP 200`, dan pasal yang benar tetap
muncul di peringkat satu tanpa embedding sama sekali.

**Ada gerbang mutu di CI.** Tiap PR menjalankan evaluasi retrieval dan diblokir
kalau ada metrik turun lebih dari 5%. Gate ini jalan **tanpa API key dan tanpa
kuota** karena korpusnya dibekukan dan pencariannya sparse-only.

---

## Menjalankan

```bash
docker compose up -d      # Qdrant + API + dashboard
make ingest               # regulasi + FAQ -> Qdrant
```

| Alamat | Isi |
|---|---|
| <http://localhost:8000> | dashboard |
| <http://localhost:8000/docs> | Swagger |
| `POST /api/v1/query` | `answer`, `citations`, `intent`, `verdict`, `trace`, `token` |

```bash
make chat     # tanya-jawab lewat CLI
make eval     # metrik retrieval
make test     # 74 test
```

Perlu `OPENROUTER_API_KEY` dan `GOOGLE_API_KEY` di `.env`. Tanpa keduanya sistem
tetap jalan dalam mode terbatas. Daftar perintah lengkap ada di
[`docs/README-teknis.md`](docs/README-teknis.md).

---

## Sumber data

**PP 28/2025** tentang Penyelenggaraan Perizinan Berusaha Berbasis Risiko dari
<https://jdih.bkpm.go.id>, dan **FAQ OSS BKPM** dari <https://oss.go.id>.

Peraturan perundang-undangan dikecualikan dari hak cipta berdasarkan UU 28/2014
Pasal 42. FAQ diambil dari halaman publik; sumber dan tanggal aksesnya disimpan
di payload tiap potongan dan ikut tercetak di sitasi.

---

Ini proyek belajar. Yang dikejar bukan angka setinggi mungkin, melainkan **angka
yang bisa dipertanggungjawabkan** beserta pengakuan di mana dia menyesatkan.
Sebagian besar temuan paling berguna di [`docs/experiments.md`](docs/experiments.md)
adalah kesalahan yang tertangkap, bukan kemenangan.
