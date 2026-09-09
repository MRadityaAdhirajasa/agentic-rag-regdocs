# Agentic RAG untuk Dokumen Regulasi Indonesia

Sistem tanya-jawab atas peraturan perizinan berusaha berbasis risiko,
dengan sitasi tingkat pasal dan evaluasi retrieval yang terukur.

> Status: dalam pengembangan. Tahap 1 dari 13.

## Menjalankan

```bash
docker compose up -d                      # Qdrant
make ingest                               # PDF -> chunk -> Qdrant
make chat                                 # tanya-jawab CLI
```

Butuh `.env` berisi `OPENROUTER_API_KEY` (embedding) dan `GOOGLE_API_KEY`
(LLM). Contohnya ada di `.env.example`.

Embedding: `nvidia/nemotron-3-embed-1b:free` lewat OpenRouter, 2048 dimensi,
prefix `query:` / `document:`. Retrieval masih dense-only, k=3.

## Batasan yang disengaja

Bagian ini diisi di Tahap 13.

## Sumber data

- FAQ OSS BKPM, diambil dari https://oss.go.id (tanggal akses: ...)
- Peraturan dari https://jdih.bkpm.go.id