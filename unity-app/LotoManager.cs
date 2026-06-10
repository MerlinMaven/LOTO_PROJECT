using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class LotoManager : MonoBehaviour
{
    public static LotoManager Instance { get; private set; }

    [Header("Network Client Reference")]
    [SerializeField] private SmartLOTOClient lotoClient;

    [Header("UI Controller Reference")]
    [SerializeField] private LotoUIController uiController;

    [Header("State")]
    public SmartLOTOClient.LOTOProcedure currentProcedure;
    public bool isLockoutPhase = true; // True = Lockout (Consignation), False = Restoration (Déconsignation)
    public int currentStageIndex = 0;
    public int currentActionIndex = 0;

    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
        }
        else
        {
            Destroy(gameObject);
        }

        if (lotoClient == null)
        {
            lotoClient = GetComponent<SmartLOTOClient>();
        }
    }

    // Called by SmartLOTOClient once the procedure JSON is fetched
    public void InitializeProcedure(SmartLOTOClient.LOTOProcedure procedure)
    {
        currentProcedure = procedure;
        isLockoutPhase = true;
        currentStageIndex = 0;
        currentActionIndex = 0;

        Debug.Log($"[LOTO] Procedure initialized: {procedure.machine_name}");
        uiController.UpdateUIForCurrentStep();
        UpdateHologramGuide();
    }

    // Returns the active step (ActionData) currently being executed
    public SmartLOTOClient.ActionData GetActiveAction()
    {
        if (currentProcedure == null || currentProcedure.workflow_stages == null) return null;

        var stages = isLockoutPhase ? currentProcedure.workflow_stages.lockout : currentProcedure.workflow_stages.restoration;
        
        if (stages == null || currentStageIndex >= stages.Length) return null;
        var currentStage = stages[currentStageIndex];

        if (currentStage.actions == null || currentActionIndex >= currentStage.actions.Length) return null;
        return currentStage.actions[currentActionIndex];
    }

    // Returns the active stage (StageData)
    public SmartLOTOClient.StageData GetActiveStage()
    {
        if (currentProcedure == null || currentProcedure.workflow_stages == null) return null;

        var stages = isLockoutPhase ? currentProcedure.workflow_stages.lockout : currentProcedure.workflow_stages.restoration;
        if (stages == null || currentStageIndex >= stages.Length) return null;
        return stages[currentStageIndex];
    }

    // Triggered when the operator clicks the "Validate" button
    public void RequestStepValidation(byte[] capturedImageBytes)
    {
        var action = GetActiveAction();
        var stage = GetActiveStage();

        if (action == null || stage == null)
        {
            Debug.LogError("[LOTO] No active action to validate.");
            return;
        }

        uiController.ShowStatus("Envoi à l'IA YOLO-World...", LotoUIController.PremiumYellow);
        lotoClient.ValidateActiveStep(stage.stage_id, action.action_id, action.vision_prompt, capturedImageBytes,
            (res) => {
                if (res.verified)
                {
                    OnStepValidated(action.action_id);
                }
                else
                {
                    OnStepValidationFailed(res.message);
                }
            },
            (error) => {
                OnStepValidationFailed(error);
            }
        );
    }

    // Triggered when the operator clicks "Manual Override" (Mode dégradé)
    public void RequestManualOverride(string reason, byte[] capturedImageBytes)
    {
        var action = GetActiveAction();
        var stage = GetActiveStage();

        if (action == null || stage == null)
        {
            Debug.LogError("[LOTO] No active action to override.");
            return;
        }

        uiController.ShowStatus("Envoi de la dérogation manuelle...", LotoUIController.PremiumYellow);
        lotoClient.ManualOverrideActiveStep(stage.stage_id, action.action_id, reason, capturedImageBytes,
            (res) => {
                OnStepValidated(action.action_id);
            },
            (error) => {
                uiController.ShowStatus($"Échec dérogation ❌\n{error}", LotoUIController.PremiumRed);
            }
        );
    }

    // Callback from SmartLOTOClient on successful validation or override
    public void OnStepValidated(string actionId)
    {
        Debug.Log($"[LOTO] Step {actionId} successfully validated.");
        uiController.ShowStatus("Étape Validée ✅", LotoUIController.PremiumGreen);
        StartCoroutine(AdvanceToNextStepAfterDelay());
    }

    // Callback from SmartLOTOClient on validation failure
    public void OnStepValidationFailed(string errorMessage)
    {
        Debug.LogWarning($"[LOTO] Step validation failed: {errorMessage}");
        uiController.ShowStatus($"Échec de détection ❌\n{errorMessage}", LotoUIController.PremiumRed);
    }

    private IEnumerator AdvanceToNextStepAfterDelay()
    {
        yield return new WaitForSeconds(1.5f);
        AdvanceStep();
    }

    private void AdvanceStep()
    {
        if (currentProcedure == null) return;

        var stages = isLockoutPhase ? currentProcedure.workflow_stages.lockout : currentProcedure.workflow_stages.restoration;
        var currentStage = stages[currentStageIndex];

        currentActionIndex++;
        if (currentActionIndex >= currentStage.actions.Length)
        {
            // Move to next stage
            currentActionIndex = 0;
            currentStageIndex++;

            if (currentStageIndex >= stages.Length)
            {
                // Finished the current phase (Lockout or Restoration)
                if (isLockoutPhase)
                {
                    // Finished Consignation -> Switch to Maintenance / Déconsignation
                    isLockoutPhase = false;
                    currentStageIndex = 0;
                    Debug.Log("[LOTO] Consignation complete. Ready for Maintenance. Next: Déconsignation phase.");
                    ClearHologramGuide();
                    uiController.ShowMaintenanceScreen();
                }
                else
                {
                    // Finished Déconsignation -> Clôture / Signature
                    Debug.Log("[LOTO] Restoration complete. Ready for closure.");
                    ClearHologramGuide();
                    uiController.ShowClosureScreen();
                }
                return;
            }
        }

        uiController.UpdateUIForCurrentStep();
        UpdateHologramGuide();
    }

    // Triggered when operator finishes maintenance and wants to start Déconsignation
    public void StartRestorationPhase()
    {
        isLockoutPhase = false;
        currentStageIndex = 0;
        currentActionIndex = 0;
        uiController.UpdateUIForCurrentStep();
        UpdateHologramGuide();
    }

    // Closes the intervention by generating and sending a mock signature
    public void CloseIntervention(byte[] signatureBytes)
    {
        uiController.ShowStatus("Clôture de l'intervention et génération du PDF...", LotoUIController.PremiumYellow);
        lotoClient.CloseActiveIntervention(signatureBytes,
            (res) => {
                OnInterventionClosed(res.pdf_report_url);
            },
            (error) => {
                OnInterventionCloseFailed(error);
            }
        );
    }

    public void OnInterventionClosed(string pdfReportUrl)
    {
        Debug.Log($"[LOTO] Intervention successfully closed. Report PDF: {pdfReportUrl}");
        ClearHologramGuide();
        uiController.ShowStatus("Intervention Clôturée ! ✅\nRapport PDF généré avec succès.", LotoUIController.PremiumGreen);
        uiController.ShowFinalReportScreen(pdfReportUrl);
    }

    public void OnInterventionCloseFailed(string error)
    {
        Debug.LogError($"[LOTO] Intervention closure failed: {error}");
        uiController.ShowStatus($"Échec de clôture ❌\n{error}", LotoUIController.PremiumRed);
    }

    // --- Hologram Spawner Logic ---

    [Header("Hologram Guidance System")]
    [SerializeField] private Transform originAnchor;
    private GameObject activeHologram;

    private void Start()
    {
        // Try to find the LOTO_Origin_Anchor in the scene automatically
        if (originAnchor == null)
        {
            GameObject anchorGo = GameObject.Find("LOTO_Origin_Anchor");
            if (anchorGo == null)
            {
                // Create a mock anchor cube for in-editor visualization
                anchorGo = GameObject.CreatePrimitive(PrimitiveType.Cube);
                anchorGo.name = "LOTO_Origin_Anchor";
                anchorGo.transform.position = new Vector3(0f, 1f, 1.5f); // 1.5 meters in front of the camera, 1 meter high
                anchorGo.transform.localScale = new Vector3(0.1f, 0.1f, 0.1f);
                
                // Style the mock anchor to look like a blue target pad
                Material anchorMat = new Material(Shader.Find("Sprites/Default"));
                if (anchorMat == null)
                {
                    anchorMat = new Material(Shader.Find("Legacy Shaders/Transparent/Diffuse"));
                }
                if (anchorMat != null)
                {
                    anchorMat.color = new Color(0.12f, 0.43f, 0.86f, 0.8f); // Royal Blue anchor pad
                    anchorGo.GetComponent<Renderer>().material = anchorMat;
                }
                Debug.Log("[LOTO] Mock origin anchor 'LOTO_Origin_Anchor' created for testing.");
            }
            originAnchor = anchorGo.transform;
        }
    }

    private void UpdateHologramGuide()
    {
        if (activeHologram != null)
        {
            Destroy(activeHologram);
            activeHologram = null;
        }

        var action = GetActiveAction();
        if (action == null || action.spatial_guide == null) return;

        // Determine correct base position (offset from anchor or target specific organ)
        Vector3 basePosition = Vector3.zero;
        if (currentProcedure != null && currentProcedure.anchors != null)
        {
            string descLower = action.description.ToLower();
            string promptLower = action.vision_prompt.ToLower();
            
            foreach (var anchor in currentProcedure.anchors)
            {
                string organLower = anchor.organ_name.ToLower();
                if (descLower.Contains(organLower) || promptLower.Contains(organLower))
                {
                    basePosition = new Vector3(anchor.pos_x, anchor.pos_y, anchor.pos_z);
                    Debug.Log($"[LOTO Spawner] Anchoring guide to organ: '{anchor.organ_name}' at offset: {basePosition}");
                    break;
                }
            }
        }

        // Add action's relative spatial guide position
        basePosition += new Vector3(action.spatial_guide.pos_x, action.spatial_guide.pos_y, action.spatial_guide.pos_z);
        Vector3 guideRot = new Vector3(action.spatial_guide.rot_x, action.spatial_guide.rot_y, action.spatial_guide.rot_z);

        // Spawn hologram relative to origin anchor
        if (originAnchor != null)
        {
            activeHologram = new GameObject($"Hologram_Guide_{action.action_id}");
            activeHologram.transform.SetParent(originAnchor, false);
            activeHologram.transform.localPosition = basePosition;
            activeHologram.transform.localRotation = Quaternion.Euler(guideRot);
            
            // Attach visual renderer component
            activeHologram.AddComponent<LotoHologramGuide>();
            Debug.Log($"[LOTO Spawner] Hologram spawned at local position: {basePosition}");
        }
    }

    private void ClearHologramGuide()
    {
        if (activeHologram != null)
        {
            Destroy(activeHologram);
            activeHologram = null;
        }
    }
}
