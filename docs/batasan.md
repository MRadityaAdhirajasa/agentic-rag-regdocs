# Yang Sengaja Tidak Dibangun

Daftar ini bagian dari hasil, bukan permintaan maaf. Tiap baris adalah
keputusan dengan alasan yang bisa diperiksa — dan beberapa di antaranya
menyelamatkan proyek ini dari berhenti di tengah jalan.

## Korpus

**Satu peraturan, bukan lima.** Rencana awal menyebut lima dokumen inti.
Tiga di antaranya ternyata sudah dicabut, dan PP 28/2025 adalah penggantinya.
Korpus lalu dikecilkan lagi dari 3 PDF (2.903 chunk) jadi 1 PDF + FAQ (829
chunk) atas keputusan sadar: korpus besar tidak menambah satu pun pelajaran
di proyek belajar, hanya memperlambat siklus coba-ukur-perbaiki dan
menghabiskan kuota harian.

**FAQ tidak disaring.** 97 item kategori "Layanan Informasi" berisi pertanyaan
remeh yang jelas tidak berguna untuk tanya-jawab hukum. Tetap dimasukkan
sebagai **pengecoh**. Korpus tanpa pengecoh membuat recall@5 terlihat bagus
semata-mata karena tidak ada saingan.

**Berkas PDF sengaja tidak diganti nama.** `UU 28 2025 - ...pdf` sebenarnya
Peraturan Pemerintah. Namanya dibiarkan salah supaya jejak kesalahannya
terlihat, dan prinsipnya melekat: identitas dokumen dibaca dari isinya,
tidak pernah dari namanya.

## Retrieval

**BM25 tanpa stemming.** Bahasa Indonesia tidak ada di py-rust-stemmers —
keterbatasan pustakanya, bukan pilihan. Akibatnya "perizinan" dan "izin"
dianggap kata berbeda. Ada test yang mengunci batasan ini; kalau suatu saat
stemming ditambahkan, test itu akan gagal dan catatan ini terpaksa diperbarui.

**Eksperimen #4 (banding model embedding) dilewat.** Membandingkan dua model
berarti meng-embed ulang seluruh korpus dua kali. Kuota harian 50 request,
dan tahap 5 sudah memakan 5 sekali jalan. Roadmap sendiri menandai eksperimen
ini boleh dilewat kalau waktu mepet.

## Evaluasi

**Golden dataset 30 pertanyaan, bukan 50.** Roadmap mengizinkan pengurangan
ini. Yang lebih penting: menambah pertanyaan tanpa ground truth yang
diverifikasi manual justru menurunkan mutu dataset, bukan menaikkan.

**Ground truth memakai halaman, bukan chunk_id.** `chunk_id` berubah setiap
cara memotong berubah — dan Tahap 5 memang mengubahnya. Halaman tetap, dan
tetap bisa diverifikasi dengan membuka PDF. Konsekuensinya patokan ini
sedikit longgar: satu chunk mencakup rata-rata 1,5 halaman.

**Label routing adalah label perak.** `expected_intent` diturunkan dari isi
jawaban FAQ lewat aturan lexical, bukan dilabeli manual. Sebagian
kesalahannya tidak mungkin dimenangkan — label melihat jawaban, router hanya
melihat pertanyaan.

**Eval Tier 2 (RAGAS) dilewat.** RAGAS menilai pakai LLM; satu kali jalan atas
30 pertanyaan memakan puluhan panggilan. Nightly RAGAS berarti kuota harian
habis sebelum hari kerja dimulai. Penggantinya: kalibrasi verifier dengan
label yang dibangun.

## Gerbang CI

**Gate tidak menjaga mutu sisi dense.** PDF tidak ada di repo dan cache
embedding 29 MB juga tidak, jadi CI tidak mungkin membangun korpus dengan
vektor dense tanpa secret dan kuota. Gate jalan di jalur sparse-only dari
korpus beku — deterministik dan gratis, tapi hanya menjaga penulisan ulang
pertanyaan, pencocokan kata harfiah, logika pencarian, dan perhitungan metrik.

**Gate tidak melihat perubahan pemotong dokumen**, karena fixture-nya beku.
Celah itu ditutup dari sisi lain oleh `tests/test_fixture.py`, yang gagal
kalau fixture sudah basi dan dilewati otomatis di CI.

## Produksi

**Cache jawaban tidak dibangun.** Roadmap menandainya boleh dilewat, dan ada
alasan tambahan: cache jawaban akan mengaburkan pengukuran latensi di tabel
benchmark.

**Upload endpoint asynchronous tidak dibangun.** Ditandai boleh dilewat oleh
roadmap; tidak menambah pelajaran baru.

**Budget LLM disimpan di memori proses.** Ikut nol saat container dibuat
ulang, dan tidak dibagi antar replika. Cukup untuk satu container; kalau nanti
jalan lebih dari satu, pindahkan ke Redis.

**Belum di-deploy.** Ditandai boleh diganti oleh roadmap. Yang menggantikan:
`docker compose up -d` menyalakan Qdrant, API, dan dashboard sekaligus di mesin
bersih. Deploy publik sengaja tidak dikejar karena kuota embedding 50/hari
bersifat akun-wide, jadi satu pengunjung iseng bisa mematikannya untuk semua
orang termasuk pengembangnya sendiri.

## Verifikasi

**Kalibrasi verifier memakai label yang dibangun, bukan dilabeli tangan.**
Karangan yang disisipkan kasar dan mencolok, jadi angkanya adalah batas
**atas** kemampuan verifier — belum membuktikan dia sanggup menangkap
halusinasi halus seperti angka yang meleset sedikit atau nomor pasal yang
keliru satu digit.
