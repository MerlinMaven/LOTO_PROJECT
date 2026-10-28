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
    private readonly Color ink = new Color32(11, 19, 30, 255);
    private readonly Color hudGlass = new Color32(11, 19, 30, 184);
    private readonly Color surface = new Color32(22, 38, 50, 235);
    private readonly Color muted = new Color32(176, 199, 211, 255);
    private readonly Color accent = new Color32(94, 234, 212, 255);
    private readonly Color hudText = new Color32(224, 242, 254, 255);

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
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var events = new GameObject("SmartLoto EventSystem", typeof(EventSystem));
#if ENABLE_INPUT_SYSTEM
            events.AddComponent<UnityEngine.InputSystem.UI.InputSystemUIInputModule>();
#else
            events.AddComponent<StandaloneInputModule>();
#endif
        }

        var header = Box("Header", safeRoot, hudGlass, .02f, .94f, .98f, .985f);
        Label(header, "SMART / LOTO", 20, accent, .02f, .15f, .35f, .85f);
        Label(header, "ASSISTANCE OPÉRATEUR · AR HUD", 14, muted, .50f, .15f, .98f, .85f, TextAnchor.MiddleRight);

        welcomePanel = Panel("Identification", false);
        var home = Box("Identification card", welcomePanel.transform, hudGlass, .70f, .55f, .98f, .91f);
        Label(home, "01 / IDENTIFICATION AR", 15, accent, .06f, .84f, .94f, .94f);
        Label(home, "Orientez votre regard vers le QR code de la machine pour charger la procédure.", 16, hudText, .06f, .38f, .94f, .82f);
        chooseManualButton = Action(home, "Sélection manuelle", .06f, .08f, .94f, .32f);
        chooseQRScanButton = Action(home, "Scan QR", 0, 0, 0, 0);
        chooseQRScanButton.gameObject.SetActive(false);

        qrReticleObject = Box("AR Gaze Reticle", welcomePanel.transform, Color.clear, .46f, .43f, .54f, .57f).gameObject;
        var ring = Box("Reticle ring", qrReticleObject.transform, new Color(0, 0.85f, 0.78f, 0.35f), 0, 0, 1, 1);
        var ringImg = ring.GetComponent<Image>();
        ringImg.type = Image.Type.Filled;
        ringImg.fillMethod = Image.FillMethod.Radial360;
        ringImg.fillOrigin = (int)Image.Origin360.Top;
        ringImg.fillAmount = 0f;
        qrReticleProgressImage = ringImg;
        Box("Center dot", qrReticleObject.transform, accent, .45f, .45f, .55f, .55f);
        Label(qrReticleObject.transform, "VISER LE QR CODE", 12, accent, -0.5f, -0.38f, 1.5f, -0.05f, TextAnchor.MiddleCenter);

        manualSelectionPanel = Panel("Machines", true);
        var manual = Box("Machine selection", manualSelectionPanel.transform, hudGlass, .24f, .21f, .76f, .78f);
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
        cameraPreviewImage = Preview(stepPanel.transform, "Operator camera", 0, 0, 1, 1);
        cameraPreviewImage.color = Color.clear;
        cameraPreviewImage.raycastTarget = false;

        var guide = Box("Action card", stepPanel.transform, hudGlass, .70f, .18f, .98f, .91f);
        AddHudEdge(guide);
        phaseTitleText = Label(guide, "CONSIGNATION", 15, accent, .06f, .92f, .94f, .97f);
        stageTitleText = Label(guide, "Étape", 18, hudText, .06f, .84f, .94f, .92f);
        stepDescText = Label(guide, "Chargement de la consigne…", 18, hudText, .06f, .69f, .94f, .84f);
        visionPromptText = ScrollableContext(guide);
        validateButton = Action(guide, "Capturer et vérifier", .06f, .22f, .94f, .33f, true);
        overrideReasonInput = Reason(guide);
        overrideButton = Action(guide, "Dérogation manuelle", .06f, .015f, .94f, .095f);

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
        Label(maintenancePanel.transform, "VUE ÉQUIPEMENT · CLIQUEZ SUR LE COMPOSANT SÉLECTIONNÉ", 16, muted,
            .04f, .10f, .64f, .16f, TextAnchor.MiddleCenter);

        var work = Box("Maintenance card", maintenancePanel.transform, hudGlass, .70f, .17f, .98f, .85f);
        AddHudEdge(work);
        Label(work, "CONSIGNE", 17, accent, .07f, .87f, .93f, .97f);
        maintenanceTaskTitleText = Label(work, "Intervention", 24, Color.white,
            .07f, .69f, .93f, .86f);
        maintenanceExpectedStateText = Label(work, "", 20, muted, .07f, .47f, .93f, .68f);
        maintenanceCalibrationText = Label(work, "Sélectionnez un composant à calibrer.",
            18, muted, .07f, .30f, .93f, .46f);
        maintenanceComponentButton = Action(work, "Composant", .07f, .17f, .93f, .28f);
        startRestorationButton = Action(work, "Poursuivre la procédure", .07f, .03f, .93f, .15f, true);

        signaturePanel = Panel("Signature", true);
        var sign = Box("Signature card", signaturePanel.transform, hudGlass, .24f, .16f, .76f, .84f);
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
        var report = Box("Report card", reportPanel.transform, hudGlass, .24f, .21f, .76f, .78f);
        Label(report, "05 / TRAÇABILITÉ", 19, accent, .065f, .79f, .935f, .91f);
        Label(report, "Rapport d'intervention", 32, Color.white, .065f, .63f, .935f, .78f);
        reportUrlText = Label(report, "Rapport", 20, muted, .065f, .38f, .935f, .62f);
        openReportButton = Action(report, "Ouvrir le rapport PDF", .065f, .20f, .935f, .34f, true);
        restartButton = Action(report, "Nouvelle intervention", .065f, .04f, .935f, .18f);

        header.SetAsLastSibling();
        var status = Box("Status", safeRoot, hudGlass, .20f, .04f, .80f, .10f);
        AddHudEdge(status);
        statusBackgroundImage = status.GetComponent<Image>();
        statusText = Label(status, "Connexion…", 15, hudText, .03f, .08f, .97f, .92f, TextAnchor.MiddleCenter);
        statusText.resizeTextMinSize = 12;

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
        var p = Box(name, safeRoot, opaque ? new Color(ink.r,ink.g,ink.b,.18f) : Color.clear, 0, .14f, 1, .88f);
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
        text.resizeTextForBestFit = true; text.resizeTextMinSize = Mathf.Min(14, size); text.resizeTextMaxSize = size;
        text.lineSpacing = 1.05f;
        return text;
    }

    private Text ScrollableContext(Transform parent)
    {
        var viewport = Box("Published step context", parent, Color.clear, .06f, .36f, .94f, .67f);
        viewport.gameObject.AddComponent<Mask>().showMaskGraphic = false;
        var scroll = viewport.gameObject.AddComponent<ScrollRect>();
        scroll.horizontal = false;
        scroll.movementType = ScrollRect.MovementType.Clamped;
        scroll.viewport = viewport;
        var text = Label(viewport, "", 16, muted, 0, 0, 1, 1, TextAnchor.UpperLeft);
        text.resizeTextForBestFit = false;
        text.verticalOverflow = VerticalWrapMode.Overflow;
        text.rectTransform.anchorMin = new Vector2(0, 1);
        text.rectTransform.anchorMax = Vector2.one;
        text.rectTransform.pivot = new Vector2(.5f, 1);
        text.rectTransform.offsetMin = text.rectTransform.offsetMax = Vector2.zero;
        text.gameObject.AddComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;
        scroll.content = text.rectTransform;
        return text;
    }
    private Button Action(Transform parent, string title, float x0, float y0, float x1, float y1, bool primary = false)
    {
        var rect = Box(title, parent, primary ? new Color32(20, 83, 88, 245) : surface, x0, y0, x1, y1);
        if (primary) AddHudEdge(rect);
        var image = rect.GetComponent<Image>(); image.raycastTarget = true;
        var button = rect.gameObject.AddComponent<Button>(); button.targetGraphic = image;
        var colors = button.colors;
        colors.highlightedColor = new Color32(200, 255, 247, 255);
        colors.pressedColor = new Color32(145, 205, 210, 255);
        colors.disabledColor = new Color32(105, 132, 143, 255);
        button.colors = colors;
        Label(rect, title, 20, hudText, .04f, .06f, .96f, .94f, TextAnchor.MiddleCenter);
        return button;
    }

    private void AddHudEdge(RectTransform rect)
    {
        var edge = rect.gameObject.AddComponent<Outline>();
        edge.effectColor = new Color32(94, 234, 212, 55);
        edge.effectDistance = new Vector2(1f, -1f);
        edge.useGraphicAlpha = true;
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
        var rect = Box("Override reason", parent, surface, .06f, .11f, .94f, .20f);
        rect.GetComponent<Image>().raycastTarget = true;
        var field = rect.gameObject.AddComponent<InputField>();
        field.targetGraphic = rect.GetComponent<Image>();
        field.textComponent = Label(rect, "", 16, Color.white, .04f, .08f, .96f, .92f);
        field.placeholder = Label(rect, "Motif de dérogation…", 16, muted, .04f, .08f, .96f, .92f);
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
