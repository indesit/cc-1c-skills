# rules/ — BSL/1C knowledge rules

Reference knowledge for 1C:Enterprise / BAF development: coding standards, anti-patterns,
query optimization, extension and form patterns, testing and refactoring guidance.
These are **knowledge documents**, not runnable skills — load the relevant one when working
on matching code.

## Provenance & license

Imported 2026-06-13 from **[Desko77/claude-code-skills-1c](https://github.com/Desko77/claude-code-skills-1c)**
(`rules/` directory), MIT License, Copyright (c) 2026 Desko77. The MIT notice is preserved in
[`LICENSE.Desko77.md`](LICENSE.Desko77.md) in this directory, as the license requires.

Content is used as-is. Local edits (if any) are tracked in this repo's git history.

## ⚠️ Rules that assume external MCP servers we do NOT run

Several rules were written for Desko77's toolchain, which drives 1C through MCP servers
(`1c-edt`, `1c-naparnik`, `1c-mcp_ssl_server`, `1c-forms-mcp`, `1c-syntax-checker-mcp`).
**We do not run those servers** (our toolchain is the cc-1c-skills compile scripts + the
Hermes `mcp_bridge`). In these rules, ignore the "verify via MCP / call `tool_x` (1c-edt)"
sections and use the documented manual fallbacks instead:

| Rule | MCP it assumes | Use it for (the part that still applies) |
|------|----------------|------------------------------------------|
| `1c-coding-standards.md` | 1c-edt, 1c-naparnik | The standards themselves; fallback = `anti_patterns.md` + `code-review-checklist.md` |
| `code-review-checklist.md` | (refers to above) | The checklist itself (manual review) |
| `code-exploration-guide.md` | 1c-edt, 1c-naparnik, bsl-platform-help | The explore-before-change methodology; map tools → our Grep/Read/meta-info |
| `query-optimization-tips.md` | 1c-edt, 1c-syntax-checker-mcp | All optimization guidance; skip the "verify via MCP" section |
| `edt-form-xml-requirements.md` | EDT MCP | General EDT Form.form XML truths; we compile via `form-compile` |
| `edt-zip-export-pitfalls.md` | EDT MCP | General EDT export pitfalls; less relevant to our headless flow |
| `forms_generation.md` | 1c-forms-mcp (localhost:8011) | Mostly drives that server — low value here; we use `form-compile` |

The other 18 rules are self-contained knowledge with no external tool dependency.

## Directly relevant to current BAF work

- `routine_assignment_ext_processor.md` — background jobs from external processors via БСП
  Long Operations. Relevant to `bonus-retry-ext` (retry as background) and the
  loyalty reconcile EPF.
- `1c-extension-patterns.md`, `anti_patterns.md` — for `kassir-avtokassa` and other CFE work.
- `bsp-profile-rights-api.md`, `1c-role-rights.md` — БСП rights when extending.
