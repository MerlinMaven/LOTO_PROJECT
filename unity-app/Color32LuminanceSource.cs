using System;
using UnityEngine;
using ZXing;

public class Color32LuminanceSource : LuminanceSource
{
    private readonly byte[] luminances;

    public Color32LuminanceSource(Color32[] colors, int width, int height) : base(width, height)
    {
        luminances = new byte[width * height];
        for (int y = 0; y < height; y++)
        {
            int unityY = height - 1 - y; // Invert Y axis: Unity starts at bottom, ZXing starts at top
            int zxingRowStart = y * width;
            int unityRowStart = unityY * width;
            for (int x = 0; x < width; x++)
            {
                Color32 c = colors[unityRowStart + x];
                luminances[zxingRowStart + x] = (byte)(c.r * 0.2126f + c.g * 0.7152f + c.b * 0.0722f);
            }
        }
    }

    // Constructor that does not require reallocation of luminance bytes
    public Color32LuminanceSource(byte[] lums, int width, int height) : base(width, height)
    {
        luminances = lums;
    }

    public override byte[] Matrix => luminances;

    public override byte[] getRow(int y, byte[] row)
    {
        int width = Width;
        if (row == null || row.Length < width)
        {
            row = new byte[width];
        }
        Array.Copy(luminances, y * width, row, 0, width);
        return row;
    }

    public override bool CropSupported => false;
    public override bool RotateSupported => false;
}
