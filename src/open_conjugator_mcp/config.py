from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    camel_morph_db: Path
    unimorph_db: Path
    host: str
    port: int
    mcp_path: str

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("MORPH_DATA_DIR", PROJECT_ROOT / "data")).resolve()
        path = os.getenv("MCP_PATH", "/api/open-conjugator-mcp")
        if not path.startswith("/") or ".." in path:
            raise ValueError("MCP_PATH must be an absolute URL path without '..'")
        return cls(
            data_dir=data_dir,
            camel_morph_db=Path(
                os.getenv("CAMEL_MORPH_DB", data_dir / "camel_morph_msa_v1.0.db")
            ).resolve(),
            unimorph_db=Path(
                os.getenv("UNIMORPH_DB", data_dir / "unimorph_verbs.sqlite3")
            ).resolve(),
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "3000")),
            mcp_path=path,
        )


settings = Settings.from_env()

