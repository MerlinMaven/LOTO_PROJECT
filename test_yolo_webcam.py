import threading

import cv2
from ultralytics import YOLO


MODEL_PATH = "yolov8s-worldv2.pt"
CONFIDENCE = 0.45


def parse_prompts(raw_prompt: str) -> list[str]:
    prompts = [part.strip() for part in raw_prompt.split(",")]
    return [prompt for prompt in prompts if prompt]


def main() -> None:
    prompt = input("Objet a chercher (anglais, ex: red padlock) : ").strip()
    if not prompt:
        print("Aucun prompt fourni.")
        return

    search_terms = parse_prompts(prompt)
    if not search_terms:
        print("Aucun prompt valide fourni.")
        return

    print("Chargement du modele...")
    model = YOLO(MODEL_PATH)
    model.set_classes(search_terms)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Impossible d'ouvrir la camera.")
        return

    print("Camera ouverte.")
    print("Tape un nouveau texte dans le terminal puis Entrer pour changer la recherche.")
    print("Laisse vide puis Entrer pour garder la recherche actuelle.")

    current_prompt = prompt
    prompt_lock = threading.Lock()

    def prompt_listener() -> None:
        nonlocal current_prompt
        while True:
            new_prompt = input("Nouvel objet a chercher : ").strip()
            if not new_prompt:
                continue
            with prompt_lock:
                current_prompt = new_prompt
            print(f"Recherche mise a jour: {new_prompt}")

    threading.Thread(target=prompt_listener, daemon=True).start()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Lecture camera impossible.")
            break

        with prompt_lock:
            active_prompt = current_prompt
            active_terms = parse_prompts(active_prompt)

        if not active_terms:
            active_terms = [active_prompt]

        model.set_classes(active_terms)
        results = model.predict(frame, conf=CONFIDENCE, verbose=False)
        boxes = results[0].boxes
        annotated = results[0].plot()

        status_text = f"Detected: {len(boxes)}"
        if len(boxes) == 0:
            status_text = "No detection - try a more specific prompt"
        else:
            best_conf = float(boxes.conf.max()) if boxes.conf is not None else 0.0
            status_text = f"Detected: {len(boxes)} | best conf: {best_conf:.2f}"

        cv2.putText(
            annotated,
            f"Search: {active_prompt}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            annotated,
            status_text,
            (10, 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0) if len(boxes) > 0 else (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.imshow("YOLO Webcam Test", annotated)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()