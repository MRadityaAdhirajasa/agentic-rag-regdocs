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
