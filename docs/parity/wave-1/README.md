# Wave 1 Parity Baseline

This folder captures the Wave 1 reference surface for the Cloudflare, Supabase, and Workers migration.

Wave 1 does not port behavior yet. It freezes the maintained UX contract and records the current implementation baseline that later waves must match.

## Contents

- [`route-inventory.md`](./route-inventory.md): maintained public and authenticated route surface for the staging demo target.
- [`ux-parity-checklist.md`](./ux-parity-checklist.md): authoritative parity checklist for layout, navigation, access gating, filters, and feedback states.
- [`copy-snapshots.md`](./copy-snapshots.md): current user-facing copy markers and route-level headings.
- [`interaction-recordings.md`](./interaction-recordings.md): interaction flows covered by automated browser baselines and trace capture.

## Automated Baseline Assets

- Browser smoke and screenshot-comparison coverage lives under [`tests/parity`](../../../tests/parity).
- API contract smoke coverage lives under [`tests/contract-smoke`](../../../tests/contract-smoke).
- Shared maintained route metadata lives under [`packages/migration-contract`](../../../packages/migration-contract).

Use the root CLI to exercise the baseline:

```bash
python ./scripts/dev.py parity-test --start-stack
python ./scripts/dev.py capture-parity-baseline --start-stack
python ./scripts/dev.py contract-smoke --start-backend
```
