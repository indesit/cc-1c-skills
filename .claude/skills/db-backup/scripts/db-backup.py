#!/usr/bin/env python3
# db-backup v1.0 — Infobase backup: .dt via Designer or online MS SQL backup.

import argparse
import glob
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


def resolve_v8path(v8path):
    if not v8path:
        found = sorted(glob.glob(r"C:\Program Files\1cv8\*\bin\1cv8.exe"))
        if found:
            return found[-1]
        print("Error: 1cv8.exe not found. Specify -V8Path", file=sys.stderr)
        sys.exit(1)
    elif os.path.isdir(v8path):
        v8path = os.path.join(v8path, "1cv8.exe")
    if not os.path.isfile(v8path):
        print(f"Error: 1cv8.exe not found at {v8path}", file=sys.stderr)
        sys.exit(1)
    return v8path


def resolve_password(password, password_env):
    """Explicit -Password wins; else env var (process env, then HKCU/HKLM registry)."""
    if password:
        return password
    if not password_env:
        return ""
    value = os.environ.get(password_env, "")
    if not value:
        try:
            import winreg
            for hive, path in (
                (winreg.HKEY_CURRENT_USER, r"Environment"),
                (winreg.HKEY_LOCAL_MACHINE,
                 r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            ):
                try:
                    with winreg.OpenKey(hive, path) as key:
                        value = str(winreg.QueryValueEx(key, password_env)[0])
                        if value:
                            break
                except OSError:
                    continue
        except ImportError:
            pass
    if not value:
        print(f"Error: environment variable {password_env} is not set", file=sys.stderr)
        sys.exit(1)
    return value


def write_manifest(mode, backup_file, extra):
    manifest = {
        "timestampUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": mode,
        "file": backup_file,
        "sizeBytes": os.path.getsize(backup_file) if os.path.isfile(backup_file) else None,
    }
    manifest.update(extra)
    path = backup_file + ".manifest.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Manifest: {path}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="1C infobase backup", allow_abbrev=False)
    parser.add_argument("-Mode", required=True, choices=["dt", "sql"])
    parser.add_argument("-OutputFile", required=True)
    parser.add_argument("-V8Path", default="")
    parser.add_argument("-InfoBasePath", default="")
    parser.add_argument("-InfoBaseServer", default="")
    parser.add_argument("-InfoBaseRef", default="")
    parser.add_argument("-UserName", default="")
    parser.add_argument("-Password", default="")
    parser.add_argument("-PasswordEnv", default="", help="Env var holding the password")
    parser.add_argument("-SqlServer", default="localhost")
    parser.add_argument("-SqlDatabase", default="")
    parser.add_argument("-Compress", action="store_true",
                        help="Add WITH COMPRESSION (smaller .bak; useful when the disk is tight)")
    args = parser.parse_args()
    args.Password = resolve_password(args.Password, args.PasswordEnv)

    out_dir = os.path.dirname(args.OutputFile)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    if args.Mode == "sql":
        if not args.SqlDatabase:
            print("Error: specify -SqlDatabase for sql mode", file=sys.stderr)
            sys.exit(1)
        if not shutil.which("sqlcmd"):
            print("Error: sqlcmd not found in PATH", file=sys.stderr)
            sys.exit(1)
        db_esc = args.SqlDatabase.replace("]", "]]")
        file_esc = args.OutputFile.replace("'", "''")
        with_opts = "COPY_ONLY, INIT, CHECKSUM, STATS = 10"
        if args.Compress:
            with_opts += ", COMPRESSION"
        query = (f"BACKUP DATABASE [{db_esc}] TO DISK = N'{file_esc}' "
                 f"WITH {with_opts}")
        print(f'Running: sqlcmd -S {args.SqlServer} -E -b -Q "{query}"')
        result = subprocess.run(["sqlcmd", "-S", args.SqlServer, "-E", "-b", "-Q", query])
        if result.returncode == 0 and os.path.isfile(args.OutputFile):
            size_mb = os.path.getsize(args.OutputFile) / 1024 / 1024
            print(f"Backup completed: {args.OutputFile} ({size_mb:.1f} MB)")
            write_manifest("sql", args.OutputFile,
                           {"sqlServer": args.SqlServer, "sqlDatabase": args.SqlDatabase,
                            "copyOnly": True, "compression": bool(args.Compress)})
        else:
            print(f"SQL backup failed (code {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)

    # --- dt mode ---
    v8path = resolve_v8path(args.V8Path)
    if not args.InfoBasePath and (not args.InfoBaseServer or not args.InfoBaseRef):
        print("Error: specify -InfoBasePath or -InfoBaseServer + -InfoBaseRef", file=sys.stderr)
        sys.exit(1)

    arguments = ["DESIGNER"]
    if args.InfoBaseServer and args.InfoBaseRef:
        arguments.extend(["/S", f"{args.InfoBaseServer}/{args.InfoBaseRef}"])
    else:
        arguments.extend(["/F", args.InfoBasePath])
    if args.UserName:
        arguments.append(f"/N{args.UserName}")
    if args.Password:
        arguments.append(f"/P{args.Password}")
    arguments.extend(["/DumpIB", args.OutputFile])
    out_file = os.path.join(tempfile.gettempdir(), f"db_backup_{random.randint(0, 999999)}.txt")
    arguments.extend(["/Out", out_file])
    arguments.append("/DisableStartupDialogs")

    masked = ["/P********" if a.startswith("/P") and len(a) > 2 else a for a in arguments]
    print(f"Running: 1cv8.exe {' '.join(masked)}")
    result = subprocess.run([v8path] + arguments, capture_output=True, text=True)

    if os.path.isfile(out_file):
        try:
            with open(out_file, "r", encoding="utf-8-sig") as f:
                log = f.read()
            if log.strip():
                print("--- Log ---")
                print(log)
                print("--- End ---")
        except Exception:
            pass
        finally:
            try:
                os.remove(out_file)
            except OSError:
                pass

    if result.returncode == 0 and os.path.isfile(args.OutputFile):
        size_mb = os.path.getsize(args.OutputFile) / 1024 / 1024
        print(f"Backup completed: {args.OutputFile} ({size_mb:.1f} MB)")
        extra = ({"server": args.InfoBaseServer, "ref": args.InfoBaseRef}
                 if args.InfoBaseServer else {"path": args.InfoBasePath})
        write_manifest("dt", args.OutputFile, extra)
    else:
        print(f"DT dump failed (code {result.returncode}). For a busy server infobase "
              f"use -Mode sql (online) or disconnect sessions first.", file=sys.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
