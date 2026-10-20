"""
SmartLOTO Field Service — Couche d'accès aux données.
Offre une interface unifiée (compatible Supabase) qui bascule automatiquement
sur SQLite local si Supabase n'est pas configuré.
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
                # Désérialisation des colonnes JSON
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

            # Filtrage éventuel des champs si select explicite autre que "*"
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

            # Sérialiser le JSON
            for k in ("workflow_stages", "logs"):
                if k in data and not isinstance(data[k], str):
                    data[k] = json.dumps(data[k])

            cols = list(data.keys())
            placeholders = ["?"] * len(cols)
            sql = f"INSERT INTO {self.table_name} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(sql, list(data.values()))
            self.conn.commit()

            # Relire la ligne insérée
            last_id = data.get("id") or data.get("machine_id")
            if last_id:
                col_id = "id" if "id" in data else "machine_id"
                return self.conn_client.table(self.table_name).select("*").eq(col_id, last_id).execute()
            return SQLiteQueryResult([data])

        elif self._operation == "UPDATE":
            if not self._update_data:
                return SQLiteQueryResult([])
            data = dict(self._update_data)
            # Sérialiser le JSON
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


SAMPLE_PUMP_WORKFLOW = {
    "lockout": [
        {
            "stage_id": 1,
            "title": "Consignation Électrique",
            "actions": [
                {
                    "action_id": "step_1",
                    "description": "Tourner le sectionneur Q1 sur la position 0 (OFF) et apposer le cadenas rouge.",
                    "vision_prompt": "red padlock on electrical rotary switch in off position",
                    "completion_check": "Cadenas en place et sectionneur verrouillé.",
                    "spatial_guide": {
                        "hologram_type": "padlock",
                        "pos_x": 0.15,
                        "pos_y": 1.20,
                        "pos_z": 0.45,
                        "rot_x": 0.0,
                        "rot_y": 90.0,
                        "rot_z": 0.0,
                    },
                }
            ],
        },
        {
            "stage_id": 2,
            "title": "Vérification d'Absence de Tension (VAT)",
            "actions": [
                {
                    "action_id": "step_2",
                    "description": "Contrôler la tension résiduelle aux bornes du moteur à l'aide d'un multimètre certifié.",
                    "vision_prompt": "digital multimeter measuring zero voltage display",
                    "completion_check": "Affichage 0.00 V confirmé.",
                    "spatial_guide": {
                        "hologram_type": "sensor",
                        "pos_x": -0.20,
                        "pos_y": 0.95,
                        "pos_z": 0.50,
                        "rot_x": 0.0,
                        "rot_y": 0.0,
                        "rot_z": 0.0,
                    },
                }
            ],
        },
    ],
    "restoration": [
        {
            "stage_id": 3,
            "title": "Déconsignation et Remise en Service",
            "actions": [
                {
                    "action_id": "step_3",
                    "description": "Retirer le cadenas de consignation et réarmer le sectionneur principal sur 1 (ON).",
                    "vision_prompt": "electrical rotary switch in on position without padlock",
                    "completion_check": "Sectionneur réarmé sur 1 (ON).",
                    "spatial_guide": {
                        "hologram_type": "switch",
                        "pos_x": 0.15,
                        "pos_y": 1.20,
                        "pos_z": 0.45,
                        "rot_x": 0.0,
                        "rot_y": 0.0,
                        "rot_z": 0.0,
                    },
                }
            ],
        }
    ],
    "anchors": {
        "Sectionneur_Q1": {
            "pos_x": 0.15,
            "pos_y": 1.20,
            "pos_z": 0.45,
            "rot_x": 0.0,
            "rot_y": 90.0,
            "rot_z": 0.0,
        },
        "Moteur_Pompe": {
            "pos_x": -0.20,
            "pos_y": 0.95,
            "pos_z": 0.50,
            "rot_x": 0.0,
            "rot_y": 0.0,
            "rot_z": 0.0,
        },
    },
}


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

        # Table des procédures LOTO
        cur.execute("""
            CREATE TABLE IF NOT EXISTS procedures (
                machine_id TEXT PRIMARY KEY,
                machine_name TEXT NOT NULL,
                created_by_hse TEXT NOT NULL,
                status TEXT DEFAULT 'APPROVED',
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

        # Vérifier si PUMP-001 existe spécifiquement
        cur.execute("SELECT workflow_stages, status FROM procedures WHERE machine_id = 'PUMP-001'")
        row = cur.fetchone()

        if not row:
            cur.execute("""
                INSERT INTO procedures (machine_id, machine_name, created_by_hse, status, workflow_stages)
                VALUES (?, ?, ?, ?, ?)
            """, (
                "PUMP-001",
                "Pompe Principale d'Extraction",
                "hse_supervisor@smartloto.io",
                "APPROVED",
                json.dumps(SAMPLE_PUMP_WORKFLOW)
            ))
            conn.commit()
            print(f"[INFO-SEED] Machine PUMP-001 inseree avec succes dans {self.db_path}")
        else:
            # Vérifier que le workflow_stages existant est complet
            existing_stages_raw = row[0]
            needs_update = False
            try:
                parsed = json.loads(existing_stages_raw) if isinstance(existing_stages_raw, str) else existing_stages_raw
                if not parsed or not parsed.get("lockout") or not parsed.get("restoration"):
                    needs_update = True
            except Exception:
                needs_update = True

            if needs_update or row[1] != "APPROVED":
                cur.execute("""
                    UPDATE procedures 
                    SET machine_name = 'Pompe Principale d''Extraction', status = 'APPROVED', workflow_stages = ?
                    WHERE machine_id = 'PUMP-001'
                """, (json.dumps(SAMPLE_PUMP_WORKFLOW),))
                conn.commit()
                print(f"[INFO-SEED] Machine PUMP-001 verifiee et mise a jour avec succes dans {self.db_path}")
            else:
                print(f"[INFO-SEED] Machine PUMP-001 deja presente et approuvee dans {self.db_path}")

        conn.close()

    def table(self, table_name: str) -> SQLiteTableQuery:
        query = SQLiteTableQuery(self._get_connection(), table_name)
        query.conn_client = self
        return query


# ── Initialisation globale de la base de données (100% Local SQLite) ──────────
db: Any = LocalSQLiteClient(str(SQLITE_DB_PATH))
print(f"[INFO] Base SQLite locale activee (Zero Cloud) : {SQLITE_DB_PATH}")


def init_db() -> None:
    """Garantit l'initialisation de la base et l'auto-seed au demarrage du serveur."""
    global db
    if db is None:
        db = LocalSQLiteClient(str(SQLITE_DB_PATH))
    else:
        db._init_db()
