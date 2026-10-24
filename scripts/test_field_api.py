import json
import urllib.request
import base64

def run_tests():
    print("--- 1. Testing GET /procedures ---")
    req = urllib.request.Request("http://127.0.0.1:8000/procedures")
    with urllib.request.urlopen(req) as resp:
        procs = json.loads(resp.read().decode('utf-8'))
        print(f"Status 200: Found {len(procs)} procedures:")
        for p in procs:
            print(f"  - {p.get('machine_id')} : {p.get('machine_name')}")

    print("\n--- 2. Testing GET /procedures/SL-POC-01 ---")
    req = urllib.request.Request("http://127.0.0.1:8000/procedures/SL-POC-01")
    with urllib.request.urlopen(req) as resp:
        proc_detail = json.loads(resp.read().decode('utf-8'))
        print(f"Status 200: Machine {proc_detail.get('machine_id')}, Status {proc_detail.get('status')}")

    print("\n--- 3. Testing POST /interventions/start ---")
    start_payload = json.dumps({
        "machine_id": "SL-POC-01",
        "operator_name": "Operator-Quest2"
    }).encode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:8000/interventions/start", data=start_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        start_res = json.loads(resp.read().decode('utf-8'))
        intervention_id = start_res["intervention"]["id"]
        print(f"Status 200: Intervention started, ID: {intervention_id}")

    print("\n--- 4. Testing POST /interventions/override-step ---")
    # 32x32 dummy JPEG
    dummy_jpg = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00 \x00 \x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
    )
    b64_image = base64.b64encode(dummy_jpg).decode('ascii')

    override_payload = json.dumps({
        "intervention_id": intervention_id,
        "stage_id": 1,
        "action_id": "A-01",
        "image_base64": b64_image,
        "reason": "Confirmation visuelle interrupteur bascule en position OFF",
        "verification_method": "visual_observation"
    }).encode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:8000/interventions/override-step", data=override_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        override_res = json.loads(resp.read().decode('utf-8'))
        print(f"Status 200: Override recorded: verified={override_res.get('verified')}, image_url={override_res.get('image_url')}")

    print("\n--- 5. Testing POST /interventions/close ---")
    sig_payload = json.dumps({
        "intervention_id": intervention_id,
        "signature_base64": b64_image
    }).encode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:8000/interventions/close", data=sig_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        close_res = json.loads(resp.read().decode('utf-8'))
        print(f"Status 200: Intervention closed: status={close_res.get('status')}, report_url={close_res.get('pdf_report_url')}")

    print("\n>>> ALL FIELD-SERVICE API TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run_tests()
