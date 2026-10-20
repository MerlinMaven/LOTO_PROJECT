# Guide de Lancement Rapide — SmartLOTO MVP (Mode Local 100% Autonome)

Ce guide résume les commandes exactes pour démarrer et démontrer l'écosystème SmartLOTO complet sur votre machine locale, sans aucune dépendance Cloud externe.

---

## Architecture des Services et Ports

| Service | Rôle | Port | Commande de lancement |
| :--- | :--- | :--- | :--- |
| **Field Service** | API Runtime Unity, Inférence YOLO-World, Rapports PDF | **`8000`** | `uvicorn main:app --port 8000 --reload` |
| **Authoring Service** | Génération de procédures LLM (OSHA 1910.147) & Validation HSE | **`8001`** | `uvicorn main:app --port 8001 --reload` |
| **HSE Dashboard** | Console Web de supervision (React / Vite) | **`5173`** | `npm run dev` |
| **Unity App** | Client AR Meta Quest / Démo PC | *(Client)* | Cible automatiquement `http://127.0.0.1:8000` |

---

## Instructions de Démarrage (3 Terminaux)

Ouvrez 3 terminaux distincts dans le répertoire du projet `LOTO_PROJECT` :

### Terminal 1 : Field Service (API Terrain & Vision)
```bash
cd apps/field-service
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
- **Documentation Swagger :** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Fichiers statiques servis (photos & PDF) :** [http://127.0.0.1:8000/storage/](http://127.0.0.1:8000/storage/)
- *Note : Si `ultralytics` ou un GPU n'est pas disponible, le moteur bascule automatiquement sur le mode Mock intelligent pour garantir la fluidité de la démo.*

---

### Terminal 2 : Authoring Service (Génération LLM & Validation HSE)
```bash
cd apps/authoring-service
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```
- **Documentation Swagger :** [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
- *Note : Utilise par défaut le mode `stub` certifié OSHA (génération instantanée sans clé API requise).*

---

### Terminal 3 : HSE Dashboard (Console Web de Supervision)
```bash
cd apps/hse-dashboard
npm install
npm run dev
```
- **Accès à l'application :** [http://localhost:5173](http://localhost:5173)
- Le proxy interne est pré-configuré pour dialoguer directement avec l'Authoring Service sur le port 8001.

---

### Connexion du Client Unity (AR Meta Quest)
1. Ouvrez votre projet Unity dans l'éditeur.
2. Le composant `SmartLOTOClient.cs` est pré-paramétré avec l'URL :
   ```csharp
   backendUrl = "http://127.0.0.1:8000";
   ```
3. Lancez la scène (Play Mode ou build APK Quest). La procédure seed `PUMP-001` ("Pompe Principale d'Extraction") est déjà injectée dans la base locale et prête à être exécutée.

---

## Données et Persistance Locale
- **Base de données SQLite partagée :** `smartloto.db` (située à la racine du monorepo).
- **Stockage physique des fichiers :** `apps/field-service/storage/` (sous-dossiers `evidence/`, `signatures/`, `reports/`).
