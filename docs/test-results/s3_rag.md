# S3: RAG for the fix guides (2026-10-08)

The spike code was throwaway and has been deleted. The source documents are kept in `../../data/reference/` (moved there on 2026-10-08) (see the table below).

## Corpus
| Source | File | Licence | sha256 (first 16) | Status |
|---|---|---|---|---|
| ANSSI, *Recommandations de sécurité pour un système d'IA générative* (ANSSI-PA-102, 29/04/2024), French | `data/reference/anssi_genai_fr.pdf` | Licence Ouverte 2.0 (Etalab) | 30d86707d665ff08 | ✓ downloaded |
| ANSSI, same guide, English | `data/reference/anssi_genai_en.pdf` | Licence Ouverte 2.0 | b717710f6b886ba6 | ✓ downloaded |
| MITRE ATLAS data, v5.6.0 (`dist/ATLAS.yaml`, mitre-atlas/atlas-data) | `data/reference/ATLAS.yaml` | Apache 2.0, © 2021–2026 MITRE (checked 2026-10-09) | c9c23971d0db07e2 | ✓ downloaded; 35 mitigations, including the agent ones AML.M0026–M0030 and M0033 |
| OWASP Top 10 for Agentic Applications 2026 | none | CC BY-SA 4.0 (announced) | none | ✗ scripted download refused ("No Access" page): **download it once by hand** from genai.owasp.org |
| Internal runbooks | written for the demo (fictional) | ours | none | 3 drafts used in the test |

**Download notes.** The old cyber.gouv.fr PDF links now land on an HTML page. The real PDFs are at `messervices.cyber.gouv.fr/documents-guides/…`. Always check the file type after downloading: two "PDFs" were actually HTML.

## Retrieval test (BM25, `bm25s` 0.3.13, `pypdf` 6.19.0)
- **Index:** 215 chunks in about 1.3 s, including PDF extraction. A query takes under 1 ms.
- **11 questions in French and English, measured two ways:**
  - **Source family judged relevant, hit@3: 11 of 11.** This is lenient.
  - **Exact passage, hit@3: about 7 of 11** (judged by hand).
- **Correct:**
  - key rotation, which goes to the runbook;
  - least privilege for an agent's tools: ATLAS M0028, M0026 and M0027;
  - dev/prod separation: the runbook;
  - retries and escalation: the runbook, plus ATLAS M0029 Human In-the-Loop;
  - « cloisonnement »: ANSSI R12;
  - rights on business applications: ANSSI R35, R26 and R10.
- **Wrong:**
  - "human validation before a critical action", in French and in English, doesn't reach ANSSI R9 (« Proscrire l'usage automatisé de systèmes d'IA pour des actions critiques ») because the wording differs;
  - "logging / journalisation" comes back on R27 and R28 instead of a logging recommendation.
- **Bias to state:** the 3 runbooks were written by us, with words that match the questions, so their scores are inflated.

**Chunking one recommendation at a time** (regex on « Rn Titre ») helps the questions about rights. But the extraction is incomplete: **27 of 35 recommendations found in French and 24 of 35 in English**, because PDF line breaks and hyphenation (« en- trées ») break the pattern.

## Edge cases and limits
- **Lexical retrieval misses paraphrases and cross-language matches.** An English question matches a French passage only if they share words.
- **PDF extraction:** hyphens, layout fonts (pypdf warns that fontTools is missing) and lost headings.
- **A good passage can rank 3rd or lower** when a generic paragraph shares more words.

## What this changes in the plan
1. **A curated corpus, prepared before the event as data, not product code.** A `corpus.json` with one entry per unit:
   - ANSSI R1–R35, French and English: id, title, page, text;
   - ATLAS mitigations: id, name, description;
   - OWASP ASI01–ASI10 mitigations, once the PDF is downloaded by hand;
   - our runbooks.

   Check each entry against the PDF. That fixes the 8 to 11 recommendations the regex misses, plus the hyphenation.
2. **Hybrid retrieval:** BM25 plus embeddings, merged by rank (reciprocal rank fusion). Then **Jev re-ranks** each candidate (« ce passage répond-il à la question ? »), with a confidence score. The embedding model (OpenAI or Bedrock) is still to be tested with keys.
3. **The LLM rewrites the incident** into two short queries, one in French and one in English, before searching.
4. **Citation check in code, as Earshot did:** every step of the guide must quote a passage verbatim, and code checks that the quote appears (normalized) in the cited unit. Steps that don't pass are marked « non sourcé » or removed.
5. **Measure on the day:** the same 11 questions plus about 20 more, reporting exact-passage hit@3 before and after the hybrid search and Jev's re-ranking.
