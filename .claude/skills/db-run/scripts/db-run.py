#!/usr/bin/env python3
# db-run v1.0 — Launch 1C:Enterprise
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills

import argparse
import glob
import os
import subprocess
import sys


def resolve_v8path(v8path):
    """Resolve path to 1cv8.exe."""
    if not v8path:
        found = sorted(glob.glob(r"C:\Program Files\1cv8\*\bin\1cv8.exe"))
        if found:
            return found[-1]
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
        description="Launch 1C:Enterprise",
        allow_abbrev=False,
    )
    parser.add_argument("-V8Path", default="")
    parser.add_argument("-InfoBasePath", default="")
    parser.add_argument("-InfoBaseServer", default="")
    parser.add_argument("-InfoBaseRef", default="")
    parser.add_argument("-UserName", default="")
    parser.add_argument("-Password", default="")
    parser.add_argument("-PasswordEnv", default="")
    parser.add_argument("-Execute", default="")
    parser.add_argument("-CParam", default="")
    parser.add_argument("-URL", default="")
    args = parser.parse_args()
    args.Password = resolve_password(args.Password, args.PasswordEnv)

    v8path = resolve_v8path(args.V8Path)

    # --- Validate connection ---
    if not args.InfoBasePath and (not args.InfoBaseServer or not args.InfoBaseRef):
        print("Error: specify -InfoBasePath or -InfoBaseServer + -InfoBaseRef", file=sys.stderr)
        sys.exit(1)

    # --- Build arguments ---
    arguments = ["ENTERPRISE"]

    if args.InfoBaseServer and args.InfoBaseRef:
        arguments.extend(["/S", f"{args.InfoBaseServer}/{args.InfoBaseRef}"])
    else:
        arguments.extend(["/F", args.InfoBasePath])

    if args.UserName:
        arguments.append(f"/N{args.UserName}")
    if args.Password:
        arguments.append(f"/P{args.Password}")

    # --- Optional params ---
    execute = args.Execute
    if execute:
        ext = os.path.splitext(execute)[1].lower()
        if ext == ".erf":
            print("[WARN] /Execute does not support ERF files (external reports).")
            print(f"       Open the report via File -> Open: {execute}")
            print("       Launching database without /Execute.")
            execute = ""

    if execute:
        arguments.extend(["/Execute", execute])
    if args.CParam:
        arguments.extend(["/C", args.CParam])
    if args.URL:
        arguments.extend(["/URL", args.URL])

    arguments.append("/DisableStartupDialogs")

    # --- Execute (background, no wait) ---
    masked = ["/P********" if a.startswith("/P") and len(a) > 2 else a for a in arguments]
    print(f"Running: 1cv8.exe {' '.join(masked)}")
    subprocess.Popen([v8path] + arguments)
    print("1C:Enterprise launched")


if __name__ == "__main__":
    main()
