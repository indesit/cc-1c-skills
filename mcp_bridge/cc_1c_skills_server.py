"""MCP server exposing selected cc-1c-skills scripts as structured tools.

The bridge is intentionally thin:
- project registry parsing and secret redaction happen here;
- existing, proven cc-1c-skills scripts remain the execution backend;
- dangerous actions default to preview/dry-run and require explicit confirmation.

Run as stdio MCP server:
    python -m mcp_bridge.cc_1c_skills_server
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cc-1c-skills")

_SECRET_KEYS = {"password", "pwd", "token", "secret", "apikey", "api_key"}
_MAX_OUTPUT_CHARS = 20_000
_TERMINATE_CONFIRMATION_TOKEN = "TERMINATE_SESSIONS"


class BridgeError(ValueError):
    """User-facing bridge error."""


@dataclass(frozen=True)
class ProjectContext:
    root: Path
    project_file: Path | None
    raw: dict[str, Any]

    @property
    def v8path(self) -> str | None:
        return _string_or_none(self.raw.get("v8path"))

    @property
    def default_db_id(self) -> str | None:
        return _string_or_none(
            self.raw.get("default")
            or self.raw.get("defaultDb")
            or self.raw.get("defaultDatabase")
        )

    @property
    def databases(self) -> list[dict[str, Any]]:
        entries = _extract_database_entries(self.raw)
        databases = [_normalize_db_entry(e, self.root) for e in entries]
        default_id = self.default_db_id
        if default_id:
            for db in databases:
                db["default"] = _db_matches(default_id, db, exact=False)
        return databases


def _repo_root() -> Path:
    configured = os.getenv("CC_1C_SKILLS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _skill_script(skill: str, script_name: str | None = None) -> Path:
    name = script_name or skill
    path = _repo_root() / ".claude" / "skills" / skill / "scripts" / name
    if not path.exists():
        raise BridgeError(f"Skill script not found: {_posix(path)}")
    return path


def _load_project(workspace: str | None = None, project_file: str | None = None) -> ProjectContext:
    if project_file:
        path = Path(project_file).expanduser().resolve()
        if not path.exists():
            raise BridgeError(f"Project file not found: {_posix(path)}")
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        return ProjectContext(root=path.parent, project_file=path, raw=raw)

    root = Path(workspace or os.getcwd()).expanduser().resolve()
    path = root / ".v8-project.json"
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        return ProjectContext(root=root, project_file=path, raw=raw)
    return ProjectContext(root=root, project_file=None, raw={})


def _extract_database_entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("databases", "dbs", "infobases", "bases"):
        value = raw.get(key)
        if isinstance(value, list):
            return [entry for entry in value if isinstance(entry, dict)]
        if isinstance(value, dict):
            return [dict(entry, id=entry.get("id") or name) for name, entry in value.items() if isinstance(entry, dict)]
    return []


def _normalize_db_entry(entry: dict[str, Any], workspace: Path) -> dict[str, Any]:
    aliases = _normalize_aliases(entry)
    db_id = _string_or_none(entry.get("id") or entry.get("name") or entry.get("ref"))
    kind = (_string_or_none(entry.get("type") or entry.get("kind")) or "server").lower()
    config_src = _string_or_none(entry.get("configSrc") or entry.get("config_src") or entry.get("configurationSource"))
    path = _string_or_none(entry.get("path") or entry.get("file") or entry.get("filePath"))
    normalized: dict[str, Any] = {
        "id": db_id,
        "name": _string_or_none(entry.get("name") or db_id),
        "kind": kind,
        "aliases": aliases,
        "server": _string_or_none(entry.get("server")),
        "ref": _string_or_none(entry.get("ref") or entry.get("database")),
        "path": _normalize_path(path, workspace) if path else None,
        "user": _string_or_none(entry.get("user") or entry.get("username")),
        "password": _string_or_none(entry.get("password")),
        "passwordEnv": _string_or_none(entry.get("passwordEnv") or entry.get("password_env")),
        "clusterUser": _string_or_none(entry.get("clusterUser") or entry.get("cluster_user")),
        "clusterPwd": _string_or_none(entry.get("clusterPwd") or entry.get("cluster_pwd")),
        "clusterPwdEnv": _string_or_none(entry.get("clusterPwdEnv") or entry.get("cluster_pwd_env")),
        "sqlServer": _string_or_none(entry.get("sqlServer") or entry.get("sql_server")),
        "sqlDatabase": _string_or_none(entry.get("sqlDatabase") or entry.get("sql_database")),
        "configSrc": _normalize_path(config_src, workspace) if config_src else None,
        "default": bool(entry.get("default")),
    }
    return {k: v for k, v in normalized.items() if v not in (None, "", [])}


def _normalize_aliases(entry: dict[str, Any]) -> list[str]:
    values: list[str] = []
    raw = entry.get("aliases")
    if isinstance(raw, list):
        values.extend(str(x).strip() for x in raw if str(x).strip())
    elif isinstance(raw, str) and raw.strip():
        values.append(raw.strip())
    alias = entry.get("alias")
    if alias and str(alias).strip():
        values.append(str(alias).strip())
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _resolve_db(ctx: ProjectContext, selector: str | None = None) -> dict[str, Any]:
    databases = ctx.databases
    if not databases:
        raise BridgeError("No databases declared in .v8-project.json")

    if selector and selector.strip():
        s = selector.strip()
        for exact in (True, False):
            matches = [db for db in databases if _db_matches(s, db, exact=exact)]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise BridgeError(f"Database selector is ambiguous: {s}")
        raise BridgeError(f"Database not found: {s}")

    default_id = ctx.default_db_id
    if default_id:
        matches = [db for db in databases if _db_matches(default_id, db, exact=False)]
        if len(matches) == 1:
            return matches[0]
    explicit_defaults = [db for db in databases if db.get("default")]
    if len(explicit_defaults) == 1:
        return explicit_defaults[0]
    if len(databases) == 1:
        return databases[0]
    raise BridgeError("Database selector required: no unique default database")


def _db_matches(selector: str, db: dict[str, Any], *, exact: bool) -> bool:
    values = [db.get("id"), db.get("name"), db.get("ref"), *db.get("aliases", [])]
    values_s = [str(v) for v in values if v]
    if exact:
        return selector in values_s
    return selector.casefold() in {v.casefold() for v in values_s}


def _connection_args(db: dict[str, Any]) -> list[str]:
    args: list[str] = []
    kind = str(db.get("kind") or db.get("type") or "server").lower()
    if kind == "file":
        path = db.get("path")
        if not path:
            raise BridgeError("File database requires path")
        args += ["-InfoBasePath", str(path)]
    else:
        server = db.get("server")
        ref = db.get("ref")
        if not server or not ref:
            raise BridgeError("Server database requires server and ref")
        args += ["-InfoBaseServer", str(server), "-InfoBaseRef", str(ref)]
    if db.get("user"):
        args += ["-UserName", str(db["user"])]
    if db.get("passwordEnv"):
        args += ["-PasswordEnv", str(db["passwordEnv"])]
    elif db.get("password"):
        args += ["-Password", str(db["password"])]
    return args


def _cluster_args(cluster_user: str | None = None, cluster_pwd_env: str | None = None, db: dict[str, Any] | None = None) -> list[str]:
    args: list[str] = []
    user = cluster_user or (db or {}).get("clusterUser")
    pwd_env = cluster_pwd_env or (db or {}).get("clusterPwdEnv")
    pwd = (db or {}).get("clusterPwd")
    if user:
        args += ["-ClusterUser", str(user)]
    if pwd_env:
        args += ["-ClusterPwdEnv", str(pwd_env)]
    elif pwd:
        args += ["-ClusterPwd", str(pwd)]
    return args


def _powershell_command(script: Path, args: list[str]) -> list[str]:
    return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args]


def _python_command(script: Path, args: list[str]) -> list[str]:
    return [sys.executable, str(script), *args]


def _run_command(cmd: list[str], *, cwd: str | Path | None = None, timeout: int = 120,
                 env: dict[str, str] | None = None) -> dict[str, Any]:
    redacted_cmd = _redact_command(cmd)
    run_env = {**os.environ, **env} if env else None
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=run_env,
        )
        stdout = _truncate(_redact_text(proc.stdout))
        stderr = _truncate(_redact_text(proc.stderr))
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "command": redacted_cmd,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exit_code": None,
            "timed_out": True,
            "timeout_sec": timeout,
            "command": redacted_cmd,
            "stdout": _truncate(_redact_text(exc.stdout or "")),
            "stderr": _truncate(_redact_text(exc.stderr or "")),
        }
    except Exception as exc:  # pragma: no cover - defensive for environment failures
        return {"ok": False, "error": _redact_text(str(exc)), "command": redacted_cmd}


def _preview(cmd: list[str], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": True, "execute": False, "command": _redact_command(cmd), **(extra or {})}


def _redact_db(db: dict[str, Any]) -> dict[str, Any]:
    out = dict(db)
    password_present = bool(out.get("password"))
    cluster_pwd_present = bool(out.get("clusterPwd"))
    for key in ("password", "clusterPwd"):
        out.pop(key, None)
    if password_present:
        out["password_present"] = True
    if cluster_pwd_present:
        out["cluster_password_present"] = True
    return out


def _redact_project(raw: Any) -> Any:
    if isinstance(raw, dict):
        result: dict[str, Any] = {}
        for key, value in raw.items():
            key_l = str(key).replace("-", "_").lower()
            if key_l in _SECRET_KEYS or any(marker in key_l for marker in ("password", "passwd", "secret", "token", "apikey")):
                result[key] = "<redacted>" if value else value
            else:
                result[key] = _redact_project(value)
        return result
    if isinstance(raw, list):
        return [_redact_project(item) for item in raw]
    return raw


def _redact_command(cmd: list[str]) -> list[str]:
    sensitive_flags = {"-Password", "-ClusterPwd", "/P"}
    redacted: list[str] = []
    skip = False
    for idx, part in enumerate(cmd):
        if skip:
            redacted.append("<redacted>")
            skip = False
            continue
        redacted.append(part)
        if part in sensitive_flags and idx + 1 < len(cmd):
            skip = True
    return redacted


def _redact_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(?i)(password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]\s*\S+", r"\1=<redacted>", text)
    text = re.sub(r"(?i)(-Password|-ClusterPwd|/P)\s+\S+", r"\1 <redacted>", text)
    return text


def _truncate(text: str, max_chars: int = _MAX_OUTPUT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... <truncated to {max_chars} chars>"


def _normalize_path(value: str, workspace: Path) -> str:
    p = Path(value)
    if not p.is_absolute() and not _looks_like_windows_abs(value):
        p = workspace / p
    return _posix(p)


def _looks_like_windows_abs(value: str) -> bool:
    return len(value) >= 3 and value[1] == ":" and value[2] in {"\\", "/"}


def _posix(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    value_s = str(value).strip()
    return value_s or None


def _v8_arg(ctx: ProjectContext) -> list[str]:
    return ["-V8Path", ctx.v8path] if ctx.v8path else []


@mcp.tool()
def cc1c_project_info(workspace: str | None = None, project_file: str | None = None) -> dict[str, Any]:
    """Read and redact a .v8-project.json registry for a 1C/BAF workspace."""
    ctx = _load_project(workspace=workspace, project_file=project_file)
    return {
        "ok": True,
        "workspace": _posix(ctx.root),
        "project_file": _posix(ctx.project_file) if ctx.project_file else None,
        "v8path": ctx.v8path,
        "default_db_id": ctx.default_db_id,
        "databases": [_redact_db(db) for db in ctx.databases],
        "raw_redacted": _redact_project(ctx.raw),
    }


@mcp.tool()
def cc1c_cf_drift(
    reference: str,
    actual: str,
    json_report: str | None = None,
    max_list: int = 50,
    no_default_ignore: bool = False,
    timeout: int = 120,
) -> dict[str, Any]:
    """Compare two 1C configuration XML dump trees using the cc-1c-skills cf-drift engine."""
    script = _skill_script("cf-drift", "cf-drift.py")
    args = ["-Reference", reference, "-Actual", actual, "-MaxList", str(max_list)]
    if json_report:
        args += ["-Json", json_report]
    if no_default_ignore:
        args += ["-NoDefaultIgnore"]
    return _run_command(_python_command(script, args), cwd=_repo_root(), timeout=timeout)


@mcp.tool()
def cc1c_db_dump_xml(
    workspace: str,
    output_dir: str | None = None,
    db: str | None = None,
    project_file: str | None = None,
    mode: Literal["Full", "Changes", "Partial", "UpdateInfo"] = "UpdateInfo",
    objects: str | None = None,
    extension: str | None = None,
    all_extensions: bool = False,
    fmt: Literal["Hierarchical", "Plain"] = "Hierarchical",
    execute: bool = False,
    timeout: int = 1800,
) -> dict[str, Any]:
    """Build or execute a read-only DumpConfigToFiles XML dump command via db-dump-xml.ps1.

    execute defaults to False so Hermes first receives a safe command preview.
    """
    ctx = _load_project(workspace=workspace, project_file=project_file)
    db_info = _resolve_db(ctx, db)
    config_dir = output_dir or db_info.get("configSrc")
    if not config_dir:
        raise BridgeError("output_dir required: DB entry has no configSrc")
    script = _skill_script("db-dump-xml", "db-dump-xml.ps1")
    args = [*_v8_arg(ctx), *_connection_args(db_info), "-ConfigDir", config_dir, "-Mode", mode, "-Format", fmt]
    if objects:
        args += ["-Objects", objects]
    if extension:
        args += ["-Extension", extension]
    if all_extensions:
        args += ["-AllExtensions"]
    cmd = _powershell_command(script, args)
    meta = {"db": _redact_db(db_info), "config_dir": config_dir, "mode": mode}
    return _run_command(cmd, cwd=ctx.root, timeout=timeout) if execute else _preview(cmd, meta)


@mcp.tool()
def cc1c_db_backup(
    workspace: str,
    output_file: str,
    mode: Literal["dt", "sql"] = "dt",
    db: str | None = None,
    project_file: str | None = None,
    sql_server: str | None = None,
    sql_database: str | None = None,
    execute: bool = False,
    timeout: int = 3600,
) -> dict[str, Any]:
    """Build or execute a 1C infobase backup using db-backup.ps1.

    execute defaults to False because backups can be heavy and paths for SQL backups are server-local.
    """
    ctx = _load_project(workspace=workspace, project_file=project_file)
    db_info = _resolve_db(ctx, db)
    script = _skill_script("db-backup", "db-backup.ps1")
    args = ["-Mode", mode, "-OutputFile", output_file]
    if mode == "dt":
        args += [*_v8_arg(ctx), *_connection_args(db_info)]
    else:
        effective_sql_db = sql_database or db_info.get("sqlDatabase") or db_info.get("ref")
        if sql_server or db_info.get("sqlServer"):
            args += ["-SqlServer", str(sql_server or db_info.get("sqlServer"))]
        if not effective_sql_db:
            raise BridgeError("sql_database required for SQL backup")
        args += ["-SqlDatabase", str(effective_sql_db)]
    cmd = _powershell_command(script, args)
    meta = {"db": _redact_db(db_info), "mode": mode, "output_file": output_file}
    return _run_command(cmd, cwd=ctx.root, timeout=timeout) if execute else _preview(cmd, meta)


@mcp.tool()
def cc1c_srv_info(
    workspace: str | None = None,
    project_file: str | None = None,
    mode: Literal["cluster", "infobases", "processes", "all"] = "all",
    ras_address: str = "localhost:1545",
    cluster_user: str | None = None,
    cluster_pwd_env: str | None = None,
    execute: bool = True,
    timeout: int = 120,
) -> dict[str, Any]:
    """Show read-only 1C server cluster state through srv-info.ps1/rac."""
    ctx = _load_project(workspace=workspace, project_file=project_file)
    script = _skill_script("srv-info", "srv-info.ps1")
    args = [*_v8_arg(ctx), "-RasAddress", ras_address, "-Mode", mode, *_cluster_args(cluster_user, cluster_pwd_env)]
    cmd = _powershell_command(script, args)
    return _run_command(cmd, cwd=ctx.root, timeout=timeout) if execute else _preview(cmd, {"mode": mode})


@mcp.tool()
def cc1c_srv_sessions(
    workspace: str | None = None,
    project_file: str | None = None,
    db: str | None = None,
    action: Literal["list", "terminate"] = "list",
    ras_address: str = "localhost:1545",
    infobase: str | None = None,
    session_id: str | None = None,
    all_sessions: bool = False,
    cluster_user: str | None = None,
    cluster_pwd_env: str | None = None,
    confirmation_token: str | None = None,
    execute: bool = True,
    timeout: int = 120,
) -> dict[str, Any]:
    """List or terminate 1C cluster sessions via srv-sessions.ps1.

    Termination is blocked unless confirmation_token is exactly TERMINATE_SESSIONS.
    """
    ctx = _load_project(workspace=workspace, project_file=project_file)
    db_info: dict[str, Any] | None = None
    if db:
        db_info = _resolve_db(ctx, db)
    target_infobase = infobase or (db_info or {}).get("ref") or (db_info or {}).get("name")

    if action == "terminate":
        if confirmation_token != _TERMINATE_CONFIRMATION_TOKEN:
            return {
                "ok": False,
                "error": "Session termination requires confirmation_token='TERMINATE_SESSIONS' after user approval.",
                "execute": False,
            }
        if not session_id and not all_sessions:
            return {"ok": False, "error": "terminate requires session_id or all_sessions=True"}

    script = _skill_script("srv-sessions", "srv-sessions.ps1")
    args = [*_v8_arg(ctx), "-RasAddress", ras_address, "-Action", action, *_cluster_args(cluster_user, cluster_pwd_env, db_info)]
    if target_infobase:
        args += ["-Infobase", str(target_infobase)]
    if session_id:
        args += ["-SessionId", session_id]
    if all_sessions:
        args += ["-All"]
    if action == "terminate":
        args += ["-IAmSure"]
    cmd = _powershell_command(script, args)
    meta = {"action": action, "infobase": target_infobase, "db": _redact_db(db_info) if db_info else None}
    return _run_command(cmd, cwd=ctx.root, timeout=timeout) if execute else _preview(cmd, meta)


@mcp.tool()
def cc1c_cf_check(
    workspace: str | None = None,
    project_file: str | None = None,
    db: str | None = None,
    mode: Literal["config", "modules", "all"] = "all",
    extension: str | None = None,
    execute: bool = True,
    timeout: int = 600,
) -> dict[str, Any]:
    """Read-only platform check of a 1C configuration/modules via cf-check.ps1 (/CheckConfig, /CheckModules).

    Connects to the infobase through Designer. Non-zero exit means problems were found.
    """
    ctx = _load_project(workspace=workspace, project_file=project_file)
    db_info = _resolve_db(ctx, db)
    script = _skill_script("cf-check", "cf-check.ps1")
    args = [*_v8_arg(ctx), *_connection_args(db_info), "-Mode", mode]
    if extension:
        args += ["-Extension", extension]
    cmd = _powershell_command(script, args)
    meta = {"db": _redact_db(db_info), "mode": mode, "extension": extension}
    return _run_command(cmd, cwd=ctx.root, timeout=timeout) if execute else _preview(cmd, meta)


@mcp.tool()
def cc1c_log_analyze(
    log_dir: str | None = None,
    infobase: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    severity: str = "E,W",
    top: int = 10,
    details: int = 20,
    json_report: str | None = None,
    execute: bool = True,
    timeout: int = 300,
) -> dict[str, Any]:
    """Analyze the 1C event log (old .lgf/.lgp format) via the log-analyze engine. Read-only.

    Auto-discovers the log directory under srvinfo if log_dir is omitted.
    """
    script = _skill_script("log-analyze", "log-analyze.py")
    args = ["-Severity", severity, "-Top", str(top), "-Details", str(details)]
    if log_dir:
        args += ["-LogDir", log_dir]
    if infobase:
        args += ["-Infobase", infobase]
    if date_from:
        args += ["-From", date_from]
    if date_to:
        args += ["-To", date_to]
    if json_report:
        args += ["-Json", json_report]
    cmd = _python_command(script, args)
    meta = {"log_dir": log_dir, "severity": severity}
    # log-analyze prints Cyrillic; the engine reconfigures stdout itself, but force utf-8 for safety.
    return _run_command(cmd, cwd=_repo_root(), timeout=timeout, env={"PYTHONUTF8": "1"}) if execute else _preview(cmd, meta)


@mcp.tool()
def cc1c_cfe_compat(
    extension_path: str,
    config_path: str | None = None,
    workspace: str | None = None,
    project_file: str | None = None,
    db: str | None = None,
    json_report: str | None = None,
    strict: bool = False,
    execute: bool = True,
    timeout: int = 300,
) -> dict[str, Any]:
    """Static compatibility check of a 1C extension against a configuration dump via cfe-compat.ps1.

    config_path defaults to the resolved DB's configSrc. Read-only static analysis.
    Non-zero exit means INCOMPATIBLE (errors found).
    """
    cfg = config_path
    if not cfg:
        ctx = _load_project(workspace=workspace, project_file=project_file)
        db_info = _resolve_db(ctx, db)
        cfg = db_info.get("configSrc")
        if not cfg:
            raise BridgeError("config_path required: resolved DB has no configSrc")
    script = _skill_script("cfe-compat", "cfe-compat.ps1")
    args = ["-ExtensionPath", extension_path, "-ConfigPath", cfg]
    if json_report:
        args += ["-Json", json_report]
    if strict:
        args += ["-Strict"]
    cmd = _powershell_command(script, args)
    meta = {"extension_path": extension_path, "config_path": cfg, "strict": strict}
    return _run_command(cmd, cwd=_repo_root(), timeout=timeout) if execute else _preview(cmd, meta)


@mcp.tool()
def cc1c_v8unpack(
    mode: Literal["extract", "build"],
    source: str,
    destination: str,
    descent: str | None = None,
    version: str | None = None,
    execute: bool = False,
    timeout: int = 600,
) -> dict[str, Any]:
    """Unpack (extract) or repack (build) a 1C CF/CFE/EPF binary via `python -m v8unpack`, no platform needed.

    extract: source=<.cf/.cfe/.epf>, destination=<sources dir>.
    build:   source=<sources dir>,   destination=<.cf/.cfe/.epf>.
    Defaults to preview (execute=False) since it writes a large tree / a binary file.
    Always runs with PYTHONUTF8=1 (v8unpack crashes on Cyrillic without it on Windows).
    """
    flag = "-E" if mode == "extract" else "-B"
    cmd = [sys.executable, "-m", "v8unpack", flag, source, destination]
    if descent:
        cmd += ["--descent", descent]
    if version:
        cmd += ["--version", version]
    meta = {"mode": mode, "source": source, "destination": destination}
    return _run_command(cmd, timeout=timeout, env={"PYTHONUTF8": "1"}) if execute else _preview(cmd, meta)


def main() -> None:
    """Run the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
