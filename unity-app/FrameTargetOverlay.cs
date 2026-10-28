using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

// Targets use the canonical image, origin at top left. Fit without crop or mirror.
[RequireComponent(typeof(RawImage))]
public sealed class FrameTargetOverlay : MonoBehaviour
{
    public event System.Action<Vector2> Clicked;
    private RawImage outer, image, canonicalImage;
    private readonly List<GameObject> arrows = new List<GameObject>();
    private int width, height;
    public RectTransform ImageRect => image == null ? null : image.rectTransform;
    public void SetFrame(int w, int h, bool direct = false)
    {
        outer = GetComponent<RawImage>(); width = w; height = h;
        if (direct)
        {
            if (canonicalImage != null) canonicalImage.gameObject.SetActive(false);
            image = outer; Clear(); return;
        }
        image = canonicalImage;
        if (image == null)
        {
            var go = new GameObject("Canonical image", typeof(RectTransform), typeof(RawImage));
            go.transform.SetParent(transform, false); image = go.GetComponent<RawImage>(); canonicalImage = image; image.raycastTarget = false;
            go.transform.SetAsFirstSibling();
            image.raycastTarget = true;
            go.AddComponent<MaintenanceCalibrationSurface>().Clicked += pointer => {
                if (RectTransformUtility.ScreenPointToLocalPointInRectangle(image.rectTransform,
                    pointer.position, pointer.pressEventCamera, out Vector2 local))
                {
                    Rect r = image.rectTransform.rect;
                    if (r.width > 0 && r.height > 0 && r.Contains(local))
                        Clicked?.Invoke(new Vector2((local.x-r.xMin)/r.width, 1-(local.y-r.yMin)/r.height));
                }
            };
        }
        image.texture = outer.texture; image.color = Color.white;
        image.gameObject.SetActive(true);
        outer.color = Color.black; outer.texture = null;
        var fitter = outer.GetComponent<AspectRatioFitter>();
        if (fitter != null) fitter.enabled = false;
        Fit(); Clear();
    }
    private void LateUpdate() { Fit(); }
    private void Fit()
    {
        if (image == null || image == outer || width <= 0 || height <= 0) return;
        Rect bounds = outer.rectTransform.rect;
        float scale = Mathf.Min(bounds.width / width, bounds.height / height);
        var rect = image.rectTransform;
        rect.anchorMin = rect.anchorMax = new Vector2(.5f, .5f);
        rect.pivot = new Vector2(.5f, .5f); rect.anchoredPosition = Vector2.zero;
        rect.sizeDelta = new Vector2(width * scale, height * scale);
    }
    public void Clear()
    {
        foreach (var arrow in arrows) { arrow.SetActive(false); Destroy(arrow); }
        arrows.Clear();
    }
    public void ResetFrame()
    {
        Clear();
        if (image != null && image != outer) image.gameObject.SetActive(false);
    }
    public void Show(SmartLOTOClient.TargetData[] targets)
    {
        Clear();
        if (image == null) return;
        foreach (var t in targets ?? new SmartLOTOClient.TargetData[0])
        {
            if (t == null || !t.localization_clear || string.IsNullOrWhiteSpace(t.identification_feature)
                || string.IsNullOrEmpty(t.component_id) || float.IsNaN(t.x) || float.IsNaN(t.y)
                || float.IsNaN(t.confidence) || float.IsInfinity(t.confidence)
                || t.x < 0 || t.x > 1 || t.y < 0 || t.y > 1 || t.confidence < .8f) continue;
            var go = new GameObject("Target " + t.component_id, typeof(RectTransform), typeof(CanvasRenderer), typeof(FrameTargetArrow));
            go.transform.SetParent(image.transform, false);
            var rect = go.GetComponent<RectTransform>();
            rect.anchorMin = rect.anchorMax = new Vector2(t.x, 1 - t.y);
            rect.pivot = new Vector2(.5f, .5f); rect.anchoredPosition = Vector2.zero; rect.sizeDelta = new Vector2(60, 60);
            var arrow = go.GetComponent<FrameTargetArrow>(); arrow.raycastTarget = false; arrow.color = Color.yellow;
            arrow.Direction = new Vector2(t.x < .5f ? 1 : -1, t.y < .5f ? -1 : 1).normalized;
            arrows.Add(go);
        }
    }
}

// Tip is local (0,0). This designates a component; it never indicates movement.
[RequireComponent(typeof(CanvasRenderer))]
public sealed class FrameTargetArrow : Graphic
{
    public Vector2 Direction = new Vector2(-1, -1).normalized;
    protected override void OnPopulateMesh(VertexHelper vh)
    {
        vh.Clear(); Vector2 d = Direction, n = new Vector2(-d.y, d.x);
        Add(vh, Vector2.zero, d * 17 + n * 7, d * 17 - n * 7);
        Add(vh, d * 14 + n * 2, d * 45 + n * 2, d * 45 - n * 2);
        Add(vh, d * 14 + n * 2, d * 45 - n * 2, d * 14 - n * 2);
    }
    private void Add(VertexHelper vh, Vector2 a, Vector2 b, Vector2 c)
    {
        int i = vh.currentVertCount;
        vh.AddVert(a, color, Vector2.zero); vh.AddVert(b, color, Vector2.zero); vh.AddVert(c, color, Vector2.zero);
        vh.AddTriangle(i, i + 1, i + 2);
    }
}
