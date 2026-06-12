#!/usr/bin/env python3
# db-restore v1.0 — Restore 1C infobase from backup (.dt or MS SQL .bak). DESTRUCTIVE.

import argparse
import glob
import os
import random
import shutil
import subprocess
import sys
import tempfile


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


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Restore 1C infobase from backup (DESTRUCTIVE)",
                                     allow_abbrev=False)
    parser.add_argument("-Mode", required=True, choices=["dt", "sql"])
    parser.add_argument("-InputFile", required=True)
    parser.add_argument("-IAmSure", action="store_true")
    parser.add_argument("-V8Path", default="")
    parser.add_argument("-InfoBasePath", default="")
    parser.add_argument("-InfoBaseServer", default="")
    parser.add_argument("-InfoBaseRef", default="")
    parser.add_argument("-UserName", default="")
    parser.add_argument("-Password", default="")
    parser.add_argument("-PasswordEnv", default="", help="Env var holding the password")
    parser.add_argument("-SqlServer", default="localhost")
    parser.add_argument("-SqlDatabase", default="")
    args = parser.parse_args()

    if not args.IAmSure:
        print("Refusing to restore: this OVERWRITES the target database. "
              "Re-run with -IAmSure after the user explicitly confirmed.", file=sys.stderr)
        sys.exit(2)
    if not os.path.isfile(args.InputFile):
        print(f"Error: backup file not found: {args.InputFile}", file=sys.stderr)
        sys.exit(1)

    manifest = args.InputFile + ".manifest.json"
    if os.path.isfile(manifest):
        print("--- Backup manifest ---")
        with open(manifest, "r", encoding="utf-8") as f:
            print(f.read())
        print("-----------------------")

    args.Password = resolve_password(args.Password, args.PasswordEnv)

    if args.Mode == "sql":
        if not args.SqlDatabase:
            print("Error: specify -SqlDatabase for sql mode", file=sys.stderr)
            sys.exit(1)
        if not shutil.which("sqlcmd"):
            print("Error: sqlcmd not found in PATH", file=sys.stderr)
            sys.exit(1)
        db_esc = args.SqlDatabase.replace("]", "]]")
        file_esc = args.InputFile.replace("'", "''")
        query = (
            f"ALTER DATABASE [{db_esc}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;\n"
            f"RESTORE DATABASE [{db_esc}] FROM DISK = N'{file_esc}' WITH REPLACE, CHECKSUM, STATS = 10;\n"
            f"ALTER DATABASE [{db_esc}] SET MULTI_USER;"
        )
        print(f"Restoring [{args.SqlDatabase}] on {args.SqlServer} from {args.InputFile} ...")
        result = subprocess.run(["sqlcmd", "-S", args.SqlServer, "-E", "-b", "-Q", query])
        if result.returncode == 0:
            print(f"Restore completed: [{args.SqlDatabase}] <- {args.InputFile}")
        else:
            print(f"SQL restore failed (code {result.returncode}). Check database state: "
                  f"it may be left in SINGLE_USER or RESTORING.", file=sys.stderr)
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
    arguments.extend(["/RestoreIB", args.InputFile])
    out_file = os.path.join(tempfile.gettempdir(), f"db_restore_{random.randint(0, 999999)}.txt")
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

    if result.returncode == 0:
        print(f"Restore completed from: {args.InputFile}")
    else:
        print(f"RestoreIB failed (code {result.returncode}). Server infobases require "
              f"exclusive access — disconnect sessions first.", file=sys.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
