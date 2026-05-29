from __future__ import annotations

import sqlite3
from typing import Any, Optional


class DocumentsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_documents(self, type: Optional[str], limit: int) -> list[Any]:
        if type and type != "all":
            rows = self._conn.execute(
                "SELECT * FROM documents WHERE type=? ORDER BY created_at DESC LIMIT ?",
                (type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_by_type(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT type, COUNT(*) as cnt FROM documents GROUP BY type"
        ).fetchall()
        return {r["type"]: r["cnt"] for r in rows}

    def create_document(self, doc: Any) -> Any:
        cur = self._conn.execute(
            "INSERT INTO documents (type, title, content, tags, url) VALUES (?,?,?,?,?)",
            (doc.type, doc.title, doc.content, doc.tags, doc.url),
        )
        self._conn.commit()
        row = self._conn.execute("SELECT * FROM documents WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)

    def update_document(self, doc_id: int, doc: Any) -> Any:
        existing = self._conn.execute("SELECT id FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not existing:
            return None
        self._conn.execute(
            """UPDATE documents
               SET type=?, title=?, content=?, tags=?, url=?,
                   updated_at=datetime('now','localtime')
               WHERE id=?""",
            (doc.type, doc.title, doc.content, doc.tags, doc.url, doc_id),
        )
        self._conn.commit()
        row = self._conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        return dict(row)

    def delete_document(self, doc_id: int) -> bool:
        existing = self._conn.execute("SELECT id FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not existing:
            return False
        self._conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        self._conn.commit()
        return True
