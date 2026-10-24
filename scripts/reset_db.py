#!/usr/bin/env python3
"""
SmartLOTO - Script de remise à zéro de la base de données et des fichiers temporaires.
Usage depuis la racine : python scripts/reset_db.py
"""

import sqlite3
from workspace_paths import DB_PATH, ROOT_DIR


def clean_database() -> None:
    if not DB_PATH.exists():
        print(f"[!] Fichier de base {DB_PATH} introuvable.")
        return

    print(f"[*] Nettoyage de la base de données : {DB_PATH.name}...")
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Liste des tables applicatives
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]

    cur.execute("PRAGMA foreign_keys = OFF")
    for table in tables:
        cur.execute(f"DELETE FROM {table}")
        print(f"  - Table vidée : {table}")

    conn.commit()
    cur.execute("VACUUM")
    conn.close()
    print("[OK] Toutes les tables ont été vidées avec succès.\n")


def clean_storage() -> None:
    print("[*] Nettoyage des dossiers de stockage et fichiers temporaires...")
    storage_dirs = [
        ROOT_DIR / "apps" / "field-service" / "storage" / "evidence",
        ROOT_DIR / "apps" / "field-service" / "storage" / "signatures",
        ROOT_DIR / "apps" / "field-service" / "storage" / "reports",
        ROOT_DIR / "apps" / "authoring-service" / "data" / "documents",
    ]

    for s_dir in storage_dirs:
        if not s_dir.exists():
            continue
        count = 0
        for f in s_dir.iterdir():
            if f.is_file() and f.name != ".gitkeep":
                try:
                    f.unlink()
                    count += 1
                except Exception as e:
                    print(f"  [!] Erreur sur {f.name}: {e}")
        rel_path = s_dir.relative_to(ROOT_DIR)
        print(f"  - {rel_path} : {count} fichier(s) supprimé(s)")

    print("[OK] Stockage nettoyé.\n")


if __name__ == "__main__":
    clean_database()
    clean_storage()
    print("[TERMINE] Systeme pret pour un nouveau test de A a Z !")
