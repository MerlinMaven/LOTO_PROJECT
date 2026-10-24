using System;
using System.Collections.Generic;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

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

    [Header("Webcam Settings")]
    [SerializeField] private bool useWebcam = true;
    [SerializeField] private string preferredWebcamDeviceName = "";
    [SerializeField] private float webcamStartupTimeoutSeconds = 10f;
    private WebCamTexture webcamTexture;
    private Coroutine webcamStartupCoroutine;
    private bool webcamReady;
    private SignaturePad signaturePad;
    private byte[] pendingOverrideImage;
    private string pendingOverrideReason;
    private float maintenanceTargetX = .5f;
    private float maintenanceTargetY = .5f;
    private bool maintenanceTargetCalibrated;
    private string savedReportUrl;

    private SmartLOTOClient.ProcedureItem[] availableProcedures;

    // Palette de couleurs premium
    public static readonly Color PremiumGray = new Color(0.44f, 0.5f, 0.59f);       // Charcoal/Slate
    public static readonly Color PremiumGreen = new Color(0.18f, 0.77f, 0.45f);      // Emerald Green (Succès)
    public static readonly Color PremiumRed = new Color(0.9f, 0.28f, 0.28f);         // Soft Red (Danger/Erreur)
    public static readonly Color PremiumBlue = new Color(0.12f, 0.43f, 0.86f);       // Royal Blue (Info)
    public static readonly Color PremiumYellow = new Color(0.95f, 0.61f, 0.07f);     // Amber (Attention)


    private void Start()
    {
        // Initial setup - Start on Welcome Panel
        ShowPanel(welcomePanel);
        statusText.text = "Connexion au serveur et chargement des machines...";
        statusBackgroundImage.color = PremiumGray;

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

    private void StartWebcam(RawImage targetImage)
    {
        if (targetImage == null) return;

        targetImage.color = Color.white;
        SetCameraMessage(targetImage, "Démarrage de la caméra…");
        if (!useWebcam)
        {
            SetCameraUnavailable(targetImage, "Caméra indisponible : webcam désactivée.");
            return;
        }

        if (webcamStartupCoroutine != null) StopCoroutine(webcamStartupCoroutine);
        webcamStartupCoroutine = StartCoroutine(StartWebcamRoutine(targetImage));
    }

    private IEnumerator StartWebcamRoutine(RawImage targetImage)
    {
        webcamReady = false;
        if (!Application.HasUserAuthorization(UserAuthorization.WebCam))
        {
            yield return Application.RequestUserAuthorization(UserAuthorization.WebCam);
            if (!Application.HasUserAuthorization(UserAuthorization.WebCam))
            {
                SetCameraUnavailable(targetImage, "Caméra indisponible : autorisation refusée.");
                yield break;
            }
        }

        string startupError = null;
        try
        {
            if (webcamTexture == null)
            {
                WebCamDevice[] devices = WebCamTexture.devices;
                if (devices == null || devices.Length == 0)
                    throw new InvalidOperationException("aucun périphérique détecté.");

                string selectedDevice = devices[0].name;
                if (!string.IsNullOrWhiteSpace(preferredWebcamDeviceName))
                {
                    foreach (WebCamDevice device in devices)
                    {
                        if (string.Equals(device.name, preferredWebcamDeviceName, StringComparison.OrdinalIgnoreCase))
                        {
                            selectedDevice = device.name;
                            break;
                        }
                    }
                }

                webcamTexture = new WebCamTexture(selectedDevice, 1280, 720, 30);
                Debug.Log("[Camera] Selected device: " + selectedDevice);
            }

            targetImage.texture = webcamTexture;
            targetImage.color = Color.white;
            if (!webcamTexture.isPlaying) webcamTexture.Play();
        }
        catch (Exception e)
        {
            Debug.LogError("[Camera] Could not start webcam: " + e);
            startupError = e.Message;
        }

        if (!string.IsNullOrEmpty(startupError))
        {
            SetCameraUnavailable(targetImage, "Caméra indisponible : " + startupError);
            yield break;
        }

        float deadline = Time.realtimeSinceStartup + Mathf.Max(1f, webcamStartupTimeoutSeconds);
        while (Time.realtimeSinceStartup < deadline)
        {
            if (targetImage == null) yield break;
            if (webcamTexture != null && webcamTexture.isPlaying &&
                webcamTexture.width > 16 && webcamTexture.height > 16 && webcamTexture.didUpdateThisFrame)
            {
                webcamReady = true;
                UpdateCameraPreview(targetImage);
                SetCameraMessage(targetImage, "");
                ShowStatus("Caméra active — image reçue.", PremiumGreen);
                Debug.Log($"[Camera] First frame received: {webcamTexture.width}x{webcamTexture.height}, " +
                          $"rotation={webcamTexture.videoRotationAngle}, mirrored={webcamTexture.videoVerticallyMirrored}");
                yield break;
            }
            yield return null;
        }

        if (webcamTexture != null && webcamTexture.isPlaying) webcamTexture.Stop();
        SetCameraUnavailable(targetImage, "Caméra indisponible : aucune image reçue du périphérique.");
    }

    private void UpdateCameraPreview(RawImage targetImage)
    {
        if (targetImage == null || webcamTexture == null) return;
        targetImage.color = Color.white;
        int rotation = webcamTexture.videoRotationAngle;
        targetImage.rectTransform.localEulerAngles = new Vector3(0f, 0f, -rotation);

        AspectRatioFitter fitter = targetImage.GetComponent<AspectRatioFitter>();
        if (fitter == null) fitter = targetImage.gameObject.AddComponent<AspectRatioFitter>();
        fitter.aspectMode = AspectRatioFitter.AspectMode.FitInParent;
        bool rotated = rotation == 90 || rotation == 270;
        fitter.aspectRatio = rotated
            ? (float)webcamTexture.height / webcamTexture.width
            : (float)webcamTexture.width / webcamTexture.height;

        Vector3 scale = targetImage.rectTransform.localScale;
        targetImage.rectTransform.localScale = new Vector3(Mathf.Abs(scale.x),
            webcamTexture.videoVerticallyMirrored ? -Mathf.Abs(scale.y) : Mathf.Abs(scale.y), scale.z);

        Transform message = targetImage.transform.Find("Camera Status");
        if (message != null)
        {
            message.localEulerAngles = new Vector3(0f, 0f, rotation);
            Vector3 messageScale = message.localScale;
            message.localScale = new Vector3(1f,
                webcamTexture.videoVerticallyMirrored ? -Mathf.Abs(messageScale.y) : Mathf.Abs(messageScale.y), 1f);
        }
        if (targetImage == maintenancePreviewImage) UpdateMaintenanceGuideVisuals();
    }

    private void SetCameraUnavailable(RawImage targetImage, string message)
    {
        webcamReady = false;
        if (webcamTexture != null && webcamTexture.isPlaying) webcamTexture.Stop();
        if (targetImage != null)
        {
            targetImage.texture = null;
            targetImage.color = Color.white;
            targetImage.rectTransform.localEulerAngles = Vector3.zero;
            Vector3 scale = targetImage.rectTransform.localScale;
            targetImage.rectTransform.localScale = new Vector3(Mathf.Abs(scale.x), Mathf.Abs(scale.y), scale.z);
            SetCameraMessage(targetImage, message);
            Transform cameraMessage = targetImage.transform.Find("Camera Status");
            if (cameraMessage != null)
            {
                cameraMessage.localEulerAngles = Vector3.zero;
                cameraMessage.localScale = Vector3.one;
            }
        }
        ShowStatus(message, PremiumRed);
        Debug.LogWarning("[Camera] " + message);
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
            label.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
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

    private void StopWebcam()
    {
        webcamReady = false;
        if (webcamStartupCoroutine != null)
        {
            StopCoroutine(webcamStartupCoroutine);
            webcamStartupCoroutine = null;
        }
        if (webcamTexture != null && webcamTexture.isPlaying)
        {
            webcamTexture.Stop();
            Debug.Log("Webcam stopped.");
        }
    }

    private void ShowPanel(GameObject panelToShow)
    {
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
        StartWebcam(qrCameraPreviewImage);
        ShowStatus("Scanner actif. C cadres du QR Code...", PremiumBlue);
        
        var scanner = GetComponent<LotoQRScanner>();
        if (scanner != null)
        {
            scanner.ResumeScanning();
        }
    }

    private void OnChooseManualPressed()
    {
        ShowPanel(manualSelectionPanel);
        StopWebcam();
        ShowStatus("Sélectionnez une machine et cliquez sur Démarrer.", PremiumGray);
    }

    private void OnBackToWelcomePressed()
    {
        ShowPanel(welcomePanel);
        StopWebcam();
        ShowStatus("Sélectionnez le mode d'initialisation.", PremiumGray);
    }

    private void OnStartPressed()
    {
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
                ShowPanel(stepPanel);
                StartWebcam(cameraPreviewImage);
            },
            (error) => {
                startButton.interactable = true;
                ShowStatus($"Échec connexion : {error}", PremiumRed);
            }
        );
    }

    private void OnValidatePressed()
    {
        byte[] imageBytes = GetCapturedImageBytes();
        if (imageBytes == null) return;
        lotoManager.RequestStepValidation(imageBytes);
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
        ShowPanel(stepPanel);
        StartWebcam(cameraPreviewImage);
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
        lotoClient.activeInterventionId = "";
        lotoClient.activeMachineId = "";
        ShowPanel(welcomePanel);
        StopWebcam();
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

    public WebCamTexture GetWebcamTexture()
    {
        return webcamTexture;
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
        var action = lotoManager.GetActiveAction();
        var stage = lotoManager.GetActiveStage();

        if (action == null || stage == null) return;

        var phases = lotoManager.currentProcedure.workflow_stages.phases;
        phaseTitleText.text = phases != null && phases.Length > lotoManager.currentPhaseIndex
            ? phases[lotoManager.currentPhaseIndex].title
            : (lotoManager.isLockoutPhase ? "Consignation" : "Déconsignation");
        stageTitleText.text = $"Étape {stage.StageNumber} - {stage.title}";
        stepDescText.text = $"Action {action.Id} : {action.InstructionText}";
        string criteria = action.VerificationCriteria != null && action.VerificationCriteria.Length > 0
            ? string.Join("; ", action.VerificationCriteria)
            : action.ExpectedText;
        visionPromptText.text = $"Vérification ({action.VerificationMethod}) : {criteria}";

        ShowStatus("Prêt pour la capture", PremiumBlue);
    }

    public void ShowMaintenanceScreen()
    {
        ShowPanel(maintenancePanel);
        maintenanceTaskTitleText.text = "Remplacer l'ampoule";
        StartWebcam(maintenancePreviewImage);
        LoadMaintenanceCalibration();
        ShowStatus("Consignation validée. Calibrez la zone de maintenance sur la vue caméra.", PremiumGreen);
    }

    public void ShowClosureScreen()
    {
        StopWebcam();
        ShowPanel(signaturePanel);
        if (signaturePad != null) signaturePad.Clear();
        string machine = lotoClient != null ? lotoClient.activeMachineId : "machine";
        closureSummaryText.text = $"Machine : {machine}\nConsignation et déconsignation terminées.";
        SetSignatureSubmitting(false);
        ShowStatus("Déconsignation terminée. Dessinez votre signature pour clôturer.", PremiumBlue);
    }

    public void ShowFinalReportScreen(string pdfReportUrl)
    {
        savedReportUrl = pdfReportUrl;
        reportUrlText.text = $"Lien du rapport PDF :\n{pdfReportUrl}";
        ShowPanel(reportPanel);
    }

    public void ShowStatus(string message, Color color)
    {
        statusText.text = message;
        statusBackgroundImage.color = color;
    }

    private byte[] GetCapturedImageBytes()
    {
        if (!webcamReady || webcamTexture == null || !webcamTexture.isPlaying ||
            webcamTexture.width <= 16 || webcamTexture.height <= 16)
        {
            ShowStatus("Caméra indisponible : aucune image réelle à envoyer.", PremiumRed);
            return null;
        }

        try
        {
            int sourceWidth = webcamTexture.width;
            int sourceHeight = webcamTexture.height;
            int rotation = webcamTexture.videoRotationAngle;
            Color32[] source = webcamTexture.GetPixels32();
            if (source == null || source.Length != sourceWidth * sourceHeight)
                throw new InvalidOperationException("La caméra n'a pas fourni une image complète.");

            bool rotated = rotation == 90 || rotation == 270;
            int outputWidth = rotated ? sourceHeight : sourceWidth;
            int outputHeight = rotated ? sourceWidth : sourceHeight;
            Color32[] output = new Color32[outputWidth * outputHeight];
            bool mirrorY = webcamTexture.videoVerticallyMirrored;

            for (int y = 0; y < outputHeight; y++)
            {
                for (int x = 0; x < outputWidth; x++)
                {
                    int sourceX;
                    int sourceY;
                    switch (rotation)
                    {
                        case 90:  sourceX = y; sourceY = sourceHeight - 1 - x; break;
                        case 180: sourceX = sourceWidth - 1 - x; sourceY = sourceHeight - 1 - y; break;
                        case 270: sourceX = sourceWidth - 1 - y; sourceY = x; break;
                        default:  sourceX = x; sourceY = y; break;
                    }
                    if (mirrorY) sourceY = sourceHeight - 1 - sourceY;
                    output[y * outputWidth + x] = source[sourceY * sourceWidth + sourceX];
                }
            }

            Texture2D snap = new Texture2D(outputWidth, outputHeight, TextureFormat.RGB24, false);
            snap.SetPixels32(output);
            snap.Apply();
            byte[] bytes = snap.EncodeToJPG(90);
            Destroy(snap);
            if (bytes == null || bytes.Length < 100)
                throw new InvalidOperationException("L'image de la caméra est vide.");
            return bytes;
        }
        catch (Exception e)
        {
            ShowStatus("Capture caméra impossible : " + e.Message, PremiumRed);
            Debug.LogError("[Camera] Capture failed: " + e);
            return null;
        }
    }

    private byte[] GetSignatureImageBytes()
    {
        return signaturePad != null && signaturePad.HasInk ? signaturePad.EncodeToPng() : null;
    }

    private string MaintenanceCalibrationKey(string axis)
    {
        string machineId = lotoClient != null && !string.IsNullOrEmpty(lotoClient.activeMachineId)
            ? lotoClient.activeMachineId
            : "default";
        return "SmartLOTO.MaintenanceGuide." + machineId + "." + axis;
    }

    private void LoadMaintenanceCalibration()
    {
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
        if (maintenancePreviewImage == null || !maintenancePanel.activeSelf || !webcamReady)
            return;

        if (!RectTransformUtility.ScreenPointToLocalPointInRectangle(
                maintenancePreviewImage.rectTransform, pointer.position, pointer.pressEventCamera, out Vector2 localPoint))
            return;

        Rect rect = maintenancePreviewImage.rectTransform.rect;
        if (rect.width <= 0 || rect.height <= 0) return;
        maintenanceTargetX = Mathf.Clamp01((localPoint.x - rect.xMin) / rect.width);
        maintenanceTargetY = Mathf.Clamp01((localPoint.y - rect.yMin) / rect.height);
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

        bool showGuide = webcamReady && maintenanceTargetCalibrated;
        maintenanceArrowLine.gameObject.SetActive(showGuide);
        maintenanceArrowHead.gameObject.SetActive(showGuide);
        if (!webcamReady)
        {
            maintenanceCalibrationText.text = "Caméra indisponible : le repère ne peut pas être calibré.";
            return;
        }
        if (!maintenanceTargetCalibrated)
        {
            maintenanceCalibrationText.text = "Cliquez sur l'ampoule dans l'image pour calibrer le repère de cette maquette.";
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

    private void OnDestroy()
    {
        DisposeRedesignedView();
        if (webcamTexture != null)
        {
            webcamTexture.Stop();
        }
    }
}
