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
    public int currentPhaseIndex = 0;
    public int currentStageIndex = 0;
    public int currentActionIndex = 0;

    private bool validationPending;
    private bool maintenancePresented;
    private bool maintenanceVisible;
    private int validationGeneration;
    public bool TestMode { get; private set; }
    public bool IsValidationPending => validationPending;

    public void InvalidateValidation()
    {
        validationGeneration++;
        StopAllCoroutines();
        validationPending = false;
        uiController.SetValidationBusy(false);
        uiController.ClearFrameTargets();
        ClearHologramGuide();
    }

    public bool SelectTestAction(string id)
    {
        var phases = currentProcedure?.workflow_stages?.phases;
        if (phases == null) return false;
        for (int p = 0; p < phases.Length; p++)
            for (int s = 0; s < phases[p].stages.Length; s++)
            {
                var steps = phases[p].stages[s].steps ?? phases[p].stages[s].actions;
                for (int a = 0; a < steps.Length; a++)
                    if (steps[a].Id == id)
                    {
                        InvalidateValidation();
                        TestMode = true;
                        currentPhaseIndex = p; currentStageIndex = s; currentActionIndex = a;
                        uiController.ShowStepScreen(); uiController.UpdateUIForCurrentStep();
                        UpdateHologramGuide();
                        return true;
                    }
            }
        return false;
    }

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
        validationGeneration++;
        TestMode = uiController.ImageTestMode;
        StopAllCoroutines();
        currentProcedure = SmartLOTOClient.NormalizeProcedure(procedure);
        isLockoutPhase = true;
        currentPhaseIndex = currentStageIndex = currentActionIndex = 0;
        validationPending = maintenancePresented = maintenanceVisible = false;
        ShowCurrentScreen();
    }

    // Returns the active step (ActionData) currently being executed
    public SmartLOTOClient.ActionData GetActiveAction()
    {
        if (currentProcedure == null || currentProcedure.workflow_stages == null) return null;

        var activeStage = GetActiveStage();
        if (activeStage != null)
        {
            var steps = activeStage.steps != null && activeStage.steps.Length > 0 ? activeStage.steps : activeStage.actions;
            if (steps != null && currentActionIndex < steps.Length) return steps[currentActionIndex];
            return null;
        }

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

        var phases = currentProcedure.workflow_stages.phases;
        if (phases != null && phases.Length > 0)
        {
            if (currentPhaseIndex >= phases.Length || phases[currentPhaseIndex].stages == null || currentStageIndex >= phases[currentPhaseIndex].stages.Length) return null;
            return phases[currentPhaseIndex].stages[currentStageIndex];
        }

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

        if (validationPending || capturedImageBytes == null || capturedImageBytes.Length == 0) return;
        validationPending = true;
        int generation = ++validationGeneration;
        string frame = uiController.FrameIdentity;
        string actionId = action.Id;
        uiController.ClearFrameTargets();
        ClearHologramGuide();
        uiController.SetValidationBusy(true);
        uiController.ShowStatus("Analyse de la capture selon les criteres HSE...", LotoUIController.PremiumYellow);
        string requestIdentity = Guid.NewGuid().ToString();
        if (TestMode)
        {
            string requestId = Guid.NewGuid().ToString();
            lotoClient.VerifyTestImage(uiController.TestVersionId, stage.StageNumber, stage.stage_code, actionId,
                capturedImageBytes, requestId, res => {
                    if (!IsCurrentValidation(generation, actionId, frame)) return;
                    validationPending = false; uiController.SetValidationBusy(false);
                    if (res == null || !res.test_mode || res.request_id != requestId || res.action_id != actionId
                        || res.image_sha256 != uiController.FrameSha256 || res.procedure_version_id != uiController.TestVersionId)
                    { OnStepValidationFailed("Erreur technique : résultat non associé à cette capture."); return; }
                    uiController.ShowFrameResult(res);
                }, error => { if (IsCurrentValidation(generation, actionId, frame)) OnStepValidationFailed(error); });
            return;
        }
        lotoClient.ValidateActiveStep(stage.StageNumber, action.Id, action.vision_prompt ?? string.Empty, capturedImageBytes,
            (res) => {
                if (!IsCurrentValidation(generation, actionId, frame)) return;
                if (res == null || res.request_id != requestIdentity || res.action_id != actionId
                    || res.image_sha256 != uiController.FrameSha256 || string.IsNullOrEmpty(res.outcome))
                { OnStepValidationFailed("Erreur technique : résultat non associé à cette capture."); return; }
                uiController.ShowFrameResult(res);
                if (res.verified)
                {
                    OnStepValidated(action.Id, FormatObservation(res));
                }
                else
                {
                    OnStepValidationFailed(FormatObservation(res));
                }
            },
            (error) => {
                if (!IsCurrentValidation(generation, actionId, frame)) return;
                OnStepValidationFailed(error);
            }, requestIdentity
        );
    }

    public void RequestHumanConfirmation()
    {
        var action = GetActiveAction(); var stage = GetActiveStage();
        if (validationPending || action == null || stage == null || action.VerificationMethod != "human_confirmation") return;
        validationPending = true;
        int generation = ++validationGeneration;
        string actionId = action.Id, requestId = Guid.NewGuid().ToString();
        uiController.SetValidationBusy(true);
        uiController.ShowStatus("Enregistrement de la confirmation humaine...", LotoUIController.PremiumYellow);
        lotoClient.ConfirmActiveStep(stage.StageNumber, stage.stage_code, actionId, TestMode, uiController.TestVersionId, requestId,
            result => {
                // An operator attestation is tied to the action, never to a camera frame.
                if (generation != validationGeneration || GetActiveAction()?.Id != actionId) return;
                if (result == null || !result.verified || result.outcome != "human_confirmed" || result.action_id != actionId
                    || result.request_id != requestId || result.test_mode != TestMode)
                { OnStepValidationFailed("Confirmation non enregistrée : contexte incorrect."); return; }
                if (TestMode) { validationPending = false; uiController.SetValidationBusy(false); uiController.ShowFrameResult(result); }
                else OnStepValidated(actionId, "Opération confirmée par l'opérateur.");
            }, error => { if (generation == validationGeneration && GetActiveAction()?.Id == actionId) OnStepValidationFailed(error); });
    }

    private bool IsCurrentValidation(int generation, string actionId, string frame)
    {
        return generation == validationGeneration && GetActiveAction()?.Id == actionId && uiController.FrameIdentity == frame;
    }

    // Triggered when the operator clicks "Manual Override" (Mode dégradé)
    public void RequestManualOverride(string reason, byte[] capturedImageBytes,
        Action onSuccess, Action<string> onFailure)
    {
        if (TestMode) { onFailure?.Invoke("TEST : aucune dérogation d'intervention autorisée."); return; }
        var action = GetActiveAction();
        var stage = GetActiveStage();

        if (action == null || stage == null)
        {
            Debug.LogError("[LOTO] No active action to override.");
            onFailure?.Invoke("Aucune étape active pour cette dérogation.");
            return;
        }

        if (validationPending) { onFailure?.Invoke("Une vérification est déjà en cours."); return; }
        validationPending = true;
        uiController.SetValidationBusy(true);
        uiController.ShowStatus("Envoi de la dérogation manuelle...", LotoUIController.PremiumYellow);
        int generation = ++validationGeneration;
        string frame = uiController.FrameIdentity;
        string verificationMethod = currentProcedure.schema_version == "2.0" ? action.VerificationMethod : string.Empty;
        lotoClient.ManualOverrideActiveStep(stage.StageNumber, action.Id, reason, verificationMethod, capturedImageBytes,
            (res) => {
                if (!IsCurrentValidation(generation, action.Id, frame)) return;
                if (res != null && res.verified)
                {
                    OnStepValidated(action.Id);
                    onSuccess?.Invoke();
                }
                else
                {
                    string message = res != null && !string.IsNullOrEmpty(res.message)
                        ? res.message
                        : "Le serveur n'a pas confirmé la dérogation.";
                    OnStepValidationFailed(message);
                    onFailure?.Invoke(message);
                }
            },
            (error) => {
                if (!IsCurrentValidation(generation, action.Id, frame)) return;
                OnStepValidationFailed(error);
                onFailure?.Invoke(error);
            }
        );
    }

    // Callback from SmartLOTOClient on successful validation or override
    public void OnStepValidated(string actionId, string diagnosis = null)
    {
        Debug.Log($"[LOTO] Step {actionId} successfully validated.");
        uiController.ShowStatus(diagnosis ?? "Dérogation enregistrée.", LotoUIController.PremiumGreen);
        StartCoroutine(AdvanceToNextStepAfterDelay());
    }

    // Callback from SmartLOTOClient on validation failure
    public void OnStepValidationFailed(string errorMessage)
    {
        validationPending = false;
        uiController.SetValidationBusy(false);
        Debug.LogWarning($"[LOTO] Step validation failed: {errorMessage}");
        uiController.ShowStatus(errorMessage, LotoUIController.PremiumYellow);
    }

    private IEnumerator AdvanceToNextStepAfterDelay()
    {
        yield return new WaitForSeconds(1.5f);
        validationPending = false;
        uiController.SetValidationBusy(false);
        AdvanceStep();
    }

    private void AdvanceStep()
    {
        if (currentProcedure == null) return;

        var phases = currentProcedure.workflow_stages != null ? currentProcedure.workflow_stages.phases : null;
        if (phases != null && phases.Length > 0)
        {
            AdvanceCanonicalPhaseStep(phases);
            return;
        }

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
                    PresentMaintenance();
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

    private void AdvanceCanonicalPhaseStep(SmartLOTOClient.ProcedurePhaseData[] phases)
    {
        // Advance the action pointer within the current stage.
        // ShowCurrentScreen will roll over to the next stage/phase as needed.
        currentActionIndex++;
        ShowCurrentScreen();
    }

    private static bool IsMaintenanceBoundary(string type)
    {
        string value = (type ?? "").ToUpperInvariant();
        return value == "INTERVENTION" || value == "MAINTENANCE" || value == "RESTORATION"
            || value == "RESTORE" || value == "DECONSIGNATION" || value == "DÉCONSIGNATION";
    }

    public void ShowCurrentScreen()
    {
        if (maintenanceVisible) return;
        var phases = currentProcedure?.workflow_stages?.phases;
        if (phases != null && phases.Length > 0)
        {
            // Advance through every declared step, including arbitrary phase names and empty groups.
            while (currentPhaseIndex < phases.Length)
            {
                var phase = phases[currentPhaseIndex];
                if (phase == null) { currentPhaseIndex++; continue; }
                if (currentProcedure.phase_model_version == 0 && !maintenancePresented && IsMaintenanceBoundary(phase.phase_type))
                {
                    PresentMaintenance();
                    return;
                }
                var stages = phase.stages ?? new SmartLOTOClient.StageData[0];
                while (currentStageIndex < stages.Length)
                {
                    var stage = stages[currentStageIndex];
                    var steps = stage?.steps != null && stage.steps.Length > 0 ? stage.steps : stage?.actions;
                    if (steps != null && currentActionIndex < steps.Length)
                    {
                        if (steps[currentActionIndex] == null) { currentActionIndex++; continue; }
                        isLockoutPhase = !IsMaintenanceBoundary(phase.phase_type);
                        uiController.ShowStepScreen();
                        uiController.UpdateUIForCurrentStep();
                        UpdateHologramGuide();
                        return;
                    }
                    currentActionIndex = 0;
                    currentStageIndex++;
                }
                currentStageIndex = 0;
                currentPhaseIndex++;
            }
            ClearHologramGuide();
            if (currentProcedure.phase_model_version == 0 && !maintenancePresented) PresentMaintenance();
            else uiController.ShowClosureScreen();
            return;
        }
        if (GetActiveAction() == null)
        {
            if (isLockoutPhase && !maintenancePresented) { isLockoutPhase = false; PresentMaintenance(); }
            else uiController.ShowClosureScreen();
            return;
        }
        uiController.ShowStepScreen();
        uiController.UpdateUIForCurrentStep();
        UpdateHologramGuide();
    }

    private void PresentMaintenance()
    {
        maintenancePresented = maintenanceVisible = true;
        ClearHologramGuide();
        uiController.ShowMaintenanceScreen();
    }

    public void StartRestorationPhase()
    {
        if (!maintenanceVisible) return;
        maintenanceVisible = false;
        ShowCurrentScreen();
    }

    private static string FormatObservation(SmartLOTOClient.StepValidationResponse response)
    {
        if (response == null) return "Le serveur n'a pas fourni de diagnostic.";
        return response.message + "\n" + response.observed_state
            + (string.IsNullOrEmpty(response.detected_component) ? "" : "\nOrgane : " + response.detected_component)
            + " | Confiance : " + response.confidence.ToString("P0");
    }

    public List<SmartLOTOClient.ComponentData> GetActiveComponents()
    {
        var result = new List<SmartLOTOClient.ComponentData>();
        var action = GetActiveAction();
        if (action == null) return result;
        foreach (var component in currentProcedure.components ?? new SmartLOTOClient.ComponentData[0])
            if (SmartLOTOClient.ReferencesComponent(action, component)) result.Add(component);
        return result;
    }

    public string PhaseProgress()
    {
        var phases = currentProcedure?.workflow_stages?.phases ?? currentProcedure?.phases;
        if (phases == null || phases.Length == 0)
            return isLockoutPhase ? "CONSIGNATION" : "DÉCONSIGNATION";

        if (currentPhaseIndex >= phases.Length)
            return isLockoutPhase ? "CONSIGNATION" : "DÉCONSIGNATION";

        var phase = phases[currentPhaseIndex];
        // Count total steps in this phase and steps before the current stage
        int total = 0, before = 0;
        var stages = phase.stages ?? new SmartLOTOClient.StageData[0];
        for (int i = 0; i < stages.Length; i++)
        {
            int count = stages[i]?.steps?.Length ?? stages[i]?.actions?.Length ?? 0;
            total += count;
            if (i < currentStageIndex) before += count;
        }
        string kind = (phase.phase_type ?? "").ToLowerInvariant();
        string phaseName = kind == "restoration" ? "DÉCONSIGNATION / REMISE EN SERVICE"
            : kind == "maintenance" || kind == "intervention" ? "MAINTENANCE"
            : kind == "consignation" || kind == "isolation" || kind == "lockout" ? "CONSIGNATION"
            : kind == "preparation" ? "PRÉPARATION" : !string.IsNullOrEmpty(phase.title) ? phase.title.ToUpperInvariant()
            : $"PHASE {currentPhaseIndex + 1}";
        int stepNum = before + currentActionIndex + 1;
        return $"{phaseName} · Étape {stepNum} / {Mathf.Max(total, stepNum)}";
    }

    // Closes the intervention with the operator's drawn signature.
    public void CloseIntervention(byte[] signatureBytes)
    {
        if (TestMode) { uiController.ShowStatus("TEST : aucune intervention à clôturer.", LotoUIController.PremiumYellow); return; }
        uiController.SetSignatureSubmitting(true);
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
        uiController.SetSignatureSubmitting(false);
        Debug.Log($"[LOTO] Intervention successfully closed. Report PDF: {pdfReportUrl}");
        ClearHologramGuide();
        uiController.ShowStatus("Intervention Clôturée ! ✅\nRapport PDF généré avec succès.", LotoUIController.PremiumGreen);
        uiController.ShowFinalReportScreen(pdfReportUrl);
    }

    public void OnInterventionCloseFailed(string error)
    {
        uiController.SetSignatureSubmitting(false);
        Debug.LogError($"[LOTO] Intervention closure failed: {error}");
        uiController.ShowStatus($"Échec de clôture ❌\n{error}", LotoUIController.PremiumRed);
    }

    // --- Hologram Spawner Logic ---

    [Header("Hologram Guidance System")]
    [SerializeField] private Transform originAnchor;
    private GameObject activeHologram;

    private void Start() { EnsureVirtualMaquetteVisible(); }

    public Transform EnsureVirtualMaquetteVisible()
    {
        if (originAnchor == null)
            foreach (var candidate in Resources.FindObjectsOfTypeAll<Transform>())
                if (candidate.name == "LOTO_Origin_Anchor" && candidate.gameObject.scene.IsValid()
                    && candidate.gameObject.scene.isLoaded) { originAnchor = candidate; break; }
        if (originAnchor == null) return null;
        originAnchor.gameObject.SetActive(true);
        Transform maquette = null;
        foreach (var child in originAnchor.GetComponentsInChildren<Transform>(true))
            if (child.name == "VirtualMaquette") { maquette = child; break; }
        if (maquette != null)
        {
            for (Transform t = maquette; t != null && t != originAnchor; t = t.parent) t.gameObject.SetActive(true);
            foreach (var renderer in maquette.GetComponentsInChildren<Renderer>(true)) renderer.enabled = true;
        }
        return originAnchor;
    }

    public void UpdateHologramGuide()
    {
        // Virtual step guidance comes only from this frame's AI localization.
        // Manual maintenance calibration must not spawn a second, fixed arrow.
        if (uiController != null && uiController.IsVirtualCameraSource)
        {
            ClearHologramGuide();
            return;
        }
        if (activeHologram != null)
        {
            Destroy(activeHologram);
            activeHologram = null;
        }

        var action = GetActiveAction();
        if (maintenanceVisible || validationPending || (TestMode && !uiController.IsVirtualCameraSource)
            || !spatialTrackingConfirmed || action == null) return;

        // Determine correct base position (offset from anchor or target specific organ)
        Vector3 basePosition = Vector3.zero;
        bool targetResolved = false;
        if (currentProcedure != null && currentProcedure.anchors != null)
        {
            var components = GetActiveComponents();
            foreach (var anchor in currentProcedure.anchors)
            {
                if (anchor == null) continue;
                bool matches = components.Exists(c =>
                    (string.IsNullOrEmpty(action.primary_component) || action.primary_component == c.component_id
                        || action.primary_component == c.tag || action.primary_component == c.unity_class_id)
                    && (anchor.organ_name == c.component_id || anchor.organ_name == c.tag || anchor.organ_name == c.unity_class_id));
                if (!matches) continue;
                basePosition = new Vector3(anchor.pos_x, anchor.pos_y, anchor.pos_z);
                targetResolved = true;
                break;
            }
        }

        // Add action's relative spatial guide position
        Vector3 guideRot = Vector3.zero;
        if (action.spatial_guide != null)
        {
            basePosition += new Vector3(action.spatial_guide.pos_x, action.spatial_guide.pos_y, action.spatial_guide.pos_z);
            guideRot = new Vector3(action.spatial_guide.rot_x, action.spatial_guide.rot_y, action.spatial_guide.rot_z);
            targetResolved = true;
        }
        else if (originAnchor != null && uiController.IsVirtualCameraSource)
        {
            // A calibrated model point is valid even when the procedure has no spatial guide.
            foreach (var component in GetActiveComponents())
            {
                if (!string.IsNullOrEmpty(action.primary_component)
                    && action.primary_component != component.component_id && action.primary_component != component.tag
                    && action.primary_component != component.unity_class_id) continue;
                string componentId = SmartLOTOClient.FirstText(component.component_id, component.tag);
                if (!uiController.TryGetVirtualComponentPoint(componentId, out Vector3 worldPoint)) continue;
                basePosition = originAnchor.InverseTransformPoint(worldPoint);
                targetResolved = true;
                break;
            }
        }
        if (!targetResolved) return;

        // Spawn hologram relative to origin anchor
        if (originAnchor != null)
        {
            activeHologram = new GameObject($"Hologram_Guide_{action.Id}");
            activeHologram.transform.SetParent(originAnchor, false);
            activeHologram.transform.localPosition = basePosition;
            activeHologram.transform.localRotation = Quaternion.Euler(guideRot);
            
            // Attach visual renderer component
            var guide = activeHologram.AddComponent<LotoHologramGuide>();
            Transform model = uiController.VirtualMaquetteTransform;
            if (uiController.IsVirtualCameraSource && model != null)
                guide.AttachToSurface(model, model.InverseTransformPoint(activeHologram.transform.position));
            Debug.Log($"[LOTO Spawner] Hologram spawned at local position: {basePosition}");
        }
    }

    // Explicit tracking origin, or the known scene origin for the virtual 3D camera.
    private bool spatialTrackingConfirmed;
    public void SetTrackedOrigin(Transform anchor, bool trackingValid)
    {
        originAnchor = anchor;
        spatialTrackingConfirmed = anchor != null && trackingValid;
        if (!spatialTrackingConfirmed) ClearHologramGuide();
        else UpdateHologramGuide();
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
