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

    private void Start()
    {
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
        // Bouncing animation
        float newY = baseLocalPosition.y + Mathf.Sin(Time.time * bounceSpeed) * bounceHeight;
        transform.localPosition = new Vector3(baseLocalPosition.x, newY, baseLocalPosition.z);

        // Rotation animation
        transform.Rotate(Vector3.up, rotateSpeed * Time.deltaTime, Space.World);
    }
}
