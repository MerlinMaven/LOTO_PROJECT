using System;
using UnityEngine;
using UnityEngine.EventSystems;

/// <summary>Forwards UI pointer clicks on the maintenance camera view to its calibrator.</summary>
public sealed class MaintenanceCalibrationSurface : MonoBehaviour, IPointerClickHandler
{
    public event Action<PointerEventData> Clicked;

    public void OnPointerClick(PointerEventData eventData)
    {
        Clicked?.Invoke(eventData);
    }
}
