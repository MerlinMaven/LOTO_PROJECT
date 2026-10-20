using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

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

    [Header("Status UI")]
    [SerializeField] private Text statusText;
    [SerializeField] private Image statusBackgroundImage;

    [Header("Maintenance Panel UI")]
    [SerializeField] private Button startRestorationButton;

    [Header("Signature Panel UI")]
    [SerializeField] private RawImage signatureCanvas; // Can be used to draw or simulation
    [SerializeField] private Button submitSignatureButton;

    [Header("Report Panel UI")]
    [SerializeField] private Text reportUrlText;
    [SerializeField] private Button openReportButton;
    [SerializeField] private Button restartButton;

    [Header("Webcam Settings")]
    [SerializeField] private bool useWebcam = true;
    private WebCamTexture webcamTexture;
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
        startRestorationButton.onClick.AddListener(OnStartRestorationPressed);
        submitSignatureButton.onClick.AddListener(OnSubmitSignaturePressed);
        openReportButton.onClick.AddListener(OnOpenReportPressed);
        restartButton.onClick.AddListener(OnRestartPressed);

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
        if (!useWebcam) return;
        try
        {
            if (webcamTexture == null)
            {
                if (WebCamTexture.devices.Length > 0)
                {
                    webcamTexture = new WebCamTexture(640, 480);
                }
            }

            if (webcamTexture != null)
            {
                targetImage.texture = webcamTexture;
                targetImage.material.mainTexture = webcamTexture;
                if (!webcamTexture.isPlaying)
                {
                    webcamTexture.Play();
                }
                Debug.Log("Webcam started and assigned to: " + targetImage.name);
            }
            else
            {
                Debug.LogWarning("No webcam detected. Fallback to mock image generation.");
                targetImage.texture = CreateDummyTexture(Color.blue);
            }
        }
        catch (Exception e)
        {
            Debug.LogError("Error starting webcam: " + e.Message);
            targetImage.texture = CreateDummyTexture(Color.red);
        }
    }

    private void StopWebcam()
    {
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
        lotoManager.RequestManualOverride(reason, imageBytes);
        overrideReasonInput.text = ""; // Reset input
    }

    private void OnStartRestorationPressed()
    {
        lotoManager.StartRestorationPhase();
        ShowPanel(stepPanel);
        StartWebcam(cameraPreviewImage);
    }

    private void OnSubmitSignaturePressed()
    {
        byte[] sigBytes = GetSignatureImageBytes();
        lotoManager.CloseIntervention(sigBytes);
        StopWebcam();
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

        phaseTitleText.text = lotoManager.isLockoutPhase ? "PHASE 1 : CONSIGNATION (Lockout)" : "PHASE 3 : DÉCONSIGNATION (Restoration)";
        stageTitleText.text = $"Étape {stage.stage_id} - {stage.title}";
        stepDescText.text = $"Action {action.action_id} : {action.description}";
        visionPromptText.text = $"Objet recherché par l'IA : '{action.vision_prompt}'";

        ShowStatus("Prêt pour la capture", PremiumBlue);
    }

    public void ShowMaintenanceScreen()
    {
        ShowPanel(maintenancePanel);
        ShowStatus("Consignation validée. Effectuez les opérations de maintenance physiques.", PremiumGreen);
    }

    public void ShowClosureScreen()
    {
        ShowPanel(signaturePanel);
        signatureCanvas.texture = CreateDummySignature();
        ShowStatus("Déconsignation validée. Veuillez signer pour clôturer.", PremiumBlue);
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
        if (webcamTexture != null && webcamTexture.isPlaying)
        {
            Texture2D snap = new Texture2D(webcamTexture.width, webcamTexture.height);
            snap.SetPixels(webcamTexture.GetPixels());
            snap.Apply();
            byte[] bytes = snap.EncodeToJPG(80);
            Destroy(snap);
            return bytes;
        }

        Texture2D mockTex = CreateDummyTexture(Color.blue);
        byte[] mockBytes = mockTex.EncodeToJPG();
        Destroy(mockTex);
        return mockBytes;
    }

    private byte[] GetSignatureImageBytes()
    {
        Texture2D mockSig = CreateDummySignature();
        byte[] bytes = mockSig.EncodeToPNG();
        Destroy(mockSig);
        return bytes;
    }

    private Texture2D CreateDummyTexture(Color baseColor)
    {
        Texture2D tex = new Texture2D(256, 256);
        for (int y = 0; y < tex.height; y++)
        {
            for (int x = 0; x < tex.width; x++)
            {
                if (x < 10 || x > 246 || y < 10 || y > 246)
                    tex.SetPixel(x, y, Color.black);
                else
                    tex.SetPixel(x, y, baseColor);
            }
        }
        tex.Apply();
        return tex;
    }

    private Texture2D CreateDummySignature()
    {
        Texture2D tex = new Texture2D(250, 100);
        for (int y = 0; y < tex.height; y++)
            for (int x = 0; x < tex.width; x++)
                tex.SetPixel(x, y, Color.white);

        for (int i = 0; i < 100; i++)
        {
            tex.SetPixel(20 + i, 20 + i / 2, Color.blue);
            tex.SetPixel(20 + i, 21 + i / 2, Color.blue);
            tex.SetPixel(150 - i, 20 + i / 2, Color.blue);
            tex.SetPixel(150 - i, 21 + i / 2, Color.blue);
        }
        tex.Apply();
        return tex;
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
