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
