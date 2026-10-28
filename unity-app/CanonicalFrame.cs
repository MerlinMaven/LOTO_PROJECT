using System;
using UnityEngine;

// Unity pixel arrays use a bottom-left origin. Normalize webcam mirror BEFORE clockwise rotation.
public static class CanonicalFrame
{
    public static Color32[] Transform(Color32[] source, int width, int height, int rotation, bool mirrorY,
        out int outputWidth, out int outputHeight)
    {
        rotation = ((rotation % 360) + 360) % 360;
        if (rotation % 90 != 0 || width <= 0 || height <= 0 || source == null || source.Length != width * height)
            throw new ArgumentException("Invalid canonical frame dimensions or rotation");
        outputWidth = rotation % 180 == 0 ? width : height;
        outputHeight = rotation % 180 == 0 ? height : width;
        var output = new Color32[source.Length];
        for (int y = 0; y < outputHeight; y++) for (int x = 0; x < outputWidth; x++)
        {
            int sx = x, sy = y;
            if (rotation == 90) { sx = width - 1 - y; sy = x; }
            if (rotation == 180) { sx = width - 1 - x; sy = height - 1 - y; }
            if (rotation == 270) { sx = y; sy = height - 1 - x; }
            if (mirrorY) sy = height - 1 - sy;
            output[y * outputWidth + x] = source[sy * width + sx];
        }
        return output;
    }
}
