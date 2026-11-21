# Rollout

Measured on a developer machine on 2026-11-20, with the local Legilo container built from `supporting-docs-md` (inline Dockerfile, uv 0.9.3), Redis 8.10.3 from `compose.yaml`, and Bedrock `amazon.titan-embed-text-v2:0` in eu-west-2. Dataset order: seed 20261120, no ids file. The EIDC catalogue had 2,207 published datasets.

## 20 datasets

| Stage | Figure |
|---|---|
| Download | 26 s for 20 datasets, no failures |
| Raw store | 62 MB |
| Supporting files | all 20 datasets have them; 50 files |
| Conversion | under 2 s for 20 datasets (build total 1.6 s); 46 Markdown files, 1.0 MB |
| Conversion errors | 4 files: 3 PDFs needing OCR (rejected by design), 1 `README.txt` not UTF-8 |
| Bundle | 20 datasets, 46 documents, 79 people, 27 organisations, 14 grants, 140 themes, 23 ontology; 2.6 MB |
| Load | 349 concepts, 2,226 chunks; 3 min 9 s with no cached embeddings |
| Rebuild | 0 Legilo requests (20 conversions cached) |

Checks on the loaded 20 bundle:

- `/v1/query/semantic` ranks supporting-document passages first for "saltmarsh extent change predictors" (`GB_MarshExtentChange_Metadata.rtf`), "earthquake hazard parameters Istanbul" (the hazard-parameter PDFs) and "protozoa in Sourhope soil" (`P2130_Sourhope_Protozoa_document.rtf`).
- AI Summary answered "What sampling protocol was used at the Sourhope soil biodiversity site?" (search, search, read, read) by naming the "Protocol for Sampling and Recording at the Sourhope Experimental Site" supporting document, and "How was saltmarsh extent change measured across Great Britain?" (search, search, read) from the dataset's metadata document.
- `scripts/smoke-test.py` passes every check, including supporting documents in the bundle (15 document concepts for the 10 smoke datasets).

## 100 datasets

| Stage | Figure |
|---|---|
| Download | 80 new datasets (the first 20 were skipped); about 60 s in total, including one interrupted and resumed run; no failures |
| Raw store | 195 MB (187 MB original supporting files, 4.4 MB Markdown) |
| Supporting files | all 100 datasets have them; 187 files |
| Conversion | 80 datasets converted, 20 cached; build total 9.0 s; 164 Markdown files, 3.4 MB; largest 0.21 MB (`LCM2007 Final Report.pdf`) |
| Conversion errors | 19 files: 13 `.txt` files not UTF-8 (Latin-1 `°` characters), 5 PDFs needing OCR, 4 `.qml` and 1 `.jpg` unsupported |
| Bundle | 100 datasets, 164 documents, 330 people, 92 organisations, 60 grants, 588 themes, 23 ontology; 9.6 MB |
| Load | 1,357 concepts, 7,270 chunks; 4 min 42 s (the 20 bundle's embeddings were cached, so about 5,000 new chunks) |
| Redis memory | 169 MB used |

## Full collection estimate (2,207 datasets)

Linear extrapolation from the 100 sample. File sizes are heavy-tailed, so treat disk and conversion figures as lower bounds.

| Figure | Estimate | Basis |
|---|---|---|
| Download time | about 30 min | about 0.8 s per dataset |
| Raw store | about 4–5 GB | 1.95 MB per dataset |
| Conversion time | about 5–15 min | 80 datasets in under 9 s; a few very large PDFs could dominate |
| Conversion errors | about 400 files | 19 per 100 datasets; most are non-UTF-8 text files |
| Chunks | about 160,000 | 73 per dataset |
| Load time | about 2.5 h with no cached embeddings | about 18 new chunks per second |
| Embedding cost | under $1 | about 32 M tokens (160,000 chunks of about 200 tokens) at Titan Text Embeddings V2 list price (about $0.02 per million tokens); check current eu-west-2 pricing |
| Embedding cache (`.cache/embeddings`) | about 3.8 GB | about 24 KB per cached chunk |
| Redis memory | about 3.7 GB | 169 MB for 7,270 chunks |

## Findings

- About two thirds of the conversion errors are plain-text files that are not UTF-8. Legilo's `convert_file_to_text` opens `.txt` and `.md` as UTF-8 only; falling back to `chardet`, already a Legilo dependency, would recover them. That is a Legilo change.
- Redis memory for the full index (4.7 GB measured) is the main resource to plan for, both locally and on the deploy host.
- Every dataset in the first 100 has supporting documents; the full collection exercised the "no supporting files" path with 5 datasets.

## Full collection

Run on 2026-11-21 after agreement to the estimate above.

| Stage | Figure |
|---|---|
| Download | 2,107 new datasets (the first 100 were skipped); 24 min; no failures |
| Raw store | 6.5 GB (6.4 GB original supporting files, 29 MB metadata, 129 MB Markdown) |
| Supporting files | 2,202 of 2,207 datasets have them; 4,204 files; largest 333 MB (`EnsembleDepictions.zip`, unsupported) |
| Conversion | 2,102 datasets converted, 100 cached, none failed; build total 6 min 0 s |
| Conversion errors | 552 files. Largest groups: unsupported types (114 `.qml`, 71 `.lyr`, 70 `.jpg`, 51 `.R`, 19 `.hash`, 18 `.zip`, 8 `.clr`) and PDFs needing OCR |
| Bundle | 2,207 datasets, 3,629 documents, 2,515 people, 485 organisations, 642 grants, 3,871 themes, 25 ontology; 176 MB, 124 MB of Markdown (about 31 M tokens) |

| Load | 13,372 concepts, 220,407 chunks (2 more were over Titan's 8,192-token limit and left out), 40,755 relation records, 3,761 theme labels |
| Load time | embeddings: 3 h 50 min for 193,454 new chunks at about 14 per second; final load from cached embeddings: 4 min 32 s |
| Embedding cache | 4.3 GB |
| Redis memory | 4.68 GB used; RDB snapshot 1.77 GB, restored and fully indexed in 51 s |
| Deploy archive | `dist/serka-eidc-full-2026-11-21.tar.gz`, 1.46 GB: the RDB snapshot, `bundles/full` and restore notes |

The estimate held for download time and disk (6.5 GB against 4–5 GB, as the heavy tail predicted). Conversion errors were higher (552 against about 400) because the wider collection has many more GIS and code files that Legilo does not support; non-UTF-8 text is a smaller share than in the 100 sample (54 files). Chunks (220,407 against about 160,000) and Redis memory (4.7 GB against about 3.7 GB) were higher than the linear estimate.

Checks on the full index through the compose stack (UI on 8080, API on 9000), 2026-11-21:

- The UI loads and proxies `/v1/` to the API.
- Semantic search puts the expected datasets in the top three for pike in Windermere, Seychelles warbler telomeres, Chernobyl contamination, Land Cover Map 2015, river flow gauging, Countryside Survey soil carbon, pollinator monitoring (UK Pollinator Monitoring Scheme) and ozone measurements; the Sourhope sampling protocol query returns supporting-document passages.
- AI Summary named the Windermere pike growth dataset; counted 2,207 datasets with `aggregate`; listed the authors of three Windermere pike datasets and their UKCEH affiliation (search, then read three times); described the Sourhope protocol from its supporting PDF; listed UK hydrological drought datasets; and refused an off-topic request.

Problems found at full scale, and fixed in `serka.okf.loader`:

- The loader held every embedding in memory before writing (about 10 GB for the full bundle), and the OOM killer stopped it twice on a 15 GB machine. It now embeds and writes 2,000 chunks at a time; the loader peaked at about 1.5 GB.
- redis-py 8's default 5 s socket timeout broke dropping the old index (about 20 s for 100,000 chunks), and made large pipelines time out and be resent, slowing writes from about 1,500 to about 30 chunks per second. The loader's client now waits up to 10 minutes.

Still open:

- Clearing the answer cache builds RedisVL's `SemanticCache`, which test-embeds a string with Bedrock; with expired AWS credentials the clear is logged and skipped, leaving answers from the previous index.
- 150-word chunks can still exceed Titan's 8,192 tokens when the words are very long (2 chunks in the full collection).
