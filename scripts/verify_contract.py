import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

sys.stdout.reconfigure(encoding='utf-8')

def verify_file(filepath):
    print(f"\n========================================================")
    print(f"VERIFYING CONTRACT: {filepath}")
    print(f"========================================================")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print('--- 1. METADATA CHECK ---')
    for field in ['procedure_id', 'version', 'title', 'objective', 'expected_final_state', 'hse_approval_status', 'status']:
        val = data.get(field)
        assert val, f'Missing {field}'
        print(f'  ✓ {field}: {val}')

    print('\n--- 2. WORKFLOW STEPS & SEQUENTIAL PHASES ---')
    phases = data.get('phases', [])
    assert len(phases) >= 4, f'Expected at least 4 phases, got {len(phases)}'
    for p in phases:
        print(f"  ✓ Phase {p['phase_id']} [{p['phase_type']}]: {p['title']} ({len(p['stages'])} stages)")
        for s in p['stages']:
            for st in s['steps']:
                v = st['verification']
                assert v['method'], f"Missing method for {st['step_id']}"
                assert isinstance(v['criteria'], list), f"Criteria not a list for {st['step_id']}"
                print(f"     Step {st['step_id']} [seq {st['sequence']}]: {st['instruction'][:40]}... (method: {v['method']}, fallback: {v.get('fallback_mode')})")

    print('\n--- 3. AR VISION MATRIX CHECK (7 COMPONENTS) ---')
    expected_comps = {
        'C01': ('switch_c01', {'MARQUAGE', 'GÉOMÉTRIE'}, {'OFF', 'ON'}),
        'C02': ('battery_c02', {'GÉOMÉTRIE'}, {'REMOVED', 'CONNECTED'}),
        'C03': ('battery_holder_c03', {'MARQUAGE'}, {'EMPTY', 'OCCUPIED'}),
        'C04': ('safe_box_c04', {'PICTOGRAMME', 'MARQUAGE'}, {'STORED', 'EMPTY'}),
        'C05': ('guard_c05', {'SYMBOLE', 'GÉOMÉTRIE'}, {'CLOSED', 'OPEN'}),
        'C06': ('lamp_c06', {'SYMBOLE', 'GÉOMÉTRIE'}, {'EXTINGUISHED', 'ILLUMINATED'}),
        'C07': ('markers_c07', {'SYMBOLE'}, {'REFERENCE'}),
    }

    comps = {c['tag']: c for c in data.get('components', [])}
    assert len(comps) == 7, f'Expected 7 components, got {len(comps)}'

    for tag, (unity_id, expected_sig_types, expected_states) in expected_comps.items():
        assert tag in comps, f'Missing component {tag}'
        c = comps[tag]
        assert c['unity_class_id'] == unity_id, f"Mismatch unity_class_id for {tag}: {c['unity_class_id']} != {unity_id}"
        sig_types = {s['signature_type'] for s in c['physical_signatures']}
        assert expected_sig_types.issubset(sig_types), f"{tag} signatures {sig_types} missing some of {expected_sig_types}"
        state_names = {s['state_name'] for s in c['state_rules']}
        assert expected_states.issubset(state_names), f"{tag} states {state_names} missing some of {expected_states}"
        print(f"  ✓ {tag} ({unity_id}): signatures={sig_types}, states={state_names}")

    print('\n--- 4. NULL CHECK (RECURSIVE) ---')
    null_paths = []
    def check_nulls(obj, path='root'):
        if obj is None:
            null_paths.append(path)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if k == 'spatial_guide':
                    continue
                check_nulls(v, f'{path}.{k}')
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                check_nulls(item, f'{path}[{i}]')

    check_nulls(data)
    if null_paths:
        print(f'  Found nulls at: {null_paths}')
        raise AssertionError("Found null values in payload!")
    else:
        print('  ✓ ZERO blocking nulls found across entire payload!')

    print(f"\n>>> CONTRACT {filepath} IS 100% VALID! <<<")

if __name__ == "__main__":
    verify_file(ROOT_DIR / 'docs/contracts/SL-POC-01_unity_contract.json')
    verify_file(ROOT_DIR / 'unity-app/Assets/StreamingAssets/SL-POC-01_unity_contract.json')
