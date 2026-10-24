using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

/// <summary>Pointer-driven signature surface used by the Unity operator HUD.</summary>
public sealed class SignaturePad : MonoBehaviour, IPointerDownHandler, IDragHandler, IPointerUpHandler
{
    [SerializeField] private int textureWidth = 1024;
    [SerializeField] private int textureHeight = 256;
    [SerializeField] private int strokeRadius = 4;

    private RawImage surface;
    private Texture2D texture;
    private Color32[] blankPixels;
    private bool drawing;
    private bool hasInk;
    private Vector2Int previousPixel;

    public bool HasInk => hasInk;

    public void Initialize(RawImage target)
    {
        surface = target;
        if (surface == null) return;

        texture = new Texture2D(textureWidth, textureHeight, TextureFormat.RGBA32, false);
        texture.name = "Operator signature";
        texture.wrapMode = TextureWrapMode.Clamp;
        texture.filterMode = FilterMode.Bilinear;
        blankPixels = new Color32[textureWidth * textureHeight];
        for (int i = 0; i < blankPixels.Length; i++) blankPixels[i] = Color.white;
        Clear();
        surface.texture = texture;
        surface.color = Color.white;
        surface.raycastTarget = true;
    }

    public void Clear()
    {
        if (texture == null) return;
        texture.SetPixels32(blankPixels);
        texture.Apply(false, false);
        drawing = false;
        hasInk = false;
    }

    public byte[] EncodeToPng()
    {
        if (!hasInk || texture == null) return null;
        texture.Apply(false, false);
        return texture.EncodeToPNG();
    }

    public void OnPointerDown(PointerEventData eventData)
    {
        if (TryGetPixel(eventData, out Vector2Int pixel))
        {
            drawing = true;
            previousPixel = pixel;
            DrawLine(pixel, pixel);
        }
    }

    public void OnDrag(PointerEventData eventData)
    {
        if (!drawing || !TryGetPixel(eventData, out Vector2Int pixel)) return;
        DrawLine(previousPixel, pixel);
        previousPixel = pixel;
    }

    public void OnPointerUp(PointerEventData eventData) => drawing = false;

    private bool TryGetPixel(PointerEventData eventData, out Vector2Int pixel)
    {
        pixel = default;
        if (surface == null || texture == null ||
            !RectTransformUtility.ScreenPointToLocalPointInRectangle(
                surface.rectTransform, eventData.position, eventData.pressEventCamera, out Vector2 local))
            return false;

        Rect rect = surface.rectTransform.rect;
        if (!rect.Contains(local) || rect.width <= 0 || rect.height <= 0) return false;
        float x = (local.x - rect.xMin) / rect.width;
        float y = (local.y - rect.yMin) / rect.height;
        pixel = new Vector2Int(
            Mathf.Clamp(Mathf.RoundToInt(x * (textureWidth - 1)), 0, textureWidth - 1),
            Mathf.Clamp(Mathf.RoundToInt(y * (textureHeight - 1)), 0, textureHeight - 1));
        return true;
    }

    private void DrawLine(Vector2Int from, Vector2Int to)
    {
        int steps = Mathf.Max(Mathf.Abs(to.x - from.x), Mathf.Abs(to.y - from.y));
        for (int step = 0; step <= steps; step++)
        {
            float t = steps == 0 ? 0f : (float)step / steps;
            int x = Mathf.RoundToInt(Mathf.Lerp(from.x, to.x, t));
            int y = Mathf.RoundToInt(Mathf.Lerp(from.y, to.y, t));
            DrawDot(x, y);
        }
        texture.Apply(false, false);
        hasInk = true;
    }

    private void DrawDot(int centerX, int centerY)
    {
        Color32 ink = new Color32(12, 22, 31, 255);
        int radiusSquared = strokeRadius * strokeRadius;
        for (int y = -strokeRadius; y <= strokeRadius; y++)
        {
            int py = centerY + y;
            if (py < 0 || py >= textureHeight) continue;
            for (int x = -strokeRadius; x <= strokeRadius; x++)
            {
                int px = centerX + x;
                if (px < 0 || px >= textureWidth || x * x + y * y > radiusSquared) continue;
                texture.SetPixel(px, py, ink);
            }
        }
    }

    private void OnDestroy()
    {
        if (texture != null) Destroy(texture);
    }
}
