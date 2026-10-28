using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

public class SmartLOTOClient : MonoBehaviour
{
    [Header("Configuration API")]
    [SerializeField] private string backendUrl = "http://127.0.0.1:8000"; // URL de l'API FastAPI
    [SerializeField] private int verificationTimeoutSeconds = 110;

    [Header("État de l'Intervention")]
    public string activeInterventionId;
    public string activeMachineId;
    public string operatorName = "Operator-Quest2";

    // Modèles de données pour la désérialisation
    [System.Serializable]
    public class SpatialGuideData
    {
        public string hologram_type;
        public float pos_x;
        public float pos_y;
        public float pos_z;
        public float rot_x;
        public float rot_y;
        public float rot_z;
    }

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
        public PhysicalSignatureData[] invariant_features;
        public StateRuleData[] state_rules;
        public StateRuleData[] verifiable_states;
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
        public string component_ref;
        public string primary_component;
        public string vision_prompt;
        public string completion_check;
        public string expected_result;
        public SpatialGuideData spatial_guide;
        public VerificationData verification;
        public string execution_phase;
        public GuidanceData guidance;

        public string Id => string.IsNullOrEmpty(action_id) ? step_id : action_id;
        public string InstructionText => string.IsNullOrEmpty(description) ? instruction : description;
        public string ExpectedText => string.IsNullOrEmpty(completion_check) ? expected_result : completion_check;
        public string VerificationMethod => verification == null ? "visual_observation" : verification.method;
        public string[] VerificationCriteria => verification == null ? new string[0] : (verification.criteria ?? new string[0]);
    }

    [Serializable]
    public class GuidanceData { public string[] component_refs; public string[] observable_cues; }

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
        public ClarificationResolution resolution;
    }

    [System.Serializable]
    public class ClarificationResolution
    {
        public string answer;
        public string rationale;
    }

    [System.Serializable]
    public class WorkflowPhases
    {
        public int phase_model_version;
        public string schema_version;
        public string procedure_id;
        public string machine_id;
        public string machine_name;
        public string maintenance_objective;
        public string objective;
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
        public int phase_model_version;
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
        public AnchorItem[] anchors; // Populated manually
    }

    [System.Serializable]
    private class StartInterventionRequest
    {
        public string machine_id;
        public string operator_name;
    }

    [System.Serializable]
    private class StartInterventionResponse
    {
        public string status;
        public InterventionData intervention;
    }

    [System.Serializable]
    public class InterventionData
    {
        public string id;
        public string machine_id;
        public string procedure_version_id;
        public string operator_name;
        public string status;
        public int current_stage_id;
    }

    [System.Serializable]
    private class StepValidationRequest
    {
        public string intervention_id;
        public int stage_id;
        public string action_id;
        public string image_base64;
        public string vision_prompt;
        public string stage_code;
        public string request_id;
    }

    [System.Serializable]
    public class StepValidationResponse
    {
        public bool verified;
        public string message;
        public string image_url;
        public float confidence;
        public string detected_component;
        public string observed_state;
        public string evaluation_mode;
        public string evaluation_goal;
        public bool state_identified;
        public string outcome;
        public string request_id;
        public string action_id;
        public string procedure_version_id;
        public string image_sha256;
        public int image_width;
        public int image_height;
        public bool test_mode;
        public TargetData[] targets;
        public CriterionObservationData[] criterion_observations;
    }

    [Serializable]
    public class CriterionObservationData
    {
        public int criterion_index;
        public string status, observation;
    }

    [Serializable]
    public class TargetData
    {
        public string component_id, identification_feature;
        public float x, y, confidence;
        public bool localization_clear;
    }

    [Serializable]
    private class ConfirmationRequest
    {
        public string intervention_id, machine_id, version_id, stage_code, action_id, request_id, statement;
        public int stage_id;
        public bool confirmed;
    }

    public void ConfirmActiveStep(int stage, string stageCode, string action, bool testMode, string version,
        string requestId, Action<StepValidationResponse> success, Action<string> failure)
    {
        var data = new ConfirmationRequest { intervention_id = activeInterventionId, machine_id = activeMachineId,
            version_id = version, stage_id = stage, stage_code = stageCode, action_id = action,
            request_id = requestId, confirmed = true, statement = "Je confirme avoir réalisé l'opération décrite." };
        StartCoroutine(PostConfirmation(JsonUtility.ToJson(data), testMode, success, failure));
    }

    private IEnumerator PostConfirmation(string json, bool testMode, Action<StepValidationResponse> success, Action<string> failure)
    {
        using (var request = new UnityWebRequest(backendUrl + (testMode ? "/tests/confirm-step" : "/interventions/confirm-step"), "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
            request.downloadHandler = new DownloadHandlerBuffer(); request.timeout = verificationTimeoutSeconds;
            request.SetRequestHeader("Content-Type", "application/json");
            yield return request.SendWebRequest();
            if (request.result != UnityWebRequest.Result.Success) { failure?.Invoke("Confirmation non enregistrée : " + request.error); yield break; }
            StepValidationResponse result = null;
            try { result = JsonUtility.FromJson<StepValidationResponse>(request.downloadHandler.text); } catch (Exception) { }
            if (result == null || result.outcome != "human_confirmed") failure?.Invoke("Confirmation non enregistrée : réponse inexploitable.");
            else success?.Invoke(result);
        }
    }

    [Serializable]
    private class TestRequest
    {
        public string machine_id, version_id, action_id, stage_code, image_base64, request_id;
        public int stage_id;
    }

    [Serializable]
    public class GuidanceResponse
    {
        public bool guidance_only, verified, test_mode;
        public string request_id, action_id, procedure_version_id, image_sha256;
        public int image_width, image_height;
        public TargetData[] targets;
    }

    [Serializable]
    private class GuidanceRequest
    {
        public string machine_id, version_id, intervention_id, action_id, stage_code, image_base64, request_id;
        public int stage_id;
        public bool test_mode;
    }

    public Coroutine LocateStepTargets(string version, int stage, string stageCode, string action,
        byte[] image, string requestId, bool testMode, Action<GuidanceResponse> success, Action<string> failure)
    {
        var data = new GuidanceRequest { machine_id = activeMachineId, version_id = version,
            intervention_id = testMode ? "" : activeInterventionId, test_mode = testMode,
            stage_id = stage, stage_code = stageCode, action_id = action,
            image_base64 = Convert.ToBase64String(image), request_id = requestId };
        return StartCoroutine(PostGuidance(JsonUtility.ToJson(data), success, failure));
    }

    private IEnumerator PostGuidance(string json, Action<GuidanceResponse> success, Action<string> failure)
    {
        using (var request = new UnityWebRequest(backendUrl + "/guidance/locate-step", "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
            request.downloadHandler = new DownloadHandlerBuffer();
            request.timeout = verificationTimeoutSeconds;
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("ngrok-skip-browser-warning", "true");
            yield return request.SendWebRequest();
            if (request.result != UnityWebRequest.Result.Success)
            { failure?.Invoke("Localisation IA indisponible : " + request.error); yield break; }
            GuidanceResponse result = null;
            try { result = JsonUtility.FromJson<GuidanceResponse>(request.downloadHandler.text); } catch (Exception) { }
            if (result == null || !result.guidance_only || result.verified)
                failure?.Invoke("Réponse de guidage inexploitable.");
            else success?.Invoke(result);
        }
    }

    public void VerifyTestImage(string versionId, int stageId, string stageCode, string actionId,
        byte[] image, string requestId, Action<StepValidationResponse> success, Action<string> failure)
    {
        var data = new TestRequest { machine_id = activeMachineId, version_id = versionId,
            stage_id = stageId, stage_code = stageCode, action_id = actionId,
            image_base64 = Convert.ToBase64String(image), request_id = requestId };
        StartCoroutine(PostTestImage(JsonUtility.ToJson(data), success, failure));
    }

    private IEnumerator PostTestImage(string json, Action<StepValidationResponse> success, Action<string> failure)
    {
        using (var request = new UnityWebRequest(backendUrl + "/tests/verify-step", "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
            request.downloadHandler = new DownloadHandlerBuffer();
            request.timeout = verificationTimeoutSeconds;
            request.SetRequestHeader("Content-Type", "application/json");
            yield return request.SendWebRequest();
            if (request.result != UnityWebRequest.Result.Success) { failure?.Invoke("Erreur technique : " + request.error); yield break; }
            StepValidationResponse result = null;
            try { result = JsonUtility.FromJson<StepValidationResponse>(request.downloadHandler.text); }
            catch (Exception) { }
            if (result == null || string.IsNullOrEmpty(result.outcome)) failure?.Invoke("Erreur technique : réponse inexploitable.");
            else success?.Invoke(result);
        }
    }

    [System.Serializable]
    public class AnchorItem
    {
        public string organ_name;
        public float pos_x;
        public float pos_y;
        public float pos_z;
        public float rot_x;
        public float rot_y;
        public float rot_z;
    }

    [System.Serializable]
    public class AnchorsUpdate
    {
        public AnchorItem[] anchors_list;
    }

    [System.Serializable]
    private class StepOverrideRequest
    {
        public string intervention_id;
        public int stage_id;
        public string action_id;
        public string image_base64;
        public string reason;
        public string verification_method;
        public string stage_code;
    }

    [System.Serializable]
    public class StepOverrideResponse
    {
        public bool verified;
        public string message;
        public string image_url;
    }

    [System.Serializable]
    public struct ProcedureItem
    {
        public string machine_id;
        public string machine_name;
    }

    [System.Serializable]
    public class ProcedureListWrapper
    {
        public ProcedureItem[] items;
    }

    // Récupère la liste de toutes les machines/procédures approuvées
    public void GetProceduresList(Action<ProcedureItem[]> onSuccess, Action<string> onFailure)
    {
        StartCoroutine(FetchProceduresList(onSuccess, onFailure));
    }

    private IEnumerator FetchProceduresList(Action<ProcedureItem[]> onSuccess, Action<string> onFailure)
    {
        string url = $"{backendUrl}/procedures";

        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            request.SetRequestHeader("ngrok-skip-browser-warning", "true");
            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                string rawJson = request.downloadHandler.text;
                // Formater le JSON tableau pour JsonUtility (encapsulation)
                string wrappedJson = "{\"items\":" + rawJson + "}";
                try
                {
                    ProcedureListWrapper wrapper = JsonUtility.FromJson<ProcedureListWrapper>(wrappedJson);
                    onSuccess?.Invoke(wrapper.items);
                }
                catch (Exception e)
                {
                    onFailure?.Invoke($"Erreur désérialisation liste : {e.Message}");
                }
            }
            else
            {
                onFailure?.Invoke(request.error);
            }
        }
    }

    // Démarre une intervention sur Supabase via le Backend
    public void StartIntervention(string machineId, Action onSuccess, Action<string> onFailure)
    {
        if (LotoManager.Instance != null && LotoManager.Instance.TestMode)
        { onFailure?.Invoke("TEST actif : aucune intervention réelle ne peut être créée."); return; }
        activeMachineId = machineId;
        StartCoroutine(PostStartIntervention(onSuccess, onFailure));
    }

    private IEnumerator PostStartIntervention(Action onSuccess, Action<string> onFailure)
    {
        string url = $"{backendUrl}/interventions/start";
        
        StartInterventionRequest req = new StartInterventionRequest
        {
            machine_id = activeMachineId,
            operator_name = operatorName
        };

        string jsonPayload = JsonUtility.ToJson(req);
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("ngrok-skip-browser-warning", "true");

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                var response = JsonUtility.FromJson<StartInterventionResponse>(request.downloadHandler.text);
                activeInterventionId = response.intervention.id;
                // Pin the client session to the published revision selected by the server.
                activeProcedureVersionId = response.intervention.procedure_version_id;
                Debug.Log($"✅ Intervention démarrée avec succès. ID: {activeInterventionId}");
                
                // Charger la procédure et initialiser la checklist AR
                StartCoroutine(GetLOTOProcedure(activeMachineId, onSuccess, onFailure));
            }
            else
            {
                string errorMsg = $"Échec de démarrage : {request.error} | {request.downloadHandler.text}";
                Debug.LogError($"❌ {errorMsg}");
                onFailure?.Invoke(errorMsg);
            }
        }
    }

    public string activeProcedureVersionId;

    public static string FirstText(params string[] values)
    {
        foreach (string value in values) if (!string.IsNullOrWhiteSpace(value)) return value;
        return string.Empty;
    }

    public static LOTOProcedure ParseProcedure(string json)
    {
        // Published schema IDs may be strings; retain them beside the legacy numeric slot.
        json = System.Text.RegularExpressions.Regex.Replace(json,
            "\"stage_id\"\\s*:\\s*\"((?:\\\\.|[^\"\\\\])*)\"",
            match => "\"stage_code\":\"" + match.Groups[1].Value + "\",\"stage_id\":0");
        return NormalizeProcedure(JsonUtility.FromJson<LOTOProcedure>(json));
    }

    public static LOTOProcedure NormalizeProcedure(LOTOProcedure procedure)
    {
        if (procedure == null) throw new ArgumentException("Procédure vide.");
        var wf = procedure.workflow_stages ?? new WorkflowPhases();
        procedure.workflow_stages = wf;
        wf.phases = wf.phases != null && wf.phases.Length > 0 ? wf.phases : procedure.phases;
        wf.components = wf.components != null && wf.components.Length > 0 ? wf.components : procedure.components;
        wf.clarifications_required = wf.clarifications_required != null && wf.clarifications_required.Length > 0
            ? wf.clarifications_required : procedure.clarifications_required;
        procedure.schema_version = FirstText(wf.schema_version, procedure.schema_version);
        procedure.machine_id = FirstText(procedure.machine_id, wf.machine_id, procedure.procedure_id);
        procedure.machine_name = FirstText(procedure.machine_name, wf.machine_name, procedure.title, procedure.machine_id);
        procedure.maintenance_objective = FirstText(wf.maintenance_objective, wf.objective, procedure.maintenance_objective, procedure.objective);
        procedure.expected_final_state = FirstText(wf.expected_final_state, procedure.expected_final_state);
        procedure.phases = wf.phases;
        procedure.phase_model_version = Math.Max(procedure.phase_model_version, wf.phase_model_version);
        procedure.components = wf.components ?? new ComponentData[0];
        procedure.clarifications_required = wf.clarifications_required ?? new ResolvedClarificationData[0];
        foreach (var c in procedure.components)
        {
            c.component_id = FirstText(c.component_id, c.internal_id, c.tag, c.source_tag);
            c.tag = FirstText(c.tag, c.source_tag, c.component_id);
            c.component_name = FirstText(c.component_name, c.label, c.tag);
            c.physical_signatures = c.physical_signatures != null && c.physical_signatures.Length > 0 ? c.physical_signatures : c.invariant_features;
            c.state_rules = c.state_rules != null && c.state_rules.Length > 0 ? c.state_rules : c.verifiable_states;
        }
        foreach (var q in procedure.clarifications_required)
        {
            q.answer = FirstText(q.answer, q.resolution?.answer);
            q.rationale = FirstText(q.rationale, q.resolution?.rationale);
        }
        if (wf.phases != null) foreach (var phase in wf.phases)
        {
            if (phase?.stages == null) continue;
            for (int i = 0; i < phase.stages.Length; i++)
            {
                var stage = phase.stages[i];
                if (stage == null) continue;
                if (stage.stage_id <= 0) stage.stage_id = i + 1;
                stage.steps = stage.steps != null && stage.steps.Length > 0 ? stage.steps : stage.actions;
                foreach (var step in stage.steps ?? new ActionData[0])
                {
                    if (step == null) continue;
                    step.execution_phase = FirstText(step.execution_phase, phase.phase_type);
                    string kind = step.execution_phase.ToLowerInvariant();
                    if (kind == "maintenance" || kind == "intervention" || kind == "accès" || kind == "acces")
                    { if (step.verification == null) step.verification = new VerificationData(); step.verification.method = "human_confirmation"; }
                }
            }
        }
        return procedure;
    }

    public static bool ReferencesComponent(ActionData action, ComponentData component)
    {
        var refs = new List<string>(action.component_refs ?? new string[0]);
        refs.Add(action.primary_component);
        refs.Add(action.component_ref);
        foreach (var id in new[] { component.component_id, component.internal_id, component.tag, component.source_tag, component.unity_class_id })
            if (!string.IsNullOrEmpty(id) && refs.Contains(id)) return true;
        return false;
    }

    // Récupère la procédure LOTO approuvée pour la machine
    private IEnumerator GetLOTOProcedure(string machineId, Action onSuccess, Action<string> onFailure)
    {
        string url = $"{backendUrl}/procedures/{Uri.EscapeDataString(machineId)}?version_id={Uri.EscapeDataString(activeProcedureVersionId ?? string.Empty)}";

        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            request.SetRequestHeader("ngrok-skip-browser-warning", "true");
            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                string rawJson = request.downloadHandler.text;
                LOTOProcedure procedure;
                try { procedure = ParseProcedure(rawJson); }
                catch (Exception e)
                {
                    onFailure?.Invoke("Procédure illisible : " + e.Message);
                    yield break;
                }
                if (procedure == null || string.IsNullOrEmpty(procedure.procedure_version_id) ||
                    !string.Equals(procedure.procedure_version_id, activeProcedureVersionId, StringComparison.Ordinal))
                {
                    onFailure?.Invoke("La révision publiée a changé entre le démarrage et le chargement. Redémarrez l'intervention.");
                    yield break;
                }
                
                // The API returns typed anchors keyed by the published component identifiers.
                procedure.anchors = procedure.anchors ?? new AnchorItem[0];

                int stepCount = 0;
                if (procedure.workflow_stages?.phases != null)
                {
                    foreach (var phase in procedure.workflow_stages.phases)
                        if (phase?.stages != null)
                            foreach (var stage in phase.stages)
                                stepCount += stage.steps != null && stage.steps.Length > 0 ? stage.steps.Length : (stage.actions?.Length ?? 0);
                }
                else
                {
                    StageData[][] legacyPhases = new StageData[][] { procedure.workflow_stages?.lockout, procedure.workflow_stages?.restoration };
                    foreach (var phase in legacyPhases)
                        if (phase != null)
                            foreach (var stage in phase)
                                stepCount += stage.actions?.Length ?? 0;
                }
                Debug.Log($"✅ Procédure chargée: {procedure.machine_name}. {stepCount} actions. {procedure.anchors.Length} ancres. Révision {procedure.procedure_version_id}.");
                
                // Diffuser la procédure à l'UI et au système de guidage 3D
                LotoManager.Instance.InitializeProcedure(procedure);
                onSuccess?.Invoke();
            }
            else
            {
                string errorMsg = $"Échec du chargement de la procédure: {request.error}";
                Debug.LogError($"❌ {errorMsg}");
                onFailure?.Invoke(errorMsg);
            }
        }
    }

    // Valide une étape en envoyant la capture de caméra à YOLO-World
    public void ValidateActiveStep(int stageId, string actionId, string visionPrompt, byte[] imageBytes, Action<StepValidationResponse> onSuccess, Action<string> onFailure, string requestId = "")
    {
        string base64Image = Convert.ToBase64String(imageBytes);
        StartCoroutine(PostValidateStep(stageId, actionId, visionPrompt, base64Image, onSuccess, onFailure, requestId));
    }

    private IEnumerator PostValidateStep(int stageId, string actionId, string visionPrompt, string base64Image, Action<StepValidationResponse> onSuccess, Action<string> onFailure, string requestId)
    {
        string url = $"{backendUrl}/interventions/validate-step";

        StepValidationRequest req = new StepValidationRequest
        {
            intervention_id = activeInterventionId,
            stage_id = stageId,
            action_id = actionId,
            image_base64 = base64Image,
            vision_prompt = visionPrompt,
            request_id = requestId,
            stage_code = LotoManager.Instance?.GetActiveStage()?.stage_code ?? string.Empty
        };

        string jsonPayload = JsonUtility.ToJson(req);
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.timeout = verificationTimeoutSeconds;
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("ngrok-skip-browser-warning", "true");

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                StepValidationResponse res = null;
                try { res = JsonUtility.FromJson<StepValidationResponse>(request.downloadHandler.text); }
                catch (Exception) { }
                if (res == null || string.IsNullOrEmpty(res.outcome)) onFailure?.Invoke("Erreur technique : réponse inexploitable.");
                else onSuccess?.Invoke(res);
            }
            else
            {
                string errorMsg = $"Vérification refusée : {request.error} | {request.downloadHandler.text}";
                Debug.LogError($"❌ {errorMsg}");
                onFailure?.Invoke(errorMsg);
            }
        }
    }

    // Uploads calibrated anchor positions from Unity Quest (AR) directly to the database
    public void UploadCalibratedAnchors(string machineId, AnchorItem[] anchors, Action onSuccess, Action<string> onFailure)
    {
        StartCoroutine(PostCalibratedAnchors(machineId, anchors, onSuccess, onFailure));
    }

    private IEnumerator PostCalibratedAnchors(string machineId, AnchorItem[] anchors, Action onSuccess, Action<string> onFailure)
    {
        string url = $"{backendUrl}/procedures/{machineId}/anchors";

        AnchorsUpdate payload = new AnchorsUpdate
        {
            anchors_list = anchors
        };

        string jsonPayload = JsonUtility.ToJson(payload);
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("ngrok-skip-browser-warning", "true");

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                Debug.Log("✅ Points d'ancrage spatial téléversés avec succès vers le backend !");
                onSuccess?.Invoke();
            }
            else
            {
                string errorMsg = $"Échec de téléversement des ancrages : {request.error} | {request.downloadHandler.text}";
                Debug.LogError($"❌ {errorMsg}");
                onFailure?.Invoke(errorMsg);
            }
        }
    }

    // Sends a manual override validation request with reasoning and a camera proof image
    public void ManualOverrideActiveStep(int stageId, string actionId, string reason, string verificationMethod, byte[] imageBytes, Action<StepOverrideResponse> onSuccess, Action<string> onFailure)
    {
        string base64Image = Convert.ToBase64String(imageBytes);
        StartCoroutine(PostManualOverrideStep(stageId, actionId, reason, verificationMethod, base64Image, onSuccess, onFailure));
    }

    private IEnumerator PostManualOverrideStep(int stageId, string actionId, string reason, string verificationMethod, string base64Image, Action<StepOverrideResponse> onSuccess, Action<string> onFailure)
    {
        string url = $"{backendUrl}/interventions/override-step";

        StepOverrideRequest req = new StepOverrideRequest
        {
            intervention_id = activeInterventionId,
            stage_id = stageId,
            action_id = actionId,
            image_base64 = base64Image,
            reason = reason,
            verification_method = verificationMethod,
            stage_code = LotoManager.Instance?.GetActiveStage()?.stage_code ?? string.Empty
        };

        string jsonPayload = JsonUtility.ToJson(req);
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("ngrok-skip-browser-warning", "true");

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                StepOverrideResponse res = JsonUtility.FromJson<StepOverrideResponse>(request.downloadHandler.text);
                Debug.Log("[Camera] Backend saved received override image: " + res.image_url);
                onSuccess?.Invoke(res);
            }
            else
            {
                string errorMsg = $"Échec de dérogation manuelle : {request.error} | {request.downloadHandler.text}";
                Debug.LogError($"❌ {errorMsg}");
                onFailure?.Invoke(errorMsg);
            }
        }
    }

    // Close the LOTO intervention and submit operator signature to generate the audit report PDF
    [System.Serializable]
    private class CloseInterventionRequest
    {
        public string intervention_id;
        public string signature_base64;
    }

    [System.Serializable]
    public class CloseInterventionResponse
    {
        public string status;
        public string message;
        public string pdf_report_url;
    }

    public void CloseActiveIntervention(byte[] signatureBytes, Action<CloseInterventionResponse> onSuccess, Action<string> onFailure)
    {
        string base64Sig = Convert.ToBase64String(signatureBytes);
        StartCoroutine(PostCloseIntervention(base64Sig, onSuccess, onFailure));
    }

    private IEnumerator PostCloseIntervention(string base64Sig, Action<CloseInterventionResponse> onSuccess, Action<string> onFailure)
    {
        string url = $"{backendUrl}/interventions/close";

        CloseInterventionRequest req = new CloseInterventionRequest
        {
            intervention_id = activeInterventionId,
            signature_base64 = base64Sig
        };

        string jsonPayload = JsonUtility.ToJson(req);
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("ngrok-skip-browser-warning", "true");

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                CloseInterventionResponse res = JsonUtility.FromJson<CloseInterventionResponse>(request.downloadHandler.text);
                onSuccess?.Invoke(res);
            }
            else
            {
                string errorMsg = $"Échec de clôture de l'intervention : {request.error} | {request.downloadHandler.text}";
                Debug.LogError($"❌ {errorMsg}");
                onFailure?.Invoke(errorMsg);
            }
        }
    }

}
