# GitHub release preparation

## Scope

This pass prepares the existing workspace for review and publication through five
successive Conventional Commits. Existing backend, frontend and Unity changes are
included as they stood at the start of cleanup. No business logic, endpoint,
database schema, C# script, prefab or asset metadata is edited by this pass.

The SHA-256 baseline covers 182 existing source, contract, schema and asset files.
The working locations of `apps/`, `unity-app/`, `Assets/`, `data/` and the field
storage paths are preserved. The existing deletion of the retired, unversioned
sample PDF is retained; its official v0.3 replacement is included.

## Dry-run audit and cleanup decisions

The initial dry run found no tracked runtime/cache file covered by the existing
ignore rules. Local SQLite data, uploaded PDFs, caches, frontend dependencies and
build output remain on disk and are excluded from Git.

The following local-only material is excluded without deleting its working copy:

- One-off DB inspection/repair and fixed-demo API/replay scripts:
  `scripts/check_db.py`, `preflight_check.py`, `replay_sequence.py`,
  `patch_sl_poc_01.py` and `test_field_api.py`.
- Historical session reports: `docs/walkthrough.md`,
  `docs/verification-smartloto.md` and `docs/bugfix-hse-publication.md`.
- The sequence package's local `PROMPT_CODEX.md` instruction sheet.
- Duplicate `Assets/Editor/SmartLotoCleaner.cs`; the byte-identical canonical
  source is retained in `unity-app/Assets/Editor/`.

Reusable application tests, launchers, the explicit demo-reset utility, contract
checker, official PDF, simulation images, reference JSON and branding stay tracked.
No `.meta` files were present in this source bundle; no Unity metadata is deleted
or globally ignored. Unity-generated folders and Android build products are ignored.

## Commit sequence

1. `chore(repo): configure production .gitignore and environment templates`
2. `feat(backend): add AI LOTO extraction pipeline, HSE validation API, and PDF audit generator`
3. `feat(frontend): implement HSE validation console, workflow editor, and vision matrix UI`
4. `feat(ar-unity): add Unity AR client and component state detection integration`
5. `docs(readme): add technical architecture overview, visual workflow, and setup guide`

The commits append to the existing branch history; they do not squash or rewrite
previous work. Backend fixtures/tests accompany their service, and the Unity
StreamingAssets fixture accompanies the client sources.

## Verification and deployment scope

Release checks cover ignore rules, staged-file secret patterns, documentation links,
unchanged source fingerprints, frontend typechecking/tests/build, and isolated
backend/contract/report tests. Exact commands are in [LAUNCH.md](../LAUNCH.md).
Provider-dependent integration tests and a Unity headset build require their own
configured environments; no operational database reset is part of these checks.

The README image slots are labelled placeholders. The repository contains a Unity
source bundle rather than a full editor project. The existing identity-header
authentication stub, permissive CORS, development self-review policy and historical
Compose configuration are documented, not redesigned. Preparing the GitHub history
does not make those deployment choices production-hardened or certify OSHA compliance.

Real `.env` files, private keys, generated reports, user evidence, model weights and
local databases must remain outside Git. The templates contain blank provider keys.
Pushing to the configured remote is a separate action requiring explicit approval.
