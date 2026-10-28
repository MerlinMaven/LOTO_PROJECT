"""Dashboard confidence: keep the 60/20/20 formula aligned with src/lib/kpi.ts."""
import math


def _records(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _steps(workflow):
    return [step for phase in _records(workflow.get("phases"))
            for stage in _records(phase.get("stages")) for step in _records(stage.get("steps"))]


def clarification_resolved(question):
    resolution = question.get("resolution") or {}
    return (question.get("status") == "resolved" and bool(str(resolution.get("answer") or "").strip())
            and resolution.get("answer_complete") is True and question.get("affected_steps_reviewed") is True)


def business_blockers(workflow):
    questions = _records(workflow.get("clarifications_required"))
    issues = {f"clarification:{q.get('id', index)}": q for index, q in enumerate(questions) if not clarification_resolved(q)}
    diagnostics = _records(workflow.get("validation_diagnostics")) + [
        {"entity_id": step.get("step_id"), **diag} for step in _steps(workflow) for diag in _records(step.get("diagnostics"))]
    for diag in diagnostics:
        code = str(diag.get("code") or "").lower()
        if (diag.get("resolved") or str(diag.get("severity") or "").lower() not in {"blocking", "error"}
                or str(diag.get("category") or "").lower() == "source_integrity" or "fact_citation" in code
                or code == "verification_method_unsupported_by_operator_client"):
            continue
        if code in {"clarification_open", "clarification_resolution_incomplete", "clarification_review_incomplete"} and any(
                str(q.get("id")) == str(diag.get("entity_id")) for q in questions):
            continue
        key = (code, str(diag.get("entity_id") or ""), "" if code else str(diag.get("message") or ""))
        issues[key] = diag
    return list(issues.values())


def confidence_breakdown(workflow):
    components = _records(workflow.get("components"))
    has_visuals = bool(_records(workflow.get("visual_observations"))) or any(
        _records(c.get("invariant_features")) or _records(c.get("physical_signatures")) for c in components)
    structure = (20 if components else 0) + (20 if _steps(workflow) else 0) + (20 if has_visuals else 0)
    count = len(business_blockers(workflow))
    maturity = max(0, 20 - count * 4)
    facts = _records(workflow.get("technical_facts"))
    unmatched = sum(f.get("citation_status") not in {"verified", "manual_verified", "inferred_absence", "typography_normalized"} for f in facts)
    citation = math.floor(20 * (len(facts) - unmatched) / len(facts) + 0.5) if facts else 20
    return {"score": structure + maturity + citation, "breakdown": {
        "structureScore": structure, "blockingScore": maturity, "citationScore": citation,
        "blockingCount": count, "unmatchedCount": unmatched, "totalFacts": len(facts)}}
