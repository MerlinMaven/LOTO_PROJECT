# Passerelle d'Intégration Unity AR — SmartLOTO (Feature Freeze Backend)

Ce document valide et fige le contrat d'intégration entre les services Backend (`field-service` et `authoring-service`) et l'application Réalité Mixte / AR (`unity-app`).

Le backend et le tableau de bord HSE (`hse-dashboard`) sont en **Feature Freeze**. Le contrat de données décrit ci-dessous est **déterministe, complet et exempt de valeurs `null` bloquantes**.

---

## 1. Endpoints de l'API Terrain (`field-service` & `authoring-service`)

### Configuration Réseau Unity
- **Field Service (API Temps Réel AR)** : `http://127.0.0.1:8000` (ou IP locale du PC de dev sur le réseau Wi-Fi du casque Quest)
- **Authoring Service (Référence / Export)** : `http://127.0.0.1:8001`

### Endpoints d'Exécution AR

| Méthode | URL Endpoint | Description & Usage Unity |
| :--- | :--- | :--- |
| **`GET`** | `/procedures` | **Liste des procédures publiées** : Utilisé par `LotoUIController` pour peupler le menu déroulant (`machineIdDropdown`). |
| **`GET`** | `/procedures/{machine_id}` | **Détail complet de la procédure** : Retourne la procédure `SL-POC-01` avec ses 7 composants et ses 4 phases. Accepte `?version_id={id}`. |
| **`POST`** | `/interventions/start` | **Initialisation de session** : Démarre une intervention sur `SL-POC-01`, verrouille la révision active et retourne `intervention_id`. |
| **`POST`** | `/interventions/validate-step` | **Validation IA temps réel** : Envoie une photo caméra (base64) et le prompt visuel (`switch_c01`, `guard_c05`...) pour détection d'objet candidat. |
| **`POST`** | `/interventions/override-step` | **Validation / Progression opérateur** : Enregistre la validation physique d'une étape avec motif, méthode et preuve photographique. Fait progresser l'intervention. |
| **`POST`** | `/procedures/{machine_id}/anchors` | **Téléversement des ancres spatiales** : Enregistre les positions spatiales 3D calibrées (`pos_x`, `pos_y`, `pos_z`, `rot_x`, `rot_y`, `rot_z`) par l'opérateur en AR. |
| **`POST`** | `/interventions/close` | **Clôture & Signature** : Reçoit la signature tactile de l'opérateur, archive l'intervention et compile le rapport d'audit PDF. |
| **`GET`** | `/v1/procedures/{procedure_id}/export` | *(Sur port 8001)* **Export Golden Payload** : Retourne le JSON statique de référence directement depuis `authoring-service`. |

---

## 2. Snapshot de Référence (« Golden Payload »)

Le fichier de référence est sauvegardé et prêt à l'emploi :
- Emplacement Fallback Casque (Offline / Standalone) : `unity-app/Assets/StreamingAssets/SL-POC-01_unity_contract.json`
- Emplacement Documentation : `docs/contracts/SL-POC-01_unity_contract.json`

### Matrice Vision AR (7 Composants Didactiques)

| Tag | Composant | `unity_class_id` | Signatures Physiques Invariantes | Règles d'État Vérifiables |
| :--- | :--- | :--- | :--- | :--- |
| **C01** | Interrupteur bascule blanc | `switch_c01` | `MARQUAGE` ('ON' / 'OFF')<br>`GÉOMÉTRIE` (Bascule blanche mobile) | `OFF` : Bascule côté repère OFF<br>`ON` : Bascule côté repère ON |
| **C02** | Pile cylindrique amovible | `battery_c02` | `GÉOMÉTRIE` (Corps cylindrique amovible) | `REMOVED` : Déposée dans C04<br>`CONNECTED` : Insérée dans C03 |
| **C03** | Support de pile (boîtier rouge) | `battery_holder_c03` | `MARQUAGE` (Boîtier rouge, '+/-' et 'X') | `EMPTY` : Logement droit exempt de pile<br>`OCCUPIED` : Pile présente dans logement actif |
| **C04** | Boîte de stockage (Safe Box) | `safe_box_c04` | `PICTOGRAMME` (Cadenas sérigraphié)<br>`MARQUAGE` ('Safe Box') | `STORED` : Pile présente sous pictogramme<br>`EMPTY` : Réceptacle vide |
| **C05** | Carter mobile (écran transparent) | `guard_c05` | `SYMBOLE` (Carré blanc mobile)<br>`GÉOMÉTRIE` (Translation verticale) | `CLOSED` : Carré aligné avec cercle plein C07<br>`OPEN` : Carré aligné avec cercle vide C07 |
| **C06** | Lampe (cible maintenance) | `lamp_c06` | `SYMBOLE` (Cercle avec croix ⊗ didactique)<br>`GÉOMÉTRIE` (Ampoule / voyant supérieur) | `EXTINGUISHED` : Extinction visible<br>`ILLUMINATED` : Émission lumineuse visible |
| **C07** | Repères fixes de carter | `markers_c07` | `SYMBOLE` (Cercle noir plein et cercle vide) | `REFERENCE` : Repères passifs d'alignement |

### Phases du Workflow Séquentiel

1. **`ISOLATION` (P1)** : Mise en sécurité du circuit
   - `A-01` : Placer l'interrupteur en position OFF (`C01`) — *Observation visuelle*
   - `A-02` : Retirer la pile du support et la placer dans la Safe Box (`C02`, `C03`, `C04`) — *Observation visuelle*
   - `A-03` : Vérifier l'absence de tension aux bornes de la lampe (`C06`) — *Mesure multimètre (Bouton virtuel)*
2. **`ACCÈS` (P2)** : Ouverture de l'accès au composant
   - `A-04` : Déplacer le carter transparent en position ouverte (`C05`, `C07`) — *Observation visuelle* (Décision HSE intégrée : translation vers le bas)
3. **`INTERVENTION` (P3)** : Remplacement du composant lumineux
   - `A-05` : Démonter la lampe et installer celle de remplacement (`C06`) — *Confirmation humaine* (Décision HSE intégrée : ampoule incandescente 3V, outillage non requis)
4. **`RESTORATION` (P4)** : Rétablissement de la protection et de l'alimentation
   - `A-06` : Refermer le carter transparent (`C05`, `C07`) — *Observation visuelle*
   - `A-07` : Reconnecter la pile dans le logement fonctionnel de C03 (`C02`, `C03`) — *Observation visuelle*
   - `A-08` : Placer l'interrupteur en position ON (`C01`) — *Observation visuelle*

---

## 3. Modèles C# (`[System.Serializable]`) pour Unity

Ces classes sont directement intégrées dans [SmartLOTOClient.cs](file:///unity-app/SmartLOTOClient.cs) et sont prêtes à être désérialisées avec `JsonUtility` ou `Newtonsoft.Json` :

```csharp
using System;
using UnityEngine;

[System.Serializable]
public class PhysicalSignatureData
{
    public string signature_type; // MARQUAGE, GÉOMÉTRIE, PICTOGRAMME, SYMBOLE
    public string feature_type;   // marking, local_geometry, pictogram, symbol
    public string description;
    public string details;
}

[System.Serializable]
public class StateRuleData
{
    public string state_name;     // OFF, ON, OPEN, CLOSED, EMPTY, OCCUPIED, etc.
    public string physical_rule;
    public string candidate_prompt;
    public bool supported_by_unity;
    public bool requires_human_confirmation;
}

[System.Serializable]
public class ComponentData
{
    public string component_id;
    public string internal_id;
    public string tag;            // C01, C02, etc.
    public string source_tag;
    public string unity_class_id; // switch_c01, guard_c05, etc.
    public string component_name;
    public string label;
    public string description;
    public PhysicalSignatureData[] physical_signatures;
    public StateRuleData[] state_rules;
    public string[] relations;
    public bool clarification_needed;
}

[System.Serializable]
public class VerificationData
{
    public string method;
    public string[] criteria;
    public string[] required_evidence;
    public string[] instrument_refs;
    public string[] indeterminate_when;
    public string[] candidate_prompts;
    public string fallback_mode;
    public bool virtual_button;
    public string unity_ui_hint;
}

[System.Serializable]
public class ActionData
{
    public string action_id;
    public string step_id;
    public int sequence;
    public string description;
    public string instruction;
    public string[] component_refs;
    public string primary_component;
    public string vision_prompt;
    public string completion_check;
    public string expected_result;
    public SpatialGuideData spatial_guide;
    public VerificationData verification;

    public string Id => string.IsNullOrEmpty(action_id) ? step_id : action_id;
    public string InstructionText => string.IsNullOrEmpty(description) ? instruction : description;
    public string ExpectedText => string.IsNullOrEmpty(completion_check) ? expected_result : completion_check;
    public string VerificationMethod => verification == null ? "visual_observation" : verification.method;
    public string[] VerificationCriteria => verification == null ? new string[0] : (verification.criteria ?? new string[0]);
}

[System.Serializable]
public class StageData
{
    public int stage_id;
    public string stage_code;
    public int sequence;
    public string title;
    public ActionData[] actions;
    public ActionData[] steps;
    public int StageNumber => stage_id > 0 ? stage_id : sequence;
}

[System.Serializable]
public class ProcedurePhaseData
{
    public string phase_id;
    public string phase_type; // ISOLATION, ACCÈS, INTERVENTION, RESTORATION
    public int sequence;
    public string title;
    public string description;
    public StageData[] stages;
}

[System.Serializable]
public class ResolvedClarificationData
{
    public string id;
    public string question;
    public string status;
    public string answer;
    public string rationale;
    public string[] affected_step_ids;
    public string[] related_component_ids;
}

[System.Serializable]
public class WorkflowPhases
{
    public string schema_version;
    public string procedure_id;
    public string machine_id;
    public string machine_name;
    public string maintenance_objective;
    public string expected_final_state;
    public ComponentData[] components;
    public ProcedurePhaseData[] phases;
    public ResolvedClarificationData[] clarifications_required;
    public StageData[] lockout;
    public StageData[] restoration;
}

[System.Serializable]
public class LOTOProcedure
{
    public string procedure_id;
    public string machine_id;
    public string machine_name;
    public string title;
    public string version;
    public string procedure_version_id;
    public string schema_version;
    public string status;
    public string hse_approval_status;
    public string created_by_hse;
    public string objective;
    public string maintenance_objective;
    public string expected_final_state;
    public ComponentData[] components;
    public ProcedurePhaseData[] phases;
    public ResolvedClarificationData[] clarifications_required;
    public string workflow_json;
    public WorkflowPhases workflow_stages;
    public AnchorItem[] anchors;
}
```

---

## 4. Démarrage Rapide du Backend (1 seule commande)

Pour faire tourner le backend en arrière-plan pendant que vous développez exclusivement sous Unity :

### Option A — Script PowerShell (Recommandé)
```powershell
.\scripts\start_backend.ps1
```

### Option B — Script Batch (Invite de commandes standard)
```cmd
.\scripts\start_backend.bat
```

### Option C — Ligne de commande PowerShell directe
```powershell
Start-Process python -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8000 --reload" -WorkingDirectory "apps\field-service" -WindowStyle Hidden; Start-Process python -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8001 --reload" -WorkingDirectory "apps\authoring-service" -WindowStyle Hidden
```

Pour vérifier que les backends répondent :
```powershell
Invoke-RestMethod http://127.0.0.1:8000/procedures/SL-POC-01 | Select-Object machine_id, status, hse_approval_status
```
Sortie attendue :
```text
machine_id status    hse_approval_status
---------- ------    -------------------
SL-POC-01  PUBLISHED approved
```

---

## 5. Statut de Verrouillage

- **Feature Freeze `hse-dashboard` :** Actif (aucun changement UI).
- **Feature Freeze `authoring-service` :** Actif (API figée).
- **Contrat Unity :** Figé, testé et validé à 100%.
