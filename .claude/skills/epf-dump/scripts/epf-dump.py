#!/usr/bin/env python3
# epf-dump v1.0 — Dump external data processor or report (EPF/ERF) to XML sources
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills

import argparse
import glob
import os
import random
import shutil
import subprocess
import sys
import tempfile


def resolve_v8path(v8path):
    """Resolve path to 1cv8.exe."""
    if not v8path:
        candidates = glob.glob(r"C:\Program Files\1cv8\*\bin\1cv8.exe")
        if candidates:
            candidates.sort()
            return candidates[-1]
        else:
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
    parser = argparse.ArgumentParser(
        description="Dump external data processor or report (EPF/ERF) to XML sources",
        allow_abbrev=False,
    )
    parser.add_argument("-V8Path", default="", help="Path to 1cv8.exe or its bin directory")
    parser.add_argument("-InfoBasePath", default="", help="Path to file infobase")
    parser.add_argument("-InfoBaseServer", default="", help="1C server (for server infobase)")
    parser.add_argument("-InfoBaseRef", default="", help="Infobase name on server")
    parser.add_argument("-UserName", default="", help="1C user name")
    parser.add_argument("-Password", default="", help="1C user password")
    parser.add_argument("-PasswordEnv", default="", help="Env var holding the password")
    parser.add_argument("-InputFile", required=True, help="Path to EPF/ERF file")
    parser.add_argument("-OutputDir", required=True, help="Directory for dumped XML sources")
    parser.add_argument(
        "-Format",
        default="Hierarchical",
        choices=["Hierarchical", "Plain"],
        help="Dump format (default: Hierarchical)",
    )
    args = parser.parse_args()
    args.Password = resolve_password(args.Password, args.PasswordEnv)

    # --- Resolve V8Path ---
    v8path = resolve_v8path(args.V8Path)

    # --- Validate database connection ---
    if not args.InfoBasePath and (not args.InfoBaseServer or not args.InfoBaseRef):
        print("Error: database connection required. Specify -InfoBasePath or -InfoBaseServer/-InfoBaseRef", file=sys.stderr)
        print("Dump in an empty database loses reference types (CatalogRef, DocumentRef, etc.) irreversibly.")
        sys.exit(1)

    # --- Validate input file ---
    if not os.path.isfile(args.InputFile):
        print(f"Error: input file not found: {args.InputFile}", file=sys.stderr)
        sys.exit(1)

    # --- Ensure output directory exists ---
    if not os.path.exists(args.OutputDir):
        os.makedirs(args.OutputDir, exist_ok=True)

    # --- Temp dir ---
    temp_dir = os.path.join(tempfile.gettempdir(), f"epf_dump_{random.randint(0, 999999)}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # --- Build arguments ---
        arguments = ["DESIGNER"]

        if args.InfoBaseServer and args.InfoBaseRef:
            arguments += ["/S", f"{args.InfoBaseServer}/{args.InfoBaseRef}"]
        else:
            arguments += ["/F", args.InfoBasePath]

        if args.UserName:
            arguments.append(f"/N{args.UserName}")
        if args.Password:
            arguments.append(f"/P{args.Password}")

        arguments += ["/DumpExternalDataProcessorOrReportToFiles", args.OutputDir, args.InputFile]
        arguments += ["-Format", args.Format]

        # --- Output ---
        out_file = os.path.join(temp_dir, "dump_log.txt")
        arguments += ["/Out", out_file]
        arguments.append("/DisableStartupDialogs")

        # --- Execute ---
        masked = ["/P********" if a.startswith("/P") and len(a) > 2 else a for a in arguments]
        print(f"Running: 1cv8.exe {' '.join(masked)}")
        result = subprocess.run(
            [v8path] + arguments,
            capture_output=True,
            text=True,
        )
        exit_code = result.returncode

        # --- Result ---
        if exit_code == 0:
            print(f"Dump completed successfully to: {args.OutputDir}")
        else:
            print(f"Error dumping (code: {exit_code})", file=sys.stderr)

        if os.path.isfile(out_file):
            try:
                with open(out_file, "r", encoding="utf-8-sig") as f:
                    log_content = f.read()
                if log_content:
                    print("--- Log ---")
                    print(log_content)
                    print("--- End ---")
            except Exception:
                pass

        sys.exit(exit_code)

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
