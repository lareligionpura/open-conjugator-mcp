# Third-party data and software

Open Conjugator MCP is MIT-licensed code. Its generated runtime data directory contains
third-party linguistic resources under their own licenses:

- **CAMeL Tools 1.6.0** — New York University Abu Dhabi, MIT license.
- **CAMeL Morph MSA v1.0** — CAMeL Lab, CC BY 4.0. The pinned release is the
  LREC-COLING 2024 database at commit `15f5aede4b609db54abd6f87aded1f5ec5d930af`.
- **UniMorph English, Spanish, and French datasets** — UniMorph contributors,
  CC BY-SA 3.0. The runtime SQLite index is a transformed subset containing verb rows;
  it remains available under CC BY-SA 3.0.

Source URLs, exact commits, and SHA-256 checksums are recorded in
`scripts/prepare_data.py` and included in tool responses.

