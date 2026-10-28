using System;
using UnityEngine;
using UnityEngine.UI;
using ZXing;

public class LotoQRScanner : MonoBehaviour
{
    [Header("UI & Logic References")]
    [SerializeField] private LotoUIController uiController;
    [SerializeField] private LotoManager lotoManager;

    [Header("Scanner Properties")]
    [SerializeField] private float scanInterval = 0.35f; // Scan every 350ms to save CPU
    
    private BarcodeReaderGeneric barcodeReader;
    private float nextScanTime = 0f;
    private bool isScanningActive = true;

    private void Start()
    {
        barcodeReader = new BarcodeReaderGeneric
        {
            AutoRotate = true,
            Options = new ZXing.Common.DecodingOptions
            {
                TryHarder = true,
                PossibleFormats = new System.Collections.Generic.List<BarcodeFormat> { BarcodeFormat.QR_CODE }
            }
        };

        if (uiController == null)
        {
            uiController = GetComponent<LotoUIController>();
        }
        if (lotoManager == null)
        {
            lotoManager = GetComponent<LotoManager>();
        }
    }

    private void Update()
    {
        // Only scan when on the selection screen, scanning is active, and it's time to scan
        if (!isScanningActive || Time.time < nextScanTime) return;
        
        // Check if QR scan screen is active
        if (uiController == null || !uiController.IsOnQRScanScreen()) return;

        nextScanTime = Time.time + scanInterval;

        Texture2D frame = uiController.ReadVirtualCameraFrame();
        if (frame == null) return;
        Texture2D readable = frame.isReadable ? frame : LotoUIController.CreateReadableTexture(frame);
        try
        {
            Color32[] pixels = readable.GetPixels32();
            int width = readable.width;
            int height = readable.height;
            // Decode in a background thread or main thread (main thread is fine since interval is large and image is small)
            LuminanceSource source = new Color32LuminanceSource(pixels, width, height);
            Result result = barcodeReader.Decode(source);

            if (result != null && !string.IsNullOrEmpty(result.Text))
            {
                string scannedCode = result.Text.Trim();
                Debug.Log($"[QR Scanner] Decoded code: '{scannedCode}'");
                ProcessScannedCode(scannedCode);
            }
        }
        catch (Exception e)
        {
            // A missing virtual frame never starts a physical device.
            Debug.LogWarning("QR Scan Warning: " + e.Message);
        }
        finally
        {
            if (readable != frame && readable != null) Destroy(readable);
            if (frame != null) Destroy(frame);
        }
    }

    private void ProcessScannedCode(string code)
    {
        code = ExtractProcedureId(code);
        if (string.IsNullOrEmpty(code))
        {
            uiController.ShowStatus("Ce QR code ne contient pas d'identifiant de procédure lisible.", Color.yellow);
            return;
        }
        // Try to match the scanned code with available machines in UI controller
        bool matchFound = uiController.SelectMachineById(code);
        
        if (matchFound)
        {
            uiController.ShowStatus($"QR Code détecté : {code}! Initialisation...", Color.green);
            isScanningActive = false; // Pause scanner
            
            uiController.IdentifyVirtualMaquette(code);
        }
        else
        {
            uiController.ShowStatus($"QR Code détecté : '{code}' (Non configurée en base)", Color.yellow);
        }
    }

    public void IdentifyVirtualMaquette()
    {
        isScanningActive = false;
        uiController.IdentifyVirtualMaquette("SL-POC-01");
    }

    [Serializable]
    private class QrPayload
    {
        public string machine_id;
        public string procedure_id;
        public string machineId;
        public string procedureId;
        public string id;
        public string url;
    }

    public static string ExtractProcedureId(string value)
    {
        if (string.IsNullOrWhiteSpace(value)) return null;
        value = value.Trim();
        if (value.StartsWith("{"))
        {
            try
            {
                var data = JsonUtility.FromJson<QrPayload>(value);
                value = SmartLOTOClient.FirstText(data.machine_id, data.procedure_id, data.machineId, data.procedureId, data.id, data.url);
            }
            catch (Exception) { return null; }
        }
        Uri uri;
        if (Uri.TryCreate(value, UriKind.Absolute, out uri) && (uri.Scheme == "http" || uri.Scheme == "https"))
        {
            string route = string.IsNullOrEmpty(uri.Fragment) ? uri.PathAndQuery : uri.Fragment.TrimStart('#');
            string query = route.Contains("?") ? route.Substring(route.IndexOf('?') + 1) : uri.Query.TrimStart('?');
            foreach (var part in query.Split('&'))
            {
                var pair = part.Split(new[] { '=' }, 2);
                if (pair.Length == 2 && (pair[0] == "machine_id" || pair[0] == "procedure_id" || pair[0] == "id"))
                    return Uri.UnescapeDataString(pair[1].Replace("+", " "));
            }
            string path = route.Split('?')[0];
            var segments = path.Split(new[] { '/' }, StringSplitOptions.RemoveEmptyEntries);
            for (int i = 0; i + 1 < segments.Length; i++)
                if (segments[i] == "procedures" || segments[i] == "machines" || segments[i] == "review")
                    return Uri.UnescapeDataString(segments[i + 1]);
            return null;
        }
        return string.IsNullOrWhiteSpace(value) || value.StartsWith("[") || value.StartsWith("{") ? null : value;
    }

    // Call this when restarting or return to selection screen to resume scanning
    public void ResumeScanning()
    {
        isScanningActive = true;
    }
}
