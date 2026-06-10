import os
import json
import base64
import numpy as np
import cv2
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client, Client
from ultralytics import YOLO

# Pour la génération du PDF d'audit
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Charger les variables d'environnement
load_dotenv()

app = FastAPI(
    title="SmartLOTO API",
    description="Backend d'assistance cognitive AR/MR pour la consignation industrielle (LOTO)",
    version="1.0.0"
)

# Activer CORS pour les requêtes provenant du casque AR (Unity) ou du tableau de bord
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialisation Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("⚠️ Supabase non configuré. Renseignez SUPABASE_URL et SUPABASE_KEY dans le fichier .env.")
    db: Optional[Client] = None
else:
    try:
        db = create_client(supabase_url, supabase_key)
        print("✅ Client Supabase connecté avec succès.")
    except Exception as e:
        print(f"❌ Erreur de connexion Supabase : {e}")
        db = None

# Chargement du modèle de fondation visuelle YOLO-World (Zero-Shot)
print("📦 Chargement du modèle YOLO-World en cours...")
try:
    # Utilisation de yolov8s-worldv2 pour de meilleures performances CPU/mémoire en local
    model = YOLO('yolov8s-worldv2.pt')
    print("✅ Modèle YOLO-World chargé avec succès.")
except Exception as e:
    print(f"❌ Erreur lors du chargement de YOLO-World : {e}")
    model = None

# --- Modèles de Données Pydantic ---

class ActionValidation(BaseModel):
    intervention_id: str
    stage_id: int
    action_id: str
    image_base64: str  # Image capturée par l'opérateur (Quest 2)
    vision_prompt: str  # Invite visuelle (ex: "red pen", "black switch")

class ActionOverride(BaseModel):
    intervention_id: str
    stage_id: int
    action_id: str
    image_base64: str
    reason: str

class StartIntervention(BaseModel):
    machine_id: str
    operator_name: str

class CloseIntervention(BaseModel):
    intervention_id: str
    signature_base64: str

class AnchorItem(BaseModel):
    organ_name: str
    pos_x: float
    pos_y: float
    pos_z: float
    rot_x: float
    rot_y: float
    rot_z: float

class AnchorsUpdate(BaseModel):
    anchors_list: List[AnchorItem]


# --- Fonctions Helpers ---

def decode_base64_image(base64_str: str) -> np.ndarray:
    """Décode une image base64 en image OpenCV."""
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    img_data = base64.b64decode(base64_str)
    nparr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img, img_data

def upload_to_supabase_storage(file_bytes: bytes, file_path: str, content_type: str = "image/jpeg") -> str:
    """Téléverse un fichier brut dans le bucket Supabase et renvoie l'URL publique."""
    if not db:
        raise HTTPException(status_code=500, detail="Supabase non disponible.")
    
    try:
        bucket_name = "smartloto-assets"
        # Téléversement via l'API Storage
        db.storage.from_(bucket_name).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": content_type, "x-upsert": "true"}
        )
        # Obtenir l'URL publique
        url_res = db.storage.from_(bucket_name).get_public_url(file_path)
        return url_res
    except Exception as e:
        print(f"Erreur lors du téléversement vers le bucket : {e}")
        # En cas d'erreur de stockage, on tente de continuer
        return ""

# --- API Routes ---

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "SmartLOTO API",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/procedures")
async def list_procedures():
    """Récupère toutes les procédures approuvées."""
    if not db:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")
    
    res = db.table("procedures").select("machine_id, machine_name").eq("status", "APPROVED").execute()
    return res.data

@app.get("/procedures/{machine_id}")
async def get_procedure(machine_id: str):
    """Récupère une procédure approuvée et figée."""
    if not db:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")
    
    res = db.table("procedures").select("*").eq("machine_id", machine_id).eq("status", "APPROVED").execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Aucune procédure approuvée trouvée pour la machine {machine_id}.")
    
    return res.data[0]

@app.post("/interventions/start")
async def start_intervention(data: StartIntervention):
    """Démarre une nouvelle intervention de maintenance (LOTO)."""
    if not db:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")
    
    # Vérifier que la procédure existe
    p_res = db.table("procedures").select("*").eq("machine_id", data.machine_id).eq("status", "APPROVED").execute()
    if not p_res.data:
        raise HTTPException(status_code=404, detail="Procédure non trouvée ou non approuvée.")
    
    try:
        new_int = {
            "machine_id": data.machine_id,
            "operator_name": data.operator_name,
            "status": "IN_PROGRESS",
            "current_stage_id": 1,
            "logs": []
        }
        res = db.table("interventions").insert(new_int).execute()
        return {"status": "success", "intervention": res.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/interventions/validate-step")
async def validate_step(data: ActionValidation):
    """Valide une étape de consignation par détection visuelle assistée par YOLO-World."""
    if not db:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")
    if not model:
        raise HTTPException(status_code=500, detail="Modèle YOLO-World indisponible.")

    # 1. Décoder l'image
    try:
        img, img_bytes = decode_base64_image(data.image_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image base64 invalide : {e}")

    # 2. Inférence YOLO-World (Zero-Shot)
    # Définir dynamiquement la classe à rechercher
    model.set_classes([data.vision_prompt])
    results = model.predict(img, conf=0.45) # Confiance de 45% pour le test
    
    boxes = results[0].boxes
    is_detected = len(boxes) > 0

    # 3. Uploader l'image de preuve
    filename = f"evidence/{data.intervention_id}_stage_{data.stage_id}_act_{data.action_id}.jpg"
    img_url = upload_to_supabase_storage(img_bytes, filename)

    # 4. Charger l'intervention en cours pour mettre à jour les logs
    int_res = db.table("interventions").select("*").eq("id", data.intervention_id).execute()
    if not int_res.data:
        raise HTTPException(status_code=404, detail="Intervention non trouvée.")
    
    intervention = int_res.data[0]
    logs = intervention.get("logs", [])
    if not isinstance(logs, list):
        logs = []

    # Ajouter le log
    new_log = {
        "timestamp": datetime.now().isoformat(),
        "stage_id": data.stage_id,
        "action_id": data.action_id,
        "action_description": f"Vérification de '{data.vision_prompt}'",
        "type": "vision_detection",
        "success": is_detected,
        "image_url": img_url,
        "details": f"Confiance détection : {float(boxes[0].conf[0]):.2f}" if is_detected else "Non détecté"
    }
    logs.append(new_log)

    # Mettre à jour l'intervention
    update_data = {"logs": logs}
    if is_detected:
        # Avancer l'étape actuelle si validation réussie
        # Dans un MVP, on laisse le client Quest gérer la transition ou on l'incrémente ici
        pass
        
    db.table("interventions").update(update_data).eq("id", data.intervention_id).execute()

    return {
        "verified": is_detected,
        "message": "Proxy de condamnation détecté avec succès" if is_detected else "Objet non détecté ou visuel non conforme",
        "image_url": img_url
    }

@app.post("/interventions/override-step")
async def override_step(data: ActionOverride):
    """Validation manuelle avec signature/preuve en cas de mauvaise détection de l'IA (mode dégradé)."""
    if not db:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")

    # 1. Décoder l'image de preuve
    try:
        _, img_bytes = decode_base64_image(data.image_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image base64 invalide : {e}")

    # 2. Uploader l'image de preuve
    filename = f"evidence/{data.intervention_id}_stage_{data.stage_id}_act_{data.action_id}_override.jpg"
    img_url = upload_to_supabase_storage(img_bytes, filename)

    # 3. Charger l'intervention en cours
    int_res = db.table("interventions").select("*").eq("id", data.intervention_id).execute()
    if not int_res.data:
        raise HTTPException(status_code=404, detail="Intervention non trouvée.")
    
    intervention = int_res.data[0]
    logs = intervention.get("logs", [])
    if not isinstance(logs, list):
        logs = []

    # Ajouter le log de dérogation
    new_log = {
        "timestamp": datetime.now().isoformat(),
        "stage_id": data.stage_id,
        "action_id": data.action_id,
        "action_description": "Dérogation manuelle par l'opérateur",
        "type": "manual_override_with_evidence",
        "success": True,
        "image_url": img_url,
        "details": f"Raison de la dérogation : {data.reason}"
    }
    logs.append(new_log)

    db.table("interventions").update({"logs": logs}).eq("id", data.intervention_id).execute()

    return {
        "verified": True,
        "message": "Dérogation manuelle enregistrée avec succès.",
        "image_url": img_url
    }

@app.post("/interventions/close")
async def close_intervention(data: CloseIntervention):
    """Clôture l'intervention, génère la signature numérique et produit le rapport d'audit PDF."""
    if not db:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")

    # 1. Charger l'intervention
    int_res = db.table("interventions").select("*").eq("id", data.intervention_id).execute()
    if not int_res.data:
        raise HTTPException(status_code=404, detail="Intervention non trouvée.")
    
    intervention = int_res.data[0]
    machine_id = intervention.get("machine_id")

    # Charger la procédure correspondante
    p_res = db.table("procedures").select("*").eq("machine_id", machine_id).execute()
    machine_name = p_res.data[0].get("machine_name") if p_res.data else "Machine Inconnue"

    # 2. Uploader la signature
    try:
        _, sig_bytes = decode_base64_image(data.signature_base64)
        sig_filename = f"signatures/{data.intervention_id}_signature.png"
        sig_url = upload_to_supabase_storage(sig_bytes, sig_filename, content_type="image/png")
    except Exception as e:
        print(f"Erreur de décodage de la signature : {e}")
        sig_url = ""

    # 3. Générer le rapport PDF d'audit
    pdf_filename = f"reports/Audit_Report_{data.intervention_id}.pdf"
    pdf_local_path = f"scratch_report_{data.intervention_id}.pdf"
    
    # Créer le PDF localement
    doc = SimpleDocTemplate(pdf_local_path, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Styles personnalisés
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=22,
        textColor=colors.HexColor('#1A365D'),
        spaceAfter=15
    )
    
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.HexColor('#2B6CB0'),
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = styles['BodyText']

    elements = []
    
    # Titre du rapport
    elements.append(Paragraph("SmartLOTO - Rapport d'Audit HSE", title_style))
    elements.append(Paragraph(f"Généré automatiquement le : {datetime.now().strftime('%d/%m/%Y à %H:%M')}", body_style))
    elements.append(Spacer(1, 15))
    
    # Informations générales
    info_data = [
        [Paragraph("<b>Identifiant Intervention :</b>", body_style), Paragraph(data.intervention_id, body_style)],
        [Paragraph("<b>Code Machine :</b>", body_style), Paragraph(machine_id, body_style)],
        [Paragraph("<b>Nom Machine :</b>", body_style), Paragraph(machine_name, body_style)],
        [Paragraph("<b>Opérateur :</b>", body_style), Paragraph(intervention.get("operator_name"), body_style)],
        [Paragraph("<b>Début d'intervention :</b>", body_style), Paragraph(intervention.get("started_at"), body_style)],
        [Paragraph("<b>Fin d'intervention :</b>", body_style), Paragraph(datetime.now().isoformat(), body_style)],
    ]
    
    t_info = Table(info_data, colWidths=[150, 300])
    t_info.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F7FAFC')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 15))
    
    # Journal des étapes validées
    elements.append(Paragraph("Journal d'Audit des Étapes", h2_style))
    
    logs = intervention.get("logs", [])
    log_rows = [["Horodatage", "Étape", "Action", "Type", "Résultat"]]
    
    for log in logs:
        log_rows.append([
            log.get("timestamp")[11:19],
            f"Stage {log.get('stage_id')}",
            log.get("action_description"),
            log.get("type"),
            "Succès (IA)" if log.get("success") and log.get("type") == "vision_detection" else ("Dérogation" if log.get("type") == "manual_override_with_evidence" else "Échec")
        ])
        
    t_logs = Table(log_rows, colWidths=[70, 60, 150, 100, 70])
    t_logs.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2B6CB0')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 5),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    elements.append(t_logs)
    elements.append(Spacer(1, 20))
    
    # Signature
    elements.append(Paragraph("Signature de l'opérateur", h2_style))
    if sig_url:
        elements.append(Paragraph("Signature numérique apposée à la clôture de la checklist AR :", body_style))
        elements.append(Spacer(1, 5))
        # Pour le PDF, on peut essayer de télécharger temporairement la signature ou la mettre directement si stockée en local
        # Comme la signature est en base64, on peut l'écrire localement pour l'inclure dans le PDF
        sig_local_path = f"sig_temp_{data.intervention_id}.png"
        with open(sig_local_path, "wb") as f:
            f.write(sig_bytes)
        try:
            elements.append(Image(sig_local_path, width=150, height=75))
        except Exception as img_err:
            elements.append(Paragraph(f"[Erreur rendu image signature: {img_err}]", body_style))
    else:
        elements.append(Paragraph("Aucune signature fournie.", body_style))
        
    # Construire le document PDF
    doc.build(elements)
    
    # Lire le fichier PDF généré
    with open(pdf_local_path, "rb") as f:
        pdf_bytes = f.read()
        
    # Téléverser sur Supabase Storage
    pdf_url = upload_to_supabase_storage(pdf_bytes, pdf_filename, content_type="application/pdf")
    
    # Supprimer les fichiers temporaires locaux
    if os.path.exists(pdf_local_path):
        os.remove(pdf_local_path)
    if 'sig_local_path' in locals() and os.path.exists(sig_local_path):
        os.remove(sig_local_path)

    # 4. Mettre à jour l'intervention à COMPLETED
    update_int = {
        "status": "COMPLETED",
        "signature_url": sig_url,
        "pdf_report_url": pdf_url,
        "completed_at": datetime.now().isoformat()
    }
    db.table("interventions").update(update_int).eq("id", data.intervention_id).execute()

    return {
        "status": "success",
        "message": "Intervention clôturée avec succès et rapport PDF généré.",
        "pdf_report_url": pdf_url
    }

@app.post("/procedures/{machine_id}/anchors")
async def update_procedure_anchors(machine_id: str, data: AnchorsUpdate):
    """Met à jour les points d'ancrage spatial calibrés pour une procédure spécifique."""
    if not db:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")
        
    # Charger la procédure existante
    res = db.table("procedures").select("*").eq("machine_id", machine_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Procédure non trouvée pour la machine {machine_id}.")
        
    proc = res.data[0]
    stages = proc.get("workflow_stages", {})
    if not isinstance(stages, dict):
        stages = {"lockout": [], "restoration": []}
        
    # Convertir la liste d'ancrages en dictionnaire pour préserver la compatibilité avec le dashboard et la base de données
    anchors_dict = {}
    for item in data.anchors_list:
        anchors_dict[item.organ_name] = {
            "pos_x": item.pos_x,
            "pos_y": item.pos_y,
            "pos_z": item.pos_z,
            "rot_x": item.rot_x,
            "rot_y": item.rot_y,
            "rot_z": item.rot_z
        }
        
    stages["anchors"] = anchors_dict
    
    # Mettre à jour la base de données
    db.table("procedures").update({"workflow_stages": stages}).eq("machine_id", machine_id).execute()
    return {"status": "success", "message": "Ancrages enregistrés avec succès."}
