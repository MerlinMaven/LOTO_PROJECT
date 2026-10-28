"""Lossless aliases for published workflows and server-owned step context."""
from copy import deepcopy

SIGNATURE_TYPES = {"marking": "MARQUAGE", "fixed_text": "MARQUAGE",
                   "color_pattern": "MARQUAGE", "local_geometry": "GÉOMÉTRIE",
                   "pictogram": "PICTOGRAMME", "symbol": "SYMBOLE"}


def component_ids(component):
    return {str(component[key]) for key in ("component_id", "internal_id", "tag", "source_tag", "unity_class_id") if component.get(key)}


def step_refs(step):
    return list(dict.fromkeys(str(value) for value in [
        step.get("primary_component"), step.get("component_ref"), *(step.get("component_refs") or [])
    ] if value))


def normalize_workflow(raw):
    """Add Unity aliases without inventing signatures, states or HSE decisions."""
    wf = deepcopy(raw)
    wf["maintenance_objective"] = wf.get("maintenance_objective") or wf.get("objective") or ""
    wf["expected_final_state"] = wf.get("expected_final_state") or ""
    for component in wf.get("components") or []:
        cid = component.get("component_id") or component.get("tag") or component.get("source_tag") or component.get("internal_id") or ""
        component.setdefault("component_id", cid)
        component.setdefault("tag", component.get("source_tag") or cid)
        component.setdefault("component_name", component.get("label") or cid)
        signatures = deepcopy(component.get("physical_signatures") or component.get("invariant_features") or [])
        for signature in signatures:
            signature.setdefault("signature_type", SIGNATURE_TYPES.get(signature.get("feature_type"), signature.get("feature_type", "")))
        component["physical_signatures"] = signatures
        component["state_rules"] = deepcopy(component.get("state_rules") or component.get("verifiable_states") or component.get("states") or [])
    for phase in wf.get("phases") or []:
        for index, stage in enumerate(phase.get("stages") or [], 1):
            original_id = stage.get("stage_code") or stage.get("stage_id") or str(index)
            stage["stage_code"] = str(original_id)
            # JsonUtility's legacy StageData expects a number. Keep the canonical ID too.
            stage["stage_id"] = index
            steps = stage.get("steps") or stage.get("actions") or []
            stage["steps"] = steps
            stage["actions"] = steps
            for step in steps:
                step["action_id"] = step.get("step_id") or step.get("action_id") or ""
                step.setdefault("step_id", step["action_id"])
                step["instruction"] = step.get("instruction") or step.get("description") or ""
                step["description"] = step["instruction"]
                step["component_refs"] = step_refs(step)
                step.setdefault("primary_component", next(iter(step["component_refs"]), ""))
                step["verification"] = deepcopy(step.get("verification") or step.get("validation") or {})
                step["execution_phase"] = step.get("execution_phase") or phase.get("phase_type", "")
                step["guidance"] = deepcopy(step.get("guidance") or {"component_refs": step["component_refs"]})
                if step["execution_phase"].lower() in {"maintenance", "intervention", "accès", "acces", "access"}:
                    step["verification"]["method"] = "human_confirmation"
                step.setdefault("expected_result", step.get("completion_check") or "")
                # Preserve vision_prompt for the VLM evaluation pipeline
                step.setdefault("vision_prompt", step.get("vision_prompt") or "")
    for clarification in wf.get("clarifications_required") or []:
        resolution = clarification.get("resolution") or {}
        clarification["answer"] = clarification.get("answer") or resolution.get("answer") or ""
        clarification["rationale"] = clarification.get("rationale") or resolution.get("rationale") or ""
    return wf


def steps_in_workflow(workflow):
    if workflow.get("phases"):
        for phase in workflow["phases"]:
            for stage in phase.get("stages") or []:
                for step in stage.get("steps") or stage.get("actions") or []:
                    yield phase, stage, step
    else:
        for phase_name in ("lockout", "restoration"):
            for stage in workflow.get(phase_name) or []:
                for step in stage.get("actions") or stage.get("steps") or []:
                    yield {"phase_type": phase_name}, stage, step


def verification_context(workflow, action_id, stage_id, stage_code=""):
    wf = normalize_workflow(workflow)
    matches = [(phase, stage, step) for phase, stage, step in steps_in_workflow(wf)
               if str(step.get("step_id") or step.get("action_id")) == action_id]
    if len(matches) != 1:
        raise ValueError("Étape absente ou identifiant ambigu dans la révision publiée.")
    phase, stage, step = matches[0]
    if stage_code:
        if str(stage.get("stage_code") or stage.get("stage_id")) != stage_code:
            raise ValueError("Le groupe d'étapes ne correspond pas à la révision publiée.")
    elif str(stage.get("stage_id")) != str(stage_id):
        raise ValueError("Le numéro de groupe ne correspond pas à l'étape demandée.")
    refs = set(step_refs(step))
    components = [c for c in wf.get("components") or [] if refs & component_ids(c)]
    resolved_ids = set().union(*(component_ids(c) for c in components)) if components else set()
    missing = sorted(refs - resolved_ids)
    clarifications = [q for q in wf.get("clarifications_required") or []
        if q.get("status", "").lower() in {"resolved", "approved", "answered"} and q.get("answer")
        and (action_id in q["affected_step_ids"] if q.get("affected_step_ids")
             else resolved_ids.intersection(q.get("related_component_ids") or []))]
    verification = step.get("verification") or step.get("validation") or {}
    # Enrich each component with its physical_signatures and state_rules for the VLM
    enriched_components = []
    for c in components:
        ec = dict(c)
        ec["physical_signatures"] = c.get("physical_signatures") or []
        ec["state_rules"] = c.get("state_rules") or []
        enriched_components.append(ec)
    return {
        "action_id": action_id, "phase": phase.get("phase_type", ""),
        "execution_phase": step.get("execution_phase", phase.get("phase_type", "")),
        "guidance": step.get("guidance") or {},
        "stage_code": str(stage.get("stage_code") or stage.get("stage_id")),
        "instruction": step.get("instruction") or step.get("description") or "",
        "expected_result": step.get("expected_result") or step.get("completion_check") or "",
        "vision_prompt": step.get("vision_prompt") or "",
        "verification": verification, "components": enriched_components,
        "reference_components": [c for c in wf.get("components") or [] if c not in components],
        "open_clarifications": [q for q in wf.get("clarifications_required") or []
            if q.get("status", "").lower() not in {"resolved", "approved", "answered"}
            and (q.get("id") in (step.get("blocking_clarification_ids") or [])
                 or action_id in (q.get("affected_step_ids") or [])
                 or resolved_ids.intersection(q.get("related_component_ids") or []))],
        "blocking_clarification_ids": list(step.get("blocking_clarification_ids") or []),
        "unresolved_conditions": list(step.get("unresolved_conditions") or []),
        "missing_component_refs": missing, "clarifications_required": clarifications,
        "maintenance_objective": wf.get("maintenance_objective", ""),
        "expected_final_state": wf.get("expected_final_state", ""),
    }
