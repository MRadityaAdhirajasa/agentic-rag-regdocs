# Format Golden Dataset — Agentic RAG Regdocs

Dokumen acuan untuk Tahap 4 di roadmap. Dipakai juga di Tahap 9 untuk
evaluasi routing.

---

## 1. Letak File

```
eval/
├── golden.jsonl            # 50 pertanyaan evaluasi retrieval
├── holdout_routing.jsonl   # 50 item FAQ disisihkan, khusus uji routing
├── baseline.json           # snapshot metrik terakhir yang diterima
└── metrics.py              # implementasi recall@k, MRR, nDCG
```

JSONL (satu objek per baris), bukan JSON array. Alasannya: diff di Git
jadi bersih, satu pertanyaan berubah cuma bikin satu baris berubah.

---

## 2. Skema Satu Entri

```json
{
  "qid": "g_001",
  "question": "Berapa lama jangka waktu penerbitan NIB untuk usaha risiko rendah?",
  "category": "lookup_faktual",
  "expected_intent": "lookup",
  "expected_source_type": "regulasi",
  "relevant_chunk_ids": [
    "pp-5-2021_bab3_p12_a1",
    "pp-5-2021_bab3_p12_a2"
  ],
  "origin": {
    "type": "faq_paraphrase",
    "faq_id": "faq-ppb-023",
    "faq_category": "Proses Perizinan Berusaha"
  },
  "notes": "Jawaban FAQ menyebut 'langsung terbit', pasal menyebut jangka waktu spesifik"
}
```

### Penjelasan Field

| Field | Isi | Wajib |
|---|---|---|
| `qid` | `g_001` sampai `g_050`, urut, jangan dipakai ulang | ya |
| `question` | Pertanyaan versi final, sudah diparafrase | ya |
| `category` | Salah satu dari 6 kategori di bawah | ya |
| `expected_intent` | `lookup` / `comparison` / `summary` / `troubleshooting` | ya |
| `expected_source_type` | `regulasi` / `faq` / `none` | ya |
| `relevant_chunk_ids` | Daftar chunk yang benar. Kosong untuk kategori negatif | ya |
| `origin` | Asal-usul pertanyaan, untuk audit kebocoran | ya |
| `notes` | Catatan bebas untuk diri sendiri | tidak |

### Nilai `origin.type`

- `faq_paraphrase` — diambil dari FAQ lalu diparafrase. Wajib isi `faq_id`
- `authored` — dikarang sendiri, tidak ada asal FAQ
- `doc_reading` — muncul saat membaca dokumen regulasi

Field ini yang membuat kamu bisa membuktikan tidak ada kebocoran, dan
membuat kamu bisa melaporkan metrik terpisah per asal pertanyaan.

---

## 3. Enam Kategori

| `category` | Jumlah | Sumber | `expected_source_type` |
|---|---|---|---|
| `lookup_faktual` | 22 | Proses Perizinan (16), Pelaporan/Sanksi (6) | `regulasi` |
| `lookup_teknis` | 4 | Manajemen Akun, Kendala Teknis | `faq` |
| `komparatif` | 10 | Proses + Pelaporan | `regulasi` |
| `status_supersesi` | 5 | Proses Perizinan | `regulasi` |
| `alias_lembaga` | 4 | Dikarang sendiri | `regulasi` |
| `negatif` | 5 | Dikarang sendiri | `none` |

Total 50.

### Catatan per kategori

**`lookup_faktual`** — inti dataset. Pertanyaan asli dari FAQ, tapi
jawabannya dicari di pasal, bukan di entri FAQ-nya.

**`lookup_teknis`** — pertanyaan yang memang cuma FAQ yang bisa jawab.
Metriknya dilaporkan terpisah, jangan digabung ke angka utama.

**`komparatif`** — butuh chunk dari lebih dari satu dokumen. Contoh:
membandingkan ketentuan di Perban 5/2021 dengan PP 5/2021.

**`status_supersesi`** — pertanyaan tentang tata cara pelayanan hari ini.
Jawaban yang benar mengutip Permen 5/2025. Kalau sistem menjawab dari
Perban 4/2021, itu salah meski sitasinya valid. Isi `relevant_chunk_ids`
hanya dengan chunk dari dokumen yang berlaku.

**`alias_lembaga`** — menyebut lembaga dengan nama lama. Contoh bentuk:
"aturan BKPM soal pengawasan", "peraturan Kementerian Investasi tentang
fasilitas". Harus tetap menemukan dokumen dengan nama lembaga versi
apa pun.

**`negatif`** — tidak terjawab dari FAQ **maupun** regulasi. Karena FAQ
ada di dalam korpus, pertanyaan dari kategori FAQ mana pun tidak bisa
dipakai di sini. Karang sendiri yang terdengar wajar tapi di luar
cakupan: perizinan yang wewenangnya di kementerian lain, atau topik
yang mirip tapi tidak diatur di lima dokumen inti.

---

## 4. Aturan Parafrase

Berlaku untuk semua entri dengan `origin.type = faq_paraphrase`.
Ini yang menjaga angka `recall@5` kamu tetap jujur.

**Lima aturan:**

1. **Ubah struktur kalimat, bukan cuma ganti sinonim.** Kalau strukturnya
   sama dan cuma satu-dua kata diganti, embedding-nya masih terlalu dekat.

2. **Jangan salin lebih dari 4 kata berurutan** dari `question` aslinya.

3. **Pakai istilah yang dipakai orang bertanya**, bukan istilah yang
   disalin dari `answer`. Kalau kamu pakai kata dari jawaban, kamu
   sedang menandai chunk-nya.

4. **Buang penanda khas FAQ.** Awalan seperti "Kenapa saat..." atau
   "Bagaimana jika..." yang persis sama akan mencocokkan entri aslinya.

5. **Uji hasilnya.** Cari pertanyaan hasil parafrase dengan pencarian
   kata kunci biasa di file FAQ. Kalau entri aslinya muncul di peringkat
   satu dengan selisih jauh, parafrasenya belum cukup — ulangi.

### Contoh

FAQ asli (`faq-ppb-xxx`):
> "Bagaimana cara mengajukan perizinan berusaha untuk kegiatan usaha
> dengan tingkat risiko menengah tinggi?"

**Parafrase lemah** (jangan dipakai):
> "Bagaimana cara mengurus izin usaha untuk risiko menengah tinggi?"

Struktur identik, cuma sinonim. Masih akan mencocokkan entri FAQ-nya.

**Parafrase kuat:**
> "Perusahaan saya masuk kategori risiko menengah tinggi. Dokumen apa
> yang harus dipenuhi sebelum bisa beroperasi?"

Struktur beda, sudut pandang beda, kosakata beda. Yang tersisa cuma
konsep hukumnya — dan itu yang memang mau diuji.

---

## 5. Cara Mengisi `relevant_chunk_ids`

Ini bagian yang paling memakan waktu. Kerjakan sambil membaca dokumen
untuk keperluan lain, jangan dijadikan sesi terpisah.

**Alur:**

1. Ambil satu entri FAQ dari kategori hukum
2. Baca `answer`-nya, cari kata kunci hukum di situ
3. Cari kata kunci itu di dokumen regulasi, temukan pasalnya
4. Catat `chunk_id` dari pasal tersebut
5. Baru tulis pertanyaannya, diparafrase, tanpa melihat `question` asli lagi

Urutan ini penting. Kalau kamu menulis pertanyaan dulu baru mencari
chunk, kamu cenderung menulis pertanyaan yang kamu sudah tahu ada
jawabannya — dan itu bias.

**Boleh lebih dari satu chunk.** Kalau jawaban lengkap butuh Pasal 12
dan Pasal 13, masukkan keduanya. `recall@5` menghitung berapa persen
dari daftar itu yang tertangkap.

**Kalau tidak ketemu pasalnya**, jangan dipaksakan. Buang pertanyaan itu,
ambil entri FAQ lain. Golden dataset yang salah lebih merusak daripada
golden dataset yang kecil.

---

## 6. Pelaporan Metrik

Jangan laporkan satu angka gabungan. Minimal pecah tiga:

| Kelompok | Yang dilaporkan |
|---|---|
| `expected_source_type = regulasi` (41 pertanyaan) | Angka utama. Ini yang masuk `baseline.json` dan jadi gate CI |
| `expected_source_type = faq` (4 pertanyaan) | Dilaporkan terpisah, dengan catatan bahwa angkanya optimistis |
| `category = negatif` (5 pertanyaan) | Bukan recall. Metriknya: berapa persen yang benar dijawab "tidak didukung" |

Menyebutkan sendiri bahwa angka kelompok kedua optimistis itu bikin
kamu terlihat teliti, bukan lemah.

---

## 7. Holdout Routing

Sisihkan 50 item FAQ yang **tidak** dipakai di `golden.jsonl`.
Ambil proporsional dari lima kategori terbesar.

```json
{
  "faq_id": "faq-mad-012",
  "question": "Kenapa email verifikasi tidak masuk saat daftar akun?",
  "true_category": "Manajemen Akun dan Pendaftaran",
  "expected_intent": "troubleshooting",
  "expected_source_type": "faq"
}
```

Dipakai di Tahap 9 untuk mengukur akurasi `route_intent`. Metriknya
akurasi klasifikasi biasa, plus confusion matrix kalau mau lebih bagus.

Pertanyaan di sini **tidak perlu diparafrase**, karena yang diuji
keputusan routing, bukan retrieval.

---

## 8. Urutan Pengerjaan

Jangan tulis 50 sekaligus. Sebar sesuai roadmap:

| Kapan | Jumlah | Fokus |
|---|---|---|
| Tahap 4 | 10 | `lookup_faktual` saja, dari Proses Perizinan |
| Tahap 5 | +10 | `lookup_faktual` dari Pelaporan/Sanksi, plus `komparatif` |
| Tahap 6 | +10 | `komparatif` sisanya, plus `alias_lembaga` |
| Tahap 7 | +10 | `status_supersesi`, plus `lookup_teknis` |
| Tahap 13 | +10 | `negatif`, plus melengkapi yang kurang |

Baseline di `eval/baseline.json` diperbarui setiap kali jumlah
pertanyaan bertambah. Catat jumlah pertanyaan di dalam file baseline,
supaya perbandingan antar-tahap tidak menyesatkan.
