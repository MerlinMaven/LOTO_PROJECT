# Spécification et Workflow de l'Application AR (Unity) — SmartLOTO

Ce document détaille l'architecture des écrans (Panels), le déroulement logique (Workflow) et le système de guidage holographique de l'application Unity. Il sert de base de référence pour uniformiser l'interface et lui appliquer un thème visuel cohérent.

---

## 1. Architecture des Écrans (Panels UI)

L'interface utilisateur de l'application Unity est structurée autour de **7 panneaux principaux** activés sélectivement par le script `LotoUIController.cs` :

| Nom du Panneau (`GameObject`) | Rôle & Composants Principaux |
| :--- | :--- |
| **`welcomePanel`** | **Écran d'Accueil** : Choix du mode d'initialisation de l'intervention.<br>• Bouton `chooseQRScanButton` (Scanner QR Code)<br>• Bouton `chooseManualButton` (Sélection Manuelle) |
| **`qrScanPanel`** | **Scanner QR Code** : Initialisation rapide en filmant le QR Code de la machine.<br>• Flux vidéo de la caméra (`RawImage` + `LotoQRScanner` avec bibliothèque ZXing)<br>• Bouton Retour `qrBackButton`<br>• Ligne laser animée de balayage `scanLaserLine` |
| **`manualSelectionPanel`** | **Sélection Manuelle** : Choix de la machine dans une liste déroulante si le scan n'est pas possible.<br>• Menu déroulant `machineIdDropdown`<br>• Bouton de démarrage `startButton`<br>• Bouton Retour `manualBackButton` |
| **`stepPanel`** | **Console d'Exécution des Étapes** : Écran central guidant l'opérateur dans la consignation ou déconsignation.<br>• Phase en cours `phaseTitleText` (Consignation / Déconsignation)<br>• Titre de l'étape `stageTitleText` et description de l'action `stepDescText`<br>• Consigne pour l'IA `visionPromptText` (ex: *cadenas rouge*, *disjoncteur*)<br>• Retour caméra en temps réel `cameraPreviewImage`<br>• Zone de texte pour le motif `overrideReasonInput`<br>• Bouton de détection IA `validateButton`<br>• Bouton de forçage manuel `overrideButton` |
| **`maintenancePanel`** | **Écran de Maintenance** : Transition invitant l'opérateur à réaliser ses réparations physiques une fois la machine consignée.<br>• Message d'instruction<br>• Bouton `startRestorationButton` (Débuter la Déconsignation) |
| **`signaturePanel`** | **Écran de Signature** : Validation de la fin de l'intervention par signature tactile.<br>• Zone de dessin/signature `signatureCanvas`<br>• Bouton `submitSignatureButton` (Clôturer l'intervention) |
| **`reportPanel`** | **Écran du Rapport** : Clôture avec accès au fichier d'audit.<br>• Zone d'affichage de l'URL `reportUrlText`<br>• Bouton `openReportButton` (Ouvrir le PDF dans le navigateur)<br>• Bouton `restartButton` (Retour à l'accueil) |

---

## 2. Déroulement du Workflow (Cycle de Vie)

Le diagramme ci-dessous décrit le workflow complet de l'application, de l'accueil jusqu'à la génération du rapport final :

```mermaid
flowchart TD
    Start([1. Démarrage de l'App]) --> Welcome{2. Mode d'Initialisation}
    
    Welcome -- QR Code Scan --> QRScan[Balayage de la machine via Caméra]
    Welcome -- Manuel --> SelectDropdown[Sélection de la machine dans la liste]
    
    QRScan -->|QR Détecté| FetchProc[3. Chargement de la Procédure Approved]
    SelectDropdown -->|Bouton Démarrer| FetchProc
    
    FetchProc --> StartInt[Envoi API POST /interventions/start]
    StartInt --> RunLockout[4. Phase 1 : Consignation Lockout]
    
    subgraph Etape_LOTO [Cycle d'une Action]
        direction TB
        ActiveGuide[Afficher Hologramme de Guidage 3D] --> ShowInstruction[Afficher instructions à l'écran]
        ShowInstruction --> UserAction[Réalisation de l'action physique par l'opérateur]
        UserAction --> DecisionVal{Mode de Validation}
        
        DecisionVal -- Valider IA --> YOLO[Caméra + API YOLO-World /validate-step]
        YOLO -->|Objet détecté| SuccessVal[Étape Validée ✅]
        YOLO -->|Non détecté| FailVal[Échec de détection ❌]
        
        DecisionVal -- Dérogation --> CheckReason{Motif renseigné ?}
        CheckReason -- Non --> AlertReason[Alerte : Motif requis] --> UserAction
        CheckReason -- Oui --> SendOverride[API POST /override-step + Motif] --> SuccessVal
    end
    
    RunLockout --> Etape_LOTO
    SuccessVal -->|Action suivante| Etape_LOTO
    
    SuccessVal -->|Toutes étapes lockout OK| MaintScreen[5. Phase de Maintenance Physique]
    MaintScreen -->|Bouton Restoration| RunRestor[6. Phase 3 : Déconsignation Restoration]
    
    RunRestor --> Etape_LOTO
    
    SuccessVal -->|Toutes étapes restoration OK| SigScreen[7. Signature Tactile de Clôture]
    SigScreen -->|Bouton Clôturer| SendClose[API POST /interventions/close + Signature]
    
    SendClose --> ReportScreen[8. Affichage du Rapport PDF et Clôture]
    ReportScreen -->|Bouton Recommencer| Start
```

---

## 3. Système de Guidage Holographique 3D

Pour aider visuellement l'opérateur en Réalité Mixte, le script `LotoHologramGuide.cs` génère un pointeur 3D dynamique :

1. **Calcul de Position (`LotoManager.cs`)** :
   * Le manager recherche un GameObject racine nommé `LOTO_Origin_Anchor` dans la scène Unity (qui sert d'origine spatiale calibrée via les ancres de la machine).
   * Pour chaque étape, il vérifie si la description ou l'invite visuelle correspond à un organe de la machine dont la position 3D est connue.
   * Il instancie un hologramme à la position correspondante relative à l'ancre d'origine.
2. **Forme Visuelle (`LotoHologramGuide.cs`)** :
   * L'hologramme est construit dynamiquement à l'aide de primitives géométriques : un **cylindre** (tige de la flèche) pointant vers le bas, surmonté d'une **sphère** (tête du pointeur).
   * Un shader transparent coloré (vert transparent par défaut) lui est appliqué pour lui donner un aspect de "projection holographique".
3. **Animations intégrées** :
   * **Rebond (Bouncing)** : La hauteur locale du pointeur oscille continuellement suivant une onde sinusoïdale (`Mathf.Sin(Time.time * bounceSpeed)`) pour attirer le regard.
   * **Rotation** : Le pointeur tourne sur son axe vertical à une vitesse constante (`Space.World`).

---

## 4. Charte Graphique Actuelle & Thème (UI System)

Le script `LotoUIController.cs` embarque une palette de couleurs premium pour piloter les retours utilisateur et les statuts système :

* **Gris Premium (`PremiumGray`)** : `#708097` — Écrans d'attente, états inactifs, neutres.
* **Vert Premium (`PremiumGreen`)** : `#2EC473` — Succès, étapes validées, fin de procédure.
* **Rouge Premium (`PremiumRed`)** : `#E64747` — Alertes, erreurs de détection, saisie manquante.
* **Bleu Premium (`PremiumBlue`)** : `#1E6EDB` — Notifications d'information, consignes de recherche.
* **Jaune/Ambre Premium (`PremiumYellow`)** : `#F29C12` — Attente de traitement API, traitements YOLO-World.

### Suggestions pour l'application d'un Thème Cohérent

Pour aligner l'application Unity avec le thème Streamlit (`config.toml` : `#1A365D` pour le bleu foncé primaire, `#2D3748` pour le texte foncé), nous pouvons :
1. **Remplacer `PremiumBlue`** par le bleu marine du thème : `new Color(0.10f, 0.21f, 0.36f)` (`#1A365D`).
2. **Utiliser une police géométrique moderne** (ex: *Outfit* ou *Inter*) sur tous les composants TextMeshPro de Unity.
3. **Ajouter un effet de Glassmorphism** (panneaux semi-transparents avec flou d'arrière-plan) pour renforcer l'esthétique premium de la réalité mixte.
4. **Donner à l'hologramme de guidage 3D** une couleur néon cyan/bleue vibrante assortie plutôt que le vert de base.
