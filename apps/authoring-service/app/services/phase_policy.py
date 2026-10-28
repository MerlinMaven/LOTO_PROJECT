"""Draft-only semantic phase normalization. Never mutate a published workflow."""
from copy import deepcopy
import re
import unicodedata

LABELS = {"preparation": "Préparation", "consignation": "Consignation",
          "maintenance": "Maintenance", "restoration": "Déconsignation / remise en service"}


def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", str(value or "").lower()) if not unicodedata.combining(c))


def phase_kind(value):
    text = normalized(value).replace("-", "_")
    for kind, aliases in {
        "restoration": ("restoration", "restore", "deconsignation", "remise_en_service", "remise en service"),
        "maintenance": ("maintenance", "intervention", "acces", "access", "repair"),
        "consignation": ("consignation", "lockout", "isolation", "separation", "storage", "stockage"),
        "preparation": ("preparation", "verification", "identification"),
    }.items():
        if text in aliases: return kind
    return ""


def classify_step(step, parent):
    text = normalized(step.get("instruction") or step.get("description"))
    # Moving a protective guard to gain access is maintenance even when its
    # purpose follows "pour"; withdrawing an energy source for later repair is not.
    if (re.match(r"(?:deplacer|ouvrir|faire coulisser|open|slide)\b", text)
            and re.search(r"\b(carter|capot|guard)\b", text)
            and re.search(r"\b(ouvrir|degager|acces|access|open)\b", text)):
        return "maintenance"
    text = re.split(r"\b(?:pour|afin de|avant de|before|in order to)\b", text, maxsplit=1)[0]
    # Operations take precedence over a misleading group title; no equipment/step IDs.
    if re.search(r"\b(remplac\w*|repar\w*|demonter|remonter|replace(?:d|s|ment|ments)?|replacing|repair\w*|nettoyer|clean\w*)\b", text):
        return "maintenance"
    if re.search(r"\b(ouvrir|open\w*|degager|acceder)\b.*\b(carter|capot|guard|acces|access|composant)\b", text):
        return "maintenance"
    if re.search(r"\b(carter|capot|guard)\b", text) and re.search(r"\b(ouverte?|open)\b", text): return "maintenance"
    if re.search(r"\b(reinser\w*|reconnect\w*|retabl\w*|redemarr\w*|restart\w*)\b", text): return "restoration"
    if re.search(r"\b(fermer|replacer|close\w*)\b.*\b(carter|capot|guard)\b", text): return "restoration"
    if re.search(r"\b(carter|capot|guard)\b", text) and re.search(r"\b(fermee?|closed)\b", text): return "restoration"
    if re.search(r"\b(on|marche)\b", text) and re.search(r"\b(placer|mettre|basculer|commander|switch|turn)\b", text): return "restoration"
    if re.search(r"\b(off|arret)\b", text) and re.search(r"\b(placer|mettre|basculer|commander|switch|turn)\b", text): return "consignation"
    if re.search(r"\b(retirer|separer|deconnecter|isoler|stocker|deposer)\b", text) and re.search(r"\b(pile|batterie|source|alimentation|battery|energy)\b", text): return "consignation"
    explicit = phase_kind(step.get("execution_phase"))
    if explicit: return explicit
    return phase_kind(parent)


def normalize_draft_phases(workflow):
    """Preserve action content and unknown phase extensions; split misleading mixed groups."""
    wf = deepcopy(workflow)
    phases = []
    for phase in wf.get("phases") or []:
        groups = {}
        for stage in phase.get("stages") or []:
            for step in stage.get("steps") or []:
                kind = classify_step(step, phase.get("phase_type"))
                key = kind or str(phase.get("phase_type", ""))
                if key not in groups:
                    group = deepcopy(phase); group["stages"] = []
                    group["phase_type"] = key
                    if kind: group["title"] = LABELS[kind]
                    groups[key] = group
                group = groups[key]
                if not group["stages"] or group["stages"][-1].get("stage_id") != stage.get("stage_id"):
                    new_stage = deepcopy(stage); new_stage["steps"] = []; group["stages"].append(new_stage)
                step["execution_phase"] = key
                step.setdefault("guidance", {"component_refs": list(step.get("component_refs") or []),
                    "observable_cues": list((step.get("verification") or {}).get("criteria") or [])})
                if kind == "maintenance":
                    verification = step.setdefault("verification", {})
                    verification["method"] = "human_confirmation"
                    verification["required_evidence"] = ["Attestation de l'opérateur ayant réalisé l'opération"]
                    verification["instrument_refs"] = []
                group["stages"][-1]["steps"].append(step)
        for key, group in groups.items():
            if len(groups) > 1:
                group["phase_id"] = str(phase.get("phase_id")) + "-" + key
                for stage in group["stages"]: stage["stage_id"] = str(stage["stage_id"]) + "-" + key
            phases.append(group)
    # Known phases follow the procedure lifecycle; arbitrary extension phases keep their position.
    if phases and all(p["phase_type"] in LABELS for p in phases):
        phases.sort(key=lambda p: list(LABELS).index(p["phase_type"]))
    for index, phase in enumerate(phases, 1):
        phase["sequence"] = index
    wf["phases"] = phases
    wf["phase_model_version"] = 1
    return wf
