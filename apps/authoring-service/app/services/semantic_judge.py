"""
Module de validation sémantique par LLM-as-a-Judge (Natural Language Inference).
Évalue la fidélité sémantique des affirmations techniques vis-à-vis du document source.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from app.config import (
    DOCUMENT_GENERATION_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    PROVIDER_REQUEST_TIMEOUT_SECONDS,
)

SYSTEM_PROMPT = (
    "Tu es un auditeur HSE industriel strict. Ta tâche est de vérifier si l'affirmation technique (Claim) "
    "est factuellement et logiquement déductible de l'extrait source (Source). Tolère les reformulations et synonymes. "
    "Ne valide pas si l'affirmation invente un détail absent de la source. "
    "Réponds UNIQUEMENT par un JSON valide avec la clé booléenne is_supported."
)


async def verify_semantic_grounding(pdf_extract: str, ai_claim: str) -> bool:
    """Use the selected Gemini model; provider failures never become heuristic approval."""
    if not ai_claim or not ai_claim.strip() or not pdf_extract or not pdf_extract.strip():
        return False
    if DOCUMENT_GENERATION_PROVIDER != "gemini" or not GEMINI_API_KEY or not GEMINI_MODEL:
        raise ValueError("Configure DOCUMENT_GENERATION_PROVIDER=gemini, GEMINI_API_KEY and GEMINI_MODEL locally")
    async with httpx.AsyncClient(timeout=httpx.Timeout(PROVIDER_REQUEST_TIMEOUT_SECONDS, connect=5)) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": GEMINI_API_KEY},
            json={"system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                  "contents": [{"role": "user", "parts": [{"text": f"Source: {pdf_extract.strip()}\n\nClaim: {ai_claim.strip()}"}]}],
                  "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                      "responseJsonSchema": {"type": "object", "properties": {"is_supported": {"type": "boolean"}}, "required": ["is_supported"]}}})
        response.raise_for_status()
        parts = response.json()["candidates"][0]["content"]["parts"]
        result = json.loads("".join(part.get("text", "") for part in parts))
        if type(result.get("is_supported")) is not bool:
            raise ValueError("Invalid semantic verification response")
        return result["is_supported"]


_ABSENCE_PHRASES = (
    "n'est pas documenté",
    "non documenté",
    "non confirmé",
    "n'est pas établi",
    "n'est pas mentionné",
    "aucune mention",
    "not documented",
    "not confirmed",
    "not established",
    "no mention",
    "not mentioned",
    "information non disponible",
)


def _is_absence_claim(fact: dict) -> bool:
    """
    Retourne True si le fait exprime un constat d’absence documentaire.
    Ce n'est pas une hallucination — c'est une synthèse du manque d'information.
    """
    if fact.get("qualification") == "unknown":
        return True
    claim_lower = str(fact.get("value") or fact.get("source_quote") or "").lower()
    return any(phrase in claim_lower for phrase in _ABSENCE_PHRASES)


async def verify_all_facts_grounding(
    facts: list[dict[str, any]],
    extracted_by_page: dict[int, str],
    all_text: str,
) -> list[dict[str, any]]:
    """
    Parallélise la vérification de toutes les citations via asyncio.gather pour ne pas ralentir le pipeline.
    """
    async def _evaluate(fact: dict[str, any]) -> dict[str, any]:
        # —— Cas 1 : Constat d’absence documentaire — VALIDÉ sans appel LLM ————————
        if _is_absence_claim(fact):
            fact["citation_status"] = "inferred_absence"
            fact["verification_note"] = None
            return fact

        quote = str(fact.get("source_quote") or "").strip()
        claim = str(fact.get("value") or quote).strip()
        pages = fact.get("source_pages", [])

        # —— Cas 2 : Ni citation ni valeur — VALIDÉ par défaut (MVP) ——————————————
        if not quote and not claim:
            fact["citation_status"] = "inferred_absence"
            fact["verification_note"] = None
            return fact

        # Extrait le contexte textuel des pages concernées ou du document complet
        if isinstance(pages, list) and pages:
            pdf_extract = "\n".join(
                extracted_by_page[p] for p in pages if p in extracted_by_page
            ).strip()
        else:
            pdf_extract = ""
        # Toujours utiliser le texte complet en fallback (jamais un fragment vide)
        if not pdf_extract:
            pdf_extract = all_text

        # —— Cas 3 : Évaluation LLM Juge (NLI) sur le texte complet disponible ————
        eval_claim = quote if quote else claim
        is_supported = await verify_semantic_grounding(pdf_extract=pdf_extract, ai_claim=eval_claim)

        if is_supported:
            fact["citation_status"] = "verified"
            fact["verification_note"] = None
        else:
            fact["citation_status"] = "unmatched"
            fact["verification_note"] = "Affirmation non étayée par l'extrait source (inférence non confirmée)."

        return fact

    tasks = [_evaluate(fact) for fact in facts]
    return await asyncio.gather(*tasks)
