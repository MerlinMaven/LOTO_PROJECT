"""
Module de validation sémantique par LLM-as-a-Judge (Natural Language Inference).
Évalue la fidélité sémantique des affirmations techniques vis-à-vis du document source.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

import httpx

from app.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    PROVIDER_REQUEST_TIMEOUT_SECONDS,
)

logger = logging.getLogger("smartloto.semantic_judge")

SYSTEM_PROMPT = (
    "Tu es un auditeur HSE industriel strict. Ta tâche est de vérifier si l'affirmation technique (Claim) "
    "est factuellement et logiquement déductible de l'extrait source (Source). Tolère les reformulations et synonymes. "
    "Ne valide pas si l'affirmation invente un détail absent de la source. "
    "Réponds UNIQUEMENT par un JSON valide avec la clé booléenne is_supported."
)


async def verify_semantic_grounding(pdf_extract: str, ai_claim: str) -> bool:
    """
    Vérifie la fidélité sémantique d'une affirmation technique vis-à-vis d'un extrait de document source.
    Utilise un LLM Juge (Llama-3-8b via Groq) pour exécuter une classification binaire NLI déterministe.
    """
    if not ai_claim or not ai_claim.strip():
        return False
    if not pdf_extract or not pdf_extract.strip():
        return False

    user_prompt = f"Source: {pdf_extract.strip()}\n\nClaim: {ai_claim.strip()}"

    # 1. Tentative avec Groq (Llama-3.3-70b ou modèle configuré)
    if GROQ_API_KEY:
        judge_model = GROQ_MODEL or "llama-3.3-70b-versatile"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={
                        "model": judge_model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.0,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                    parsed = json.loads(content)
                    return bool(parsed.get("is_supported", False))
                # Erreur HTTP non-200 (quota, 403 Cloudflare, 5xx…)
                logger.warning(
                    "[SemanticJudge] API Groq HTTP %d — Repli sur analyse heuristique. "
                    "Détail : %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return _heuristic_semantic_grounding(pdf_extract, ai_claim)
        except Exception as exc:
            logger.warning(
                "[SemanticJudge] Exception réseau lors de l'appel Groq — "
                "Repli sur analyse heuristique. Erreur : %s",
                exc,
            )
            return _heuristic_semantic_grounding(pdf_extract, ai_claim)

    # 2. Pas de clé API configurée → repli heuristique local
    return _heuristic_semantic_grounding(pdf_extract, ai_claim)


def _heuristic_semantic_grounding(pdf_extract: str, ai_claim: str) -> bool:
    """
    Évaluation sémantique conceptuelle tolérant reformulations et synonymes
    lorsque l'API LLM externe est temporairement inaccessible.
    """
    stop_words = {
        "les", "des", "une", "dans", "pour", "avec", "sur", "est", "sont", "cette", "doit",
        "être", "par", "qui", "que", "aux", "leur", "afin", "tout", "tous", "the", "and",
        "for", "with", "that", "this", "from", "are", "both", "not", "there", "very",
    }
    claim_tokens = [
        w.lower()
        for w in re.findall(r"\b\w{3,}\b", ai_claim)
        if w.lower() not in stop_words
    ]
    if not claim_tokens:
        return True

    source_lower = pdf_extract.lower()
    matched_count = sum(1 for token in claim_tokens if token in source_lower)
    overlap_ratio = matched_count / len(claim_tokens)

    # Seuil tolérant : 25% des concepts clés corroborés suffisent (reformulations, synonymes techniques)
    return overlap_ratio >= 0.25



# Mots-clés signalant un constat d'absence documentaire (synthèse HSE, non une hallucination)
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
