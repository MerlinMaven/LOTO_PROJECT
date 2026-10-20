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
    public class ActionData
    {
        public string action_id;
        public string description;
        public string vision_prompt;
        public string completion_check;
        public SpatialGuideData spatial_guide;
    }

    [System.Serializable]
    public class StageData
    {
        public int stage_id;
        public string title;
        public ActionData[] actions;
    }

    [System.Serializable]
    public class WorkflowPhases
    {
        public StageData[] lockout;
        public StageData[] restoration;
    }

    [System.Serializable]
    public class LOTOProcedure
    {
        public string machine_id;
        public string machine_name;
        public string created_by_hse;
        public string status;
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

    // Récupère la procédure LOTO approuvée pour la machine
    private IEnumerator GetLOTOProcedure(string machineId, Action onSuccess, Action<string> onFailure)
    {
        string url = $"{backendUrl}/procedures/{machineId}";

        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            request.SetRequestHeader("ngrok-skip-browser-warning", "true");
            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                string rawJson = request.downloadHandler.text;
                LOTOProcedure procedure = JsonUtility.FromJson<LOTOProcedure>(rawJson);
                
                // Parse anchors manually
                List<AnchorItem> parsedAnchors = ParseAnchorsFromJson(rawJson);
                procedure.anchors = parsedAnchors.ToArray();

                int lockoutLength = procedure.workflow_stages?.lockout?.Length ?? 0;
                int restorationLength = procedure.workflow_stages?.restoration?.Length ?? 0;
                Debug.Log($"✅ Procédure chargée: {procedure.machine_name}. {lockoutLength + restorationLength} étapes. {procedure.anchors.Length} ancres.");
                
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
    public void ManualOverrideActiveStep(int stageId, string actionId, string reason, byte[] imageBytes, Action<StepOverrideResponse> onSuccess, Action<string> onFailure)
    {
        string base64Image = Convert.ToBase64String(imageBytes);
        StartCoroutine(PostManualOverrideStep(stageId, actionId, reason, base64Image, onSuccess, onFailure));
    }

    private IEnumerator PostManualOverrideStep(int stageId, string actionId, string reason, string base64Image, Action<StepOverrideResponse> onSuccess, Action<string> onFailure)
    {
        string url = $"{backendUrl}/interventions/override-step";

        StepOverrideRequest req = new StepOverrideRequest
        {
            intervention_id = activeInterventionId,
            stage_id = stageId,
            action_id = actionId,
            image_base64 = base64Image,
            reason = reason
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

