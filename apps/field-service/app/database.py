"""
SmartLOTO Field Service â€” Couche d'accÃ¨s aux donnÃ©es.
Offre une interface unifiÃ©e (compatible Supabase) qui bascule automatiquement
sur SQLite local si Supabase n'est pas configurÃ©.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import SQLITE_DB_PATH


class SQLiteQueryResult:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data


class SQLiteTableQuery:
    def __init__(self, conn: sqlite3.Connection, table_name: str):
        self.conn = conn
        self.table_name = table_name
        self._select_fields: str = "*"
        self._where_clauses: List[str] = []
        self._where_params: List[Any] = []
        self._operation: str = "SELECT"
        self._insert_data: Optional[Dict[str, Any]] = None
        self._update_data: Optional[Dict[str, Any]] = None

    def select(self, fields: str = "*") -> SQLiteTableQuery:
        self._operation = "SELECT"
        self._select_fields = fields
        return self

    def eq(self, column: str, value: Any) -> SQLiteTableQuery:
        self._where_clauses.append(f"{column} = ?")
        self._where_params.append(value)
        return self

    def insert(self, data: Dict[str, Any]) -> SQLiteTableQuery:
        self._operation = "INSERT"
        self._insert_data = dict(data)
        return self

    def update(self, data: Dict[str, Any]) -> SQLiteTableQuery:
        self._operation = "UPDATE"
        self._update_data = dict(data)
        return self

    def execute(self) -> SQLiteQueryResult:
        cursor = self.conn.cursor()

        if self._operation == "SELECT":
            query = f"SELECT * FROM {self.table_name}"
            if self._where_clauses:
                query += " WHERE " + " AND ".join(self._where_clauses)
            cursor.execute(query, self._where_params)
            rows = cursor.fetchall()
            col_names = [d[0] for d in cursor.description] if cursor.description else []
            results = []
            for row in rows:
                row_dict = dict(zip(col_names, row))
                # DÃ©sÃ©rialisation des colonnes JSON
                if "workflow_stages" in row_dict and isinstance(row_dict["workflow_stages"], str):
                    try:
                        row_dict["workflow_stages"] = json.loads(row_dict["workflow_stages"])
                    except Exception:
                        pass
                if "logs" in row_dict and isinstance(row_dict["logs"], str):
                    try:
                        row_dict["logs"] = json.loads(row_dict["logs"])
                    except Exception:
                        pass
                results.append(row_dict)

            # Filtrage Ã©ventuel des champs si select explicite autre que "*"
            if self._select_fields != "*":
                fields = [f.strip() for f in self._select_fields.split(",")]
                filtered = []
                for item in results:
                    filtered.append({k: v for k, v in item.items() if k in fields})
                return SQLiteQueryResult(filtered)
            return SQLiteQueryResult(results)

        elif self._operation == "INSERT":
            if not self._insert_data:
                return SQLiteQueryResult([])
            data = dict(self._insert_data)
            if self.table_name == "interventions" and "id" not in data:
                data["id"] = str(uuid.uuid4())
            if "started_at" not in data and self.table_name == "interventions":
                data["started_at"] = datetime.now().isoformat()

            # SÃ©rialiser le JSON
            for k in ("workflow_stages", "logs"):
                if k in data and not isinstance(data[k], str):
                    data[k] = json.dumps(data[k])

            cols = list(data.keys())
            placeholders = ["?"] * len(cols)
            sql = f"INSERT INTO {self.table_name} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(sql, list(data.values()))
            self.conn.commit()

            # Relire la ligne insÃ©rÃ©e
            last_id = data.get("id") or data.get("machine_id")
            if last_id:
                col_id = "id" if "id" in data else "machine_id"
                return self.conn_client.table(self.table_name).select("*").eq(col_id, last_id).execute()
            return SQLiteQueryResult([data])

        elif self._operation == "UPDATE":
            if not self._update_data:
                return SQLiteQueryResult([])
            data = dict(self._update_data)
            # SÃ©rialiser le JSON
            for k in ("workflow_stages", "logs"):
                if k in data and not isinstance(data[k], str):
                    data[k] = json.dumps(data[k])

            set_clause = ", ".join(f"{k} = ?" for k in data.keys())
            params = list(data.values()) + self._where_params
            sql = f"UPDATE {self.table_name} SET {set_clause}"
            if self._where_clauses:
                sql += " WHERE " + " AND ".join(self._where_clauses)
            cursor.execute(sql, params)
            self.conn.commit()
            return SQLiteQueryResult([data])

        return SQLiteQueryResult([])


class LocalSQLiteClient:
    """Client SQLite reproduisant l'API Supabase pour un mode autonome 100% hors-ligne."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        cur = conn.cursor()

        # Table des procÃ©dures LOTO
        cur.execute("""
            CREATE TABLE IF NOT EXISTS procedures (
                machine_id TEXT PRIMARY KEY,
                machine_name TEXT NOT NULL,
                created_by_hse TEXT NOT NULL,
                status TEXT DEFAULT 'DRAFT_PENDING_REVIEW',
                workflow_stages TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table des interventions Unity
        cur.execute("""
            CREATE TABLE IF NOT EXISTS interventions (
                id TEXT PRIMARY KEY,
                machine_id TEXT NOT NULL,
                procedure_version_id TEXT,
                operator_name TEXT NOT NULL,
                status TEXT DEFAULT 'IN_PROGRESS',
                current_stage_id INT DEFAULT 1,
                logs TEXT DEFAULT '[]',
                signature_url TEXT,
                pdf_report_url TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        cur.execute("PRAGMA table_info(interventions)")
        columns = {row[1] for row in cur.fetchall()}
        if "procedure_version_id" not in columns:
            cur.execute("ALTER TABLE interventions ADD COLUMN procedure_version_id TEXT")

        conn.close()

    def table(self, table_name: str) -> SQLiteTableQuery:
        query = SQLiteTableQuery(self._get_connection(), table_name)
        query.conn_client = self
        return query


# â”€â”€ Initialisation globale de la base de donnÃ©es (100% Local SQLite) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
db: Any = None


def init_db() -> None:
    """Garantit l'initialisation de la base et l'auto-seed au demarrage du serveur."""
    global db
    if db is None:
        db = LocalSQLiteClient(str(SQLITE_DB_PATH))
    else:
        db._init_db()
