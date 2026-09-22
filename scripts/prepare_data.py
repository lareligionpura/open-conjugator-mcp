#!/usr/bin/env python3
"""Download pinned linguistic resources and build the read-only runtime index."""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
import unicodedata
import urllib.request
from dataclasses import dataclass
from pathlib import Path


USER_AGENT = "Open-Conjugator-MCP-data-builder/2.0 (+https://github.com/)"
CAMEL_MORPH_COMMIT = "15f5aede4b609db54abd6f87aded1f5ec5d930af"  # pragma: allowlist secret


@dataclass(frozen=True)
class Resource:
    filename: str
    url: str
    sha256: str


CAMEL_MORPH = Resource(
    filename="camel_morph_msa_v1.0.db",
    url=(
        "https://raw.githubusercontent.com/CAMeL-Lab/camel_morph/"
        f"{CAMEL_MORPH_COMMIT}/official_releases/lrec-coling2024_release/"
        "databases/camel-morph-msa/camel_morph_msa_v1.0.db"
    ),
    sha256="110e03baa282874062d076e23d9671e985b6f76520b891d58cba4e55de0b8f60",  # pragma: allowlist secret
)

UNIMORPH: dict[str, Resource] = {
    "eng": Resource(
        "eng",
        "https://raw.githubusercontent.com/unimorph/eng/"
        "66e0e9e8e2dcd196da081a25a48e5c1fe3d8b49b/eng",
        "20a191cefdc7cad6fa74b00f49d6f658684f17b14541aae372e5a3d5a8c15c67",  # pragma: allowlist secret
    ),
    "spa": Resource(
        "spa",
        "https://raw.githubusercontent.com/unimorph/spa/"
        "b9655efb0e5ce0f99809badaa7f4e93017ab8430/spa",
        "7a165d4b44eb078d23964f3eee3813f5140c5df0ffab0143c806c562e67f8771",  # pragma: allowlist secret
    ),
    "fra": Resource(
        "fra",
        "https://raw.githubusercontent.com/unimorph/fra/"
        "f672f8cceb2d5f5a1e2241b5622c8845f8274635/fra",
        "4760fc36435a9ffba9b4de6f0787d8eca5b15022e6b141e3b242b129f0d88dcb",  # pragma: allowlist secret
    ),
}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def download(resource: Resource, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and digest(destination) == resource.sha256:
        print(f"verified {destination}")
        return destination

    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(resource.url, headers={"User-Agent": USER_AGENT})
    print(f"downloading {resource.url}")
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    actual = digest(temporary)
    if actual != resource.sha256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"checksum mismatch for {resource.filename}: expected {resource.sha256}, got {actual}"
        )
    temporary.replace(destination)
    return destination


def normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def is_verb(features: str) -> bool:
    tags = features.split(";")
    return any(tag == "V" or tag.startswith("V.") for tag in tags)


def iter_rows(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            lemma, form, features = parts
            if lemma and form and features and is_verb(features):
                yield lemma, normalized(lemma), form, normalized(form), features
            elif line_number == 1 and not line.strip():
                continue


def build_unimorph_database(sources: dict[str, Path], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            PRAGMA temp_store=MEMORY;
            CREATE TABLE forms (
                language TEXT NOT NULL,
                lemma TEXT NOT NULL,
                lemma_norm TEXT NOT NULL,
                form TEXT NOT NULL,
                form_norm TEXT NOT NULL,
                features TEXT NOT NULL
            );
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        for language, source in sources.items():
            batch: list[tuple[str, str, str, str, str, str]] = []
            count = 0
            for lemma, lemma_norm, form, form_norm, features in iter_rows(source):
                batch.append((language, lemma, lemma_norm, form, form_norm, features))
                if len(batch) >= 10_000:
                    connection.executemany("INSERT INTO forms VALUES (?, ?, ?, ?, ?, ?)", batch)
                    count += len(batch)
                    batch.clear()
            if batch:
                connection.executemany("INSERT INTO forms VALUES (?, ?, ?, ?, ?, ?)", batch)
                count += len(batch)
            connection.execute(
                "INSERT INTO metadata VALUES (?, ?)", (f"rows.{language}", str(count))
            )
            print(f"indexed {count:,} UniMorph verb forms for {language}")

        connection.executescript(
            """
            CREATE INDEX forms_by_lemma ON forms(language, lemma_norm);
            CREATE INDEX forms_by_form ON forms(language, form_norm);
            CREATE TABLE lemmas AS
                SELECT language, lemma, lemma_norm, COUNT(*) AS form_count
                FROM forms GROUP BY language, lemma, lemma_norm;
            CREATE UNIQUE INDEX lemmas_exact ON lemmas(language, lemma_norm, lemma);
            CREATE TABLE models AS
                SELECT language, features, COUNT(*) AS form_count, MIN(lemma) AS sample_lemma
                FROM forms GROUP BY language, features;
            CREATE INDEX models_by_language ON models(language, form_count DESC);
            INSERT INTO metadata VALUES ('schema_version', '1');
            ANALYZE;
            """
        )
        connection.commit()
    finally:
        connection.close()
    temporary.replace(destination)
    print(f"wrote {destination} ({destination.stat().st_size / 1024 / 1024:.1f} MiB)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache"))
    parser.add_argument("--force-index", action="store_true")
    args = parser.parse_args()

    args.data_dir.mkdir(parents=True, exist_ok=True)
    camel_cached = download(CAMEL_MORPH, args.cache_dir / CAMEL_MORPH.filename)
    camel_destination = args.data_dir / CAMEL_MORPH.filename
    if not camel_destination.exists() or digest(camel_destination) != CAMEL_MORPH.sha256:
        camel_destination.write_bytes(camel_cached.read_bytes())
    print(f"ready {camel_destination}")

    sources = {
        language: download(resource, args.cache_dir / "unimorph" / resource.filename)
        for language, resource in UNIMORPH.items()
    }
    index = args.data_dir / "unimorph_verbs.sqlite3"
    if args.force_index or not index.exists():
        build_unimorph_database(sources, index)
    else:
        print(f"ready {index}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"data preparation failed: {error}", file=sys.stderr)
        raise
