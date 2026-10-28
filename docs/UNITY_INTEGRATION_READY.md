# Unity integration — source bundle

`unity-app/` contains the C# client sources, an editor utility and StreamingAssets
fixtures. It does **not** contain `Packages/`, `ProjectSettings/`, scenes, prefabs or
an Android build. Open a configured host project rather than treating this folder
as a standalone Unity project.

## Host project requirements

Use the Unity version and XR/render-pipeline configuration of your existing host
project. The source references Unity UI (`UnityEngine.UI`), the Input System
(`UnityEngine.InputSystem`) and ZXing (`ZXing.Net`). Those dependencies must be
installed in the host project. No package manifest or version is inferred here.

For a new integration, import the root `unity-app/*.cs` scripts into a dedicated
scripts folder, `unity-app/Assets/Editor/` into an editor-only folder, and the contents
of `unity-app/Assets/StreamingAssets/` into the host's `Assets/StreamingAssets/`.
Import each script once. The repository-root editor export is a local duplicate;
the canonical copy is `unity-app/Assets/Editor/SmartLotoCleaner.cs`.

For an existing integration, update the scripts at their existing locations.
Preserve the host's `.meta` files and scene references. This source bundle contains
no `.meta` files; newly imported assets receive their GUIDs in the host project.
Track those generated `.meta` files with their assets in that project's repository.
Never commit Unity `Library/`, `Temp/`, `Obj/`, `Build/`, `Builds/`, `Logs/` or
`UserSettings/` caches.

## Launch and configure

```powershell
$unityEditor = 'C:\Program Files\Unity\Hub\Editor\<installed-version>\Editor\Unity.exe'
$unityProject = 'C:\path\to\your\SmartLOTOUnityProject'
& $unityEditor -projectPath $unityProject
```

1. Start the APIs and HSE console using [LAUNCH.md](../LAUNCH.md).
2. Wire the receiving scene's serialized references for `LotoUIController`,
   `LotoManager`, `SmartLOTOClient`, `LotoQRScanner`, guidance and signature UI.
3. Set `SmartLOTOClient.backendUrl` to `http://127.0.0.1:8000` for desktop Play Mode,
   or the server's reachable LAN address for a headset. Set backend `BASE_URL` to
   that same reachable address for report/evidence links.
4. Load an HSE-published procedure through the normal selection or QR flow. A test
   contract file is not a substitute for a published procedure in the backend.
5. Execute the methods specified by the pinned revision, then close with the
   operator signature and inspect the returned PDF.

The [synthetic sequence guide](../apps/authoring-service/data/reference/SmartLOTO_sequence_A09_corrigee/GUIDE_UNITY.md)
describes optional rendered-Quad fixtures. Keep test imagery and draft review
separate from a real intervention. No editor scene, XR build or headset run was
performed as part of this documentation/repository release preparation.

## Contracts

The [API reference](unity_api_contracts.md) links the implemented DTOs and tests.
The C01–C07 sample matrices remain at:

- [Documentation snapshot](contracts/SL-POC-01_unity_contract.json)
- [StreamingAssets snapshot](../unity-app/Assets/StreamingAssets/SL-POC-01_unity_contract.json)

These are demonstration fixtures. The backend exports the components and rules of
the selected procedure; it does not replace arbitrary equipment with this sample.
