using System;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.UI;

public partial class LotoUIController
{
    public string FrameIdentity { get; private set; } = "";
    public string FrameSha256 { get; private set; } = "";
    public string TestVersionId { get; private set; } = "";
    public bool ImageTestMode { get; private set; }
    private Texture2D fixedFrame;
    private byte[] fixedFrameBytes;
    private FrameTargetOverlay frameTargets;
    private readonly System.Collections.Generic.List<GameObject> virtualFrameTargets = new System.Collections.Generic.List<GameObject>();
    private Coroutine pendingStepGuidance, stepGuidanceRequest;
    private int stepGuidanceGeneration;
    private string stepGuidanceKey = "";
    private SmartLOTOClient.StepValidationResponse lastFrameResult;
    private string testContract = "", testVersion = "", testImageName = "";
    private string[] testImages = new string[0];
    private Vector2 testScroll;
    private bool showTestBrowser;
    public bool SequenceBrowserOpen => showTestBrowser;
    private int testRotation;
    private string manualTargetId = "";
    private int sequenceIndex = -1;
    [Serializable] private class SequenceTimeline { public SequenceImage[] images; }
    [Serializable] private class SequenceImage { public string image; public int index; }

    public void LoadTestSequence(string directory)
    {
        string root = Path.GetFullPath(directory);
        string timeline = Path.Combine(root, "timeline.json");
        if (File.Exists(timeline))
        {
            var data = JsonUtility.FromJson<SequenceTimeline>(File.ReadAllText(timeline));
            var paths = new System.Collections.Generic.List<string>();
            foreach (var row in data.images)
            {
                string path = Path.GetFullPath(Path.Combine(root, row.image));
                if (!path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new ArgumentException("Image hors du dossier TEST.");
                paths.Add(path);
            }
            testImages = paths.ToArray();
        }
        else
        {
            testImages = Array.FindAll(Directory.GetFiles(root), path =>
                path.EndsWith(".png", StringComparison.OrdinalIgnoreCase) || path.EndsWith(".jpg", StringComparison.OrdinalIgnoreCase)
                || path.EndsWith(".jpeg", StringComparison.OrdinalIgnoreCase));
            Array.Sort(testImages, MockupSequenceTester.NaturalCompare);
        }
        sequenceIndex = -1;
        if (testImages.Length > 0) SelectTestSequenceImage(0);
    }
    public void SelectTestSequenceImage(int index)
    {
        if (index < 0 || index >= testImages.Length) return;
        LoadTestImage(testImages[index], 0);
    }

    private void OnGUI()
    {
        if (Event.current.type == EventType.KeyDown && Event.current.keyCode == KeyCode.F8)
            showTestBrowser = !showTestBrowser;
        if (!showTestBrowser) return;
        GUILayout.BeginArea(new Rect(12, 45, 440, Mathf.Min(Screen.height - 60, 650)), GUI.skin.box);
        GUILayout.Label("Procédure");
        GUILayout.Label("Contrat JSON de la révision"); testContract = GUILayout.TextField(testContract);
        GUILayout.Label("Identifiant de révision"); testVersion = GUILayout.TextField(testVersion);
        if (GUILayout.Button("Charger la procédure"))
        {
            try { LoadTestProcedure(File.ReadAllText(testContract), testVersion); }
            catch (Exception e) { ShowStatus(e.Message, PremiumRed); }
        }
        testScroll = GUILayout.BeginScrollView(testScroll);
        if (ImageTestMode && lotoManager.currentProcedure != null)
            foreach (var phase in lotoManager.currentProcedure.workflow_stages.phases)
                foreach (var stage in phase.stages)
                    foreach (var step in stage.steps ?? stage.actions)
                        if (GUILayout.Button(step.Id + " : " + step.InstructionText)) lotoManager.SelectTestAction(step.Id);
        if (lastFrameResult != null)
        {
            GUILayout.Label("Constats candidats du modele / ne resolvent pas les blocages HSE");
            foreach (var evidence in lastFrameResult.criterion_observations ?? new SmartLOTOClient.CriterionObservationData[0])
                GUILayout.Label("C" + (evidence.criterion_index + 1) + " / " + evidence.status + " : " + evidence.observation);
        }
        GUILayout.EndScrollView();
        GUILayout.EndArea();
    }

    public void LoadTestProcedure(string json, string version)
    {
        if (string.IsNullOrWhiteSpace(version)) throw new ArgumentException("Identifiant de révision TEST requis.");
        var procedure = SmartLOTOClient.ParseProcedure(json);
        ImageTestMode = true; TestVersionId = version.Trim(); ClearFrameTargets();
        lotoClient.activeMachineId = procedure.machine_id;
        lotoManager.InitializeProcedure(procedure);
        foreach (var phase in procedure.workflow_stages.phases)
            foreach (var stage in phase.stages)
                foreach (var step in stage.steps ?? stage.actions)
                { lotoManager.SelectTestAction(step.Id); return; }
    }

    public void LoadTestImage(string path, int clockwiseDegrees)
    {
        if (!ImageTestMode) throw new InvalidOperationException("Chargez une révision en TEST avant l'image.");
        var source = new Texture2D(2, 2, TextureFormat.RGB24, false);
        if (!source.LoadImage(File.ReadAllBytes(path))) { Destroy(source); throw new ArgumentException("Image illisible."); }
        fixedImageInput = true;
        testRotation = ((clockwiseDegrees % 360) + 360) % 360;
        if (testRotation % 90 != 0) { Destroy(source); throw new ArgumentException("Rotation multiple de 90° requise."); }
        int w = source.width, h = source.height;
        var pixels = source.GetPixels32();
        var rotated = CanonicalFrame.Transform(pixels, w, h, testRotation, false, out int ow, out int oh);
        var frame = new Texture2D(ow, oh, TextureFormat.RGB24, false);
        frame.SetPixels32(rotated); frame.Apply(); Destroy(source);
        lotoManager.InvalidateValidation(); testImageName = Path.GetFullPath(path);
        sequenceIndex = Array.IndexOf(testImages, testImageName);
        SetFixedFrame(frame);
        Debug.Log("[Image input] " + testImageName + " / " + testRotation + "°");
        ShowStatus("", PremiumGray);
    }

    private void SetFixedFrame(Texture2D frame, bool livePreview = false)
    {
        if (fixedFrame != null) Destroy(fixedFrame);
        fixedFrame = frame; fixedFrameBytes = frame.EncodeToPNG();
        using (var sha = SHA256.Create())
            FrameSha256 = BitConverter.ToString(sha.ComputeHash(fixedFrameBytes)).Replace("-", "").ToLowerInvariant();
        FrameIdentity = Guid.NewGuid().ToString();
        if (livePreview)
        {
            BindVirtualPreview(cameraPreviewImage);
            if (frameTargets == null) frameTargets = cameraPreviewImage.gameObject.AddComponent<FrameTargetOverlay>();
            frameTargets.SetFrame(frame.width, frame.height, true);
            return;
        }
        cameraPreviewImage.texture = fixedFrame;
        cameraPreviewImage.uvRect = new Rect(0, 0, 1, 1);
        cameraPreviewImage.rectTransform.localEulerAngles = Vector3.zero;
        cameraPreviewImage.rectTransform.localScale = Vector3.one;
        if (frameTargets == null) frameTargets = cameraPreviewImage.gameObject.AddComponent<FrameTargetOverlay>();
        frameTargets.SetFrame(frame.width, frame.height);
        frameTargets.Clicked -= OnTestTargetClicked;
        frameTargets.Clicked += OnTestTargetClicked;
        SetCameraMessage(cameraPreviewImage, "");
        var reticle = cameraPreviewImage.transform.Find("Framing aid - not object tracking");
        if (reticle != null) reticle.gameObject.SetActive(false);
        overrideButton.interactable = !ImageTestMode;
    }

    public void ClearFrameTargets()
    {
        CancelStepGuidance();
        lastFrameResult = null;
        if (frameTargets != null) frameTargets.Clear();
        foreach (var target in virtualFrameTargets)
            if (target != null) { target.SetActive(false); Destroy(target); }
        virtualFrameTargets.Clear();
    }

    private void CancelStepGuidance()
    {
        stepGuidanceGeneration++;
        stepGuidanceKey = "";
        if (pendingStepGuidance != null) StopCoroutine(pendingStepGuidance);
        pendingStepGuidance = null;
        if (stepGuidanceRequest != null && lotoClient != null) lotoClient.StopCoroutine(stepGuidanceRequest);
        stepGuidanceRequest = null;
    }

    private void QueueStepGuidance()
    {
        var action = lotoManager.GetActiveAction();
        var stage = lotoManager.GetActiveStage();
        string version = ImageTestMode ? TestVersionId : lotoManager.currentProcedure?.procedure_version_id;
        if (!IsVirtualCameraSource || VirtualMaquetteTransform == null || !virtualCameraReady
            || sourceSequence.ActiveTexture == null || !stepPanel.activeSelf
            || action == null || stage == null || string.IsNullOrEmpty(version)
            || lotoManager.IsValidationPending || pendingCapture != null) return;
        string key = version + ":" + stage.stage_code + ":" + action.Id + ":" + FrameIdentity
            + ":" + sourceSequence.currentIndex;
        if (stepGuidanceKey == key) return;
        CancelStepGuidance();
        stepGuidanceKey = key;
        pendingStepGuidance = StartCoroutine(CaptureStepGuidance(stepGuidanceGeneration, version));
    }

    private System.Collections.IEnumerator CaptureStepGuidance(int generation, string version)
    {
        yield return new WaitForEndOfFrame();
        pendingStepGuidance = null;
        if (generation != stepGuidanceGeneration || !stepPanel.activeSelf
            || pendingCapture != null || lotoManager.IsValidationPending) yield break;
        var action = lotoManager.GetActiveAction();
        var stage = lotoManager.GetActiveStage();
        if (action == null || stage == null) yield break;
        string actionId = action.Id, frameId = FrameIdentity, requestId = Guid.NewGuid().ToString();
        string stageCode = stage.stage_code;
        bool testMode = ImageTestMode;
        var procedure = lotoManager.currentProcedure;
        Texture2D texture = null;
        byte[] bytes = null;
        int width = 0, height = 0;
        try
        {
            // This snapshot never becomes a validation/evidence frame.
            texture = ReadVirtualCameraFrame();
            if (texture != null) { width = texture.width; height = texture.height; bytes = texture.EncodeToPNG(); }
        }
        catch (Exception error) { Debug.LogWarning("[Guidage] " + error.Message); }
        finally { if (texture != null) Destroy(texture); }
        if (bytes == null || bytes.Length == 0) yield break;
        string hash;
        using (var sha = SHA256.Create())
            hash = BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        Func<bool> isCurrent = () => generation == stepGuidanceGeneration && stepPanel.activeSelf
            && IsVirtualCameraSource && !lotoManager.IsValidationPending && pendingCapture == null
            && lotoManager.currentProcedure == procedure && lotoManager.GetActiveAction()?.Id == actionId
            && lotoManager.GetActiveStage()?.stage_code == stageCode && FrameIdentity == frameId;
        stepGuidanceRequest = lotoClient.LocateStepTargets(version, stage.StageNumber, stageCode, actionId,
            bytes, requestId, testMode, result => {
                if (!isCurrent()) return;
                stepGuidanceRequest = null;
                if (!result.guidance_only || result.verified || result.test_mode != testMode
                    || result.request_id != requestId || result.action_id != actionId
                    || result.procedure_version_id != version || result.image_sha256 != hash
                    || result.image_width != width || result.image_height != height) return;
                ShowVirtualFrameTargets(result.targets);
            }, error => {
                if (!isCurrent()) return;
                stepGuidanceRequest = null;
                Debug.LogWarning("[Guidage] " + error);
            });
    }

    private void ShowVirtualFrameTargets(SmartLOTOClient.TargetData[] targets)
    {
        Transform model = VirtualMaquetteTransform;
        var components = lotoManager.GetActiveComponents();
        foreach (var target in targets ?? new SmartLOTOClient.TargetData[0])
        {
            if (target == null || !target.localization_clear || string.IsNullOrWhiteSpace(target.identification_feature)
                || string.IsNullOrEmpty(target.component_id) || float.IsNaN(target.x) || float.IsNaN(target.y)
                || float.IsNaN(target.confidence) || float.IsInfinity(target.confidence)
                || target.x < 0f || target.x > 1f || target.y < 0f || target.y > 1f || target.confidence < .8f) continue;
            if (!components.Exists(component => target.component_id == component.component_id
                || target.component_id == component.tag || target.component_id == component.internal_id
                || target.component_id == component.source_tag || target.component_id == component.unity_class_id)) continue;
            var marker = new GameObject("POI " + target.component_id);
            marker.AddComponent<LotoHologramGuide>().AttachToSurface(model,
                new Vector3(target.x - .5f, .5f - target.y, 0f));
            virtualFrameTargets.Add(marker);
        }
    }
    private void ResumeLivePreview()
    {
        if (fixedImageInput) return;
        StartVirtualPreview(cameraPreviewImage);
    }
    private void OnTestTargetClicked(Vector2 point)
    {
        if (ImageTestMode && !string.IsNullOrEmpty(manualTargetId)) ShowTestCalibrationTarget(manualTargetId, point);
    }
    public void ShowTestCalibrationTarget(string componentId, Vector2 point)
    {
        if (!ImageTestMode || frameTargets == null || !lotoManager.GetActiveComponents().Exists(c =>
            c.component_id == componentId || c.tag == componentId)) return;
        frameTargets.Show(new[] { new SmartLOTOClient.TargetData { component_id = componentId,
            x = point.x, y = point.y, confidence = 1, localization_clear = true,
            identification_feature = "Désignation manuelle explicite, pas une détection IA" } });
        ShowStatus("TEST / CALIBRATION MANUELLE 2D : " + componentId
            + "\nAucune détection automatique ; aucun état validé.", PremiumYellow);
    }
    public void ShowFrameResult(SmartLOTOClient.StepValidationResponse result)
    {
        ClearFrameTargets();
        if (result == null) { ShowStatus("Erreur technique : résultat vide.", PremiumYellow); return; }
        lastFrameResult = result;
        var components = lotoManager.GetActiveComponents();
        var stepTargets = Array.FindAll(result.targets ?? new SmartLOTOClient.TargetData[0], target =>
            target != null && components.Exists(component =>
                target.component_id == component.component_id || target.component_id == component.tag
                || target.component_id == component.internal_id || target.component_id == component.source_tag
                || target.component_id == component.unity_class_id));
        if (frameTargets != null && fixedFrame != null && result.image_width == fixedFrame.width && result.image_height == fixedFrame.height)
        {
            if (IsVirtualCameraSource && VirtualMaquetteTransform != null)
                ShowVirtualFrameTargets(stepTargets);
            else frameTargets.Show(stepTargets);
        }
        string state = result.outcome == "satisfied" ? "SATISFAIT" : result.outcome == "contradicted" ? "CONTREDIT"
            : result.outcome == "human_confirmation_required" ? "CONFIRMATION HUMAINE REQUISE"
            : result.outcome == "technical_error" ? "ERREUR TECHNIQUE" : "INDÉTERMINÉ";
        if (result.outcome == "human_confirmed") state = "CONFIRMÉ PAR L’OPÉRATEUR";
        if (result.evaluation_goal == "state_identification" && result.state_identified)
            state = "ÉTAT IDENTIFIÉ — condition de sécurité non évaluée";
        ShowStatus(state + "\n" + result.message + "\n" + result.observed_state,
            result.verified ? PremiumGreen : PremiumYellow);
    }
}
