using System;
using UnityEngine;
using UnityEngine.InputSystem;

public class MockupSequenceTester : MonoBehaviour
{
    [Header("29 images in timeline order")]
    public Texture2D[] sequenceImages;
    [Range(0, 28)] public int currentIndex;
    public Texture2D ActiveTexture { get; private set; }
    public int ImageCount => sequenceImages == null ? 0 : sequenceImages.Length;
    public event Action<Texture2D> TextureChanged;
    private int lastIndex = -1;
    private Renderer quadRenderer;
    private Material runtimeMaterial;
    private LotoUIController ui;

    private void Awake()
    {
        SortImagesNumerically();
    }

    private void Start()
    {
        gameObject.SetActive(true);
        if (ui == null) ui = FindAnyObjectByType<LotoUIController>();
        quadRenderer = GetComponent<Renderer>();
        if (quadRenderer != null) quadRenderer.enabled = true;
        SortImagesNumerically();
        currentIndex = 0;
        lastIndex = -1;
        ApplyTexture(0);
    }

    private void OnEnable()
    {
        if (quadRenderer == null) quadRenderer = GetComponent<Renderer>();
        if (quadRenderer != null) quadRenderer.enabled = true;
        if (ImageCount > 0)
        {
            int idx = Mathf.Clamp(currentIndex, 0, ImageCount - 1);
            ApplyTexture(idx);
        }
    }

    private void Update()
    {
        if (sequenceImages == null || sequenceImages.Length == 0) return;
        var keyboard = Keyboard.current;
        if (keyboard != null && !IsTextInputActive() && !IsShortcutPressed(keyboard) && !(ui != null && ui.SequenceBrowserOpen))
        {
            if (keyboard.fKey.wasPressedThisFrame)
                MoveImage(1);
            else if (keyboard.sKey.wasPressedThisFrame)
                MoveImage(-1);
        }
        if (currentIndex != lastIndex) ApplyTexture(currentIndex);
    }

    public void MoveImage(int delta)
    {
        if (ImageCount == 0) return;
        int next = Mathf.Clamp(currentIndex + delta, 0, ImageCount - 1);
        if (next != currentIndex) ApplyTexture(next);
    }

    public void ApplyTexture(int index)
    {
        if (sequenceImages == null || sequenceImages.Length == 0) return;
        index = Mathf.Clamp(index, 0, sequenceImages.Length - 1);
        if (sequenceImages[index] == null) return;
        if (quadRenderer == null) quadRenderer = GetComponent<Renderer>();
        if (quadRenderer == null) return;
        if (runtimeMaterial == null) runtimeMaterial = quadRenderer.material;
        if (runtimeMaterial == null) return;
        if (runtimeMaterial.HasProperty("_BaseMap")) runtimeMaterial.SetTexture("_BaseMap", sequenceImages[index]);
        if (runtimeMaterial.HasProperty("_MainTex")) runtimeMaterial.SetTexture("_MainTex", sequenceImages[index]);
        runtimeMaterial.mainTexture = sequenceImages[index];
        quadRenderer.enabled = true;
        currentIndex = lastIndex = index;
        ActiveTexture = sequenceImages[index];
        TextureChanged?.Invoke(ActiveTexture);
        Debug.Log("[VirtualMaquette] Image " + (index + 1) + "/" + sequenceImages.Length + " : " + ActiveTexture.name);
    }

    private bool IsTextInputActive()
    {
        // 1. IMGUI text controls (e.g. GUILayout.TextField in F8 panel)
        if (GUIUtility.keyboardControl != 0) return true;

        // 2. UI Controller explicit check (derogation reason input field)
        if (ui == null) ui = FindAnyObjectByType<LotoUIController>();
        if (ui != null && ui.IsTextInputFocused) return true;

        // 3. Unity EventSystem currently focused element (UI InputField or TextMeshPro TMP_InputField)
        var es = UnityEngine.EventSystems.EventSystem.current;
        if (es != null && es.currentSelectedGameObject != null)
        {
            var go = es.currentSelectedGameObject;
            var input = go.GetComponentInParent<UnityEngine.UI.InputField>();
            if (input != null && input.isFocused) return true;

            var tmp = go.GetComponentInParent<TMPro.TMP_InputField>();
            if (tmp != null && tmp.isFocused) return true;
        }

        return false;
    }

    private bool IsShortcutPressed(Keyboard keyboard)
    {
        if (keyboard == null) return false;
        return keyboard.ctrlKey.isPressed
            || keyboard.altKey.isPressed
            || keyboard.leftMetaKey.isPressed
            || keyboard.rightMetaKey.isPressed;
    }

    public void SortImagesNumerically()
    {
        if (sequenceImages == null || sequenceImages.Length <= 1) return;
        Array.Sort(sequenceImages, (a, b) =>
        {
            if (a == null && b == null) return 0;
            if (a == null) return -1;
            if (b == null) return 1;
            return NaturalCompare(a.name, b.name);
        });
    }

    public static int NaturalCompare(string a, string b)
    {
        if (ReferenceEquals(a, b)) return 0;
        if (a == null) return -1;
        if (b == null) return 1;

        string nameA = System.IO.Path.GetFileNameWithoutExtension(a);
        string nameB = System.IO.Path.GetFileNameWithoutExtension(b);

        int iA = 0, iB = 0;
        while (iA < nameA.Length && iB < nameB.Length)
        {
            char cA = nameA[iA];
            char cB = nameB[iB];

            if (char.IsDigit(cA) && char.IsDigit(cB))
            {
                int startA = iA;
                while (iA < nameA.Length && char.IsDigit(nameA[iA])) iA++;
                int startB = iB;
                while (iB < nameB.Length && char.IsDigit(nameB[iB])) iB++;

                string numStrA = nameA.Substring(startA, iA - startA);
                string numStrB = nameB.Substring(startB, iB - startB);

                long valA, valB;
                if (long.TryParse(numStrA, out valA) && long.TryParse(numStrB, out valB))
                {
                    int cmp = valA.CompareTo(valB);
                    if (cmp != 0) return cmp;
                }
                else
                {
                    int cmp = string.Compare(numStrA, numStrB, StringComparison.Ordinal);
                    if (cmp != 0) return cmp;
                }
            }
            else
            {
                int cmp = char.ToUpperInvariant(cA).CompareTo(char.ToUpperInvariant(cB));
                if (cmp != 0) return cmp;
                iA++;
                iB++;
            }
        }

        return nameA.Length.CompareTo(nameB.Length);
    }

#if UNITY_EDITOR
    private void OnValidate()
    {
        SortImagesNumerically();
    }
#endif

    private void OnDestroy()
    {
        if (runtimeMaterial != null) Destroy(runtimeMaterial);
    }
}
