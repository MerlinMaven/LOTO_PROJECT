using System;
using System.IO;
using System.Collections.Generic;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;

public partial class LotoUIController : MonoBehaviour
{
    [Header("Manager References")]
    [SerializeField] private LotoManager lotoManager;
    [SerializeField] private SmartLOTOClient lotoClient;

    [Header("Panels")]
    [SerializeField] private GameObject welcomePanel;
    [SerializeField] private GameObject manualSelectionPanel;
    [SerializeField] private GameObject qrScanPanel;
    [SerializeField] private GameObject stepPanel;
    [SerializeField] private GameObject maintenancePanel;
    [SerializeField] private GameObject signaturePanel;
    [SerializeField] private GameObject reportPanel;

    [Header("Welcome Panel UI")]
    [SerializeField] private Button chooseQRScanButton;
    [SerializeField] private Button chooseManualButton;

    [Header("QR Scan Panel UI")]
    [SerializeField] private RawImage qrCameraPreviewImage;
    [SerializeField] private Button qrBackButton;
    [SerializeField] private RectTransform scanLaserLine;
    [SerializeField] private float laserSpeed = 150f;
    [SerializeField] private float laserMaxY = 100f;
    [SerializeField] private float laserMinY = -100f;
    private bool laserMovingDown = true;

    [Header("Manual Selection Panel UI")]
    [SerializeField] private Dropdown machineIdDropdown;
    [SerializeField] private Button startButton;
    [SerializeField] private Button manualBackButton;

    [Header("Step Panel UI")]
    [SerializeField] private Text phaseTitleText;
    [SerializeField] private Text stageTitleText;
    [SerializeField] private Text stepDescText;
    [SerializeField] private Text visionPromptText;
    [SerializeField] private RawImage cameraPreviewImage;
    [SerializeField] private InputField overrideReasonInput;
    [SerializeField] private Button validateButton;
    [SerializeField] private Button overrideButton;
    [SerializeField] private GameObject overrideConfirmationPanel;
    [SerializeField] private Text overrideConfirmationText;
    [SerializeField] private Button overrideCancelButton;
    [SerializeField] private Button overrideConfirmButton;

    [Header("Status UI")]
    [SerializeField] private Text statusText;
    [SerializeField] private Image statusBackgroundImage;

    [Header("Maintenance Panel UI")]
    [SerializeField] private RawImage maintenancePreviewImage;
    [SerializeField] private Text maintenanceTaskTitleText;
    [SerializeField] private Text maintenanceCalibrationText;
    private Text maintenanceExpectedStateText;
    private Button maintenanceComponentButton;
    private SmartLOTOClient.ComponentData[] calibrationComponents = new SmartLOTOClient.ComponentData[0];
    private int calibrationComponentIndex;
    [SerializeField] private RectTransform maintenanceArrowLine;
    [SerializeField] private Text maintenanceArrowHead;
    [SerializeField] private Button startRestorationButton;

    [Header("Signature Panel UI")]
    [SerializeField] private RawImage signatureCanvas;
    [SerializeField] private Button clearSignatureButton;
    [SerializeField] private Text closureSummaryText;
    [SerializeField] private Button submitSignatureButton;

    [Header("Report Panel UI")]
    [SerializeField] private Text reportUrlText;
    [SerializeField] private Button openReportButton;
    [SerializeField] private Button restartButton;

    [Header("Virtual 3D camera (no physical camera)")]
    [SerializeField] private Camera virtualSourceCamera;
    [SerializeField] private RenderTexture virtualCameraTarget;
    private Camera virtualCaptureCamera;
    private RenderTexture virtualRenderTexture;
    private bool ownsVirtualTarget;
    private bool virtualCameraReady;
    private bool firstVirtualFrameVerified;
    private bool virtualPoseRecorded;
    private Matrix4x4 previousVirtualPose, previousVirtualProjection, previousMockupPose;
    private bool fixedImageInput;
    private Coroutine pendingCapture;
    private Coroutine pendingFrameReady;
    private MockupSequenceTester sourceSequence;
    public bool IsVirtualCameraSource => virtualCaptureCamera != null && !fixedImageInput;
    public Transform VirtualMaquetteTransform => sourceSequence != null ? sourceSequence.transform : null;
    private Vector3 initialCameraLocalPos;
    private Quaternion initialCameraLocalRot = Quaternion.identity;
    private float currentPitch = 0f;
    private float currentYaw = 0f;
    private bool cameraFramingInitialized = false;

    [Header("AR Gaze QR Reticle")]
    [SerializeField] private GameObject qrReticleObject;
    [SerializeField] private Image qrReticleProgressImage;
    private GameObject virtualQrTag;
    private GameObject virtualQrEasel;
    private GameObject workbenchObject;
    private Coroutine gazeRecenterCoroutine;
    private float qrGazeDwellTimer = 0f;
    private const float QR_GAZE_DWELL_TARGET = 0.75f;
    private bool qrScanCompleted = false;

    public bool IsTextInputFocused
    {
        get
        {
            if (overrideReasonInput != null && overrideReasonInput.isFocused) return true;
            if (GUIUtility.keyboardControl != 0) return true;
            var es = EventSystem.current;
            if (es != null && es.currentSelectedGameObject != null)
            {
                var input = es.currentSelectedGameObject.GetComponentInParent<InputField>();
                if (input != null && input.isFocused) return true;
            }
            return false;
        }
    }
    public RenderTexture VirtualCameraTexture => virtualRenderTexture;
    private SignaturePad signaturePad;
    private byte[] pendingOverrideImage;
    private string pendingOverrideReason;
    private float maintenanceTargetX = .5f;
    private float maintenanceTargetY = .5f;
    private bool maintenanceTargetCalibrated;
    private string savedReportUrl;

    private SmartLOTOClient.ProcedureItem[] availableProcedures;

    // Palette de couleurs premium
    public static readonly Color PremiumGray = new Color32(148, 163, 184, 255);
    public static readonly Color PremiumGreen = new Color32(52, 211, 153, 255);
    public static readonly Color PremiumRed = new Color32(251, 113, 133, 255);
    public static readonly Color PremiumBlue = new Color32(125, 211, 252, 255);
    public static readonly Color PremiumYellow = new Color32(251, 191, 36, 255);
    public static readonly Color PremiumTeal = new Color32(94, 234, 212, 255);


    private void Start()
    {
        if (lotoManager == null) lotoManager = GetComponent<LotoManager>();
        if (lotoClient == null) lotoClient = GetComponent<SmartLOTOClient>();
        StartVirtualPreview(cameraPreviewImage);
        // Initial setup - Start on Welcome Panel
        ShowPanel(welcomePanel);
        ShowStatus("Connexion au serveur et chargement des machines...", PremiumGray);

        // Welcome Panel buttons
        chooseQRScanButton.onClick.AddListener(OnChooseQRScanPressed);
        chooseManualButton.onClick.AddListener(OnChooseManualPressed);

        // Navigation buttons
        qrBackButton.onClick.AddListener(OnBackToWelcomePressed);
        manualBackButton.onClick.AddListener(OnBackToWelcomePressed);

        // Core actions
        startButton.onClick.AddListener(OnStartPressed);
        validateButton.onClick.AddListener(OnValidatePressed);
        overrideButton.onClick.AddListener(OnOverridePressed);
        overrideCancelButton.onClick.AddListener(CancelOverrideConfirmation);
        overrideConfirmButton.onClick.AddListener(ConfirmOverride);
        startRestorationButton.onClick.AddListener(OnStartRestorationPressed);
        if (maintenanceComponentButton != null)
        {
            maintenanceComponentButton.onClick.AddListener(() => {
                if (calibrationComponents.Length == 0) return;
                calibrationComponentIndex = (calibrationComponentIndex + 1) % calibrationComponents.Length;
                LoadMaintenanceCalibration();
            });
        }
        clearSignatureButton.onClick.AddListener(() => signaturePad?.Clear());
        submitSignatureButton.onClick.AddListener(OnSubmitSignaturePressed);
        openReportButton.onClick.AddListener(OnOpenReportPressed);
        restartButton.onClick.AddListener(OnRestartPressed);

        signaturePad = signatureCanvas.gameObject.AddComponent<SignaturePad>();
        signaturePad.Initialize(signatureCanvas);
        var calibrationSurface = maintenancePreviewImage.gameObject.AddComponent<MaintenanceCalibrationSurface>();
        calibrationSurface.Clicked += CalibrateMaintenanceTargetFromPointer;

        startButton.interactable = false;

        // Charger la liste des procédures/machines existantes
        lotoClient.GetProceduresList(OnProceduresLoaded, OnProceduresLoadFailed);
    }

    private void OnProceduresLoaded(SmartLOTOClient.ProcedureItem[] procedures)
    {
        availableProcedures = procedures;
        machineIdDropdown.ClearOptions();
        
        List<string> options = new List<string>();
        foreach (var proc in procedures)
        {
            options.Add($"{proc.machine_name} ({proc.machine_id})");
        }
        
        machineIdDropdown.AddOptions(options);
        startButton.interactable = procedures.Length > 0;
        
        if (procedures.Length > 0)
        {
            ShowStatus("Machines chargées. Choisissez un mode pour démarrer.", PremiumGreen);
        }
        else
        {
            ShowStatus("Aucune procédure approuvée trouvée dans la base.", PremiumYellow);
        }
    }

    private void OnProceduresLoadFailed(string error)
    {
        ShowStatus($"Échec de chargement des machines : {error}", PremiumRed);
        startButton.interactable = false;
    }

    private void StartVirtualPreview(RawImage targetImage)
    {
        if (targetImage == null || (fixedImageInput && targetImage == cameraPreviewImage)) return;
        try
        {
            if (virtualCaptureCamera == null) InitializeVirtualCamera();
            BindVirtualPreview(targetImage);
        }
        catch (Exception error)
        {
            virtualCameraReady = false;
            SetCameraMessage(targetImage, "Camera virtuelle indisponible : " + error.Message);
            ShowStatus("Camera virtuelle indisponible : " + error.Message, PremiumRed);
        }
    }

    private void InitializeVirtualCamera()
    {
        Transform origin = lotoManager != null ? lotoManager.EnsureVirtualMaquetteVisible() : null;
        if (virtualSourceCamera == null) virtualSourceCamera = Camera.main;
        if (virtualSourceCamera == null)
            foreach (var candidate in Resources.FindObjectsOfTypeAll<Camera>())
                if (candidate.gameObject.scene.IsValid() && candidate.gameObject.scene.isLoaded
                    && (candidate.CompareTag("MainCamera") || candidate.name == "Main Camera"))
                { virtualSourceCamera = candidate; break; }
        if (virtualSourceCamera == null) throw new InvalidOperationException("Main Camera absente de la scene.");
        virtualSourceCamera.gameObject.SetActive(true);
        RenderTexture candidateTarget = virtualCameraTarget != null ? virtualCameraTarget : virtualSourceCamera.targetTexture;
        virtualSourceCamera.targetTexture = null; // Display 1 must keep its camera.
        virtualSourceCamera.targetDisplay = 0;
        virtualSourceCamera.enabled = true;
        virtualSourceCamera.cullingMask = ~0;
        int uiLayer = LayerMask.NameToLayer("UI");
        if (uiLayer >= 0) virtualSourceCamera.cullingMask &= ~(1 << uiLayer);
        virtualSourceCamera.clearFlags = CameraClearFlags.SolidColor;
        virtualSourceCamera.backgroundColor = new Color(0.06f, 0.08f, 0.12f, 1f);
        virtualSourceCamera.nearClipPlane = 0.01f;
        virtualSourceCamera.fieldOfView = 60f;

        virtualSourceCamera.transform.position = new Vector3(0f, 1.38f, 0.95f);
        virtualSourceCamera.transform.rotation = Quaternion.Euler(48f, 0f, 0f);
        if (!cameraFramingInitialized)
        {
            initialCameraLocalPos = virtualSourceCamera.transform.localPosition;
            initialCameraLocalRot = virtualSourceCamera.transform.localRotation;
            cameraFramingInitialized = true;
        }

        if (candidateTarget != null && candidateTarget.width == 1280 && candidateTarget.height == 720 && candidateTarget.depth >= 24)
            virtualRenderTexture = candidateTarget;
        else
        {
            virtualRenderTexture = new RenderTexture(1280, 720, 24, RenderTextureFormat.ARGB32)
                { name = "SmartLOTO Virtual Camera 1280x720", filterMode = FilterMode.Bilinear };
            ownsVirtualTarget = true;
        }
        if (!virtualRenderTexture.IsCreated() && !virtualRenderTexture.Create())
            throw new InvalidOperationException("RenderTexture 1280x720 non disponible.");
        var cameraObject = new GameObject("SmartLOTO Virtual Capture Camera");
        cameraObject.SetActive(false);
        cameraObject.transform.SetParent(origin != null ? origin : virtualSourceCamera.transform.parent, false);
        cameraObject.transform.localPosition = virtualSourceCamera.transform.localPosition;
        cameraObject.transform.localRotation = virtualSourceCamera.transform.localRotation;
        virtualCaptureCamera = cameraObject.AddComponent<Camera>();
        UpdateVirtualCameraSettings();
        cameraObject.SetActive(true);
        if (origin != null)
        {
            sourceSequence = origin.GetComponentInChildren<MockupSequenceTester>(true);
            if (sourceSequence != null)
            {
                sourceSequence.TextureChanged += OnVirtualTextureChanged;
                FrameVirtualMaquette();
            }
        }
        BindVirtualPreview(cameraPreviewImage);
        BindVirtualPreview(qrCameraPreviewImage);
        BindVirtualPreview(maintenancePreviewImage);
        if (origin != null) lotoManager.SetTrackedOrigin(origin, true);
        QueueVirtualFrameReady();
        Debug.Log("[Virtual Camera] Main Camera -> AR Fullscreen view; capture camera -> 1280x720 RenderTexture.");
    }

    private void FrameVirtualMaquette()
    {
        if (sourceSequence == null || virtualSourceCamera == null) return;

        // 0. Création d'un vrai plateau d'établi horizontal bien visible sous les objets
        EnsureWorkbenchSurface();

        // 1. Format Paysage strict (largeur X = 0.58m > profondeur Z = 0.35m, ratio 1.655)
        float aspect = 1614f / 975f; // ≈ 1.655
        float tableWidth = 0.58f; // Largeur horizontale (axe X monde)
        float tableDepth = tableWidth / aspect; // Profondeur (axe Z monde) ≈ 0.35m

        // Sur le Quad Unity (texture native 975x1614) avec rotation paysage -90° sur Z :
        // local X (975) s'aligne avec Z monde (tableDepth = 0.35m)
        // local Y (1614) s'aligne avec X monde (tableWidth = 0.58m)
        sourceSequence.transform.localScale = new Vector3(tableDepth, tableWidth, 1f);

        // 2. Pose de la maquette posée horizontalement à plat sur la table (espace Monde) :
        // X = -0.16 m : cadrée dans les deux tiers gauche/centre (Viewport X ∈ [0.06, 0.63]),
        // dégageant plus de 15 cm avec la carte d'action HUD à droite (X ∈ [0.68, 0.98])
        // Y = 0.954 m : repose à plat strictement au-dessus du plateau d'établi (Y = 0.950 m) sans aucune intersection
        // Z = 1.38 m : distance naturelle de travail devant l'opérateur
        sourceSequence.transform.position = new Vector3(-0.16f, 0.954f, 1.38f);

        // Orientation paysage horizontal strictement à plat sur la table (Pitch = 90° exact) :
        // Le pitch à 90° garantit que le plan reste parfaitement horizontal et ne s'enfonce jamais
        // dans le cube de la table, éliminant ainsi toute coupure / discontinuité visuelle.
        // - 90° sur X : rigoureusement parallèle au plateau d'établi
        // - -90° sur Z :
        //   * Porte-piles rouge en haut à gauche
        //   * Boîtier/interrupteur blanc en bas à gauche (avec ON/OFF à l'endroit)
        //   * Carter transparent avec ampoule sur la moitié droite
        sourceSequence.transform.rotation = Quaternion.Euler(90f, 0f, -90f);

        // 3. Pose de la caméra opérateur (Meta Quest) :
        virtualSourceCamera.transform.position = new Vector3(0f, 1.38f, 0.95f);
        virtualSourceCamera.transform.rotation = Quaternion.Euler(48f, 0f, 0f);

        // Mémoriser le cadrage initial pour le recentrage (touche R) et le Mouse Look
        initialCameraLocalPos = virtualSourceCamera.transform.localPosition;
        initialCameraLocalRot = virtualSourceCamera.transform.localRotation;
        currentPitch = 0f;
        currentYaw = 0f;

        // 4. Ancrage du chevalet QR Code 3D sur l'établi à gauche
        EnsureVirtualQRCodeTag();

        Debug.Log($"[VirtualMaquette] Pose table paysage : {tableWidth:F2}x{tableDepth:F2}m, pos {sourceSequence.transform.position}, regard Quest 48°");
    }

    private void UpdateVirtualCameraSettings()
    {
        if (virtualCaptureCamera == null || virtualSourceCamera == null) return;
        virtualSourceCamera.targetTexture = null;
        virtualCaptureCamera.CopyFrom(virtualSourceCamera);
        virtualCaptureCamera.transform.SetPositionAndRotation(
            virtualSourceCamera.transform.position, virtualSourceCamera.transform.rotation);
        virtualCaptureCamera.targetTexture = virtualRenderTexture;
        virtualCaptureCamera.nearClipPlane = .01f;
        virtualCaptureCamera.aspect = 1280f / 720f;
        virtualCaptureCamera.depth = virtualSourceCamera.depth - 1;
        int uiLayer = LayerMask.NameToLayer("UI");
        if (uiLayer >= 0) virtualCaptureCamera.cullingMask &= ~(1 << uiLayer);
        virtualCaptureCamera.enabled = true;
    }

    private void BindVirtualPreview(RawImage target)
    {
        if (target == null) return;
        target.gameObject.SetActive(true);
        target.enabled = true;
        target.texture = virtualRenderTexture;
        target.color = Color.white;
        target.raycastTarget = target == maintenancePreviewImage;
        if (target == maintenancePreviewImage)
        {
            if (maintenanceArrowLine != null)
            {
                var graphic = maintenanceArrowLine.GetComponent<Graphic>();
                if (graphic != null) graphic.raycastTarget = false;
            }
            if (maintenanceArrowHead != null) maintenanceArrowHead.raycastTarget = false;
        }
        SetCameraMessage(target, "");
    }

    private void QueueVirtualFrameReady()
    {
        virtualCameraReady = false;
        if (pendingFrameReady != null) StopCoroutine(pendingFrameReady);
        pendingFrameReady = StartCoroutine(WaitForVirtualFrame());
    }
    private IEnumerator WaitForVirtualFrame()
    {
        yield return new WaitForEndOfFrame();
        virtualCameraReady = (sourceSequence != null && sourceSequence.ActiveTexture != null)
            || (virtualCaptureCamera != null && virtualCaptureCamera.enabled
            && virtualRenderTexture != null && virtualRenderTexture.IsCreated());
        pendingFrameReady = null;
        if (virtualCameraReady && !firstVirtualFrameVerified)
        {
            Texture2D firstFrame = null;
            try
            {
                firstFrame = ReadVirtualCameraFrame();
                if (firstFrame == null) throw new InvalidOperationException("Premier rendu indisponible.");
                int bytes = firstFrame.EncodeToPNG().Length;
                firstVirtualFrameVerified = true;
                Debug.Log("[Virtual Camera] First rendered frame " + firstFrame.width + "x" + firstFrame.height + " / " + bytes + " PNG bytes.");
            }
            catch (Exception error)
            {
                virtualCameraReady = false;
                ShowStatus("Lecture du rendu virtuel impossible : " + error.Message, PremiumRed);
            }
            finally { if (firstFrame != null) Destroy(firstFrame); }
        }
        if (virtualCameraReady && pendingCapture == null && !lotoManager.IsValidationPending)
        {
            lotoManager.UpdateHologramGuide();
            QueueStepGuidance();
        }
    }

    private void OnVirtualTextureChanged(Texture2D texture)
    {
        if (fixedImageInput) return;
        if (pendingCapture != null) { StopCoroutine(pendingCapture); pendingCapture = null; }
        bool human = lotoManager.GetActiveAction()?.VerificationMethod == "human_confirmation";
        if (human) ClearFrameTargets();
        else lotoManager.InvalidateValidation();
        FrameIdentity = Guid.NewGuid().ToString(); FrameSha256 = "";
        if (lotoManager.GetActiveAction() != null && !human)
            ShowStatus("", PremiumGray);

        if (sourceSequence != null)
        {
            float aspect = 1614f / 975f;
            float tableWidth = 0.58f;
            float tableDepth = tableWidth / aspect;
            sourceSequence.transform.localScale = new Vector3(tableDepth, tableWidth, 1f);
        }

        QueueVirtualFrameReady();
    }

    public static Texture2D CreateReadableTexture(Texture source, TextureFormat format = TextureFormat.RGBA32)
    {
        if (source == null) return null;
        int w = source.width;
        int h = source.height;
        RenderTexture tempRT = RenderTexture.GetTemporary(w, h, 0, RenderTextureFormat.ARGB32);
        RenderTexture prevRT = RenderTexture.active;
        try
        {
            Graphics.Blit(source, tempRT);
            RenderTexture.active = tempRT;
            Texture2D readableTex = new Texture2D(w, h, format, false);
            readableTex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            readableTex.Apply();
            return readableTex;
        }
        finally
        {
            RenderTexture.active = prevRT;
            RenderTexture.ReleaseTemporary(tempRT);
        }
    }

    public Texture2D ReadVirtualCameraFrame()
    {
        if (sourceSequence != null && sourceSequence.ActiveTexture != null)
        {
            return CreateReadableTexture(sourceSequence.ActiveTexture, TextureFormat.RGB24);
        }

        if (!virtualCameraReady || virtualRenderTexture == null || !virtualRenderTexture.IsCreated()) return null;
        RenderTexture previous = RenderTexture.active;
        Texture2D frame = null;
        try
        {
            RenderTexture.active = virtualRenderTexture;
            frame = new Texture2D(virtualRenderTexture.width, virtualRenderTexture.height, TextureFormat.RGB24, false);
            frame.ReadPixels(new Rect(0, 0, virtualRenderTexture.width, virtualRenderTexture.height), 0, 0);
            frame.Apply();
            return frame;
        }
        catch { if (frame != null) Destroy(frame); throw; }
        finally { RenderTexture.active = previous; }
    }

    public void IdentifyVirtualMaquette(string machineId)
    {
        Transform origin = lotoManager.EnsureVirtualMaquetteVisible();
        lotoManager.SetTrackedOrigin(origin, origin != null);
        fixedImageInput = false;
        StartVirtualPreview(qrCameraPreviewImage);
        SelectMachineById(machineId);
        if (ImageTestMode && lotoManager.currentProcedure != null && lotoManager.currentProcedure.machine_id == machineId)
        {
            ShowStepScreen(); UpdateUIForCurrentStep();
            ShowStatus("SIMULATION 3D : " + machineId + " identifie, origine virtuelle ancree.", PremiumGreen);
        }
        else
        {
            // Identification is not consent to create an intervention or replace a draft.
            showTestBrowser = true;
            ShowStatus("Equipement identifie et ancre. Chargez la procedure.", PremiumBlue);
        }
    }

    private void SetCameraMessage(RawImage targetImage, string message)
    {
        if (targetImage == null) return;
        Transform existing = targetImage.transform.Find("Camera Status");
        Text label;
        if (existing == null)
        {
            GameObject labelObject = new GameObject("Camera Status", typeof(RectTransform), typeof(Text));
            labelObject.transform.SetParent(targetImage.transform, false);
            RectTransform rect = labelObject.GetComponent<RectTransform>();
            rect.anchorMin = Vector2.zero;
            rect.anchorMax = Vector2.one;
            rect.offsetMin = new Vector2(12f, 12f);
            rect.offsetMax = new Vector2(-12f, -12f);
            label = labelObject.GetComponent<Text>();
           label.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            label.alignment = TextAnchor.MiddleCenter;
            label.fontSize = 20;
            label.color = Color.white;
            label.raycastTarget = false;
            Outline outline = labelObject.AddComponent<Outline>();
            outline.effectColor = Color.black;
            outline.effectDistance = new Vector2(1f, -1f);
        }
        else label = existing.GetComponent<Text>();
        label.text = message;
        label.enabled = !string.IsNullOrEmpty(message);
    }

    private void ShowPanel(GameObject panelToShow)
    {
        if (panelToShow != stepPanel) ClearFrameTargets();
        welcomePanel.SetActive(panelToShow == welcomePanel);
        manualSelectionPanel.SetActive(panelToShow == manualSelectionPanel);
        qrScanPanel.SetActive(panelToShow == qrScanPanel);
        stepPanel.SetActive(panelToShow == stepPanel);
        maintenancePanel.SetActive(panelToShow == maintenancePanel);
        signaturePanel.SetActive(panelToShow == signaturePanel);
        reportPanel.SetActive(panelToShow == reportPanel);
    }

    private void OnChooseQRScanPressed()
    {
        ShowPanel(qrScanPanel);
        StartVirtualPreview(qrCameraPreviewImage);
        ShowStatus("Scanner actif. Cadrez le QR code...", PremiumBlue);
        
        var scanner = GetComponent<LotoQRScanner>();
        if (scanner != null)
        {
            scanner.IdentifyVirtualMaquette();
        }
        else IdentifyVirtualMaquette("SL-POC-01");
    }

    private void OnChooseManualPressed()
    {
        ShowPanel(manualSelectionPanel);
        ClearFrameTargets();
        ShowStatus("Sélectionnez une machine et cliquez sur Démarrer.", PremiumGray);
    }

    private void OnBackToWelcomePressed()
    {
        if (gazeRecenterCoroutine != null) { StopCoroutine(gazeRecenterCoroutine); gazeRecenterCoroutine = null; }
        currentPitch = 0f;
        currentYaw = 0f;
        if (virtualSourceCamera != null) virtualSourceCamera.transform.localRotation = initialCameraLocalRot;
        qrScanCompleted = false;
        qrGazeDwellTimer = 0f;
        ShowPanel(welcomePanel);
        ClearFrameTargets();
        ShowStatus("Sélectionnez le mode d'initialisation.", PremiumGray);
    }

    private void OnStartPressed()
    {
        if (ImageTestMode) { ShowStatus("TEST actif : redémarrez pour ouvrir une intervention réelle.", PremiumYellow); return; }
        if (availableProcedures == null || availableProcedures.Length == 0)
        {
            ShowStatus("Erreur : Aucune machine disponible.", PremiumRed);
            return;
        }

        int selectedIndex = machineIdDropdown.value;
        string machineId = availableProcedures[selectedIndex].machine_id;

        ShowStatus("Connexion au serveur...", PremiumYellow);
        startButton.interactable = false;

        lotoClient.StartIntervention(machineId,
            () => {
                startButton.interactable = true;
                qrScanCompleted = true;
                if (qrReticleObject != null) qrReticleObject.SetActive(false);
                if (gazeRecenterCoroutine != null) StopCoroutine(gazeRecenterCoroutine);
                gazeRecenterCoroutine = StartCoroutine(SmoothRecenterGaze(0.5f));
            },
            (error) => {
                startButton.interactable = true;
                ShowStatus($"Échec connexion : {error}", PremiumRed);
            }
        );
    }

    private void OnValidatePressed()
    {
        if (lotoManager.IsValidationPending) return;
        if (lotoManager.GetActiveAction()?.VerificationMethod == "human_confirmation")
        { lotoManager.RequestHumanConfirmation(); return; }
        if (pendingCapture != null) return;
        if (fixedImageInput)
        {
            byte[] fixedBytes = GetCapturedImageBytes();
            if (fixedBytes != null) lotoManager.RequestStepValidation(fixedBytes);
            return;
        }
        pendingCapture = StartCoroutine(CaptureRenderedFrame());
    }

    private IEnumerator CaptureRenderedFrame()
    {
        string action = lotoManager.GetActiveAction()?.Id;
        // Remove application guidance before rendering the evidence frame.
        lotoManager.InvalidateValidation();
        SetValidationBusy(true);
        yield return new WaitForEndOfFrame();
        pendingCapture = null;
        SetValidationBusy(false);
        if (lotoManager.GetActiveAction()?.Id != action) yield break;
        virtualCameraReady = virtualRenderTexture != null && virtualRenderTexture.IsCreated();
        byte[] bytes = GetCapturedImageBytes();
        if (bytes != null) lotoManager.RequestStepValidation(bytes);
    }

    private void OnOverridePressed()
    {
        string reason = overrideReasonInput.text.Trim();
        if (string.IsNullOrEmpty(reason))
        {
            ShowStatus("Veuillez indiquer un motif de dérogation !", PremiumRed);
            return;
        }

        byte[] imageBytes = GetCapturedImageBytes();
        if (imageBytes == null) return;
        pendingOverrideReason = reason;
        pendingOverrideImage = imageBytes;
        overrideConfirmationText.text = $"Motif :\n{reason}\n\nLa photo de preuve sera jointe à cette dérogation.";
        overrideConfirmationPanel.SetActive(true);
        overrideConfirmationPanel.transform.SetAsLastSibling();
    }

    private void CancelOverrideConfirmation()
    {
        overrideConfirmationPanel.SetActive(false);
        pendingOverrideReason = null;
        pendingOverrideImage = null;
    }

    private void ConfirmOverride()
    {
        if (string.IsNullOrWhiteSpace(pendingOverrideReason) || pendingOverrideImage == null)
        {
            overrideConfirmationPanel.SetActive(false);
            ShowStatus("La dérogation ne peut pas être envoyée : motif ou photo manquant.", PremiumRed);
            return;
        }

        overrideConfirmationPanel.SetActive(false);
        ShowStatus("Envoi de la dérogation et de sa preuve…", PremiumYellow);
        lotoManager.RequestManualOverride(pendingOverrideReason, pendingOverrideImage,
            () =>
            {
                overrideReasonInput.text = "";
                pendingOverrideReason = null;
                pendingOverrideImage = null;
            },
            (error) => ShowStatus($"Échec de la dérogation : {error}", PremiumRed));
    }

    private void OnStartRestorationPressed()
    {
        lotoManager.StartRestorationPhase();
    }

    private void OnSubmitSignaturePressed()
    {
        if (signaturePad == null || !signaturePad.HasInk)
        {
            ShowStatus("Dessinez votre signature avant de clôturer l'intervention.", PremiumRed);
            return;
        }

        byte[] sigBytes = GetSignatureImageBytes();
        if (sigBytes == null || sigBytes.Length == 0)
        {
            ShowStatus("La signature n'a pas pu être encodée. Elle est conservée à l'écran.", PremiumRed);
            return;
        }

        SetSignatureSubmitting(true);
        lotoManager.CloseIntervention(sigBytes);
    }

    public void SetSignatureSubmitting(bool submitting)
    {
        if (submitSignatureButton != null) submitSignatureButton.interactable = !submitting;
        if (clearSignatureButton != null) clearSignatureButton.interactable = !submitting;
    }

    private void OnOpenReportPressed()
    {
        if (!string.IsNullOrEmpty(savedReportUrl))
        {
            Application.OpenURL(savedReportUrl);
        }
    }

    private void OnRestartPressed()
    {
        if (gazeRecenterCoroutine != null) { StopCoroutine(gazeRecenterCoroutine); gazeRecenterCoroutine = null; }
        currentPitch = 0f;
        currentYaw = 0f;
        if (virtualSourceCamera != null) virtualSourceCamera.transform.localRotation = initialCameraLocalRot;
        qrScanCompleted = false;
        qrGazeDwellTimer = 0f;
        lotoClient.activeInterventionId = "";
        lotoClient.activeMachineId = "";
        ShowPanel(welcomePanel);
        ClearFrameTargets();
        ShowStatus("Chargement des machines...", PremiumGray);
        lotoClient.GetProceduresList(OnProceduresLoaded, OnProceduresLoadFailed);
        
        var scanner = GetComponent<LotoQRScanner>();
        if (scanner != null)
        {
            scanner.ResumeScanning();
        }
    }

    public bool IsOnQRScanScreen()
    {
        return qrScanPanel != null && qrScanPanel.activeSelf;
    }

    public bool SelectMachineById(string machineId)
    {
        if (availableProcedures == null || availableProcedures.Length == 0) return false;
        
        for (int i = 0; i < availableProcedures.Length; i++)
        {
            if (availableProcedures[i].machine_id.Equals(machineId, StringComparison.OrdinalIgnoreCase))
            {
                machineIdDropdown.value = i;
                return true;
            }
        }
        return false;
    }

    public void TriggerStart()
    {
        OnStartPressed();
    }

    public void UpdateUIForCurrentStep()
    {
        ClearFrameTargets();
        ResumeLivePreview();
        var action = lotoManager.GetActiveAction();
        var stage = lotoManager.GetActiveStage();

        if (action == null || stage == null) return;
        bool human = action.VerificationMethod == "human_confirmation";
        validateButton.GetComponentInChildren<Text>().text = human ? "Je confirme avoir réalisé l’opération" : "Capturer et vérifier";
        overrideReasonInput.gameObject.SetActive(!human);
        overrideButton.gameObject.SetActive(!human);
        if (human)
        {
            ClearFrameTargets();
            SetCameraMessage(cameraPreviewImage, "");
        }
        else if (!fixedImageInput) StartVirtualPreview(cameraPreviewImage);

        phaseTitleText.text = lotoManager.PhaseProgress();
        stageTitleText.text = stage.title;
        stepDescText.text = action.InstructionText;
        string criteria = action.VerificationCriteria != null && action.VerificationCriteria.Length > 0
            ? string.Join("; ", action.VerificationCriteria)
            : action.ExpectedText;
        var context = new System.Text.StringBuilder();
        var components = lotoManager.GetActiveComponents();
        var componentIds = new HashSet<string>();
        foreach (var c in components)
        {
            foreach (var id in new[] { c.component_id, c.internal_id, c.tag, c.source_tag, c.unity_class_id })
                if (!string.IsNullOrEmpty(id)) componentIds.Add(id);
            context.AppendLine(c.tag + " · " + c.component_name);
            foreach (var signature in c.physical_signatures ?? new SmartLOTOClient.PhysicalSignatureData[0])
                context.AppendLine("Repère " + SmartLOTOClient.FirstText(signature.signature_type, signature.feature_type) + " : " + signature.description + " " + signature.details);
            foreach (var state in c.state_rules ?? new SmartLOTOClient.StateRuleData[0])
                context.AppendLine("État " + state.state_name + " : " + state.physical_rule);
        }
        context.AppendLine("À vérifier (" + action.VerificationMethod + ") : " + criteria);
        if (!string.IsNullOrEmpty(action.expected_result)) context.AppendLine("Résultat attendu : " + action.expected_result);
        foreach (var q in lotoManager.currentProcedure.clarifications_required ?? new SmartLOTOClient.ResolvedClarificationData[0])
        {
            string status = (q.status ?? "").ToLowerInvariant();
            if ((status != "resolved" && status != "approved" && status != "answered") || string.IsNullOrWhiteSpace(q.answer)) continue;
            bool relevant = Array.IndexOf(q.affected_step_ids ?? new string[0], action.Id) >= 0;
            if (q.affected_step_ids == null || q.affected_step_ids.Length == 0)
                foreach (var id in q.related_component_ids ?? new string[0]) relevant |= componentIds.Contains(id);
            if (relevant) context.AppendLine("Décision HSE : " + q.question + " — " + q.answer + " " + q.rationale);
        }
        visionPromptText.text = context.ToString();
        SetValidationBusy(false);

        ShowStatus(human ? "Confirmation humaine normale — aucune caméra ni dérogation requise." : "Prêt pour la capture", PremiumBlue);
        QueueStepGuidance();
    }

    public void ShowMaintenanceScreen()
    {
        ShowPanel(maintenancePanel);
        var procedure = lotoManager.currentProcedure;
        maintenanceTaskTitleText.text = SmartLOTOClient.FirstText(procedure.maintenance_objective, procedure.objective, "Intervention prévue par la procédure");
        maintenanceExpectedStateText.text = "État final attendu : " + procedure.expected_final_state;
        calibrationComponents = procedure.components ?? new SmartLOTOClient.ComponentData[0];
        calibrationComponentIndex = 0;
        StartVirtualPreview(maintenancePreviewImage);
        LoadMaintenanceCalibration();
        ShowStatus("Consignation validée. Calibrez la zone de maintenance sur la vue caméra.", PremiumGreen);
    }

    public void ShowClosureScreen()
    {
        ClearFrameTargets();
        ShowPanel(signaturePanel);
        if (signaturePad != null) signaturePad.Clear();
        string machine = lotoClient != null ? lotoClient.activeMachineId : "machine";
        closureSummaryText.text = $"Machine : {machine}\nToutes les étapes de la procédure sont terminées.";
        SetSignatureSubmitting(false);
        ShowStatus("Procédure terminée. Dessinez votre signature pour clôturer.", PremiumBlue);
    }

    public void ShowFinalReportScreen(string pdfReportUrl)
    {
        savedReportUrl = pdfReportUrl;
        reportUrlText.text = $"Lien du rapport PDF :\n{pdfReportUrl}";
        ShowPanel(reportPanel);
    }

    public void ShowStatus(string message, Color color)
    {
        if (statusText != null)
        {
            statusText.text = message;
            statusText.color = Color.Lerp(color, Color.white, .4f);
        }
        if (statusBackgroundImage != null)
        {
            Color c = Color.Lerp(new Color32(11, 19, 30, 255), color, .12f);
            c.a = string.IsNullOrEmpty(message) ? 0f : .72f;
            statusBackgroundImage.color = c;
            var edge = statusBackgroundImage.GetComponent<Outline>();
            if (edge != null)
                edge.effectColor = new Color(color.r, color.g, color.b, string.IsNullOrEmpty(message) ? 0f : .65f);
        }
    }

    public void SetValidationBusy(bool busy)
    {
        validateButton.interactable = !busy;
        bool human = lotoManager.GetActiveAction()?.VerificationMethod == "human_confirmation";
        var label = validateButton.GetComponentInChildren<Text>();
        if (label != null)
        {
            label.color = new Color32(224, 242, 254, 255);
            label.text = busy ? (human ? "Confirmation en cours..." : "Analyse HSE en cours...")
                : human ? "Je confirme avoir réalisé l’opération" : "Capturer et vérifier";
        }
        overrideButton.interactable = !busy && !ImageTestMode && lotoManager.GetActiveAction()?.VerificationMethod != "human_confirmation";
        overrideConfirmButton.interactable = !busy;
    }

    public void ShowStepScreen()
    {
        if (stepPanel.activeSelf) return;
        ShowPanel(stepPanel);
        if (lotoManager.GetActiveAction()?.VerificationMethod != "human_confirmation") StartVirtualPreview(cameraPreviewImage);
    }

    private string CalibrationComponentId => calibrationComponents.Length == 0 ? string.Empty
        : SmartLOTOClient.FirstText(calibrationComponents[calibrationComponentIndex].component_id, calibrationComponents[calibrationComponentIndex].tag);

    private byte[] GetCapturedImageBytes()
    {
        if (fixedImageInput) return fixedFrameBytes;
        Texture2D frame = null;
        try
        {
            frame = ReadVirtualCameraFrame();
            if (frame == null) { ShowStatus("Camera virtuelle : attendez le rendu de la premiere image.", PremiumYellow); return null; }
            SetFixedFrame(frame, true);
            Debug.Log("[Virtual Camera] Captured rendered frame " + frame.width + "x" + frame.height + " / " + fixedFrameBytes.Length
                + " PNG bytes / frame " + FrameIdentity + " / SHA256 " + FrameSha256);
            return fixedFrameBytes;
        }
        catch (Exception error)
        {
            ShowStatus("Capture virtuelle impossible : " + error.Message, PremiumRed);
            return null;
        }
    }

    private byte[] GetSignatureImageBytes()
    {
        return signaturePad != null && signaturePad.HasInk ? signaturePad.EncodeToPng() : null;
    }

    private string MaintenanceCalibrationKey(string axis, string componentId = null)
    {
        string machineId = lotoClient != null && !string.IsNullOrEmpty(lotoClient.activeMachineId)
            ? lotoClient.activeMachineId
            : "default";
        return "SmartLOTO.MaintenanceGuide." + Uri.EscapeDataString(machineId) + "."
            + Uri.EscapeDataString(componentId ?? CalibrationComponentId) + "." + axis;
    }

    public bool TryGetVirtualComponentPoint(string componentId, out Vector3 worldPoint)
    {
        worldPoint = Vector3.zero;
        if (sourceSequence == null || string.IsNullOrEmpty(componentId)) return false;
        string x = MaintenanceCalibrationKey("model.x", componentId);
        string y = MaintenanceCalibrationKey("model.y", componentId);
        string z = MaintenanceCalibrationKey("model.z", componentId);
        if (!PlayerPrefs.HasKey(x) || !PlayerPrefs.HasKey(y) || !PlayerPrefs.HasKey(z))
        {
            // Authored scene targets can supply guidance before the first calibration.
            foreach (var target in sourceSequence.GetComponentsInChildren<Transform>(true))
                if (target != sourceSequence.transform && target.name == componentId)
                { worldPoint = target.position; return true; }
            return false;
        }
        worldPoint = sourceSequence.transform.TransformPoint(new Vector3(
            PlayerPrefs.GetFloat(x), PlayerPrefs.GetFloat(y), PlayerPrefs.GetFloat(z)));
        return true;
    }

    private void LoadMaintenanceCalibration()
    {
        maintenanceComponentButton.interactable = calibrationComponents.Length > 1;
        maintenanceComponentButton.GetComponentInChildren<Text>().text = calibrationComponents.Length == 0
            ? "Aucun composant à calibrer" : calibrationComponents[calibrationComponentIndex].tag + " · "
                + calibrationComponents[calibrationComponentIndex].component_name + " (suivant)";
        string xKey = MaintenanceCalibrationKey("x");
        string yKey = MaintenanceCalibrationKey("y");
        maintenanceTargetCalibrated = PlayerPrefs.HasKey(xKey) && PlayerPrefs.HasKey(yKey);
        if (maintenanceTargetCalibrated)
        {
            maintenanceTargetX = PlayerPrefs.GetFloat(xKey);
            maintenanceTargetY = PlayerPrefs.GetFloat(yKey);
        }
        UpdateMaintenanceGuideVisuals();
    }

    private void CalibrateMaintenanceTargetFromPointer(PointerEventData pointer)
    {
        if (maintenancePreviewImage != null && maintenancePreviewImage.texture is RenderTexture
            && (!IsVirtualCameraSource || sourceSequence == null))
        {
            ShowStatus("Un repère écran ne suit pas la maquette. Utilisez le mode image TEST ou un suivi AR validé.", PremiumYellow);
            return;
        }
        if (maintenancePreviewImage == null || !maintenancePanel.activeSelf || !virtualCameraReady || string.IsNullOrEmpty(CalibrationComponentId))
            return;

        if (!RectTransformUtility.ScreenPointToLocalPointInRectangle(
                maintenancePreviewImage.rectTransform, pointer.position, pointer.pressEventCamera, out Vector2 localPoint))
            return;

        Rect rect = maintenancePreviewImage.rectTransform.rect;
        if (rect.width <= 0 || rect.height <= 0 || !rect.Contains(localPoint)) return;
        maintenanceTargetX = Mathf.Clamp01((localPoint.x - rect.xMin) / rect.width);
        maintenanceTargetY = Mathf.Clamp01((localPoint.y - rect.yMin) / rect.height);
        if (maintenancePreviewImage.texture is RenderTexture)
        {
            Rect uv = maintenancePreviewImage.uvRect;
            Ray ray = virtualCaptureCamera.ViewportPointToRay(new Vector3(
                uv.x + maintenanceTargetX * uv.width, uv.y + maintenanceTargetY * uv.height, 0f));
            Transform model = sourceSequence.transform;
            Plane plane = new Plane(model.forward, model.position);
            if (!plane.Raycast(ray, out float distance)) return;
            Vector3 point = model.InverseTransformPoint(ray.GetPoint(distance));
            if (Mathf.Abs(point.x) > .5f || Mathf.Abs(point.y) > .5f)
            {
                ShowStatus("Cliquez sur la maquette pour placer le repère.", PremiumYellow);
                return;
            }
            PlayerPrefs.SetFloat(MaintenanceCalibrationKey("model.x"), point.x);
            PlayerPrefs.SetFloat(MaintenanceCalibrationKey("model.y"), point.y);
            PlayerPrefs.SetFloat(MaintenanceCalibrationKey("model.z"), point.z);
        }
        maintenanceTargetCalibrated = true;
        PlayerPrefs.SetFloat(MaintenanceCalibrationKey("x"), maintenanceTargetX);
        PlayerPrefs.SetFloat(MaintenanceCalibrationKey("y"), maintenanceTargetY);
        PlayerPrefs.Save();
        UpdateMaintenanceGuideVisuals();
        ShowStatus("Zone de maintenance calibrée pour cette machine.", PremiumGreen);
    }

    private void UpdateMaintenanceGuideVisuals()
    {
        if (maintenanceArrowLine == null || maintenanceArrowHead == null || maintenancePreviewImage == null)
            return;

        bool live = maintenancePreviewImage.texture is RenderTexture;
        bool liveUntracked = live && (!IsVirtualCameraSource || sourceSequence == null);
        bool targetVisible = true;
        if (live && !liveUntracked)
        {
            maintenanceTargetCalibrated = TryGetVirtualComponentPoint(CalibrationComponentId, out Vector3 worldPoint);
            if (maintenanceTargetCalibrated)
            {
                Vector3 viewport = virtualCaptureCamera.WorldToViewportPoint(worldPoint);
                Rect uv = maintenancePreviewImage.uvRect;
                targetVisible = viewport.z > 0f && uv.width != 0f && uv.height != 0f;
                if (targetVisible)
                {
                    maintenanceTargetX = (viewport.x - uv.x) / uv.width;
                    maintenanceTargetY = (viewport.y - uv.y) / uv.height;
                    targetVisible = maintenanceTargetX >= 0f && maintenanceTargetX <= 1f
                        && maintenanceTargetY >= 0f && maintenanceTargetY <= 1f;
                }
            }
        }
        bool showGuide = virtualCameraReady && maintenanceTargetCalibrated && !liveUntracked && targetVisible;
        maintenanceArrowLine.gameObject.SetActive(showGuide);
        maintenanceArrowHead.gameObject.SetActive(showGuide);
        if (liveUntracked)
        {
            maintenanceCalibrationText.text = "Flux caméra : aucun suivi AR validé. Calibration 2D disponible sur image en mode TEST.";
            return;
        }
        if (!virtualCameraReady)
        {
            maintenanceCalibrationText.text = "Caméra indisponible : le repère ne peut pas être calibré.";
            return;
        }
        if (!maintenanceTargetCalibrated)
        {
            maintenanceCalibrationText.text = "Sélectionnez le composant, puis cliquez sur sa position dans l'image : " + CalibrationComponentId;
            return;
        }

        maintenanceCalibrationText.text = "Repère calibré. Vous pouvez recliquer pour le déplacer.";
        RectTransform previewRect = maintenancePreviewImage.rectTransform;
        Rect rect = previewRect.rect;
        Vector2 source = new Vector2(0f, rect.yMin + rect.height * .08f);
        Vector2 target = new Vector2((maintenanceTargetX - .5f) * rect.width,
            (maintenanceTargetY - .5f) * rect.height);
        Vector2 delta = target - source;
        float angle = Mathf.Atan2(delta.y, delta.x) * Mathf.Rad2Deg;

        maintenanceArrowLine.anchorMin = maintenanceArrowLine.anchorMax = new Vector2(.5f, .08f);
        maintenanceArrowLine.pivot = new Vector2(0f, .5f);
        maintenanceArrowLine.anchoredPosition = Vector2.zero;
        maintenanceArrowLine.sizeDelta = new Vector2(delta.magnitude, Mathf.Max(5f, rect.height * .008f));
        maintenanceArrowLine.localEulerAngles = new Vector3(0f, 0f, angle);

        RectTransform head = maintenanceArrowHead.rectTransform;
        Vector2 targetAnchor = new Vector2(maintenanceTargetX, maintenanceTargetY);
        head.anchorMin = head.anchorMax = targetAnchor;
        head.pivot = new Vector2(.5f, .5f);
        head.anchoredPosition = Vector2.zero;
        head.sizeDelta = new Vector2(42f, 42f);
        head.localEulerAngles = new Vector3(0f, 0f, angle);
    }

    private void Update()
    {
        HandleOperatorLookInput();
        UpdateVirtualCameraSettings();
        UpdateARGazeQRScan();
        if (maintenancePanel != null && maintenancePanel.activeSelf) UpdateMaintenanceGuideVisuals();
        if (qrScanPanel != null && qrScanPanel.activeSelf && scanLaserLine != null)
        {
            Vector3 pos = scanLaserLine.localPosition;
            if (laserMovingDown)
            {
                pos.y -= laserSpeed * Time.deltaTime;
                if (pos.y <= laserMinY)
                {
                    pos.y = laserMinY;
                    laserMovingDown = false;
                }
            }
            else
            {
                pos.y += laserSpeed * Time.deltaTime;
                if (pos.y >= laserMaxY)
                {
                    pos.y = laserMaxY;
                    laserMovingDown = true;
                }
            }
            scanLaserLine.localPosition = pos;
        }
    }

    private void HandleOperatorLookInput()
    {
        if (virtualSourceCamera == null) return;
        var keyboard = Keyboard.current;
        var mouse = Mouse.current;

        // Reset view orientation with R key
        if (keyboard != null && keyboard.rKey.wasPressedThisFrame)
        {
            if (!IsTextInputFocused && !IsModifierPressed(keyboard))
            {
                if (gazeRecenterCoroutine != null) { StopCoroutine(gazeRecenterCoroutine); gazeRecenterCoroutine = null; }
                currentPitch = 0f;
                currentYaw = 0f;
                virtualSourceCamera.transform.localRotation = initialCameraLocalRot;
            }
        }

        // Mouse Look with right button held
        if (mouse != null)
        {
            if (mouse.rightButton.wasPressedThisFrame && !IsTextInputFocused)
            {
                if (gazeRecenterCoroutine != null) { StopCoroutine(gazeRecenterCoroutine); gazeRecenterCoroutine = null; }
                Cursor.lockState = CursorLockMode.Locked;
                Cursor.visible = false;
            }
            else if (mouse.rightButton.isPressed && !IsTextInputFocused)
            {
                Vector2 delta = mouse.delta.ReadValue();
                if (delta.sqrMagnitude > 0.0001f)
                {
                    float sensitivity = 0.12f;
                    currentYaw += delta.x * sensitivity;
                    currentPitch -= delta.y * sensitivity;

                    currentPitch = Mathf.Clamp(currentPitch, -35f, 35f);
                    currentYaw = Mathf.Clamp(currentYaw, -45f, 45f);

                    virtualSourceCamera.transform.localRotation = initialCameraLocalRot * Quaternion.Euler(currentPitch, currentYaw, 0f);
                }
            }
            else if (mouse.rightButton.wasReleasedThisFrame)
            {
                Cursor.lockState = CursorLockMode.None;
                Cursor.visible = true;
            }
            else if (!mouse.rightButton.isPressed && Cursor.lockState != CursorLockMode.None)
            {
                Cursor.lockState = CursorLockMode.None;
                Cursor.visible = true;
            }
        }
    }

    private bool IsModifierPressed(Keyboard keyboard)
    {
        if (keyboard == null) return false;
        return keyboard.ctrlKey.isPressed
            || keyboard.altKey.isPressed
            || keyboard.leftMetaKey.isPressed
            || keyboard.rightMetaKey.isPressed;
    }

    private void OnDisable()
    {
        CancelStepGuidance();
        Cursor.lockState = CursorLockMode.None;
        Cursor.visible = true;
    }

    private void OnApplicationFocus(bool hasFocus)
    {
        if (!hasFocus)
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }
    }

    private void EnsureWorkbenchSurface()
    {
        if (workbenchObject != null) return;

        // Plateau principal de l'établi : 1.80m large (X) x 0.04m épaisseur (Y) x 1.00m profondeur (Z)
        workbenchObject = GameObject.CreatePrimitive(PrimitiveType.Cube);
        workbenchObject.name = "WorkbenchSurface";
        // Centre de l'établi : X = -0.18m (sous maquette + QR), Y = 0.93m (surface supérieure à 0.95m), Z = 1.45m
        workbenchObject.transform.position = new Vector3(-0.18f, 0.93f, 1.45f);
        workbenchObject.transform.localScale = new Vector3(1.80f, 0.04f, 1.00f);

        // Matériau gris industriel clair/moyen (Color(0.22f, 0.25f, 0.29f))
        var renderer = workbenchObject.GetComponent<MeshRenderer>();
        if (renderer != null)
        {
            Shader shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) shader = Shader.Find("Standard");
            if (shader == null) shader = Shader.Find("Diffuse");
            Material tableMat = new Material(shader);
            tableMat.color = new Color(0.22f, 0.25f, 0.29f);
            renderer.material = tableMat;
        }

        // Bordure avant subtile pour détacher nettement l'établi du fond sombre
        var edgeObj = GameObject.CreatePrimitive(PrimitiveType.Cube);
        edgeObj.name = "WorkbenchFrontEdge";
        edgeObj.transform.SetParent(workbenchObject.transform, false);
        edgeObj.transform.localPosition = new Vector3(0f, 0.2f, -0.495f);
        edgeObj.transform.localScale = new Vector3(1.002f, 0.6f, 0.015f);
        var edgeRenderer = edgeObj.GetComponent<MeshRenderer>();
        if (edgeRenderer != null)
        {
            Material edgeMat = new Material(renderer != null ? renderer.material.shader : Shader.Find("Diffuse"));
            edgeMat.color = new Color(0.32f, 0.36f, 0.42f);
            edgeRenderer.material = edgeMat;
        }

        var col = workbenchObject.GetComponent<Collider>();
        if (col != null) Destroy(col);
        var edgeCol = edgeObj.GetComponent<Collider>();
        if (edgeCol != null) Destroy(edgeCol);
    }

    private void EnsureVirtualQRCodeTag()
    {
        if (virtualQrEasel != null && virtualQrTag != null) return;

        // 1. Racine du chevalet QR posé sur l'établi à gauche de la maquette (X=-0.72m, Y=0.95m, Z=1.42m)
        // Bien séparé de la maquette (~43 cm du bord gauche)
        if (virtualQrEasel == null)
        {
            virtualQrEasel = new GameObject("VirtualQREasel");
            virtualQrEasel.transform.position = new Vector3(-0.72f, 0.95f, 1.42f);

            // Orientation symétrique vers la caméra opérateur avec Roll = 0 strict (aucun angle tordu en losange)
            Vector3 camPos = virtualSourceCamera != null ? virtualSourceCamera.transform.position : new Vector3(0f, 1.38f, 0.95f);
            Vector3 dirToCam = (camPos - (virtualQrEasel.transform.position + new Vector3(0f, 0.12f, 0f))).normalized;
            virtualQrEasel.transform.rotation = Quaternion.LookRotation(dirToCam, Vector3.up);

            // 2. Socle / base posée sur l'établi (Cube plat gris anthracite)
            GameObject baseFoot = GameObject.CreatePrimitive(PrimitiveType.Cube);
            baseFoot.name = "QREaselBase";
            baseFoot.transform.SetParent(virtualQrEasel.transform, false);
            baseFoot.transform.localPosition = new Vector3(0f, 0.008f, 0f);
            baseFoot.transform.localScale = new Vector3(0.20f, 0.016f, 0.12f);
            var baseRenderer = baseFoot.GetComponent<MeshRenderer>();
            if (baseRenderer != null)
            {
                Shader shader = Shader.Find("Universal Render Pipeline/Lit");
                if (shader == null) shader = Shader.Find("Standard");
                if (shader == null) shader = Shader.Find("Diffuse");
                Material baseMat = new Material(shader);
                baseMat.color = new Color(0.14f, 0.17f, 0.21f);
                baseRenderer.material = baseMat;
            }
            var baseCol = baseFoot.GetComponent<Collider>();
            if (baseCol != null) Destroy(baseCol);

            // 3. Panneau dorsal / chevalet incliné
            GameObject backboard = GameObject.CreatePrimitive(PrimitiveType.Cube);
            backboard.name = "QREaselBackboard";
            backboard.transform.SetParent(virtualQrEasel.transform, false);
            backboard.transform.localPosition = new Vector3(0f, 0.12f, 0f);
            backboard.transform.localScale = new Vector3(0.18f, 0.225f, 0.012f);
            var backRenderer = backboard.GetComponent<MeshRenderer>();
            if (backRenderer != null)
            {
                Shader shader = Shader.Find("Universal Render Pipeline/Lit");
                if (shader == null) shader = Shader.Find("Standard");
                if (shader == null) shader = Shader.Find("Diffuse");
                Material backMat = new Material(shader);
                backMat.color = new Color(0.10f, 0.13f, 0.17f);
                backRenderer.material = backMat;
            }
            var backCol = backboard.GetComponent<Collider>();
            if (backCol != null) Destroy(backCol);

            // 4. Quad QR Code haute netteté sur la face avant du chevalet
            virtualQrTag = GameObject.CreatePrimitive(PrimitiveType.Quad);
            virtualQrTag.name = "VirtualQRCodeTag";
            virtualQrTag.transform.SetParent(backboard.transform, false);
            virtualQrTag.transform.localPosition = new Vector3(0f, 0f, 0.55f);
            virtualQrTag.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);
            virtualQrTag.transform.localScale = new Vector3(0.92f, 0.92f, 1f);

            string qrPath = Path.Combine(Application.streamingAssetsPath, "QRCode_SL-POC-01.png");
            Texture2D qrTex = null;
            if (File.Exists(qrPath))
            {
                byte[] bytes = File.ReadAllBytes(qrPath);
                qrTex = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                qrTex.LoadImage(bytes);
            }

            var qrRenderer = virtualQrTag.GetComponent<MeshRenderer>();
            if (qrRenderer != null)
            {
                Shader shader = Shader.Find("Unlit/Texture");
                if (shader == null) shader = Shader.Find("Standard");
                Material mat = new Material(shader != null ? shader : Shader.Find("Diffuse"));
                if (qrTex != null) mat.mainTexture = qrTex;
                qrRenderer.material = mat;
            }

            var qrCol = virtualQrTag.GetComponent<Collider>();
            if (qrCol != null) Destroy(qrCol);
        }
    }

    private void UpdateARGazeQRScan()
    {
        if (qrScanCompleted)
        {
            if (qrReticleObject != null && qrReticleObject.activeSelf)
                qrReticleObject.SetActive(false);
            return;
        }

        bool isInitialScreen = (welcomePanel != null && welcomePanel.activeSelf) || (qrScanPanel != null && qrScanPanel.activeSelf);
        if (!isInitialScreen)
        {
            if (qrReticleObject != null && qrReticleObject.activeSelf)
                qrReticleObject.SetActive(false);
            return;
        }

        if (virtualQrTag == null)
        {
            EnsureVirtualQRCodeTag();
            if (virtualQrTag == null) return;
        }

        if (qrReticleObject != null && !qrReticleObject.activeSelf)
            qrReticleObject.SetActive(true);

        if (virtualSourceCamera == null) return;

        Vector3 vp = virtualSourceCamera.WorldToViewportPoint(virtualQrTag.transform.position);
        bool isLookingAtQR = vp.z > 0f && Vector2.Distance(new Vector2(vp.x, vp.y), new Vector2(0.5f, 0.5f)) < 0.16f;

        if (isLookingAtQR)
        {
            qrGazeDwellTimer += Time.deltaTime;
            float progress = Mathf.Clamp01(qrGazeDwellTimer / QR_GAZE_DWELL_TARGET);
            if (qrReticleProgressImage != null)
            {
                qrReticleProgressImage.fillAmount = progress;
                qrReticleProgressImage.color = Color.Lerp(PremiumBlue, PremiumTeal, progress);
            }

            if (qrGazeDwellTimer >= QR_GAZE_DWELL_TARGET)
            {
                qrGazeDwellTimer = 0f;
                StartInterventionFromQR("SL-POC-01");
            }
        }
        else
        {
            qrGazeDwellTimer = Mathf.Max(0f, qrGazeDwellTimer - Time.deltaTime * 2f);
            if (qrReticleProgressImage != null)
            {
                qrReticleProgressImage.fillAmount = qrGazeDwellTimer / QR_GAZE_DWELL_TARGET;
                qrReticleProgressImage.color = PremiumBlue;
            }
        }
    }

    private IEnumerator SmoothRecenterGaze(float duration = 0.5f)
    {
        float elapsed = 0f;
        float startYaw = currentYaw;
        float startPitch = currentPitch;

        while (elapsed < duration)
        {
            elapsed += Time.deltaTime;
            float t = Mathf.SmoothStep(0f, 1f, elapsed / duration);
            currentYaw = Mathf.Lerp(startYaw, 0f, t);
            currentPitch = Mathf.Lerp(startPitch, 0f, t);
            if (virtualSourceCamera != null)
            {
                virtualSourceCamera.transform.localRotation = initialCameraLocalRot * Quaternion.Euler(currentPitch, currentYaw, 0f);
            }
            yield return null;
        }

        currentYaw = 0f;
        currentPitch = 0f;
        if (virtualSourceCamera != null)
        {
            virtualSourceCamera.transform.localRotation = initialCameraLocalRot;
        }
        gazeRecenterCoroutine = null;
    }

    public void StartInterventionFromQR(string code)
    {
        if (qrScanCompleted) return;
        code = LotoQRScanner.ExtractProcedureId(code) ?? code;
        SelectMachineById(code);
        lotoManager.EnsureVirtualMaquetteVisible();

        ShowStatus($"QR Code détecté : {code}. Initialisation...", PremiumBlue);
        if (qrReticleObject != null) qrReticleObject.SetActive(false);

        // Recentrage automatique fluide du regard vers le cadrage central de la maquette
        if (gazeRecenterCoroutine != null) StopCoroutine(gazeRecenterCoroutine);
        gazeRecenterCoroutine = StartCoroutine(SmoothRecenterGaze(0.5f));

        if (lotoClient != null)
        {
            lotoClient.StartIntervention(code,
                () =>
                {
                    qrScanCompleted = true;
                    ShowPanel(stepPanel);
                    ShowStatus("Procédure SL-POC-01 chargée par scan QR — Poste prêt pour vérification.", PremiumGreen);
                },
                (error) =>
                {
                    string localContract = Path.Combine(Application.streamingAssetsPath, $"{code}_unity_contract.json");
                    if (File.Exists(localContract))
                    {
                        try
                        {
                            var proc = SmartLOTOClient.ParseProcedure(File.ReadAllText(localContract));
                            lotoManager.InitializeProcedure(proc);
                            qrScanCompleted = true;
                            ShowPanel(stepPanel);
                            ShowStatus("Procédure SL-POC-01 chargée par scan QR — Poste prêt pour vérification.", PremiumGreen);
                            return;
                        }
                        catch {}
                    }
                    ShowStatus($"Échec initialisation {code} : {error}", PremiumRed);
                    if (qrReticleObject != null) qrReticleObject.SetActive(true);
                }
            );
        }
    }

    private void OnDestroy()
    {
        if (fixedFrame != null) Destroy(fixedFrame);
        if (virtualQrEasel != null) Destroy(virtualQrEasel);
        else if (virtualQrTag != null) Destroy(virtualQrTag);
        if (workbenchObject != null) Destroy(workbenchObject);
        if (sourceSequence != null) sourceSequence.TextureChanged -= OnVirtualTextureChanged;
        if (virtualCaptureCamera != null) { virtualCaptureCamera.enabled = false; Destroy(virtualCaptureCamera.gameObject); }
        if (ownsVirtualTarget && virtualRenderTexture != null)
        { virtualRenderTexture.Release(); Destroy(virtualRenderTexture); }
        DisposeRedesignedView();
    }
}
