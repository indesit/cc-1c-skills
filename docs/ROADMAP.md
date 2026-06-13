# Roadmap — cc-1c-skills (Secret Shop BAF fork)

Local development roadmap for the `indesit/cc-1c-skills` fork. Drives BAF infrastructure
management for Claude Code AND the Hermes agent (via `mcp_bridge/`). Test server first
(SD-218-215-XRB, ~6-month prod copy); only tagged states go to prod (see `docs/PROD-RUNBOOK.md`).

## Where we are (2026-06-13, tag `local-v2026.06.13`)

- Phases 1–3 infra skills (cf-check, db-backup/restore, srv-info/sessions, cfe-compat,
  log-analyze, cf-drift) + passwordEnv across all DB scripts.
- `mcp_bridge/` — MCP server exposing **10** tools to Hermes (project_info, cf_drift, db_dump_xml,
  db_backup, srv_info, srv_sessions, cf_check, log_analyze, cfe_compat, v8unpack). Verified
  end-to-end against the live server; unit tests 9/9.
- `rules/` — 25 imported BSL knowledge rules (Desko77, MIT).
- `v8unpack-cf` — unpack CF/CFE/EPF without the platform.

## Theme: prove on real tasks, then grow MCP / Hermes native tools

The toolset is broad enough; the next gains come from **using it on live work** and from making
Hermes a first-class BAF operator through MCP — not from adding more thin skills.

### 1. Practical validation (highest priority)
- Run the RMK smoke scenario against the published base (`:8081/bas`) — real regression of the
  `КассирАвтоКасса` loyalty-balance feature. Manual first (capture selectors), then `web-test`.
- Exercise `v8unpack-cf` on the real `Module.bin` drift: unpack two `.cfe`/`.cf` and diff sources
  that `cf-drift` can only flag by sha256.

### 2. Hermes via MCP — make it real
- Restart the Hermes gateway so tool discovery picks up the 6 MCP tools.
- Have Hermes run a real read-only BAF task end-to-end through MCP (e.g. `cc1c_srv_info` →
  `cc1c_cf_drift`). First proof Hermes drives the same proven scripts as Claude Code.
- Then a guarded write path with the preview → confirm → execute flow (e.g. `cc1c_db_backup`).

### 3. Grow the MCP bridge ✅ done 2026-06-13
Added `cc1c_cf_check`, `cc1c_log_analyze`, `cc1c_cfe_compat`, `cc1c_v8unpack` (6 → 10 tools),
keeping the safety model (`execute=false` preview default, `confirmation_token` for destructive
ops, secret redaction). Verified live. Next candidates if needed: `cf-check` config mode on a
fresh dump, a guarded `db_update` (preview→confirm→execute).

### 4. Interpret BSL libraries as rules (no GPL contamination)
Turn external 1C library knowledge into rules/skills without copying code:
- "HTTP in BSL → Connector pattern" (Apache-2.0, can also be vendored into our extensions).
- "Serialization → SerLib1C pattern" (MPL-2.0).
- Keep `cpr1c/tools_ui_1c` (GPL-3.0) as a standalone diagnostic extension only — never linked.

### 5. Hardening / ops
- Event-log rotation is frozen on the test copy (since 2024-01-19) — confirm prod behavior.
- Rotate `BAF_BAS_PASSWORD` (value unchanged since storage migrated to the Machine env var).
- Full prod-size SQL backup needs a target volume other than C: (~7 GB free vs 16 GB DB).

## Deferred (Category B) — see MyAddon `docs/tasks/skills-enrichment-2026-06/STATUS.md`
Connector / SerLib1C vendoring (blocked on the reconcile EPF core); `tools_ui_1c` standalone install.
