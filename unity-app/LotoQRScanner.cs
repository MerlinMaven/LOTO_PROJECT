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

        WebCamTexture webcam = uiController.GetWebcamTexture();
        if (webcam == null || !webcam.isPlaying || webcam.width < 100) return;

        try
        {
            Color32[] pixels = webcam.GetPixels32();
            int width = webcam.width;
            int height = webcam.height;

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
            // Suppress errors during webcam initialization or resize
            Debug.LogWarning("QR Scan Warning: " + e.Message);
        }
    }

    private void ProcessScannedCode(string code)
    {
        // Try to match the scanned code with available machines in UI controller
        bool matchFound = uiController.SelectMachineById(code);
        
        if (matchFound)
        {
            uiController.ShowStatus($"QR Code détecté : {code}! Initialisation...", Color.green);
            isScanningActive = false; // Pause scanner
            
            // Auto start after a short delay so user can see the success status
            Invoke(nameof(TriggerAutoStart), 1.0f);
        }
        else
        {
            uiController.ShowStatus($"QR Code détecté : '{code}' (Non configurée en base)", Color.yellow);
        }
    }

    private void TriggerAutoStart()
    {
        uiController.TriggerStart();
    }

    // Call this when restarting or return to selection screen to resume scanning
    public void ResumeScanning()
    {
        isScanningActive = true;
    }
}
