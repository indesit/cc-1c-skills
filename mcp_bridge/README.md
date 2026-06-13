# cc-1c-skills MCP bridge

This directory exposes a small MCP server for Hermes Agent. It wraps selected existing `cc-1c-skills` scripts as structured MCP tools while preserving the current script implementations.

## Setup

Install the Python dependency (once, from the repository root):

```bash
python -m pip install -r mcp_bridge/requirements.txt
```

## Server

Run from the repository root:

```bash
python mcp_bridge/cc_1c_skills_server.py
```

Hermes config entry created locally:

```yaml
mcp_servers:
  cc_1c_skills:
    command: C:/Users/Administrator/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe
    args:
      - C:/BAF/repos/cc-1c-skills/mcp_bridge/cc_1c_skills_server.py
    env:
      CC_1C_SKILLS_ROOT: C:/BAF/repos/cc-1c-skills
      PYTHONUTF8: '1'
      SYSTEMROOT: C:/Windows
      WINDIR: C:/Windows
      COMSPEC: C:/Windows/System32/cmd.exe
    timeout: 3600
    connect_timeout: 30
```

After changing MCP config, restart Hermes/gateway or start a new session so tool discovery runs again.

## Tools exposed

- `cc1c_project_info` — read and redact `.v8-project.json`.
- `cc1c_cf_drift` — compare two XML dump trees via `cf-drift.py`.
- `cc1c_db_dump_xml` — preview or execute `db-dump-xml.ps1`; `execute=false` by default.
- `cc1c_db_backup` — preview or execute `db-backup.ps1`; `execute=false` by default.
- `cc1c_srv_info` — read-only cluster overview via `srv-info.ps1`.
- `cc1c_srv_sessions` — list or terminate sessions via `srv-sessions.ps1`; termination requires `confirmation_token='TERMINATE_SESSIONS'`.
- `cc1c_cf_check` — read-only platform check (`/CheckConfig`, `/CheckModules`) via `cf-check.ps1`.
- `cc1c_log_analyze` — analyze the 1C event log (`.lgf`/`.lgp`) via the log-analyze engine; read-only.
- `cc1c_cfe_compat` — static extension-vs-config compatibility check via `cfe-compat.ps1`; `config_path` defaults to the DB's `configSrc`.
- `cc1c_v8unpack` — unpack/build CF/CFE/EPF via `python -m v8unpack` (no platform); `execute=false` by default, always runs with `PYTHONUTF8=1`.

Hermes will register them with the MCP prefix as e.g. `mcp_cc_1c_skills_cc1c_project_info`.

## Safety defaults

- Plain `password` and cluster passwords are redacted from tool output.
- `passwordEnv` is passed through as an environment variable name; the bridge does not read the secret.
- Backup and XML dump tools default to command preview (`execute=false`).
- Session termination is blocked unless an explicit confirmation token is supplied.

## Verification

```bash
python -m unittest tests.mcp.test_cc_1c_skills_mcp -v
hermes mcp test cc_1c_skills
```
