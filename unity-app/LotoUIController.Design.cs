using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

// This file and LotoUIController.cs form ONE component. Keep both in Assets.
public partial class LotoUIController
{
    [Header("SmartLoto interface")]
    [SerializeField] private bool buildRedesignedUI = true;
    [Tooltip("Optional font with French glyphs. Built-in font used otherwise.")]
    [SerializeField] private Font interfaceFont;
    private RectTransform safeRoot;
    private GameObject generatedView;
    private Sprite panelSprite;
    private readonly Color ink = new Color32(12, 22, 31, 255);
    private readonly Color surface = new Color32(22, 38, 50, 255);
    private readonly Color muted = new Color32(175, 194, 204, 255);
    private readonly Color accent = new Color32(91, 225, 196, 255);

    private void Awake()
    {
        if (!buildRedesignedUI) return;
        // Disable only the old panels referenced by this controller.
        foreach (var p in new[] { welcomePanel, manualSelectionPanel, qrScanPanel,
            stepPanel, maintenancePanel, signaturePanel, reportPanel })
            if (p != null && p != gameObject && !transform.IsChildOf(p.transform)) p.SetActive(false);

        if (interfaceFont == null)
        {
#if UNITY_2022_2_OR_NEWER
            interfaceFont = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
#else
            interfaceFont = Resources.GetBuiltinResource<Font>("Arial.ttf");
#endif
        }
        panelSprite = RoundedSurface();
        generatedView = new GameObject("SmartLoto · Operator HUD", typeof(RectTransform), typeof(Canvas),
            typeof(CanvasScaler), typeof(GraphicRaycaster));
        // Separate root: the controller may live underneath a legacy panel.
        var canvas = generatedView.GetComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 40;
        var scaler = generatedView.GetComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1440, 900);
        scaler.screenMatchMode = CanvasScaler.ScreenMatchMode.Expand;
        safeRoot = Node("Safe area", generatedView.transform);
        Fit(safeRoot, 0, 0, 1, 1);
        ApplySafeArea();
        if (FindObjectOfType<EventSystem>() == null)
        {
            var events = new GameObject("SmartLoto EventSystem", typeof(EventSystem));
#if ENABLE_INPUT_SYSTEM
            events.AddComponent<UnityEngine.InputSystem.UI.InputSystemUIInputModule>();
#else
            events.AddComponent<StandaloneInputModule>();
#endif
        }

        var header = Box("Header", safeRoot, ink, .02f, .89f, .98f, .98f);
        Label(header, "SMART / LOTO", 27, Color.white, .025f, .15f, .4f, .85f);
        Label(header, "ASSISTANCE OPÉRATEUR", 17, muted, .56f, .15f, .975f, .85f, TextAnchor.MiddleRight);

        welcomePanel = Panel("Identification", true);
        var home = Box("Identification card", welcomePanel.transform, ink, .24f, .21f, .76f, .78f);
        Label(home, "01 / IDENTIFICATION", 19, accent, .065f, .80f, .935f, .91f);
        Label(home, "Chaque intervention\ncommence par le bon équipement.", 34, Color.white, .065f, .49f, .935f, .79f);
        Label(home, "Identifiez la machine pour charger sa procédure.", 20, muted, .065f, .34f, .935f, .47f);
        chooseQRScanButton = Action(home, "Scanner le QR code", .065f, .17f, .935f, .30f, true);
        chooseManualButton = Action(home, "Choisir dans la liste des machines", .065f, .015f, .935f, .14f);

        manualSelectionPanel = Panel("Machines", true);
        var manual = Box("Machine selection", manualSelectionPanel.transform, ink, .24f, .21f, .76f, .78f);
        Label(manual, "01 / SÉLECTION MANUELLE", 19, accent, .065f, .79f, .935f, .91f);
        Label(manual, "Identifier l'équipement", 32, Color.white, .065f, .63f, .935f, .78f);
        machineIdDropdown = MachineDropdown(manual);
        startButton = Action(manual, "Charger la procédure", .065f, .19f, .935f, .32f, true);
        manualBackButton = Action(manual, "Retour à l'identification", .065f, .035f, .935f, .16f);

        qrScanPanel = Panel("Scan QR", false);
        qrCameraPreviewImage = Preview(qrScanPanel.transform, "QR camera", .02f, .16f, .98f, .87f);
        var target = Box("Scan target", qrScanPanel.transform, Color.clear, .32f, .30f, .68f, .74f);
        target.GetComponent<Image>().enabled = false;
        AddReticleCorners(target, "QR reticle");
        Label(qrScanPanel.transform, "Placez le QR code dans le cadre", 25, Color.white, .2f, .18f, .8f, .28f, TextAnchor.MiddleCenter);
        scanLaserLine = Box("Scan line", target, accent, 0, .49f, 1, .51f);
        laserMinY = -70; laserMaxY = 70; laserSpeed = 90;
        qrBackButton = Action(qrScanPanel.transform, "Retour", .04f, .77f, .18f, .85f);

        stepPanel = Panel("Guided action", false);
        cameraPreviewImage = Preview(stepPanel.transform, "Operator camera", .02f, .16f, .635f, .87f);
        Label(cameraPreviewImage.transform, "VUE OPÉRATEUR", 19, muted, .03f, .89f, .8f, .98f);
        var reticle = Box("Framing aid - not object tracking", cameraPreviewImage.transform,
            Color.clear, .27f, .25f, .73f, .75f);
        reticle.GetComponent<Image>().enabled = false;
        AddReticleCorners(reticle, "Action reticle");
        var guide = Box("Action card", stepPanel.transform, ink, .65f, .16f, .98f, .87f);
        phaseTitleText = Label(guide, "CONSIGNATION", 18, accent, .07f, .87f, .93f, .97f);
        stageTitleText = Label(guide, "Étape", 26, Color.white, .07f, .70f, .93f, .86f);
        stepDescText = Label(guide, "Chargement de la consigne…", 24, Color.white, .07f, .48f, .93f, .69f);
        visionPromptText = Label(guide, "Contrôle visuel", 18, muted, .07f, .34f, .93f, .47f);
        validateButton = Action(guide, "Capturer et vérifier", .07f, .22f, .93f, .32f, true);
        overrideReasonInput = Reason(guide);
        overrideButton = Action(guide, "Valider manuellement", .07f, .015f, .93f, .105f);

        maintenancePanel = Panel("Maintenance", true);
        Label(maintenancePanel.transform, "02 / MAINTENANCE GUIDÉE", 20, accent, .04f, .88f, .64f, .96f);
        maintenancePreviewImage = Preview(maintenancePanel.transform, "Maintenance camera", .04f, .17f, .64f, .85f);
        maintenancePreviewImage.raycastTarget = true;
        maintenanceArrowLine = Box("Maintenance arrow shaft", maintenancePreviewImage.transform,
            accent, 0, 0, 1, 1).GetComponent<RectTransform>();
        maintenanceArrowHead = Label(maintenancePreviewImage.transform, "▶", 38, accent,
            .45f, .45f, .55f, .55f, TextAnchor.MiddleCenter);
        maintenanceArrowLine.gameObject.SetActive(false);
        maintenanceArrowHead.gameObject.SetActive(false);
        Label(maintenancePanel.transform, "VUE DE LA MAQUETTE · CLIQUEZ SUR LA ZONE À INTERVENIR", 16, muted,
            .04f, .10f, .64f, .16f, TextAnchor.MiddleCenter);

        var work = Box("Maintenance card", maintenancePanel.transform, ink, .67f, .17f, .96f, .85f);
        Label(work, "CONSIGNE", 17, accent, .07f, .87f, .93f, .97f);
        maintenanceTaskTitleText = Label(work, "Remplacer l'ampoule", 29, Color.white,
            .07f, .69f, .93f, .86f);
        maintenanceCalibrationText = Label(work,
            "Cliquez sur l'ampoule dans l'image pour calibrer le repère de cette maquette.",
            20, muted, .07f, .40f, .93f, .68f);
        Label(work, "La calibration est enregistrée sur ce PC pour cette machine.",
            16, muted, .07f, .30f, .93f, .40f);
        startRestorationButton = Action(work, "Commencer la déconsignation", .07f, .07f, .93f, .22f, true);

        signaturePanel = Panel("Signature", true);
        var sign = Box("Signature card", signaturePanel.transform, ink, .24f, .16f, .76f, .84f);
        Label(sign, "04 / CLÔTURE", 19, accent, .065f, .87f, .935f, .97f);
        closureSummaryText = Label(sign, "Consignation et déconsignation terminées.",
            19, muted, .065f, .76f, .935f, .86f);
        Label(sign, "Dessinez votre signature dans le cadre.", 21, Color.white,
            .065f, .66f, .935f, .75f);
        signatureCanvas = Preview(sign, "Signature area", .065f, .31f, .935f, .64f);
        signatureCanvas.raycastTarget = true;
        clearSignatureButton = Action(sign, "Effacer", .065f, .17f, .32f, .27f);
        submitSignatureButton = Action(sign, "Signer et clôturer", .36f, .17f, .935f, .27f, true);
        Label(sign, "Le PDF sera généré après confirmation de la signature.",
            16, muted, .065f, .06f, .935f, .15f);

        overrideConfirmationPanel = Box("Confirm manual override", safeRoot,
            new Color(0, 0, 0, .82f), 0, 0, 1, 1).gameObject;
        overrideConfirmationPanel.GetComponent<Image>().raycastTarget = true;
        var confirmation = Box("Manual override confirmation card", overrideConfirmationPanel.transform,
            ink, .26f, .34f, .74f, .68f);
        Label(confirmation, "CONFIRMER LA VALIDATION MANUELLE", 19, accent,
            .07f, .79f, .93f, .95f, TextAnchor.MiddleCenter);
        overrideConfirmationText = Label(confirmation, "", 21, Color.white,
            .08f, .35f, .92f, .77f, TextAnchor.MiddleCenter);
        overrideCancelButton = Action(confirmation, "Retour", .07f, .08f, .43f, .26f);
        overrideConfirmButton = Action(confirmation, "Confirmer", .57f, .08f, .93f, .26f, true);
        overrideConfirmationPanel.SetActive(false);

        reportPanel = Panel("Rapport", true);
        var report = Box("Report card", reportPanel.transform, ink, .24f, .21f, .76f, .78f);
        Label(report, "05 / TRAÇABILITÉ", 19, accent, .065f, .79f, .935f, .91f);
        Label(report, "Rapport d'intervention", 32, Color.white, .065f, .63f, .935f, .78f);
        reportUrlText = Label(report, "Rapport", 20, muted, .065f, .38f, .935f, .62f);
        openReportButton = Action(report, "Ouvrir le rapport PDF", .065f, .20f, .935f, .34f, true);
        restartButton = Action(report, "Nouvelle intervention", .065f, .04f, .935f, .18f);

        header.SetAsLastSibling();
        var status = Box("Status", safeRoot, surface, .02f, .025f, .98f, .125f);
        statusBackgroundImage = status.GetComponent<Image>();
        statusText = Label(status, "Connexion…", 21, Color.white, .025f, .12f, .975f, .88f);
        ShowPanel(welcomePanel);
    }

    // Only resources created by the redesigned view are cleaned up here.
    private void DisposeRedesignedView()
    {
        if (generatedView != null) Destroy(generatedView);
        if (panelSprite != null)
        {
            Destroy(panelSprite.texture);
            Destroy(panelSprite);
        }
    }

    private void ApplySafeArea()
    {
        if (safeRoot == null || Screen.width <= 0 || Screen.height <= 0) return;
        Rect area = Screen.safeArea;
        safeRoot.anchorMin = new Vector2(area.xMin / Screen.width, area.yMin / Screen.height);
        safeRoot.anchorMax = new Vector2(area.xMax / Screen.width, area.yMax / Screen.height);
    }
    private void LateUpdate() { ApplySafeArea(); }

    private RectTransform Node(string name, Transform parent)
    {
        var node = new GameObject(name, typeof(RectTransform));
        node.transform.SetParent(parent, false);
        return node.GetComponent<RectTransform>();
    }
    private void Fit(RectTransform rect, float x0, float y0, float x1, float y1)
    {
        rect.anchorMin = new Vector2(x0, y0); rect.anchorMax = new Vector2(x1, y1);
        rect.offsetMin = Vector2.zero; rect.offsetMax = Vector2.zero;
    }
    private RectTransform Box(string name, Transform parent, Color color, float x0, float y0, float x1, float y1)
    {
        var rect = Node(name, parent); Fit(rect, x0, y0, x1, y1);
        var image = rect.gameObject.AddComponent<Image>(); image.color = color;
        image.sprite = panelSprite; image.type = Image.Type.Sliced;
        image.raycastTarget = false;
        return rect;
    }
    private GameObject Panel(string name, bool opaque)
    {
        var p = Box(name, safeRoot, opaque ? new Color(ink.r,ink.g,ink.b,.96f) : Color.clear, 0, .14f, 1, .88f);
        // Child coordinates span the entire safe area for consistent geometry.
        Fit(p, 0, 0, 1, 1);
        p.gameObject.SetActive(false);
        return p.gameObject;
    }
    private Text Label(Transform parent, string value, int size, Color color, float x0, float y0, float x1, float y1,
        TextAnchor align = TextAnchor.MiddleLeft)
    {
        var rect = Node("Text", parent); Fit(rect, x0, y0, x1, y1);
        var text = rect.gameObject.AddComponent<Text>(); text.font = interfaceFont;
        text.text = value; text.fontSize = size; text.color = color; text.alignment = align;
        text.supportRichText = false; text.raycastTarget = false;
        text.horizontalOverflow = HorizontalWrapMode.Wrap;
        text.verticalOverflow = VerticalWrapMode.Truncate;
        text.resizeTextForBestFit = true; text.resizeTextMinSize = 16; text.resizeTextMaxSize = size;
        return text;
    }
    private Button Action(Transform parent, string title, float x0, float y0, float x1, float y1, bool primary = false)
    {
        var rect = Box(title, parent, primary ? accent : surface, x0, y0, x1, y1);
        var image = rect.GetComponent<Image>(); image.raycastTarget = true;
        var button = rect.gameObject.AddComponent<Button>(); button.targetGraphic = image;
        var colors = button.colors; colors.disabledColor = new Color32(71,85,94,255); button.colors = colors;
        Label(rect, title, 22, primary ? ink : Color.white, .04f, .06f, .96f, .94f, TextAnchor.MiddleCenter);
        return button;
    }
    private RawImage Preview(Transform parent, string name, float x0, float y0, float x1, float y1)
    {
        var rect = Node(name, parent); Fit(rect, x0,y0,x1,y1);
        var image = rect.gameObject.AddComponent<RawImage>();
        // RawImage multiplies the camera pixels by this color. Alpha zero made
        // the preview fully transparent even after assigning a live texture.
        image.color = Color.white; image.raycastTarget = false;
        return image;
    }
    private void AddReticleCorners(Transform parent, string prefix)
    {
        const float cornerLength = .16f;
        const float cornerThickness = .025f;
        Box(prefix + " top left horizontal", parent, accent, 0, 1-cornerThickness, cornerLength, 1);
        Box(prefix + " top left vertical", parent, accent, 0, 1-cornerLength, cornerThickness, 1);
        Box(prefix + " top right horizontal", parent, accent, 1-cornerLength, 1-cornerThickness, 1, 1);
        Box(prefix + " top right vertical", parent, accent, 1-cornerThickness, 1-cornerLength, 1, 1);
        Box(prefix + " bottom left horizontal", parent, accent, 0, 0, cornerLength, cornerThickness);
        Box(prefix + " bottom left vertical", parent, accent, 0, 0, cornerThickness, cornerLength);
        Box(prefix + " bottom right horizontal", parent, accent, 1-cornerLength, 0, 1, cornerThickness);
        Box(prefix + " bottom right vertical", parent, accent, 1-cornerThickness, 0, 1, cornerLength);
    }
    private Sprite RoundedSurface()
    {
        const int size = 64;
        const float radius = 12;
        var texture = new Texture2D(size, size, TextureFormat.RGBA32, false);
        texture.name = "SmartLoto rounded surface";
        texture.wrapMode = TextureWrapMode.Clamp;
        texture.filterMode = FilterMode.Bilinear;
        var pixels = new Color[size * size];
        for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++)
            {
                float dx = Mathf.Max(radius - x - .5f, x + .5f - (size - radius));
                float dy = Mathf.Max(radius - y - .5f, y + .5f - (size - radius));
                float distance = new Vector2(Mathf.Max(0, dx), Mathf.Max(0, dy)).magnitude;
                pixels[y * size + x] = new Color(1, 1, 1, Mathf.Clamp01(radius + .5f - distance));
            }
        texture.SetPixels(pixels); texture.Apply();
        return Sprite.Create(texture, new Rect(0, 0, size, size), new Vector2(.5f, .5f),
            100, 0, SpriteMeshType.FullRect, new Vector4(16, 16, 16, 16));
    }
    private InputField Reason(Transform parent)
    {
        var rect = Box("Override reason", parent, surface, .07f,.12f,.93f,.205f);
        rect.GetComponent<Image>().raycastTarget = true;
        var field = rect.gameObject.AddComponent<InputField>();
        field.targetGraphic = rect.GetComponent<Image>();
        field.textComponent = Label(rect, "", 19, Color.white, .04f,.08f,.96f,.92f);
        field.placeholder = Label(rect, "Motif de dérogation…", 19, muted, .04f,.08f,.96f,.92f);
        field.characterLimit = 500;
        return field;
    }
    private Dropdown MachineDropdown(Transform parent)
    {
        var rect = Box("Machine dropdown", parent, surface, .065f,.39f,.935f,.58f);
        var image = rect.GetComponent<Image>(); image.raycastTarget = true;
        var dropdown = rect.gameObject.AddComponent<Dropdown>(); dropdown.targetGraphic = image;
        dropdown.captionText = Label(rect, "Chargement des machines…", 24, Color.white, .04f,.08f,.96f,.92f);
        var template = Box("Template", rect, surface, 0,0,1,0);
        template.pivot = new Vector2(.5f,1); template.sizeDelta = new Vector2(0,240);
        var scroll = template.gameObject.AddComponent<ScrollRect>(); scroll.horizontal = false;
        var viewport = Box("Viewport", template, surface,0,0,1,1);
        viewport.gameObject.AddComponent<RectMask2D>();
        var content = Node("Content", viewport); Fit(content,0,1,1,1);
        content.pivot = new Vector2(.5f,1); content.sizeDelta = new Vector2(0,64);
        var item = Box("Item", content, surface,0,0,1,1); item.sizeDelta = Vector2.zero;
        var toggle = item.gameObject.AddComponent<Toggle>();
        item.GetComponent<Image>().raycastTarget = true; toggle.targetGraphic = item.GetComponent<Image>();
        var mark = Box("Selected", item, accent,.01f,.2f,.025f,.8f); toggle.graphic = mark.GetComponent<Image>();
        dropdown.itemText = Label(item,"Machine",22,Color.white,.05f,0,.95f,1);
        scroll.viewport = viewport; scroll.content = content;
        dropdown.template = template; template.gameObject.SetActive(false);
        return dropdown;
    }
}
