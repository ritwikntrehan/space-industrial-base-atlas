# Atlas data layers

- `source/`: curated source snapshots or references derived from authoritative public material. These preserve retrieval context and never contain credentials.
- `canonical/`: validated, normalized, deduplicated records used as the internal source of truth.
- `website/`: compact deployment payloads containing only fields required by the application.
- `source_manifest.json`: provider, access, coverage, reuse, update, authentication, and ingestion status for every evaluated source.

Run `python scripts/build_data.py` after editing the curated source records. Large or frequently changing sources should be represented by a manifest entry and a reproducible ingestion script rather than committed as bulk downloads.
