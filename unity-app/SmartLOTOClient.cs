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
    }

    [System.Serializable]
    public class StepValidationResponse
    {
        public bool verified;
        public string message;
        public string image_url;
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

    // Récupère la procédure LOTO approuvée pour la machine
    private IEnumerator GetLOTOProcedure(string machineId, Action onSuccess, Action<string> onFailure)
    {
        string url = $"{backendUrl}/procedures/{machineId}?version_id={Uri.EscapeDataString(activeProcedureVersionId ?? string.Empty)}";

        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            request.SetRequestHeader("ngrok-skip-browser-warning", "true");
            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                string rawJson = request.downloadHandler.text;
                LOTOProcedure procedure = JsonUtility.FromJson<LOTOProcedure>(rawJson);
                if (procedure == null || string.IsNullOrEmpty(procedure.procedure_version_id) ||
                    !string.Equals(procedure.procedure_version_id, activeProcedureVersionId, StringComparison.Ordinal))
                {
                    onFailure?.Invoke("La révision publiée a changé entre le démarrage et le chargement. Redémarrez l'intervention.");
                    yield break;
                }
                
                // Parse anchors manually
                List<AnchorItem> parsedAnchors = ParseAnchorsFromJson(rawJson);
                procedure.anchors = parsedAnchors.ToArray();

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
    public void ValidateActiveStep(int stageId, string actionId, string visionPrompt, byte[] imageBytes, Action<StepValidationResponse> onSuccess, Action<string> onFailure)
    {
        string base64Image = Convert.ToBase64String(imageBytes);
        StartCoroutine(PostValidateStep(stageId, actionId, visionPrompt, base64Image, onSuccess, onFailure));
    }

    private IEnumerator PostValidateStep(int stageId, string actionId, string visionPrompt, string base64Image, Action<StepValidationResponse> onSuccess, Action<string> onFailure)
    {
        string url = $"{backendUrl}/interventions/validate-step";

        StepValidationRequest req = new StepValidationRequest
        {
            intervention_id = activeInterventionId,
            stage_id = stageId,
            action_id = actionId,
            image_base64 = base64Image,
            vision_prompt = visionPrompt
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
                StepValidationResponse res = JsonUtility.FromJson<StepValidationResponse>(request.downloadHandler.text);
                Debug.Log("[Camera] Backend saved received image: " + res.image_url);
                onSuccess?.Invoke(res);
            }
            else
            {
                string errorMsg = $"Erreur réseau lors de la validation: {request.error}";
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
            verification_method = verificationMethod
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

    // Dynamic JSON parser helper for anchors (solves JsonUtility Dictionary limitation)
    private static List<AnchorItem> ParseAnchorsFromJson(string rawJson)
    {
        List<AnchorItem> list = new List<AnchorItem>();
        
        int anchorsIndex = rawJson.IndexOf("\"anchors\"");
        if (anchorsIndex == -1) return list;
        
        int startBrace = rawJson.IndexOf("{", anchorsIndex);
        if (startBrace == -1) return list;
        
        int braceCount = 1;
        int endBrace = -1;
        for (int i = startBrace + 1; i < rawJson.Length; i++)
        {
            if (rawJson[i] == '{') braceCount++;
            else if (rawJson[i] == '}')
            {
                braceCount--;
                if (braceCount == 0)
                {
                    endBrace = i;
                    break;
                }
            }
        }
        
        if (endBrace == -1) return list;
        
        string anchorsContent = rawJson.Substring(startBrace + 1, endBrace - startBrace - 1);
        string[] parts = anchorsContent.Split(new[] { "}," }, StringSplitOptions.RemoveEmptyEntries);
        foreach (var part in parts)
        {
            int colonIndex = part.IndexOf(":");
            if (colonIndex == -1) continue;
            
            string name = part.Substring(0, colonIndex).Trim().Trim('"');
            string valuesPart = part.Substring(colonIndex + 1);
            
            valuesPart = valuesPart.Replace("{", "").Replace("}", "").Trim();
            
            float px = ExtractFloat(valuesPart, "pos_x");
            float py = ExtractFloat(valuesPart, "pos_y");
            float pz = ExtractFloat(valuesPart, "pos_z");
            float rx = ExtractFloat(valuesPart, "rot_x");
            float ry = ExtractFloat(valuesPart, "rot_y");
            float rz = ExtractFloat(valuesPart, "rot_z");
            
            AnchorItem anchor = new AnchorItem
            {
                organ_name = name,
                pos_x = px,
                pos_y = py,
                pos_z = pz,
                rot_x = rx,
                rot_y = ry,
                rot_z = rz
            };
            list.Add(anchor);
        }
        
        return list;
    }

    private static float ExtractFloat(string source, string key)
    {
        int keyIndex = source.IndexOf("\"" + key + "\"");
        if (keyIndex == -1) keyIndex = source.IndexOf(key);
        if (keyIndex == -1) return 0f;
        
        int colonIndex = source.IndexOf(":", keyIndex);
        if (colonIndex == -1) return 0f;
        
        int commaIndex = source.IndexOf(",", colonIndex);
        if (commaIndex == -1) commaIndex = source.Length;
        
        string valStr = source.Substring(colonIndex + 1, commaIndex - colonIndex - 1).Trim().Replace("}", "");
        if (float.TryParse(valStr, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float result))
        {
            return result;
        }
        return 0f;
    }
}

