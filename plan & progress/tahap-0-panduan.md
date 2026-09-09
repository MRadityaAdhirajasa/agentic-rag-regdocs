# Tahap 0 — Panduan Langkah demi Langkah

Target akhir tahap ini:

- `docker compose up -d` → Qdrant hidup
- Script Python bisa connect, bikin collection, isi 1 titik
- `docker compose down` lalu `up` → data masih ada
- Push ke GitHub, CI hijau

Belum ada RAG apa pun di sini. Ini murni fondasi.

---

## Prasyarat

Cek dulu tiga ini ada:

```bash
git --version
docker --version
docker compose version
```

Kalau uv belum ada:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Cek: `uv --version`

---

## Langkah 1 — Folder dan git

```bash
mkdir agentic-rag-regdocs
cd agentic-rag-regdocs
git init
```

Belum bikin repo di GitHub. Nanti setelah `.gitignore` aman.

---

## Langkah 2 — `.gitignore` DULU

Ini langkah pertama yang menulis file, bukan kebetulan. API key kamu
pernah bocor dua kali di file lama. Kali ini pagarnya dipasang sebelum
ada yang bisa lewat.

Bikin file `.gitignore`:

```gitignore
# Environment
.env
.env.local
*.key

# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/

# Data — PDF mentah tidak masuk repo
data/raw/
data/processed/
*.pdf

# Model cache
.cache/
models/

# Qdrant lokal (kalau pakai bind mount)
qdrant_storage/

# OS / editor
.DS_Store
.vscode/
.idea/
```

Verifikasi langsung:

```bash
echo "GOOGLE_API_KEY=test123" > .env
git status
```

`.env` **tidak boleh muncul** di daftar untracked. Kalau muncul,
`.gitignore` kamu salah — perbaiki sebelum lanjut.

---

## Langkah 3 — uv dan dependensi

```bash
uv init --python 3.12
```

Ini bikin `pyproject.toml`, `.python-version`, dan beberapa file
bawaan. Hapus `hello.py` atau `main.py` kalau ada.

Tambahkan dependensi. Tahap 0 cuma butuh sedikit:

```bash
uv add qdrant-client python-dotenv
uv add --dev ruff mypy pytest
```

`uv add` otomatis bikin `.venv`, install, dan nulis `uv.lock`.
**`uv.lock` wajib di-commit** — itu yang bikin laptopmu, CI, dan
Docker dapat versi identik.

Sekarang buka `pyproject.toml` dan tambahkan konfigurasi tool di
bagian bawah:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`mypy` sengaja belum `strict`. Naikkan nanti kalau kode sudah banyak —
strict di repo kosong cuma bikin frustrasi.

---

## Langkah 4 — Struktur folder

```bash
mkdir -p app/{api,core,agents,retrieval,ingestion,eval}
mkdir -p data/{raw,processed} docs/adr eval scripts tests
mkdir -p .github/workflows

# supaya folder kosong ikut ter-commit
touch app/__init__.py
for d in api core agents retrieval ingestion eval; do touch app/$d/__init__.py; done
touch data/raw/.gitkeep data/processed/.gitkeep
```

Folder `app/` masih kosong sepanjang Tahap 0. Nggak apa-apa —
kerangkanya ada duluan supaya kamu nggak mikirin struktur lagi nanti.

---

## Langkah 5 — Environment variable

Bikin `.env.example` (ini yang di-commit):

```bash
# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=regdocs

# Google Gemini — belum dipakai di Tahap 0
GOOGLE_API_KEY=
```

Lalu bikin `.env` asli:

```bash
cp .env.example .env
```

Isi `GOOGLE_API_KEY` biarkan kosong dulu. Belum dipakai.

**Kalau kamu masih pakai key yang ada di dua file lamamu, ganti
sekarang.** Bikin key baru di Google AI Studio, cabut yang lama.

---

## Langkah 6 — `docker-compose.yml`

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: regdocs-qdrant
    ports:
      - "6333:6333"   # REST API
      - "6334:6334"   # gRPC
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

volumes:
  qdrant_data:
```

Tiga hal yang perlu kamu perhatikan di file ini:

**`volumes:` muncul dua kali.** Yang di dalam `services` itu
sambungannya. Yang di bawah sendiri itu deklarasi named volume. Kalau
yang bawah lupa ditulis, Compose menolak jalan.

**`qdrant_data:/qdrant/storage`** — kanan adalah folder di dalam
container, kiri adalah penampung di laptopmu. Ini satu-satunya baris
yang menyelamatkanmu dari embed ulang.

**`image: latest`** cukup untuk sekarang. Kalau nanti mau reproducible
penuh, pin ke versi spesifik.

---

## Langkah 7 — Nyalakan dan cek

```bash
docker compose up -d
docker compose ps
```

Statusnya harus `running`. Cek dari browser atau curl:

```bash
curl http://localhost:6333/healthz
```

Dashboard Qdrant juga bisa dibuka di `http://localhost:6333/dashboard`.
Berguna buat lihat isi collection secara visual.

Kalau port 6333 bentrok dengan sesuatu, ganti sisi kiri saja:
`"6433:6333"`, lalu sesuaikan `QDRANT_URL` di `.env`.

---

## Langkah 8 — Script smoke test

Bikin `scripts/smoke_qdrant.py`:

```python
"""Smoke test Qdrant: bikin collection, isi satu titik, hitung ulang.

Pakai:
    uv run python scripts/smoke_qdrant.py seed
    uv run python scripts/smoke_qdrant.py check
"""

import os
import sys

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "regdocs")
VECTOR_SIZE = 768  # sesuaikan dengan model embedding nanti


def get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def seed() -> None:
    client = get_client()

    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"Collection '{COLLECTION}' dibuat.")
    else:
        print(f"Collection '{COLLECTION}' sudah ada.")

    client.upsert(
        collection_name=COLLECTION,
        points=[
            PointStruct(
                id=1,
                vector=[0.1] * VECTOR_SIZE,
                payload={
                    "source_type": "dummy",
                    "text": "titik uji coba tahap 0",
                },
            )
        ],
    )
    print("1 titik dimasukkan.")
    check()


def check() -> None:
    client = get_client()

    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION not in existing:
        print(f"GAGAL: collection '{COLLECTION}' tidak ditemukan.")
        sys.exit(1)

    total = client.count(collection_name=COLLECTION).count
    print(f"Jumlah titik di '{COLLECTION}': {total}")

    if total == 0:
        print("GAGAL: collection kosong. Volume kemungkinan tidak persist.")
        sys.exit(1)

    hits = client.query_points(
        collection_name=COLLECTION,
        query=[0.1] * VECTOR_SIZE,
        limit=1,
    )
    print(f"Hasil pencarian: {hits.points}")
    print("OK.")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    if command == "seed":
        seed()
    elif command == "check":
        check()
    else:
        print("Perintah: seed | check")
        sys.exit(1)
```

Jalankan:

```bash
uv run python scripts/smoke_qdrant.py seed
```

Harus keluar `OK.` di baris terakhir.

Catatan soal `VECTOR_SIZE = 768`: angka ini harus **persis sama**
dengan dimensi model embedding yang kamu pakai nanti. Kalau nggak
cocok, Qdrant menolak. Sekarang isinya cuma vektor dummy, jadi bebas —
tapi ingat untuk mengeceknya di Tahap 1.

---

## Langkah 9 — Tes volume (JANGAN DILEWAT)

Ini inti Tahap 0. Lakukan persis urutan ini:

```bash
# 1. Data sudah ada dari langkah sebelumnya
uv run python scripts/smoke_qdrant.py check
# → Jumlah titik: 1

# 2. Matikan container. Containernya benar-benar dihapus.
docker compose down

# 3. Pastikan memang hilang
docker compose ps
# → kosong

# 4. Nyalakan lagi
docker compose up -d
sleep 5

# 5. Cek lagi
uv run python scripts/smoke_qdrant.py check
# → Jumlah titik: 1   ← INI YANG DICARI
```

Kalau di langkah 5 jumlahnya tetap 1, volume kamu jalan. Kalau jadi 0
atau collection-nya hilang, ada yang salah di `docker-compose.yml` —
perbaiki sebelum lanjut ke mana-mana.

**Sekali lagi, hati-hati:** `docker compose down -v` menghapus volume.
Huruf `v` itu volumes. Jangan diketik kecuali memang mau reset total.

Kalau mau merasakan bedanya, coba sengaja sekali:

```bash
docker compose down -v
docker compose up -d
uv run python scripts/smoke_qdrant.py check
# → GAGAL: collection tidak ditemukan
uv run python scripts/smoke_qdrant.py seed   # isi ulang
```

Sekali merasakan, kamu nggak akan lupa.

---

## Langkah 10 — Lint dan test

Bikin satu test sederhana di `tests/test_config.py`:

```python
"""Test yang tidak butuh Qdrant, supaya CI bisa jalan tanpa service."""

import os

from dotenv import load_dotenv

load_dotenv()


def test_qdrant_url_terbaca() -> None:
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    assert url.startswith("http")


def test_collection_name_ada() -> None:
    name = os.getenv("QDRANT_COLLECTION", "regdocs")
    assert len(name) > 0
```

Jalankan bertiga:

```bash
uv run ruff check .
uv run ruff format .
uv run mypy app scripts
uv run pytest
```

Perbaiki yang merah sekarang. Lebih mudah membereskan lint di repo
kosong daripada nanti.

---

## Langkah 11 — Makefile

Bikin `Makefile`:

```makefile
.PHONY: up down logs smoke check lint fmt test all

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f qdrant

smoke:
	uv run python scripts/smoke_qdrant.py seed

check:
	uv run python scripts/smoke_qdrant.py check

lint:
	uv run ruff check .
	uv run mypy app scripts

fmt:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest

all: lint test
```

**Penting:** indentasi di Makefile harus TAB, bukan spasi. Kalau editor
kamu auto-convert tab jadi spasi, Makefile-nya error.

Pengguna Windows tanpa `make`: jalankan saja perintahnya langsung, atau
pakai WSL.

Uji: `make down && make up && make check`

---

## Langkah 12 — GitHub Actions

Bikin `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true

      - name: Install dependencies
        run: uv sync --locked --dev

      - name: Ruff
        run: uv run ruff check .

      - name: Mypy
        run: uv run mypy app scripts

      - name: Pytest
        run: uv run pytest
```

Tiga catatan:

- `uv sync --locked` gagal kalau `uv.lock` tidak cocok dengan
  `pyproject.toml`. Itu memang tujuannya — memaksa lockfile selalu
  ter-commit
- Belum ada service Qdrant di CI. Test di Tahap 0 sengaja yang tidak
  butuh koneksi
- Eval gate baru masuk di Tahap 12. Sekarang pipeline-nya dulu yang ada

---

## Langkah 13 — Dokumen dasar

**`docs/adr/`** — salin lima ADR dari Plan v3 sebagai file terpisah:

```
docs/adr/001-vectorstore-qdrant.md
docs/adr/002-provider-abstraction.md
docs/adr/003-verification-optional.md
docs/adr/004-retry-mutation.md
docs/adr/005-status-metadata.md
```

Di ADR-001, tambahkan paragraf alternatif yang ditolak: pgvector
(tidak ada text search config Bahasa Indonesia) dan ChromaDB (sekarang
punya sparse plus RRF juga; Qdrant dipilih karena named vectors dan
kematangan payload filtering).

**`README.md`** — kerangka saja dulu:

```markdown
# Agentic RAG untuk Dokumen Regulasi Indonesia

Sistem tanya-jawab atas peraturan perizinan berusaha berbasis risiko,
dengan sitasi tingkat pasal dan evaluasi retrieval yang terukur.

> Status: dalam pengembangan. Tahap 0 dari 13.

## Menjalankan

```bash
docker compose up -d
```

## Batasan yang disengaja

Bagian ini diisi di Tahap 13.

## Sumber data

- FAQ OSS BKPM, diambil dari https://oss.go.id (tanggal akses: ...)
- Peraturan dari https://jdih.bkpm.go.id
```

**`docs/notes.md`** — file kosong buat mencatat kemacetan. Serius,
bikin sekarang. Kamu akan butuh.

---

## Langkah 14 — Commit dan push

```bash
git status          # PASTIKAN .env tidak muncul
git add .
git status          # cek sekali lagi sebelum commit
git commit -m "tahap 0: kerangka repo, uv, docker compose qdrant, CI"
```

Bikin repo di GitHub (kosong, tanpa README), lalu:

```bash
git remote add origin git@github.com:USERNAME/agentic-rag-regdocs.git
git branch -M main
git push -u origin main
git tag stage-00
git push --tags
```

Cek tab Actions di GitHub. Harus hijau.

---

## Checklist Selesai

Tahap 0 beres kalau semua ini benar:

- [ ] `.env` tidak pernah muncul di `git status`
- [ ] `docker compose up -d` → Qdrant `running`
- [ ] `curl http://localhost:6333/healthz` merespons
- [ ] `make smoke` keluar `OK.`
- [ ] `down` lalu `up` lalu `check` → jumlah titik tetap 1
- [ ] `make lint` dan `make test` hijau di lokal
- [ ] CI hijau di GitHub
- [ ] `uv.lock` ter-commit
- [ ] Tag `stage-00` ada
- [ ] Key lama sudah dicabut, key baru belum masuk repo

---

## Kalau Macet

**`docker compose up` gagal, port bentrok**
Ganti sisi kiri di ports: `"6433:6333"`. Sesuaikan `QDRANT_URL`.

**`Connection refused` dari Python**
Qdrant butuh beberapa detik untuk siap. Tunggu, lalu ulangi.
Cek `docker compose logs qdrant`.

**`uv sync --locked` gagal di CI**
`uv.lock` tidak sinkron. Jalankan `uv lock` di lokal, commit hasilnya.

**mypy protes soal qdrant_client**
`ignore_missing_imports = true` sudah ada di config. Kalau masih,
persempit dengan `[[tool.mypy.overrides]]` untuk modul itu saja.

**Makefile error "missing separator"**
Indentasi pakai spasi, harusnya TAB.

**Data hilang setelah restart**
Cek `docker-compose.yml`: apakah `volumes:` ada dua kali (di dalam
service dan di level atas). Cek juga apakah kamu pernah menjalankan
`down -v`.

---

## Setelah Ini

Tahap 1: ambil `rag_langchain_2.py`, ganti Chroma jadi Qdrant, jangan
ubah apa pun yang lain. Satu variabel berubah, jadi kalau ada yang
aneh kamu tahu persis penyebabnya.
