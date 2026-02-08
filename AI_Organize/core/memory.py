import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np



# ----------------------------
# Configuration
# ----------------------------

GLOBAL_DB_PATH = Path.home() / ".local" / "share" / "ai_organize" / "global.db"

AUTO_GLOBAL_THRESHOLD = 0.85
ASK_GLOBAL_THRESHOLD = 0.60


# ----------------------------
# Helpers
# ----------------------------

def _ensure_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY,
            scope TEXT NOT NULL,
            extension TEXT,
            tokens TEXT,
            target_folder TEXT NOT NULL,
            directory_description TEXT,
            embedding BLOB NOT NULL,
            confidence REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def _serialize_embedding(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def _deserialize_embedding(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


# ----------------------------
# Public API
# ----------------------------

class MemoryStore:
    """
    Handles both project and global memory.
    """

    def __init__(self, project_db: Path):
        self.project_conn = _ensure_db(project_db)
        self.global_conn = _ensure_db(GLOBAL_DB_PATH)

    # -------- Retrieval --------

    def get_similar(
        self,
        embedding: np.ndarray,
        scope: str,
        limit: int = 5,
    ) -> List[Tuple[float, dict]]:
        conn = self.global_conn if scope == "global" else self.project_conn

        cur = conn.execute(
            "SELECT extension, tokens, target_folder, directory_description, embedding, confidence FROM decisions"
        )

        results = []
        for ext, tokens, folder, desc, emb_blob, conf in cur.fetchall():
            stored_vec = _deserialize_embedding(emb_blob)

            from akinus.ai.ollama import cosine_similarity
            score = cosine_similarity(embedding, stored_vec)


            results.append(
                (
                    score,
                    {
                        "extension": ext,
                        "tokens": tokens.split() if tokens else [],
                        "target_folder": folder,
                        "directory_description": desc,
                        "confidence": conf,
                    },
                )
            )

        results.sort(key=lambda x: x[0], reverse=True)
        return results[:limit]

    # -------- Recording --------

    def record_decision(
        self,
        *,
        embedding: np.ndarray,
        extension: str,
        tokens: List[str],
        target_folder: str,
        directory_description: Optional[str],
        confidence: float,
        ask_user_callback=None,
    ):
        """
        Record a decision using conservative hybrid rules.
        """

        # Always store in project memory
        self._insert(
            conn=self.project_conn,
            scope="project",
            embedding=embedding,
            extension=extension,
            tokens=tokens,
            target_folder=target_folder,
            directory_description=directory_description,
            confidence=confidence,
        )

        # Decide global behavior
        if confidence >= AUTO_GLOBAL_THRESHOLD:
            self._insert(
                conn=self.global_conn,
                scope="global",
                embedding=embedding,
                extension=extension,
                tokens=tokens,
                target_folder=target_folder,
                directory_description=directory_description,
                confidence=confidence,
            )

        elif confidence >= ASK_GLOBAL_THRESHOLD and ask_user_callback:
            if ask_user_callback(
                {
                    "extension": extension,
                    "tokens": tokens,
                    "target_folder": target_folder,
                    "confidence": confidence,
                }
            ):
                self._insert(
                    conn=self.global_conn,
                    scope="global",
                    embedding=embedding,
                    extension=extension,
                    tokens=tokens,
                    target_folder=target_folder,
                    directory_description=directory_description,
                    confidence=confidence,
                )

    # -------- Internal --------

    def _insert(
        self,
        *,
        conn: sqlite3.Connection,
        scope: str,
        embedding: np.ndarray,
        extension: str,
        tokens: List[str],
        target_folder: str,
        directory_description: Optional[str],
        confidence: float,
    ):
        conn.execute(
            """
            INSERT INTO decisions
            (scope, extension, tokens, target_folder, directory_description, embedding, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scope,
                extension,
                " ".join(tokens),
                target_folder,
                directory_description,
                _serialize_embedding(embedding),
                confidence,
            ),
        )
        conn.commit()
    
    # --- Clear memory --
    def clear(self, scope: str = "project"):
        """
        Clear memory entries.

        Args:
            scope: "project", "global", or "all"
        """
        if scope in ("project", "all"):
            self.project_conn.execute(
                "CREATE TABLE IF NOT EXISTS memory ("
                "embedding BLOB, "
                "extension TEXT, "
                "tokens TEXT, "
                "target_folder TEXT, "
                "directory_description TEXT, "
                "confidence REAL)"
            )
            self.project_conn.execute("DELETE FROM memory")
            self.project_conn.commit()

        if scope in ("global", "all"):
            self.global_conn.execute(
                "CREATE TABLE IF NOT EXISTS memory ("
                "embedding BLOB, "
                "extension TEXT, "
                "tokens TEXT, "
                "target_folder TEXT, "
                "directory_description TEXT, "
                "confidence REAL)"
            )
            self.global_conn.execute("DELETE FROM memory")
            self.global_conn.commit()

