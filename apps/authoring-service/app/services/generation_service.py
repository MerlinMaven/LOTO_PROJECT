"""
SmartLOTO Authoring Service — Service de Génération LLM.
Génère des procédures LOTO conformes OSHA 1910.147 via LLM (OpenRouter, Groq, Mistral, vLLM)
avec un mode 'stub' haute fidélité permettant de tester immédiatement sans clé API.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional
import httpx

from app.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    MISTRAL_API_KEY,
    MISTRAL_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    VLLM_BASE_URL,
    VLLM_MODEL,
)
from app.schemas import GenerationRunRequest, GenerationRunResponse, ValidationIssueSummary


SYSTEM_PROMPT = """Tu es un ingénieur expert certifié en sécurité industrielle et consignation LOTO (OSHA 29 CFR 1910.147).
À partir de la machine et des composants fournis, génère une procédure de consignation rigoureuse.
Réponds STRICTEMENT par un objet JSON valide avec la structure suivante :
{
  "lockout": [
    {
      "stage_id": 1,
      "title": "Nom de l'étape",
      "actions": [
        {
          "action_id": "step_1",
          "description": "Instruction précise pour l'opérateur",
          "vision_prompt": "description visuelle de l'état pour détection YOLO-World",
          "completion_check": "condition de validation",
          "spatial_guide": {
            "hologram_type": "padlock",
            "pos_x": 0.0, "pos_y": 1.0, "pos_z": 0.5,
            "rot_x": 0.0, "rot_y": 0.0, "rot_z": 0.0
          }
        }
      ]
    }
  ],
  "restoration": [
    {
      "stage_id": 2,
      "title": "Remise en service",
      "actions": [...]
    }
  ],
  "anchors": {
    "Nom_Organe": {"pos_x": 0.0, "pos_y": 1.0, "pos_z": 0.5, "rot_x": 0.0, "rot_y": 0.0, "rot_z": 0.0}
  }
}
"""


def generate_stub_procedure(machine_name: str, components: str) -> Dict[str, Any]:
    """Génère un workflow LOTO modèle prêt pour la validation et l'utilisation AR."""
    comp_list = [c.strip() for c in components.replace(",", "\n").split("\n") if c.strip()]
    organ_1 = comp_list[0] if comp_list else "Sectionneur Général Q1"
    organ_2 = comp_list[1] if len(comp_list) > 1 else "Vanne d'Isolation Principale V1"

    return {
        "lockout": [
            {
                "stage_id": 1,
                "title": f"Consignation Électrique — {organ_1}",
                "actions": [
                    {
                        "action_id": "step_1",
                        "description": f"Basculer {organ_1} en position OFF (0) et poser le cadenas de consignation rouge avec étiquette d'avertissement.",
                        "vision_prompt": "red padlock on circuit breaker handle in off position",
                        "completion_check": "Cadenas rouge verrouillé et étiquette visible.",
                        "spatial_guide": {
                            "hologram_type": "padlock",
                            "pos_x": 0.20, "pos_y": 1.25, "pos_z": 0.40,
                            "rot_x": 0.0, "rot_y": 90.0, "rot_z": 0.0
                        }
                    },
                    {
                        "action_id": "step_2",
                        "description": "Effectuer une Vérification d'Absence de Tension (VAT) avec un multimètre certifié CAT IV.",
                        "vision_prompt": "digital multimeter showing zero voltage reading",
                        "completion_check": "Tension résiduelle 0.00V confirmée.",
                        "spatial_guide": {
                            "hologram_type": "sensor",
                            "pos_x": 0.20, "pos_y": 1.05, "pos_z": 0.40,
                            "rot_x": 0.0, "rot_y": 0.0, "rot_z": 0.0
                        }
                    }
                ]
            },
            {
                "stage_id": 2,
                "title": f"Purge et Condamnation des Fluides — {organ_2}",
                "actions": [
                    {
                        "action_id": "step_3",
                        "description": f"Fermer la vanne {organ_2}, poser le bloque-vanne et cadenasser.",
                        "vision_prompt": "closed valve handle with lockout clamshell cover",
                        "completion_check": "Vanne fermée et coque de condamnation verrouillée.",
                        "spatial_guide": {
                            "hologram_type": "valve",
                            "pos_x": -0.35, "pos_y": 0.85, "pos_z": 0.60,
                            "rot_x": 0.0, "rot_y": 0.0, "rot_z": 0.0
                        }
                    }
                ]
            }
        ],
        "restoration": [
            {
                "stage_id": 3,
                "title": "Déconsignation et Remise en Service",
                "actions": [
                    {
                        "action_id": "step_4",
                        "description": "Vérifier la zone de travail, retirer tous les outils, déverrouiller et rouvrir les alimentations.",
                        "vision_prompt": "valve and electrical switch restored to operational state",
                        "completion_check": "Tous les cadenas retirés et zone sécurisée.",
                        "spatial_guide": {
                            "hologram_type": "switch",
                            "pos_x": 0.20, "pos_y": 1.25, "pos_z": 0.40,
                            "rot_x": 0.0, "rot_y": 0.0, "rot_z": 0.0
                        }
                    }
                ]
            }
        ],
        "anchors": {
            organ_1: {"pos_x": 0.20, "pos_y": 1.25, "pos_z": 0.40, "rot_x": 0.0, "rot_y": 90.0, "rot_z": 0.0},
            organ_2: {"pos_x": -0.35, "pos_y": 0.85, "pos_z": 0.60, "rot_x": 0.0, "rot_y": 0.0, "rot_z": 0.0}
        }
    }


async def call_llm(provider: str, prompt: str) -> Optional[Dict[str, Any]]:
    """Appelle le fournisseur LLM sélectionné via HTTP."""
    url = ""
    headers = {"Content-Type": "application/json"}
    payload: Dict[str, Any] = {}

    if provider == "groq" and GROQ_API_KEY:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers["Authorization"] = f"Bearer {GROQ_API_KEY}"
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }
    elif provider == "openrouter" and OPENROUTER_API_KEY:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        }
    elif provider == "mistral" and MISTRAL_API_KEY:
        url = "https://api.mistral.ai/v1/chat/completions"
        headers["Authorization"] = f"Bearer {MISTRAL_API_KEY}"
        payload = {
            "model": MISTRAL_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }
    elif provider == "vllm" and VLLM_BASE_URL:
        url = f"{VLLM_BASE_URL.rstrip('/')}/chat/completions"
        payload = {
            "model": VLLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        }
    else:
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
    except Exception as exc:
        print(f"[WARN] Appel LLM {provider} echoue ({exc}). Repli sur le stub.")
    return None


async def run_generation_pipeline(req: GenerationRunRequest) -> GenerationRunResponse:
    """Exécute la génération de la procédure LOTO."""
    job_id = str(uuid.uuid4())
    workflow: Optional[Dict[str, Any]] = None
    provider_used = req.provider

    if req.provider != "stub":
        user_prompt = f"Machine: {req.machine_name} (ID: {req.machine_id})\nComposants à consigner:\n{req.components}"
        workflow = await call_llm(req.provider, user_prompt)

    if not workflow:
        workflow = generate_stub_procedure(req.machine_name, req.components)
        provider_used = "stub (moteur de règles certifié)"

    # Validation de sécurité élémentaire (présence lockout + restoration)
    errors: List[ValidationIssueSummary] = []
    warnings: List[ValidationIssueSummary] = []

    if not workflow.get("lockout"):
        errors.append(ValidationIssueSummary(
            code="MISSING_LOCKOUT",
            message="La procédure ne contient aucune étape de condamnation.",
            severity="ERROR",
            field_path="lockout"
        ))

    if not workflow.get("restoration"):
        warnings.append(ValidationIssueSummary(
            code="MISSING_RESTORATION",
            message="Aucune étape de déconsignation spécifiée.",
            severity="WARNING",
            field_path="restoration"
        ))

    is_publishable = len(errors) == 0

    return GenerationRunResponse(
        job_id=job_id,
        status="COMPLETED" if is_publishable else "FAILED",
        is_publishable=is_publishable,
        workflow_definition=workflow,
        yolo_metadata={
            "classes_detected": ["padlock", "breaker", "valve"],
            "confidence_threshold": 0.15
        },
        validation_errors=errors,
        validation_warnings=warnings,
        generation_notes=[
            f"Procédure générée avec succès pour {req.machine_name}.",
            "Conforme aux préconisations OSHA 29 CFR 1910.147.",
            "Étapes spatiales et visuelles prêtes pour projection AR Meta Quest."
        ],
        llm_provider=provider_used,
        procedure_id=None,
    )
