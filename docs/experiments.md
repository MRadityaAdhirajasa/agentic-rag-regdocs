# Catatan Eksperimen

Tiap perubahan retrieval dicatat di sini dengan angka sebelum dan sesudah.
Tanpa ini, "sepertinya lebih bagus" tidak bisa dibedakan dari "kebetulan".

Semua angka dari `eval/golden.jsonl`, kelompok `expected_source_type = regulasi`.

---

## Eksperimen #1 — Pemotongan per pasal (Tahap 5)

**Pertanyaan:** apakah memotong dokumen mengikuti batas Pasal mengalahkan
pemotongan per 1000 karakter?

**Yang diubah:** hanya cara memotong dokumen regulasi. Model embedding,
korpus, jumlah pertanyaan, dan parameter pencarian tidak disentuh.

| Metrik | Karakter (Tahap 4) | Pasal (Tahap 5) | Selisih |
|---|---|---|---|
| recall@5 | 0,500 | **0,550** | **+0,050** |
| recall@10 | 0,567 | **0,667** | **+0,100** |
| MRR | **0,420** | 0,346 | **−0,074** |
| nDCG@10 | **0,458** | 0,440 | −0,018 |

| Bentuk korpus | Karakter | Pasal |
|---|---|---|
| chunk regulasi | 743 | 500 |
| median panjang chunk | ~1000 char | 1133 char |
| rata-rata halaman per chunk | 1,00 | 1,50 |
| porsi FAQ di korpus | 30% | 40% |

### Kesimpulan: menang tipis untuk cakupan, kalah untuk peringkat

**Recall naik, dan kenaikan recall@10 (+0,100) nyata.** Potongan yang
mengikuti batas pasal membawa satu aturan utuh, bukan potongan aturan yang
terpenggal di tengah kalimat.

**Tapi MRR turun 18%.** Jawaban yang benar tetap ditemukan, hanya
peringkatnya melorot. Penyebabnya bukan mutu potongan, melainkan komposisi
korpus: jumlah chunk regulasi turun 743 → 500 sementara FAQ tetap 326, jadi
porsi FAQ naik 30% → 40%. Entri FAQ itu pendek dan berbentuk pertanyaan,
secara alami dekat dengan embedding pertanyaan. Sekarang FAQ menguasai
**50% dari hasil top-5**, naik dari sebelumnya.

### Pengakuan: sebagian kenaikan recall itu artefak

Patokan ground truth adalah halaman. Chunk pasal rata-rata mencakup 1,50
halaman, chunk karakter hanya 1,00. Chunk yang lebih lebar **secara mekanis**
lebih mudah menyentuh halaman yang dicari. Jadi +0,050 pada recall@5 tidak
seluruhnya berasal dari mutu pemotongan.

MRR tidak terkena artefak ini — dia mengukur posisi, bukan cakupan. Dan MRR
turun. Itu sinyal yang lebih bersih, dan sinyalnya negatif.

### Keputusan

**Pemotongan per pasal dipertahankan**, dengan dua alasan yang berada di luar
angka di atas:

1. Sitasi naik kelas dari `hal. 77` jadi `Pasal 128-130, hal. 77-78`. Itu
   yang bisa diverifikasi pembaca, dan tidak terukur oleh recall.
2. Payload sekarang punya `bab` dan `pasal`, yang dibutuhkan Tahap 9 untuk
   routing dan Tahap 10 untuk verifikasi.

Masalah MRR dicatat sebagai utang: **desakan FAQ** adalah hal pertama yang
harus diperiksa di Tahap 6 (hybrid search) dan Tahap 9 (routing per
`source_type`), bukan sesuatu yang diperbaiki dengan mengutak-atik ukuran
potongan.

### Cacat parser yang ditemukan dan diperbaiki

Tiga hal sempat lolos dan semuanya menghasilkan sitasi palsu:

1. **`Pasal 138.`** — rujukan di akhir kalimat yang jatuh sendirian di satu
   baris, terbaca sebagai judul pasal. Regex tidak lagi memaafkan tanda baca.
2. **Bagian PENJELASAN** mengulang penomoran pasal dari 1, bentrok dengan
   batang tubuh. Sekarang dipisah, masuk korpus tanpa nomor pasal.
3. **Gabungan pasal tidak berurutan** disitasi `Pasal 138-209`. Penggabungan
   sekarang berhenti begitu nomornya melompat.

Setelah ketiganya diperbaiki, rentang pasal yang melompat: 25 → **0**.

### Yang tidak selesai

Nomor pasal di lapisan teks PDF rusak dengan berbagai pola: 0 terbaca O,
1 terbaca l/I/L. Dari 1125 penanda, 144 harus dibetulkan lewat daftar
samaran. Sekitar 22 nomor masih belum terdeteksi sebagai judul. Sesuai
anjuran roadmap, usaha di sini dibatasi waktunya dan sisanya dibiarkan —
kegagalan yang tercatat lebih berguna daripada parser yang dikejar
sempurna.

---

## Eksperimen #2 — Hybrid search: dense + BM25 lewat RRF (Tahap 6)

**Pertanyaan:** apakah menggabungkan pencarian makna (dense) dengan
pencocokan kata harfiah (BM25) mengalahkan dense saja?

**Yang diubah:** hanya cara mencari. Korpus, pemotongan, model embedding,
dan pertanyaan golden tidak disentuh. Ketiga mode diukur pada collection
yang sama persis, jadi perbandingannya bersih.

| Metrik | dense saja | sparse saja | **hybrid (RRF)** |
|---|---|---|---|
| recall@5 | 0,550 | 0,550 | 0,550 |
| recall@10 | **0,667** | 0,550 | 0,650 |
| MRR | 0,346 | 0,425 | **0,535** |
| nDCG@10 | 0,440 | 0,428 | **0,537** |

Mode `dense` menghasilkan angka yang sama persis dengan Tahap 5 — bukti
pemindahan ke named vectors tidak mengubah perilaku sisi dense.

### Kesimpulan: hybrid menang telak untuk peringkat

**MRR naik 0,346 → 0,535 (+55%).** nDCG@10 naik +22%. Dan yang lebih penting
secara cerita: **hybrid (0,535) melampaui baseline Tahap 4 (0,420)**, jadi
kemunduran peringkat akibat pemotongan per pasal tidak cuma pulih, tapi
terbayar lebih.

**Ongkosnya recall@10 turun tipis** (0,667 → 0,650). RRF menukar sedikit
cakupan di peringkat dalam dengan perbaikan besar di peringkat atas. Untuk
sistem yang menampilkan 3-5 hasil ke pengguna, itu pertukaran yang benar.

### Per pertanyaan: siapa menolong siapa

| qid | dense | sparse | hybrid | |
|---|---|---|---|---|
| g_003 | 4 | 1 | **1** | sparse menolong |
| g_007 | 2 | 1 | **1** | sparse menolong |
| g_008 | — | 1 | **1** | **dense tidak pernah menemukannya sejak Tahap 4** |
| g_002, g_006 | 1 | 2 | 1 | dense menahan posisi |
| g_004 | 3 | 4 | 4 | seri |
| g_005 | 8 | — | — | **sparse menenggelamkannya** |
| g_010 | 4 | — | 10 | **sparse menenggelamkannya** |
| g_001, g_009 | — | — | — | tidak tertolong |

Tiga membaik, dua memburuk. Yang membaik naik ke peringkat 1, yang memburuk
turun dari peringkat menengah — itu sebabnya MRR melonjak meski jumlah yang
memburuk hampir sebanyak yang membaik.

**g_008 adalah kasus contoh dari roadmap.** Pertanyaannya menyebut "PB UMKU"
secara harfiah. Dense tidak pernah menemukannya di Tahap 4, 5, maupun 6.
BM25 menaruhnya di peringkat 1 pada percobaan pertama. Penanda yang harus
cocok persis — nomor pasal, singkatan, kode KBLI — memang bukan wilayah
pencarian makna.

### Catatan teknis

- **RRF, bukan penjumlahan skor.** Skor cosine (0-1) dan BM25 (tak terbatas)
  tidak sebanding; menjumlahkannya butuh normalisasi yang selalu jadi
  tebakan. RRF membuang skor dan hanya memakai peringkat, jadi tidak ada
  bobot yang perlu disetel.
- **Penggabungan dikerjakan Qdrant**, bukan Python. Kalau digabung di sisi
  kita, dua daftar harus ditarik penuh lewat jaringan dan filter
  `source_type` diterapkan dua kali.
- **IDF dihitung Qdrant** lewat `Modifier.IDF`, supaya dasarnya seluruh
  korpus, bukan batch yang sedang diproses.
- **Ingest ulang: nol request embedding.** Susunan collection berubah
  (vektor tunggal jadi dua vektor bernama), tapi teks chunk-nya tidak, jadi
  seluruh sisi dense diambil dari cache Tahap 3. Ini panen yang dijanjikan
  roadmap.

### Batasan yang disadari

**BM25 kita berjalan tanpa stemming.** Bahasa Indonesia tidak ada di
py-rust-stemmers — bukan kekurangan fastembed. Akibatnya "perizinan" dan
"izin" dianggap kata berbeda. Itu melemahkan sisi sparse untuk pertanyaan
bahasa sehari-hari, tapi tidak mengganggu tugas utamanya: mencocokkan
penanda yang memang harus persis.

Kalau suatu saat perlu diperbaiki, jalurnya Sastrawi (stemmer Bahasa
Indonesia) di tahap tokenisasi — bukan mengganti BM25.

---

## Eksperimen #3 — Reranking cross-encoder (Tahap 7)

**Pertanyaan:** apakah membaca ulang 20 kandidat teratas dengan cross-encoder
memperbaiki hasil, dan berapa ongkos waktunya?

**Yang diubah:** hanya langkah terakhir. Korpus, pemotongan, dan pencarian
hybrid tidak disentuh — kandidat yang sama persis, cuma disusun ulang.

| | recall@5 | recall@10 | MRR | nDCG@10 | ms/pertanyaan |
|---|---|---|---|---|---|
| hybrid saja (Tahap 6) | 0,550 | 0,650 | 0,535 | 0,537 | **26** |
| **+ rerank 20 kandidat** | **0,583** | **0,767** | **0,567** | **0,564** | **4.526** |

Memuat model: 1,4 detik, sekali per proses. Sisanya murni waktu hitung.

### Kesimpulan: mutu naik, ongkosnya 175 kali lipat

**recall@10 naik 0,117** — kenaikan terbesar dari ketiga eksperimen sejauh
ini. MRR dan nDCG juga naik. Tidak ada metrik yang turun.

**Tapi waktunya 26 ms jadi 4.526 ms.** Pencariannya sendiri cuma 26 ms;
reranking memakan 99,4% dari total. Untuk 20 kandidat sepanjang ~1.100
karakter di CPU, itu sekitar 225 ms per pasangan pertanyaan-dokumen.

### Mencoba menekan ongkos — dan gagal

| kandidat | teks | recall@5 | recall@10 | MRR | ms |
|---|---|---|---|---|---|
| 20 | penuh | 0,583 | **0,767** | **0,567** | 4.526 |
| 20 | 600 char | 0,533 | 0,667 | 0,378 | 1.773 |
| 10 | penuh | **0,650** | 0,650 | 0,520 | 2.037 |
| 10 | 600 char | 0,450 | 0,650 | 0,387 | 887 |
| 20 | 300 char | 0,500 | 0,600 | 0,346 | 1.086 |

**Memotong teks merusak, bukan menghemat.** Ketiga varian potong punya MRR
jauh di bawah tanpa rerank sama sekali (0,535). Cross-encoder bekerja justru
karena membaca pertanyaan dan dokumen utuh berbarengan; memotong dokumennya
membuang persis kemampuan yang kita bayar mahal.

Mengurangi kandidat jadi 10 memangkas waktu separuh dan recall@5-nya
tertinggi — tapi lihat peringatan di bawah sebelum menyimpulkan itu menang.

### Peringatan: 10 pertanyaan terlalu sedikit untuk membedakan ini

Satu pertanyaan menyumbang sampai 0,1 pada recall. Jadi selisih 0,583 vs
0,650 itu **kurang dari satu pertanyaan** — tidak bisa dibedakan dari
kebetulan. Yang cukup besar untuk dipercaya cuma dua: kenaikan recall@10
(+0,117, lebih dari satu pertanyaan) dan kerusakan akibat memotong teks
(MRR anjlok ~0,15 di ketiga varian, konsisten arahnya).

Golden dataset dinaikkan jadi 50 pertanyaan di Tahap 13. Sampai saat itu,
angka dengan selisih di bawah 0,1 dibaca sebagai "kira-kira sama".

### Keputusan

**Reranking dinyalakan secara bawaan, dengan 20 kandidat dan teks penuh** —
sesuai roadmap, dan karena tidak ada metrik yang turun.

Tapi ongkos 4,5 detik dicatat sebagai utang yang harus dibayar di
**Tahap 11**: di situ ada budget dan degraded mode, dan reranking adalah
kandidat pertama untuk dimatikan saat sistem perlu cepat. Saklarnya sudah
ada sekarang (`rerank=False` / `--tanpa-rerank`), jadi Tahap 11 tinggal
memakainya, bukan membangunnya.

### Catatan model

Roadmap meminta `BAAI/bge-reranker-v2-m3`. Model itu tidak tersedia lewat
fastembed, dan memasangnya berarti menambah PyTorch (~2 GB) demi satu
fungsi. Yang dipakai `jinaai/jina-reranker-v2-base-multilingual` (1,1 GB,
ONNX) — sama-sama multilingual, dan fastembed sudah terpasang sejak Tahap 6.
`BAAI/bge-reranker-base` yang juga tersedia sengaja dilewati: dia dilatih
untuk Mandarin dan Inggris, bukan multilingual.

Skornya logit dan wajar bernilai negatif. Yang berarti selisih antar
kandidat, bukan nilai mutlaknya.

---

## Tahap 9 — Pindah ke graph, dan akurasi routing

### Pemindahan ke LangGraph: tidak ada yang hilang

Kriteria roadmap untuk tahap ini bukan "angkanya naik", melainkan **"angkanya
setara Tahap 7. Kalau turun, ada yang salah dalam pemindahan."**

| Metrik | Tahap 7/8 (pemanggilan fungsi) | Tahap 9 (lewat graph) |
|---|---|---|
| recall@5 | 0,583 | 0,583 |
| recall@10 | 0,767 | 0,767 |
| MRR | 0,567 | 0,567 |
| nDCG@10 | 0,564 | 0,564 |

Identik. Pemindahan bersih.

Catatan jujur: tak satu pun dari 10 pertanyaan golden diklasifikasi
`troubleshooting`, jadi filter routing tidak pernah aktif selama evaluasi ini.
Yang terbukti di sini cuma bahwa graph tidak merusak apa pun — bukan bahwa
routing membantu. Routing diukur terpisah di bawah.

### Akurasi routing: 70,0% (35/50)

| seharusnya \ tebakan | lookup | troubleshooting |
|---|---|---|
| **lookup** (28) | **26** | 2 |
| **troubleshooting** (22) | 13 | **9** |

`lookup` hampir tidak pernah salah (93%). `troubleshooting` terlewat 13 dari
22 — model terlalu enggan menyebut sesuatu sebagai keluhan aplikasi.

### Label "gratis" ternyata tidak gratis

Roadmap menyebut holdout ini test set yang sudah jadi, karena tiap item FAQ
sudah berlabel kategori. Ternyata tidak.

**Percobaan pertama menghasilkan akurasi 16,7%** — dan yang salah label kita,
bukan modelnya. Kategori FAQ menandai **topik**, bukan **maksud**. Kategori
"Proses Perizinan Berusaha" ternyata berisi 81 dari 147 item yang isinya
langkah-langkah aplikasi, sedangkan "Layanan Informasi" yang tadinya dilabeli
`troubleshooting` justru paling sedikit menyentuh antarmuka (79 dari 97 tidak
menyebutnya sama sekali). Pemetaan awal salah di kedua arah.

Label lalu diturunkan ulang dari isi jawaban: yang menyebut elemen antarmuka
dua kali atau lebih (klik, menu, tombol, ikon, tautan) dianggap
`troubleshooting`. Aturan ini lexical dan tidak melibatkan LLM, jadi tetap sah
dipakai menilai LLM — tapi ini **label perak, bukan emas**.

### Sebagian kesalahan tidak mungkin dimenangkan

Label diturunkan dari **jawaban**, sedangkan router hanya melihat
**pertanyaan**. Dua contoh dari daftar ketidaksepakatan:

- `faq-fkfp-003` "Bagaimana cara mengajukan Tax Holiday?" — dilabeli
  `troubleshooting` semata karena jawabannya berisi langkah di aplikasi. Dari
  pertanyaannya saja, `lookup` adalah jawaban yang wajar. **Tidak mungkin
  ditebak benar.**
- `faq-maa-037` "Saya terkendala gagal input NPWP 16 digit" — jelas keluhan
  dari pertanyaannya saja. Ini **kesalahan model yang sebenarnya.**

Jadi 70% itu mencampur dua hal berbeda: batas atas yang ditentukan cara
melabeli, dan kekurangan prompt. Memisahkan keduanya butuh pelabelan manual
22 item, dan itu ditunda.

### Perbaikan yang sudah terdiagnosis, belum dikerjakan

Prompt mendefinisikan `troubleshooting` sebagai "keluhan pemakaian aplikasi".
Sebagian besar yang terlewat berbentuk "bagaimana cara [melakukan X di
sistem]" — prosedural di aplikasi, bukan keluhan. Definisi di prompt lebih
sempit daripada definisi di label.

Tidak diperbaiki sekarang dengan sengaja: menyetel prompt sambil melihat
daftar kesalahannya adalah cara tercepat membuat angka naik tanpa sistemnya
membaik. Perbaikan ini dikerjakan saat golden dataset dilengkapi di Tahap 13,
bersama pelabelan manual yang layak.

### Ongkos yang baru muncul

Routing menambah **satu panggilan LLM per pertanyaan**. Kuota harian Gemini
habis di tengah pengukuran pertama — 28 dari 50 item. Sejak itu `route_intent`
punya jalur mundur: kalau LLM gagal, intent jatuh ke `lookup` tanpa filter,
dan permintaan tetap dilayani. Degraded mode yang sebenarnya dibangun di
Tahap 11.

### Bug yang ditemukan: alias diperluas dua kali

`normalisasi()` awalnya mengganti alias satu per satu. Hasilnya, "PB-UMKU"
berubah jadi "PB UMKU (Perizinan Berusaha untuk Menunjang Kegiatan Usaha)",
lalu potongan "PB UMKU" di dalamnya tertangkap alias berikutnya dan diperluas
lagi. Sekarang seluruh penggantian dilakukan dalam satu kali jalan, sehingga
teks yang baru disisipkan tidak ikut terpindai.

---

## Tahap 10 — Verifikasi dan percobaan ulang

Tidak ada eksperimen bernomor di sini: yang ditambahkan kemampuan baru, bukan
perubahan cara mencari. Angka retrieval tidak berubah (0,583 / 0,767 / 0,567 /
0,564), dan memang tidak seharusnya berubah — `verify` bekerja **setelah**
jawaban tersusun.

### Kriteria roadmap: terpenuhi

> Ada satu pertanyaan yang kamu tahu jawabannya tidak ada di korpus, dan
> sistem menjawab "tidak didukung" dengan `strategy_history` yang menunjukkan
> dua percobaan berbeda.

```
question    : berapa tarif pajak penghasilan badan di Indonesia
verdict     : unsupported
retry_count : 2
answer      : Tidak tahu.
sitasi      : 2 (tetap dikembalikan)
strategy_history:
  #1 lebarkan: buang filter sumber, gandakan top_k
  #2 kembali ke pertanyaan asli tanpa perluasan alias
```

Tidak mengarang, tidak 500, dan potongan yang sempat ditemukan tetap
dikembalikan supaya penanya bisa menilai sendiri.

### Ongkos: tiga jalur, tiga harga

| | detik | panggilan LLM |
|---|---|---|
| `verify: false` (bawaan) | 4,9 | 2 |
| `verify: true`, jawaban didukung | 12,2 | 3 |
| `verify: true`, di luar korpus (2 percobaan) | 24,7 | 4 |

Batas atasnya 7 panggilan kalau tiap percobaan ulang tetap menghasilkan klaim
yang perlu dinilai. Karena itu verifikasi opt-in, bukan bawaan.

### Taksonomi yang sempat salah

Percobaan pertama, penilai menyatakan **`supported`** untuk jawaban "Tidak
tahu." — dan secara logika dia benar: penolakan itu memang didukung konteks.
Yang salah taksonomi kita, yang mencampur dua hal berbeda:

1. jawaban mengarang (buruk)
2. korpus tidak memuat jawabannya (bukan salah jawabannya)

Perbaikannya sekaligus menghemat kuota: **penolakan dikenali tanpa memanggil
LLM sama sekali.** Frasa "tidak tahu" itu kita sendiri yang perintahkan lewat
prompt penyusun jawaban, jadi mencocokkannya bukan tebakan atas bahasa bebas
model. Jalur yang paling sering diulang justru jadi jalur yang paling murah.

### Aturan "wajib berubah" ditegakkan kode, bukan komentar

Roadmap menuntut tiap percobaan ulang mengubah minimal satu parameter.
`mutate_strategy` membandingkan parameter sebelum dan sesudah, lalu melempar
error kalau sama. Ada test yang sengaja memancing keadaan itu — kalau suatu
saat aturan mutasinya diubah dan jadi mandul, test-nya yang berteriak, bukan
kuota yang diam-diam habis.

### Cacat kosmetik yang ketahuan lewat API

`supporting_chunk_ids` memunculkan `pp-28-2025:pNone:464`. Chunk pembukaan dan
penjelasan tidak punya nomor pasal, dan `None`-nya ikut tercetak sejak Tahap 5
— tidak terlihat selama id itu hanya dipakai di dalam sistem. Sekarang
penanda babnya yang dipakai: `pp-28-2025:pembukaan:0`. Ingest ulang nol
request, karena teksnya tidak berubah.

---

## Tahap 11 — Tahan banting

Tidak ada eksperimen bernomor: angka retrieval tidak berubah (0,583 / 0,767 /
0,567 / 0,564). Yang ditambahkan perilaku saat sesuatu rusak.

### Kriteria roadmap: terpenuhi

> Cabut API key dari `.env`, restart, kirim query — sistem tetap mengembalikan
> pasal yang relevan tanpa error.

Kedua key dikosongkan, container dibuat ulang:

```
HTTP 200
degraded_mode : true
degraded_reason:
  - routing:   GOOGLE_API_KEY tidak tersedia: key kosong di .env
  - embedding: OPENROUTER_API_KEY tidak tersedia: key kosong di .env
  - generate:  GOOGLE_API_KEY tidak tersedia: key kosong di .env

[1] PP 28/2025, Pasal 227, hal. 127
    (1) Sebelum melakukan kegiatan usaha yang termasuk ke dalam tingkat
    Risiko tinggi, Pelaku Usaha wajib memiliki NIB ...
```

Pasal 227 memang jawaban yang benar untuk pertanyaan itu — dan ditemukan
**tanpa embedding sama sekali**. Seperti diperingatkan roadmap, jalur ini
sparse-only; BM25 dan reranker dua-duanya jalan di komputer sendiri.

### Tiga pintu, tiga jalur mundur

| Yang mati | Akibat | Yang tetap jalan |
|---|---|---|
| Embedding (OpenRouter) | sisi dense hilang | BM25 + reranker, pasal tetap keluar |
| Routing (Gemini) | intent jatuh ke `lookup` tanpa filter | seluruh korpus tetap dicari |
| Penyusun jawaban (Gemini) | kalimat jawaban hilang | sitasi dan kutipan mentah tetap dikembalikan |

Saat routing buta, filter sengaja **dibuang**, bukan ditebak. Menebak filter
berarti membuang sumber yang mungkin justru berisi jawabannya.

Saat penyusun jawaban mati, sistem **tidak merangkai kalimat sendiri** —
hanya mengutip apa adanya. Merangkai tanpa model berisiko menyiratkan
kesimpulan yang tidak ada di teksnya, dan itu lebih berbahaya daripada
menyerahkan kutipan mentah ke pembaca.

### `SystemExit` yang harus diganti

Sejak Tahap 3, kuota embedding habis melempar `SystemExit`. Di CLI itu wajar.
Di dalam server, `SystemExit` berubah jadi 500 — persis yang dilarang tahap
ini. Sekarang ada `LayananTidakTersedia`, jenis error tersendiri, supaya
pemanggil bisa membedakan "layanan luar mati" dari "ada bug di kode kita".
Yang pertama diturunkan mutunya dengan anggun; yang kedua tetap berisik.

### Bug yang ketemu saat diuji: budget bocor

Pagar budget mula-mula cuma dipasang di `route_intent`. Hasilnya: budget
dilaporkan habis, `degraded_mode: true`, tapi jawaban **tetap tersusun** —
karena `jawab()` dan `_nilai()` tidak ikut memeriksa. Budget yang bocor di
satu pintu sama saja tidak ada budget.

Sekarang ketiga pintu ke LLM memeriksa pagar yang sama, dan ada test yang
memanggil ketiganya sekaligus supaya pintu keempat yang lupa dipagari akan
ketahuan.

Bukti setelah diperbaiki, dengan ambang sengaja disetel 2:

```
panggilan 1 : degraded=False  "Lembaga OSS."
panggilan 2 : degraded=True   "Layanan penyusun jawaban sedang tidak tersedia..."
panggilan 3 : degraded=True   "Layanan penyusun jawaban sedang tidak tersedia..."
```

### Rate limit

10 permintaan per menit per alamat IP (`RATE_LIMIT_QUERY`). Diuji dengan 13
permintaan beruntun: sepuluh pertama `200`, sisanya `429` dengan pesan yang
menyebut batasnya.

Tanpa ini, satu klien yang mengulang-ulang bisa menghabiskan kuota LLM harian
untuk semua orang dalam hitungan menit.

### Yang sengaja tidak dibangun

Roadmap sendiri menandai dua hal di tahap ini boleh dilewat, dan keduanya
dilewat: **upload endpoint asynchronous** dan **cache jawaban untuk query
identik**. Keduanya tidak menambah pelajaran baru di proyek ini, dan cache
jawaban akan mengaburkan pengukuran latensi di Tahap 13.

Batas yang disadari: hitungan budget disimpan di memori proses, jadi ikut nol
saat container dibuat ulang dan tidak dibagi antar replika. Cukup untuk satu
container; kalau nanti jalan lebih dari satu, pindahkan ke Redis.

---

## Tahap 12 — Terpantau dan terjaga

### Kendala yang menentukan seluruh rancangan gate

PDF sumber **tidak ada di repo** (tertahan `*.pdf`), dan cache embedding 29 MB
juga tidak. Artinya komputer CI tidak mungkin membangun ulang korpus dengan
vektor dense — tanpa secret, tanpa kuota, dan tanpa mengunduh apa pun.

Jalan keluarnya: bekukan korpus jadi `eval/korpus_fixture.jsonl` (829 chunk,
1,8 MB — teks dan payload saja, tanpa vektor), lalu jalankan gate pada jalur
**sparse-only tanpa reranking**. BM25 dihitung di runner dalam hitungan detik,
tidak menyentuh jaringan, dan memberi angka sama persis untuk korpus yang sama.

| | jalur utama | jalur gate CI |
|---|---|---|
| pencarian | hybrid + rerank | sparse saja |
| butuh API key | ya | **tidak** |
| butuh kuota | ya | **tidak** |
| deterministik | tidak sepenuhnya | **ya** |
| recall@5 | 0,583 | 0,550 |
| MRR | 0,567 | 0,425 |

**Gate ini tidak menjaga mutu sisi dense.** Yang dijaganya: penulisan ulang
pertanyaan, pencocokan kata harfiah, logika pencarian, susunan payload, dan
perhitungan metrik. Dari pengalaman sebelas tahap, di situlah kerusakan paling
sering masuk tanpa disadari.

### Gate terbukti merah

Kerusakan disengaja — seseorang "merapikan" `search_many` dan memangkas jumlah
kandidat:

```
metrik        baseline  sekarang   selisih   status
recall@5         0.550     0.450    -0.100   GAGAL
recall@10        0.550     0.450    -0.100   GAGAL
mrr              0.425     0.400    -0.025   GAGAL
ndcg@10          0.428     0.402    -0.026   GAGAL

GATE GAGAL — turun lebih dari 5%
exit code: 1
```

Pesannya ikut menyebutkan cara memperbarui baseline, supaya penurunan yang
memang disengaja tidak berubah jadi teka-teki.

### Celah yang diakui dan ditutup

Karena fixture-nya beku, perubahan pada pemotong dokumen **tidak** terlihat
oleh gate sampai fixture dibuat ulang. Celah ini ditutup dari sisi lain:
`tests/test_fixture.py` membandingkan fixture dengan hasil pemotong sekarang,
dan gagal kalau jumlah atau urutan `chunk_id`-nya berbeda. Test itu dilewati
otomatis di CI — di sana tidak ada PDF untuk dibandingkan.

Diuji dengan sengaja memotong lima baris terakhir fixture: test-nya gagal,
lalu lolos lagi setelah `make fixture`.

### Latensi per node — bahan Tahap 13

Tiap node graph dibungkus pengukur waktu, dan angkanya ikut di respons API.
Median dari tiga permintaan, `verify: false`:

| node | median ms | |
|---|---|---|
| rerank | **5.154** | dominan, sesuai eksperimen #3 |
| generate | 1.630 | |
| route_intent | 1.166 | |
| retrieve | 650 | |
| rewrite_query | 0 | deterministik, tanpa LLM |

Satu koreksi yang layak dicatat: pengukuran pertama menunjukkan
`route_intent` 5.749 ms, dan itu **salah dibaca** — angkanya termasuk
pemanasan klien Gemini pada panggilan pertama proses. Setelah diulang tiga
kali, mediannya 1.166 ms. Pelajarannya: satu sampel bukan pengukuran.

### Audit instrumentasi terhadap panduan resmi Langfuse

Panduan `skills/langfuse/references/instrumentation.md` dibaca **sebagai
bahan**, bukan dipasang sebagai skill yang mengarahkan perilaku agen.
Berkas semacam itu adalah instruksi dari luar percakapan; yang benar adalah
menilai isinya lalu menerapkannya sendiri dengan alasan yang bisa dijelaskan.

Hasil audit terhadap daftar syarat mereka — lima cacat nyata di versi pertama:

| Syarat | Versi pertama | Sesudah |
|---|---|---|
| Nama trace deskriptif | ok | ok |
| Input/output eksplisit | ok | ok |
| `flush()` dipanggil | ok | ok |
| Import setelah `load_dotenv` | ok | ok |
| **Span bersarang** | span anak jadi **saudara**, bukan anak | bersarang lewat context OpenTelemetry |
| **Durasi span** | **semua nol**, angka asli cuma di metadata | durasi sebenarnya |
| **Tipe observasi** | semuanya `span` | `retriever`, `evaluator`, `chain`, `generation`, `tool` |
| **Nama model** | tidak dicatat | dicatat per panggilan |
| **Jumlah token** | tidak dicatat | input/output/total, jadi biaya terhitung |

Yang paling parah yang kedua. Versi pertama menyusun span **setelah** semua
node selesai, jadi tiap span dibuka dan ditutup pada saat yang sama —
Langfuse akan menampilkan durasi nol untuk semuanya, dan seluruh gunanya
(melihat langkah mana yang lambat) hilang. Sekarang span dibuka sebelum node
jalan dan ditutup sesudahnya.

Tiga panggilan LLM ditandai `generation` dengan nama sendiri —
`klasifikasi-intent`, `susun-jawaban`, `nilai-jawaban` — masing-masing membawa
nama model dan jumlah token.

### Self-audit trace: dijalankan, dan menemukan dua bug lagi

Panduan Langfuse menuntut trace ditarik kembali lalu diperiksa, bukan
diasumsikan benar. Dijalankan setelah key dipasang, dan hasilnya dua cacat
yang tidak akan pernah terlihat dari membaca kode:

**1. Span akar tidak pernah terkirim.** `flush()` dipanggil di dalam blok span
akar, jadi pengiriman jalan saat span itu belum berakhir. Trace muncul tanpa
nama dan tanpa metadata — node-nodenya seolah melayang tanpa induk. Sekarang
`flush()` dipanggil setelah blok ditutup.

**2. Pembungkus error merusak propagasi exception.** `try/except` melingkupi
`yield` di context manager, jadi error dari node tertangkap di titik yield,
generator melanjutkan, dan Python melempar `RuntimeError: generator didn't
stop after throw()` — menutupi error yang sebenarnya. Sekarang hanya
*pembuatan* observasi yang dijaga, bukan isinya. Ada test regresinya.

Cacat kedua ditemukan oleh test, bukan oleh mata. Cacat pertama hanya bisa
ditemukan dengan benar-benar menarik trace-nya kembali.

Satu koreksi terhadap laporan awal saya: nama dan metadata tingkat trace
sempat terlihat kosong, dan saya sempat menyebutnya bug kedua. Ternyata
bukan — Langfuse mengisinya belakangan dari span akar, dan pembacaan saya
terlalu cepat. Yang benar-benar rusak cuma urutan `flush()`.

### Bentuk trace setelah diperbaiki

```
tanya-regdocs         AGENT       10.34s   metadata: intent, verdict, retry_count
  rewrite_query       SPAN         0.00s   in: query           out: rewritten, alias
  route_intent        CHAIN        1.36s   in: query           out: intent, source_type
    klasifikasi-intent  GENERATION 1.33s   model + token
  retrieve            RETRIEVER    0.18s   in: query, filter   out: chunk_ids
  rerank              TOOL         5.21s   in: jumlah kandidat out: chunk_ids
  generate            CHAIN        1.90s   in: chunk_ids       out: answer
    susun-jawaban       GENERATION 1.87s   model + token
  verify              EVALUATOR    1.68s   in: answer          out: verdict, klaim
    nilai-jawaban       GENERATION 1.65s   model + token
```

Input dan output tiap node ikut dicatat. Tanpa itu, span cuma batang berwarna
dengan durasi; dengan itu, trace bisa menjawab pertanyaan yang sebenarnya:
**konteks apa yang dipegang sistem waktu mengambil keputusan itu.**

### Yang terlihat begitu trace-nya jalan

Satu permintaan dengan dua percobaan ulang terekam utuh: `retrieve → rerank →
generate → verify` muncul tiga kali, dengan `mutate_strategy` di antaranya.
Dari situ langsung terbaca dua hal yang sebelumnya cuma dugaan:

- **Percobaan ulang didominasi reranking, bukan LLM.** Tiga kali rerank
  memakan ~18 detik dari 23 detik total. Panggilan LLM-nya justru murah.
- **Retry benar-benar menyelamatkan jawaban.** Pada satu permintaan lewat API,
  percobaan 1 dan 2 menjawab "Tidak tahu" (`verify 0 ms` — penolakan dikenali
  tanpa memanggil LLM), lalu percobaan 3 dengan filter dilebarkan menemukan
  jawabannya: `verdict: supported`, `retry_count: 2`.

Keduanya bahan langsung untuk tabel benchmark Tahap 13.

### Jebakan env yang ditulis panduan mereka, dan saya tabrak juga

Daftar "Common Mistakes" Langfuse memuat: *"Langfuse import before env vars
loaded."* Saya membacanya, lalu tetap melakukannya — `app/core/tracing.py`
membaca `os.getenv` di tingkat modul, padahal `load_dotenv()` ada di
`app/core/config.py`. Modul mana yang diimpor duluan menentukan hasilnya, dan
key terbaca kosong padahal `.env`-nya benar.

Ini sekaligus melanggar aturan arsitektur proyek ini sendiri, yang sejak
Tahap 1 tertulis di `config.py`: *"satu-satunya tempat yang membaca .env"*.
Sekarang nilai Langfuse ikut dibaca di sana.

Ditambah: dokumentasi Langfuse memakai `LANGFUSE_BASE_URL`, sedangkan kode
memakai `LANGFUSE_HOST`. Keduanya sekarang diterima, yang baru didahulukan.
Region host wajib sama dengan asal key — kalau beda, key ditolak, dan itu
penyebab paling umum "sudah diisi tapi trace tidak muncul".

### Langfuse: opsional, dan alasannya

Trace dikirim ke Langfuse hanya kalau `LANGFUSE_PUBLIC_KEY` dan
`LANGFUSE_SECRET_KEY` disetel. Tanpa keduanya, modul pemantauan diam total dan
tidak menambah satu milidetik pun — sudah diuji.

Keputusan yang disengaja: **angka latensi hidup di respons API lebih dulu,
Langfuse jadi tempat menumpuknya.** Alasan Langfuse ada di roadmap adalah
sebagai bahan tabel benchmark Tahap 13; menaruh angkanya di respons membuat
bahan itu tetap ada meski dashboard-nya tidak pernah dipasang.

Pengiriman ke Langfuse dibungkus try/except yang menelan error: pemantauan
yang menjatuhkan permintaan adalah pemantauan yang salah.

### Yang sengaja tidak dibangun: eval Tier 2 (RAGAS)

Roadmap menyebut RAGAS di workflow nightly terpisah. Dilewat, dengan alasan
yang bisa dihitung: RAGAS menilai pakai LLM, dan satu kali jalan atas 10
pertanyaan memakan puluhan panggilan. Kuota harian proyek ini 50 request
embedding dan kuota Gemini gratis yang sudah pernah habis di Tahap 9. Nightly
RAGAS berarti kuota harian habis sebelum hari kerja dimulai.

Yang menggantikannya di Tahap 13: kalibrasi verifier secara manual atas 30
sampel, yang menghasilkan angka agreement rate — lebih sedikit otomatis, tapi
angkanya bisa dipertanggungjawabkan.

---

## Tahap 13 — Angka akhir

### Golden dataset: 10 -> 30 pertanyaan

| kategori | jumlah | expected_source_type |
|---|---|---|
| `lookup_faktual` | 16 | regulasi |
| `komparatif` | 5 | regulasi |
| `alias_lembaga` | 2 | regulasi |
| `lookup_teknis` | 3 | faq |
| `negatif` | 4 | none |

Asal pertanyaan: 14 parafrase dari FAQ, 10 dari membaca dokumen, 6 dikarang
sendiri. Roadmap mengizinkan 30 alih-alih 50 kalau waktu mepet, dan itu yang
diambil — menambah pertanyaan tanpa ground truth yang diverifikasi justru
menurunkan mutu dataset.

### Angkanya bertahan di korpus soal 2,3 kali lebih besar

| Metrik (`regulasi`) | 10 soal (Tahap 4-12) | 23 soal (Tahap 13) |
|---|---|---|
| recall@5 | 0,583 | **0,580** |
| recall@10 | 0,767 | 0,725 |
| MRR | 0,567 | 0,526 |
| nDCG@10 | 0,564 | 0,552 |

Ini pengujian yang sebenarnya atas seluruh angka sebelumnya: **recall@5
bergeser 0,003.** Angka Tahap 4 sampai 12 bukan kebetulan dari sepuluh soal
pilihan.

Kelompok `faq` (3 soal) mendapat recall@5 **1,000** — dan itu memang
optimistis, karena pertanyaannya parafrase dari entri yang ada di dalam
korpus. Dilaporkan terpisah, tidak pernah digabung ke angka utama.

### Tabel benchmark: verify on/off

30 pertanyaan, dijalankan dua kali. Ini yang roadmap tandai tidak boleh
dipotong.

| | verify OFF | verify ON |
|---|---|---|
| latensi p50 | **8.581 ms** | **10.794 ms** |
| latensi p95 | 13.923 ms | **27.203 ms** |
| latensi rata-rata | 8.990 ms | 12.642 ms |
| panggilan LLM / pertanyaan | 2,0 | 2,97 |
| token / pertanyaan | 1.257 | 2.881 |
| biaya USD / 1.000 pertanyaan | **0,434** | **0,927** |
| total percobaan ulang | 0 | 10 |
| faithfulness | — | **0,852** |
| negatif dijawab "tidak tahu" | **4/4** | **4/4** |

Biaya dihitung dengan harga tier berbayar `gemini-3.1-flash-lite`
(USD 0,25 per 1 juta token input, USD 1,50 output). Proyek ini jalan di tier
gratis; angka itu menjawab "kalau dibayar, berapa?" — bukan tagihan.

**Yang dibeli dengan verifikasi:** faithfulness terukur 0,852 dan 10 kali
percobaan ulang yang sebagian berhasil menyelamatkan jawaban.

**Harganya:** p50 naik 26%, tapi **p95 naik 95%** — dari 13,9 detik jadi 27,2
detik. Rata-rata menyembunyikan itu; ekor distribusinya yang terpukul, karena
percobaan ulang jatuh pada pertanyaan yang memang sulit. Biaya per seribu
pertanyaan naik dua kali lipat, tapi tetap di bawah satu dolar.

**Temuan yang paling tidak disangka: kategori negatif dijawab benar 4/4 pada
kedua mode.** Sistem menolak pertanyaan di luar korpus **tanpa** perlu
verifikasi — prompt penyusun jawaban sudah cukup. Verifikasi tidak
memperbaiki angka itu; yang dia tambahkan adalah `verdict` yang bisa dibaca
mesin, bukan penolakan yang lebih baik.

### Kalibrasi verifier: 92,3% dan 96,2%

26 sampel (13 pasang; 4 pertanyaan dilewati karena jawabannya penolakan).
Dijalankan dua kali, dan **dua angkanya berbeda** — itu sendiri informasi.

| jalan | agreement | jawaban asli | jawaban disisipi karangan |
|---|---|---|---|
| pertama | 24/26 = **92,3%** | 12/13 `supported` | 12/13 `partial` |
| kedua | 25/26 = **96,2%** | 13/13 `supported` | 12/13 `partial` |

**Seluruh selisihnya berasal dari kegagalan rate limit**, bukan dari salah
nilai. Ketidaksepakatan di kedua jalan selalu berupa `gagal_diverifikasi` —
penilai tidak pernah sempat memberi pendapat. Dari sampel yang benar-benar
dinilai: **24/24 dan 25/25.**

Yang dilaporkan sebagai angka resmi adalah **yang lebih rendah, 92,3%**. Dan
sebaran dua jalan ini lebih berguna daripada satu angka: dia menunjukkan
ketidakpastian pengukuran datang dari infrastruktur, bukan dari model.

Yang menarik: karangan selalu ditandai `partial`, tidak pernah `unsupported`.
Itu justru tepat — jawaban aslinya memang didukung, hanya kalimat sisipannya
yang tidak. Verifier membedakan "sebagian ngawur" dari "seluruhnya ngawur".

Karangan yang tidak tertangkap berbeda tiap jalan (`g_010` lalu `g_007`), dan
keduanya kebetulan sampel yang penilaiannya gagal — bukan karangan yang
berhasil mengelabui.

**Batas yang wajib ikut dilaporkan:** label di sini **dibangun**, bukan
dilabeli tangan, dan karangan yang disisipkan kasar dan mencolok. Angka 92,3%
adalah batas **atas** — belum membuktikan verifier sanggup menangkap
halusinasi halus seperti angka yang meleset sedikit atau nomor pasal yang
keliru satu digit.

### Degraded mode terbukti di bawah beban nyata

Selama benchmark 60 permintaan, kuota Gemini beberapa kali menolak:

```
verify gagal, dilewati: ClientError
route_intent mundur ke lookup: ClientError
generate turun ke kutipan mentah: ClientError
```

**Tidak satu pun permintaan gagal.** Benchmark selesai penuh 30/30 di kedua
mode. Jalur mundur Tahap 11 tidak diuji dengan simulasi di sini — dia diuji
oleh keadaan sungguhan, tanpa direncanakan.
