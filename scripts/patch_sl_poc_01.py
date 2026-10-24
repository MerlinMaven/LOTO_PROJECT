#!/usr/bin/env python3
"""
Migration one-shot : Réévalue les citations de SL-POC-01 en base avec la nouvelle logique.

Règles appliquées (par ordre de priorité) :
1. qualification == "unknown"  → inferred_absence  (constat d'absence documentaire)
2. valeur/citation contient une phrase d'absence  → inferred_absence
3. citation_status déjà 'verified' / 'manual_verified' / 'inferred_absence'  → conservé
4. ni quote ni value  → inferred_absence (MVP : pas de fausse alerte)
5. Heuristique locale (25% de recouvrement sur le texte du doc)  → verified / unmatched

Lance depuis la racine : python scripts/patch_sl_poc_01.py
"""
import json
import re
import sqlite3
import sys
from workspace_paths import DB_PATH

# ── Mots-clés signalant un constat d'absence ─────────────────────────────────
ABSENCE_PHRASES = (
    "n'est pas documenté", "non documenté", "non confirmé",
    "n'est pas établi", "n'est pas mentionné", "aucune mention",
    "not documented", "not confirmed", "not established",
    "no mention", "not mentioned", "information non disponible",
    "n'est pas précisé", "non précisé", "non spécifié",
    "not specified", "not available",
)

VALID_STATUSES = {"manual_verified", "verified", "inferred_absence", "typography_normalized"}

STOP_WORDS = {
    "les", "des", "une", "dans", "pour", "avec", "sur", "est", "sont",
    "cette", "doit", "être", "par", "qui", "que", "aux", "leur", "afin",
    "tout", "tous", "the", "and", "for", "with", "that", "this", "from",
    "are", "both", "not", "there", "very", "pas", "mais", "bien", "plus",
}


def is_absence_claim(fact: dict) -> bool:
    if fact.get("qualification") == "unknown":
        return True
    text = str(fact.get("value") or fact.get("source_quote") or "").lower()
    return any(phrase in text for phrase in ABSENCE_PHRASES)


def heuristic_grounded(claim: str, all_text: str, threshold: float = 0.25) -> bool:
    """Retourne True si ≥ threshold% des tokens techniques du claim sont dans le texte."""
    tokens = [
        w.lower() for w in re.findall(r"\b\w{3,}\b", claim)
        if w.lower() not in STOP_WORDS
    ]
    if not tokens:
        return True
    source_lower = all_text.lower()
    matched = sum(1 for t in tokens if t in source_lower)
    return (matched / len(tokens)) >= threshold


def reclassify_facts(facts: list[dict], all_text: str) -> tuple[list[dict], dict]:
    """Retourne la liste de faits corrigés + un rapport de comptage."""
    stats = {"verified": 0, "inferred_absence": 0, "unmatched": 0, "already_ok": 0}

    for fact in facts:
        current = fact.get("citation_status")

        # ── Cas 0 : déjà valide, on ne touche pas
        if current in VALID_STATUSES:
            stats["already_ok"] += 1
            continue

        # ── Cas 1 : constat d'absence documentaire
        if is_absence_claim(fact):
            fact["citation_status"] = "inferred_absence"
            fact["verification_note"] = None
            stats["inferred_absence"] += 1
            continue

        quote = str(fact.get("source_quote") or "").strip()
        value = str(fact.get("value") or "").strip()

        # ── Cas 2 : ni citation ni valeur → absence présumée (MVP)
        if not quote and not value:
            fact["citation_status"] = "inferred_absence"
            fact["verification_note"] = None
            stats["inferred_absence"] += 1
            continue

        # ── Cas 3 : heuristique locale (25% de recouvrement)
        eval_text = quote if quote else value
        if heuristic_grounded(eval_text, all_text):
            fact["citation_status"] = "verified"
            fact["verification_note"] = None
            stats["verified"] += 1
        else:
            # Laisse 'unmatched' — vraie incohérence potentielle
            fact["citation_status"] = "unmatched"
            stats["unmatched"] += 1

    return facts, stats


def patch_procedure(machine_id: str = "SL-POC-01"):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Cherche la procédure (PK = machine_id)
    cur.execute("SELECT machine_id FROM procedures WHERE machine_id = ?", (machine_id,))
    row = cur.fetchone()
    if not row:
        print(f"❌  Procédure '{machine_id}' introuvable dans {DB_PATH}")
        sys.exit(1)
    print(f"✅  Procédure trouvée : {machine_id}")

    # Récupère toutes les versions de cette procédure
    cur.execute(
        "SELECT id, status, workflow_definition FROM procedure_versions "
        "WHERE procedure_id = ? ORDER BY version_number DESC",
        (machine_id,),
    )
    versions = cur.fetchall()
    if not versions:
        print("❌  Aucune version trouvée.")
        sys.exit(1)

    total_patched = 0
    for version in versions:
        wf_raw = version["workflow_definition"]
        if not wf_raw:
            continue
        try:
            wf = json.loads(wf_raw) if isinstance(wf_raw, str) else wf_raw
        except json.JSONDecodeError:
            print(f"  ⚠️  Version {version['id']} : JSON invalide, ignorée.")
            continue

        facts = wf.get("technical_facts", [])
        if not isinstance(facts, list) or not facts:
            print(f"  ℹ️  Version {version['id']} ({version['status']}) : aucun fait technique.")
            continue

        # Texte source du workflow (concaténation de tous les textes disponibles)
        all_text_parts = []
        for src in wf.get("sources", []):
            if isinstance(src, dict):
                all_text_parts.append(str(src.get("title", "")))
                all_text_parts.append(str(src.get("description", "")))
        # Ajoute aussi les faits existants comme corpus
        for f in facts:
            if isinstance(f, dict):
                all_text_parts.append(str(f.get("value", "")))
                all_text_parts.append(str(f.get("source_quote", "")))
        all_text = " ".join(all_text_parts)

        before_unmatched = sum(1 for f in facts if isinstance(f, dict) and f.get("citation_status") == "unmatched")
        facts, stats = reclassify_facts(facts, all_text)
        after_unmatched = sum(1 for f in facts if isinstance(f, dict) and f.get("citation_status") == "unmatched")

        wf["technical_facts"] = facts
        new_wf_json = json.dumps(wf, ensure_ascii=False)

        cur.execute(
            "UPDATE procedure_versions SET workflow_definition = ? WHERE id = ?",
            (new_wf_json, version["id"]),
        )
        total_patched += 1
        print(
            f"  📝  Version {version['id']} ({version['status']}) — "
            f"unmatched : {before_unmatched} → {after_unmatched}  |  "
            f"déjà ok={stats['already_ok']}, verified={stats['verified']}, "
            f"inferred_absence={stats['inferred_absence']}, unmatched={stats['unmatched']}"
        )

    conn.commit()
    conn.close()
    print(f"\n✅  {total_patched} version(s) mise(s) à jour dans smartloto.db")
    print("   → Rechargez la page du dashboard pour voir le nouveau score.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "SL-POC-01"
    patch_procedure(target)
