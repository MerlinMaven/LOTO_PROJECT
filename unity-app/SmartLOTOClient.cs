using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

public class SmartLOTOClient : MonoBehaviour
{
    [Header("Configuration API")]
    [SerializeField] private string backendUrl = "http://localhost:8000"; // URL de l'API FastAPI

    [Header("État de l'Intervention")]
    public string activeInterventionId;
    public string activeMachineId;
    public string operatorName = "Operator-Quest2";

    // Modèles de données pour la désérialisation
    [System.Serializable]
    public class ActionData
    {
        public string action_id;
        public string description;
        public string vision_prompt;
        public string completion_check;
    }

    [System.Serializable]
    public class StageData
    {
        public int stage_id;
        public string type;
        public string title;
        public ActionData[] actions;
    }

    [System.Serializable]
    public class LOTOProcedure
    {
        public string machine_id;
        public string machine_name;
        public string created_by_hse;
        public string status;
        public StageData[] workflow_stages;
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

    // Démarre une intervention sur Supabase via le Backend
    public void StartIntervention(string machineId)
    {
        activeMachineId = machineId;
        StartCoroutine(PostStartIntervention());
    }

    private IEnumerator PostStartIntervention()
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

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                var response = JsonUtility.FromJson<StartInterventionResponse>(request.downloadHandler.text);
                activeInterventionId = response.intervention.id;
                Debug.Log($"✅ Intervention démarrée avec succès. ID: {activeInterventionId}");
                
                // Charger la procédure et initialiser la checklist AR
                StartCoroutine(GetLOTOProcedure(activeMachineId));
            }
            else
            {
                Debug.LogError($"❌ Échec de démarrage de l'intervention: {request.error} | {request.downloadHandler.text}");
            }
        }
    }

    // Récupère la procédure LOTO approuvée pour la machine
    private IEnumerator GetLOTOProcedure(string machineId)
    {
        string url = $"{backendUrl}/procedures/{machineId}";

        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                LOTOProcedure procedure = JsonUtility.FromJson<LOTOProcedure>(request.downloadHandler.text);
                Debug.Log($"✅ Procédure chargée: {procedure.machine_name}. {procedure.workflow_stages.Length} étapes.");
                
                // Diffuser la procédure à l'UI et au système de guidage 3D
                // LotoManager.Instance.InitializeProcedure(procedure);
            }
            else
            {
                Debug.LogError($"❌ Échec du chargement de la procédure: {request.error}");
            }
        }
    }

    // Valide une étape en envoyant la capture de caméra à YOLO-World
    public void ValidateActiveStep(int stageId, string actionId, string visionPrompt, byte[] imageBytes)
    {
        string base64Image = Convert.ToBase64String(imageBytes);
        StartCoroutine(PostValidateStep(stageId, actionId, visionPrompt, base64Image));
    }

    private IEnumerator PostValidateStep(int stageId, string actionId, string visionPrompt, string base64Image)
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

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                StepValidationResponse res = JsonUtility.FromJson<StepValidationResponse>(request.downloadHandler.text);
                if (res.verified)
                {
                    Debug.Log($"✅ Étape {actionId} validée par l'IA ! {res.message}");
                    // LotoManager.Instance.OnStepValidated(actionId);
                }
                else
                {
                    Debug.LogWarning($"⚠️ Échec de validation visuelle: {res.message}");
                    // LotoManager.Instance.OnStepValidationFailed(res.message);
                }
            }
            else
            {
                Debug.LogError($"❌ Erreur réseau lors de la validation: {request.error}");
            }
        }
    }
}
