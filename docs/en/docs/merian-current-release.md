# Current Merian Release Baseline

The current shared religion/TCM Merian baseline in this repository is promoted
from the `2026-07-01 KST` `bunjum2/religion` operations tree.

## Current Version

- Merian asset version: `20260701-mobile-send-icon-1`
- Service worker cache: `shared-platform-shell-reference-v55`
- Base design pass: `20260630-design-progress-5`

## Covered Products

The same Merian runtime and shared beta6 engine path should cover these product
routes:

- Islam: `/islam`, `/islam-merian-chat.html`
- Buddhist: `/buddhist`, `/buddhist-merian-chat.html`
- Christian/Catholic: `/christian`, `/catholic`, `/catholic-merian-chat.html`
- Hindu: `/hindu`, `/hindu-merian-chat.html`
- TCM/Hanui: `/tcm`, `/tcm-merian-chat.html`

## Included Fixes

- Boot residue prevention: keep the first-paint shield until JS releases the
  `merian-booting` class after initialization.
- Composer position: desktop composer bottom `104px`, mobile composer bottom
  `68px`.
- Composer alignment: textarea and send button are vertically centered.
- Final-answer transition: replace the progress entry with the final answer
  entry on completion.
- Mobile send button: render as a bordered icon button, not a solid orange tile.
- Shared engine: align `shared_platform` beta6 job lifecycle, product routes,
  native shell manifests, frontend tests, and verifier tools with the same
  operations baseline.

## Explicit Exclusion

The one-file Gemma gateway/API PowerShell handoff is not a git source artifact
for this repository. Upload that file to Google Drive for external handoff; do
not commit the gateway client token or the one-file PS1 here.

## Minimum Checks

```bash
python3 tools/verify_repo_contracts.py
node --check web/merian-chat.js
node --check web/sw.js
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q \
  tests/test_islam_merian_preview.py \
  tests/test_frontend_static.py \
  tests/test_app_shell_parity.py \
  tests/test_merian_canonical_routes.py \
  tests/test_native_shell_parity.py \
  tests/test_product_profiles.py
python3 tools/verify_app_parity.py --json
```
