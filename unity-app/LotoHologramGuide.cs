using UnityEngine;

public class LotoHologramGuide : MonoBehaviour
{
    [Header("Visual Settings")]
    [SerializeField] private Color hologramColor = new Color(0.18f, 0.77f, 0.45f, 0.6f); // Soft green with alpha
    [SerializeField] private float bounceSpeed = 3f;
    [SerializeField] private float bounceHeight = 0.08f;
    [SerializeField] private float rotateSpeed = 45f;

    private GameObject arrowVisual;
    private Vector3 baseLocalPosition;
    private bool surfaceGuide;
    private Mesh surfaceMesh;
    private Material surfaceMaterial;

    public void AttachToSurface(Transform model, Vector3 localPoint)
    {
        surfaceGuide = true;
        transform.SetParent(model, false);
        transform.localPosition = new Vector3(localPoint.x, localPoint.y, 0f);
        transform.localRotation = Quaternion.identity;
        Vector3 scale = model.lossyScale;
        transform.localScale = new Vector3(1f / Mathf.Max(Mathf.Abs(scale.x), .0001f),
            1f / Mathf.Max(Mathf.Abs(scale.y), .0001f), 1f / Mathf.Max(Mathf.Abs(scale.z), .0001f));
    }

    private void Start()
    {
        if (surfaceGuide)
        {
            surfaceMesh = new Mesh { name = "POI arrow on model" };
            surfaceMesh.vertices = new[] {
                new Vector3(0, 0, -.002f), new Vector3(.006f, .018f, -.002f),
                new Vector3(.018f, .006f, -.002f), new Vector3(.010f, .014f, -.002f),
                new Vector3(.026f, .030f, -.002f), new Vector3(.030f, .026f, -.002f),
                new Vector3(.014f, .010f, -.002f) };
            surfaceMesh.triangles = new[] { 0, 1, 2, 3, 4, 5, 3, 5, 6 };
            surfaceMesh.RecalculateBounds();
            gameObject.AddComponent<MeshFilter>().sharedMesh = surfaceMesh;
            Shader shader = Shader.Find("Sprites/Default");
            if (shader == null) return;
            surfaceMaterial = new Material(shader) { color = Color.yellow };
            gameObject.AddComponent<MeshRenderer>().sharedMaterial = surfaceMaterial;
            return;
        }
        baseLocalPosition = transform.localPosition;
        CreateArrowVisual();
    }

    private void CreateArrowVisual()
    {
        // Create a container
        arrowVisual = new GameObject("ArrowVisual");
        arrowVisual.transform.SetParent(this.transform, false);

        // Create shaft (Cylinder) pointing down
        GameObject shaft = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        Destroy(shaft.GetComponent<Collider>()); // No physics needed
        shaft.transform.SetParent(arrowVisual.transform, false);
        shaft.transform.localPosition = new Vector3(0f, 0.15f, 0f);
        shaft.transform.localScale = new Vector3(0.025f, 0.06f, 0.025f);

        // Create tip (Sphere) representing the pointer head
        GameObject tip = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        Destroy(tip.GetComponent<Collider>());
        tip.transform.SetParent(arrowVisual.transform, false);
        tip.transform.localPosition = new Vector3(0f, 0.05f, 0f);
        tip.transform.localScale = new Vector3(0.07f, 0.07f, 0.07f);

        // Apply a transparent/glowing color using standard Sprites-Default shader
        Material holoMat = new Material(Shader.Find("Sprites/Default"));
        if (holoMat == null)
        {
            holoMat = new Material(Shader.Find("Legacy Shaders/Transparent/Diffuse"));
        }
        
        if (holoMat != null)
        {
            holoMat.color = hologramColor;
            shaft.GetComponent<Renderer>().material = holoMat;
            tip.GetComponent<Renderer>().material = holoMat;
        }
    }

    private void Update()
    {
        if (surfaceGuide) return;
        // Bouncing animation
        float newY = baseLocalPosition.y + Mathf.Sin(Time.time * bounceSpeed) * bounceHeight;
        transform.localPosition = new Vector3(baseLocalPosition.x, newY, baseLocalPosition.z);

        // Rotation animation
        transform.Rotate(Vector3.up, rotateSpeed * Time.deltaTime, Space.World);
    }

    private void OnDestroy()
    {
        if (surfaceMesh != null) Destroy(surfaceMesh);
        if (surfaceMaterial != null) Destroy(surfaceMaterial);
    }
}
