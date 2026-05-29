from __future__ import annotations

import os


def get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["http://localhost:3000", "http://127.0.0.1:3000"]
