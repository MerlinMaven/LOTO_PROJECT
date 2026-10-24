# Lancer SmartLOTO en local

Toutes les commandes ci-dessous partent de la racine `LOTO_PROJECT`, dans PowerShell.
Les deux API partagent `data/smartloto.db`. Aucun compte cloud n'est nécessaire pour
les démarrer ; l'analyse réelle d'un PDF nécessite une clé Groq ou Gemini.

## Préparer l'environnement

Prérequis : Python 3.10+ et Node.js 20+. Créer un environnement Python commun :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r apps/authoring-service/requirements.txt -r apps/field-service/requirements.txt
npm.cmd --prefix apps/hse-dashboard ci
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Dans `.env`, conserver les éventuelles clés existantes et définir :

```dotenv
DATABASE_URL=sqlite+aiosqlite:///data/smartloto.db
```

Les chemins SQLite relatifs sont résolus depuis la racine, même si l'API est lancée
depuis son propre dossier. `DATABASE_URL` a priorité sur `SQLITE_DB_PATH`.
Le `.env` racine est découvert par les deux API ; un `.env` dans un service peut
le masquer et les variables du terminal ont priorité. Ne pas configurer deux bases
différentes. `data/` est intégralement ignoré par Git.

Le modèle YOLO est attendu dans `apps/field-service/weights/yolov8s-worldv2.pt`.
Sans `YOLO_MODEL_PATH`, le chemin absolu par défaut est utilisé. Pour personnaliser
ce chemin, un chemin relatif est résolu depuis `apps/field-service/` ; pour
`LOCAL_STORAGE_DIR`, utiliser un chemin absolu dans `.env`.
Si les poids sont absents, le service démarre mais les contrôles de vision retournent
un résultat indéterminé. Tesseract OCR doit être installé pour les PDF scannés.

## Démarrer les trois services

Ouvrir trois terminaux à la racine et activer `.venv` dans chacun.

Terminal 1 — authoring-service :

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --app-dir apps/authoring-service --host 0.0.0.0 --port 8001 --reload --reload-dir apps/authoring-service/app
```

Terminal 2 — field-service :

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --app-dir apps/field-service --host 0.0.0.0 --port 8000 --reload --reload-dir apps/field-service/app
```

Terminal 3 — hse-dashboard :

```powershell
npm.cmd --prefix apps/hse-dashboard run dev -- --host 0.0.0.0 --port 5173 --strictPort
```

| Service | Application / santé | Documentation |
|---|---|---|
| Authoring | http://127.0.0.1:8001/health | http://127.0.0.1:8001/docs |
| Field | http://127.0.0.1:8000/health | http://127.0.0.1:8000/docs |
| Dashboard | http://localhost:5173 | Proxy `/api` vers `http://localhost:8001` |

Le worker documentaire démarre et s'arrête avec authoring-service.
Pour lancer seulement les deux API en arrière-plan, depuis un terminal activé :

```powershell
.\scripts\start_backend.ps1
# Alternative cmd.exe : scripts\start_backend.bat
```

Unity utilise field-service sur `http://127.0.0.1:8000` en Play Mode sur le PC.
Sur un casque, configurer `backendUrl` avec l'IP LAN du PC, par exemple
`http://192.168.1.10:8000`. Les sources Unity et les contrats dans
`unity-app/Assets/StreamingAssets/` restent à leur emplacement initial.

## Réinitialiser la démo

Arrêter les deux API avec `Ctrl+C` avant de réinitialiser. Le script vide toutes
les tables applicatives de la base configurée et supprime les PDF importés,
preuves, signatures et rapports locaux dans les dossiers standard des services.
Les PDF de référence et les contrats Unity sont conservés. Si le stockage a été
personnalisé via `LOCAL_STORAGE_DIR`, le script ne nettoie pas cet emplacement.

Sauvegarder la base, puis lancer le script depuis la racine :

```powershell
New-Item -ItemType Directory -Force data/backups | Out-Null
if (Test-Path data/smartloto.db) {
    Copy-Item data/smartloto.db (Join-Path data/backups ("smartloto-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.db'))
}
python scripts/reset_db.py
```

Relancer ensuite les API. Elles créent les tables manquantes, sans injecter de
procédure de démonstration. Après un reset, régénérer et faire approuver la procédure
avant une nouvelle intervention Unity. Le script utilise le même résolveur de base
que authoring-service et refuse les URL PostgreSQL.

## Régénérer ou vérifier SL-POC-01

Le PDF source est conservé dans
`apps/authoring-service/data/reference/SmartLOTO_SL-POC-01_Dossier_Technique_Descriptif.pdf`.
Le JSON `SL-POC-01-bulb-replacement.draft.json` dans le même dossier est une référence,
pas une procédure automatiquement injectée au démarrage.

Pour une génération réelle, renseigner `GROQ_API_KEY` et
`DOCUMENT_GENERATION_PROVIDER=groq`, ou `GEMINI_API_KEY` et
`DOCUMENT_GENERATION_PROVIDER=gemini`, puis redémarrer authoring-service.
Importer le PDF dans la page de génération du dashboard, ou utiliser :

```powershell
curl.exe --fail-with-body -X POST "http://127.0.0.1:8001/api/v1/generation/documents" -H "X-User-Id: demo-hse" -F "file=@apps/authoring-service/data/reference/SmartLOTO_SL-POC-01_Dossier_Technique_Descriptif.pdf;type=application/pdf"
```

La réponse `202` contient `job_id`. Remplacer `<job_id>` ci-dessous :

```powershell
curl.exe --fail-with-body "http://127.0.0.1:8001/api/v1/generation/jobs/<job_id>" -H "X-User-Id: demo-hse"
```

Attendre `succeeded`, puis relire, résoudre les clarifications, approuver et publier
la révision dans le dashboard. Une génération seule ne publie pas la procédure.
Sur une base existante, l'import d'un document déjà traité peut retourner la tâche
existante ; utiliser la remise à zéro pour un parcours de démo entièrement neuf.

Vérifications sans appel au fournisseur LLM :

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8000/procedures/SL-POC-01
python scripts/verify_contract.py
```

La lecture terrain nécessite que `SL-POC-01` soit présent et publié. Le vérificateur
contrôle les deux contrats statiques livrés dans `docs/contracts/` et
`unity-app/Assets/StreamingAssets/` ; il ne les régénère pas. Pour réexporter une
procédure revue et publiée (cette commande remplace les deux contrats) :

```powershell
curl.exe --fail-with-body "http://127.0.0.1:8001/api/v1/procedures/SL-POC-01/export" -o docs/contracts/SL-POC-01_unity_contract.json
if ($LASTEXITCODE -eq 0) {
    Copy-Item docs/contracts/SL-POC-01_unity_contract.json unity-app/Assets/StreamingAssets/SL-POC-01_unity_contract.json
    python scripts/verify_contract.py
}
```

Le contrôle statique attend la structure du scénario de référence (sept composants,
au moins quatre phases). Un brouillon nouvellement généré peut nécessiter une revue
pour atteindre cette structure.

Les utilitaires existants restent disponibles :

```powershell
# Migration ponctuelle des citations en base ; modifie les versions existantes.
python scripts/patch_sl_poc_01.py SL-POC-01
# Parcours terrain avec création d'une intervention, preuve et rapport PDF.
# À exécuter sur une démo publiée ; écrit dans la base et le stockage terrain.
python scripts/test_field_api.py
```

La migration des citations n'est pas une commande de génération et n'est pas
nécessaire au démarrage. Les tests unitaires terrain et le build UI se lancent avec :

```powershell
Push-Location apps/field-service
python -m pytest tests -q
Pop-Location
npm.cmd --prefix apps/hse-dashboard run build
```

## Emplacements après rangement

| Ancien chemin | Chemin actuel |
|---|---|
| `patch_sl_poc_01.py` | `scripts/patch_sl_poc_01.py` |
| `reset_db.py` | `scripts/reset_db.py` |
| `verify_contract.py` | `scripts/verify_contract.py` |
| `test_field_api.py` | `scripts/test_field_api.py` |
| `start_backend.ps1`, `start_backend.bat` | `scripts/start_backend.ps1`, `scripts/start_backend.bat` |
| Les trois PNG `SmartLOTO*` de la racine | `docs/assets/branding/` (noms conservés) |
| `smartloto.db` à la racine | `data/backups/smartloto.root-before-cleanup.db` |
| Base active des deux API | `data/smartloto.db` |

Les deux bases initiales avaient la même empreinte SHA-256 ; la copie de la racine
est conservée comme sauvegarde. Les images utilisées par l'UI restent dans
`apps/hse-dashboard/public/`, notamment `/logo-smartloto.png`.
Les scripts DB partagent `scripts/workspace_paths.py` ; `.env`, `.env.example`,
les configurations SQLite des deux API, les lanceurs et les liens de documentation
utilisent les nouveaux chemins.

## Vérifications du rangement

- Démarrage des deux API sur 8000/8001, réponses `/health` et lecture de
  `SL-POC-01` : OK. Export du contrat par authoring-service : OK.
- Démarrage Vite sur 5173, images publiques et proxy `/api` : OK.
- Build du dashboard : OK. Le sandbox OneDrive a nécessité une relance autorisée.
- Vérification des deux contrats statiques et parcours `scripts/test_field_api.py`
  (création, confirmation avec preuve, clôture et rapport PDF) : OK.
- Migration des citations et nettoyage DB/stockage : vérifiés sur une copie jetable.
  La base active conserve son empreinte SHA-256 initiale.
- Tests locaux authoring-service : 27 réussis, hors test appelant réellement le LLM.
- Tests field-service : 4 réussis, 1 échec dans
  `test_canonical_v2_keeps_arbitrary_phases_methods_and_source_payload` : le test
  attend un workflow identique alors que le sérialiseur le normalise. Ni ce test
  ni le sérialiseur n'ont été modifiés pendant le rangement.

Une compilation Unity/Quest et une nouvelle génération réelle par le fournisseur
LLM n'ont pas été exécutées. Les sources C# et les contrats Unity sont inchangés.
