"""Deterministic checks for the versioned procedure document.

These checks establish data consistency only; they do not certify that a
procedure is safe or that a camera/instrument can perform its verification.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


KNOWN_VERIFICATION_METHODS = {
    "visual_observation",
    "measurement",
    "human_confirmation",
    "sensor_signal",
    "combined_evidence",
    "not_defined",
}


def iter_steps(workflow: dict[str, Any]):
    for phase in workflow.get("phases", []):
        if not isinstance(phase, dict):
            continue
        for stage in phase.get("stages", []):
            if not isinstance(stage, dict):
                continue
            for step in stage.get("steps", []):
                if isinstance(step, dict):
                    yield phase, stage, step


def apply_clarification_impact(workflow: dict[str, Any]) -> dict[str, Any]:
    """Recompute per-step review readiness from the current clarification state."""
    clarifications = workflow.get("clarifications_required", [])
    for _, _, step in iter_steps(workflow):
        step_id = str(step.get("step_id", ""))
        impacted = [
            question for question in clarifications
            if isinstance(question, dict) and step_id in question.get("affected_step_ids", [])
        ]
        blocking = []
        for question in impacted:
            resolution = question.get("resolution") if isinstance(question.get("resolution"), dict) else {}
            ans = str(resolution.get("answer", "")).strip()
            if (question.get("status") != "resolved" or not ans
                    or resolution.get("answer_complete") is not True
                    or question.get("affected_steps_reviewed") is not True):
                blocking.append(str(question.get("id", "")))
        if step.get("unresolved_conditions"):
            blocking.extend(f"condition:{index + 1}" for index, value in enumerate(step["unresolved_conditions"]) if value)
        step["blocking_clarification_ids"] = blocking
        step["review_readiness"] = "blocked" if blocking else "reviewable"
    return workflow


def validate_workflow(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Return actionable diagnostics without guessing technical correctness."""
    diagnostics: list[dict[str, Any]] = []

    def add(code: str, category: str, message: str, severity: str = "error", entity: str | None = None):
        item: dict[str, Any] = {"code": code, "category": category, "severity": severity, "message": message}
        if entity:
            item["entity_id"] = entity
        diagnostics.append(item)

    # Historical v1 records remain readable. New PDF drafts are always emitted as v2.
    if workflow.get("schema_version") not in {"1.0", "2.0"}:
        add("SCHEMA_VERSION", "schema", "Version de schéma absente ou non prise en charge.")
    if workflow.get("schema_version") == "1.0":
        return diagnostics
    if not str(workflow.get("machine_id", "")).strip():
        add("EQUIPMENT_ID_REQUIRED", "missing_information", "Identifiant d’équipement à confirmer.", "blocking")
    if workflow.get("equipment_identity_confirmed") is False:
        add(
            "EQUIPMENT_ID_UNCONFIRMED", "missing_information",
            "L’identifiant temporaire du brouillon doit être remplacé par l’identifiant vérifié de l’équipement avant approbation.",
            "blocking",
        )
    if not str(workflow.get("maintenance_objective", "")).strip():
        add("OBJECTIVE_REQUIRED", "missing_information", "Objectif de maintenance à préciser.", "blocking")
    if not str(workflow.get("expected_final_state", "")).strip():
        add("EXPECTED_FINAL_STATE_REQUIRED", "missing_information", "L'état final attendu doit être explicité ou faire l'objet d'une clarification.", "blocking")
    if not workflow.get("source_documents"):
        add("SOURCE_REQUIRED", "schema", "Aucun document source n’est associé au brouillon.")

    ids: dict[str, list[str]] = defaultdict(list)
    component_ids: set[str] = set()
    fact_ids: set[str] = set()
    source_ids: set[str] = set()
    for source in workflow.get("source_documents", []):
        if not isinstance(source, dict) or not source.get("source_id"):
            add("SOURCE_ID_REQUIRED", "schema", "Un document source n’a pas d’identifiant.")
            continue
        source_id = str(source["source_id"])
        source_ids.add(source_id)
        ids[source_id].append("source")
    for component in workflow.get("components", []):
        if isinstance(component, dict) and component.get("component_id"):
            cid = str(component["component_id"])
            component_ids.add(cid)
            ids[cid].append("component")
    for fact in workflow.get("technical_facts", []):
        if isinstance(fact, dict) and fact.get("fact_id"):
            fid = str(fact["fact_id"])
            fact_ids.add(fid)
            ids[fid].append("fact")
            citation_status = fact.get("citation_status")
            # Statuts valides : vérifié par le juge LLM, par le HSE, ou constat d'absence documentaire
            VALID_STATUSES = {"manual_verified", "verified", "inferred_absence", "typography_normalized"}
            manual_review_complete = citation_status in VALID_STATUSES
            if fact.get("qualification") == "documented" and citation_status == "unmatched" and not manual_review_complete:
                add(
                    "FACT_CITATION_UNVERIFIED", "source_integrity",
                    "La citation n'a pas été confirmée par le juge sémantique ; le fait doit être vérifié dans le PDF avant approbation.",
                    "blocking", fid,
                )
    for inference in workflow.get("inferences", []):
        if isinstance(inference, dict) and inference.get("inference_id"):
            ids[str(inference["inference_id"])].append("inference")
            for fact_id in inference.get("fact_refs", []):
                if fact_id not in fact_ids:
                    add("INFERENCE_UNKNOWN_FACT", "schema", f"Inférence liée à un fait inconnu : {fact_id}.", entity=str(inference["inference_id"]))
            for component_id in inference.get("related_component_ids", []):
                if component_id not in component_ids:
                    add("INFERENCE_UNKNOWN_COMPONENT", "schema", f"Inférence liée à un composant inconnu : {component_id}.", entity=str(inference["inference_id"]))
    for collection, id_key, kind in ((workflow.get("visual_observations", []), "observation_id", "observation"), (workflow.get("unknowns", []), "unknown_id", "unknown"), (workflow.get("contradictions", []), "contradiction_id", "contradiction"), (workflow.get("clarifications_required", []), "id", "clarification")):
        for item in collection:
            if isinstance(item, dict) and item.get(id_key):
                ids[str(item[id_key])].append(kind)

    steps: dict[str, dict[str, Any]] = {}
    counted_phases: set[int] = set()
    counted_stages: set[int] = set()
    for phase, stage, step in iter_steps(workflow):
        if id(phase) not in counted_phases and phase.get("phase_id"):
            ids[str(phase["phase_id"])].append("phase")
            counted_phases.add(id(phase))
        if id(stage) not in counted_stages and stage.get("stage_id"):
            ids[str(stage["stage_id"])].append("stage")
            counted_stages.add(id(stage))
        sid = str(step.get("step_id", ""))
        if sid:
            ids[sid].append("step")
            steps[sid] = step

    if str(workflow.get("maintenance_objective", "")).strip() and not steps:
        add("PROCEDURE_STEPS_REQUIRED", "missing_information", "L'objectif est défini, mais aucune action structurée ne permet de l'atteindre.", "blocking")
    for phase in workflow.get("phases", []):
        if isinstance(phase, dict) and not any(phase is candidate for candidate, _, _ in iter_steps(workflow)):
            add("EMPTY_PHASE", "missing_information", "Une phase ne contient aucune action exécutable.", "blocking", str(phase.get("phase_id", "")))

    for identifier, kinds in ids.items():
        if len(kinds) > 1:
            add("DUPLICATE_ID", "schema", f"Identifiant dupliqué : {identifier} ({', '.join(kinds)}).", entity=identifier)

    for phase in workflow.get("phases", []):
        if not isinstance(phase, dict):
            add("PHASE_SHAPE", "schema", "Une phase n’est pas un objet JSON.")
            continue
        if not str(phase.get("title", "")).strip():
            add("PHASE_TITLE_REQUIRED", "schema", "Une phase n’a pas de titre.", entity=str(phase.get("phase_id", "")))
        for stage in phase.get("stages", []):
            if not isinstance(stage, dict):
                add("STAGE_SHAPE", "schema", "Une étape n’est pas un objet JSON.")
                continue
            for step in stage.get("steps", []):
                if not isinstance(step, dict):
                    add("STEP_SHAPE", "schema", "Une action n’est pas un objet JSON.")
                    continue
                sid = str(step.get("step_id", ""))
                if not str(step.get("instruction", "")).strip():
                    add("INSTRUCTION_REQUIRED", "schema", "Instruction d’action manquante.", entity=sid)
                for component_id in step.get("component_refs", []):
                    if component_id not in component_ids:
                        add("UNKNOWN_COMPONENT_REF", "schema", f"Composant référencé inconnu : {component_id}.", entity=sid)
                for fact_id in step.get("fact_refs", []):
                    if fact_id not in fact_ids:
                        add("UNKNOWN_FACT_REF", "schema", f"Fait référencé inconnu : {fact_id}.", entity=sid)
                for evidence in step.get("evidence_refs", []):
                    if not isinstance(evidence, dict) or evidence.get("source_id") not in source_ids:
                        add("UNKNOWN_SOURCE_REF", "schema", "Référence de preuve sans document source associé.", entity=sid)
                verification = step.get("verification") or {}
                if any(str(c).startswith("Critère validé :") for c in verification.get("criteria", [])):
                    add("CLARIFICATION_COPIED_AS_CRITERION", "missing_information",
                        "Une réponse HSE a été recopiée comme critère. Définir un critère observable spécifique à cette action.", "blocking", sid)
                method = verification.get("method", "not_defined")
                if method not in KNOWN_VERIFICATION_METHODS:
                    add("VERIFICATION_METHOD_UNKNOWN", "execution_capability", f"Méthode de vérification non prise en charge par le client Unity : {method}.", "blocking", sid)
                elif method in {"measurement", "sensor_signal", "combined_evidence", "not_defined"}:
                    add(
                        "VERIFICATION_METHOD_UNSUPPORTED_BY_OPERATOR_CLIENT", "execution_capability",
                        f"La méthode {method} n'est pas encore exécutée fidèlement par le client Unity actuel (repli automatique : Validation Humaine / Bouton Virtuel).",
                        "warning", sid,
                    )
                    if isinstance(verification, dict):
                        verification["fallback_mode"] = "human_confirmation"
                        verification["virtual_button"] = True
                        verification["unity_ui_hint"] = "Validation Humaine (Bouton Virtuel)"
                if method not in {"not_defined", "human_confirmation"} and not verification.get("criteria"):
                    add("VERIFICATION_CRITERIA_REQUIRED", "missing_information", "Critère vérifiable à préciser.", "blocking", sid)
                if method in {"visual_observation", "measurement", "sensor_signal", "combined_evidence"} and not verification.get("indeterminate_when"):
                    add("INDETERMINATE_RULE_REQUIRED", "system_limit", "Préciser quand la preuve ne permet pas de conclure.", "blocking", sid)
                if method == "measurement" and not verification.get("instrument_refs"):
                    add("MEASURING_INSTRUMENT_UNSPECIFIED", "missing_information", "L’instrument de mesure doit être identifié et disponible avant d’exécuter cette étape.", "blocking", sid)
                for condition in step.get("unresolved_conditions", []):
                    if condition:
                        add("STEP_CONDITION_UNRESOLVED", "missing_information", str(condition), "blocking", sid)

    # Dependency integrity and cycle detection.
    graph: dict[str, list[str]] = {}
    order = {sid: idx for idx, sid in enumerate(steps)}
    for sid, step in steps.items():
        deps = step.get("depends_on", [])
        graph[sid] = [str(dep) for dep in deps]
        for dep in graph[sid]:
            if dep not in steps:
                add("UNKNOWN_DEPENDENCY", "schema", f"Dépendance inconnue : {dep}.", entity=sid)
            elif order[dep] > order[sid]:
                add("DEPENDENCY_ORDER", "technical_inconsistency", f"La dépendance {dep} apparaît après l’action qui en dépend.", "blocking", sid)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        cyclic = any(dep in graph and visit(dep) for dep in graph[node])
        visiting.remove(node)
        visited.add(node)
        return cyclic

    if any(visit(node) for node in graph if node not in visited):
        add("DEPENDENCY_CYCLE", "technical_inconsistency", "Un cycle existe dans les dépendances d’actions.", "blocking")

    for clarification in workflow.get("clarifications_required", []):
        if not isinstance(clarification, dict):
            add("CLARIFICATION_SHAPE", "schema", "Une clarification n’est pas un objet JSON.")
            continue
        if clarification.get("status", "unresolved") == "unresolved" and not clarification.get("affected_step_ids"):
            add("CLARIFICATION_UNLINKED", "missing_information", "La clarification doit indiquer les actions affectées.", "review", str(clarification.get("id", "")))
        if clarification.get("status", "unresolved") != "resolved":
            add("CLARIFICATION_OPEN", "missing_information", str(clarification.get("question", "Clarification non résolue.")), "blocking", str(clarification.get("id", "")))
        else:
            resolution = clarification.get("resolution")
            ans = str(resolution.get("answer", "")).strip() if isinstance(resolution, dict) else ""
            if not ans:
                add("CLARIFICATION_RESOLUTION_INCOMPLETE", "missing_information", "Une réponse est requise.", "blocking", str(clarification.get("id", "")))
            if (not isinstance(resolution, dict) or resolution.get("answer_complete") is not True
                    or clarification.get("affected_steps_reviewed") is not True):
                add("CLARIFICATION_REVIEW_INCOMPLETE", "missing_information",
                    "Confirmer une réponse complète et la revue séparée des critères des étapes concernées.", "blocking", str(clarification.get("id", "")))
        for sid in clarification.get("affected_step_ids", []):
            if sid not in steps:
                add("CLARIFICATION_UNKNOWN_STEP", "schema", f"La clarification référence une action inconnue : {sid}.", entity=str(clarification.get("id", "")))
    for observation in workflow.get("visual_observations", []):
        if not isinstance(observation, dict):
            continue
        if observation.get("page") not in {page for source in workflow.get("source_documents", []) if isinstance(source, dict) for page in range(1, int(source.get("page_count", 0)) + 1)}:
            add("OBSERVATION_PAGE_INVALID", "schema", "Une observation visuelle ne référence pas une page connue.", "review", str(observation.get("observation_id", "")))
        for component_id in observation.get("component_refs", []):
            if component_id not in component_ids:
                add("OBSERVATION_UNKNOWN_COMPONENT", "schema", f"Observation liée à un composant inconnu : {component_id}.", entity=str(observation.get("observation_id", "")))
    return diagnostics


def dependency_cycles(workflow: dict[str, Any]) -> bool:
    return any(item["code"] == "DEPENDENCY_CYCLE" for item in validate_workflow(workflow))
