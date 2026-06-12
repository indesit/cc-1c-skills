#!/usr/bin/env python3
# cf-check v1.0 — Platform-level 1C configuration check (/CheckConfig, /CheckModules). Read-only.

import argparse
import glob
import os
import random
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


def run_check(v8path, args, check_command, check_flags):
    arguments = ["DESIGNER"]
    if args.InfoBaseServer and args.InfoBaseRef:
        arguments.extend(["/S", f"{args.InfoBaseServer}/{args.InfoBaseRef}"])
    else:
        arguments.extend(["/F", args.InfoBasePath])
    if args.UserName:
        arguments.append(f"/N{args.UserName}")
    if args.Password:
        arguments.append(f"/P{args.Password}")

    arguments.append(check_command)
    arguments.extend(f for f in check_flags.split() if f)
    if args.Extension:
        arguments.extend(["-Extension", args.Extension])

    out_file = os.path.join(tempfile.gettempdir(), f"cf_check_{random.randint(0, 999999)}.txt")
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
                print(f"--- Log ({check_command}) ---")
                print(log)
                print("--- End ---")
        except Exception:
            pass
        finally:
            try:
                os.remove(out_file)
            except OSError:
                pass
    return result.returncode


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Platform 1C configuration check", allow_abbrev=False)
    parser.add_argument("-V8Path", default="")
    parser.add_argument("-InfoBasePath", default="")
    parser.add_argument("-InfoBaseServer", default="")
    parser.add_argument("-InfoBaseRef", default="")
    parser.add_argument("-UserName", default="")
    parser.add_argument("-Password", default="")
    parser.add_argument("-PasswordEnv", default="", help="Env var holding the password")
    parser.add_argument("-Mode", default="all", choices=["config", "modules", "all"])
    parser.add_argument("-Extension", default="")
    parser.add_argument("-ConfigArgs", default="-ConfigLogIntegrity -IncorrectReferences -ExtendedModulesCheck")
    parser.add_argument("-ModulesArgs", default="-ThinClient -Server")
    args = parser.parse_args()
    args.Password = resolve_password(args.Password, args.PasswordEnv)

    v8path = resolve_v8path(args.V8Path)
    if not args.InfoBasePath and (not args.InfoBaseServer or not args.InfoBaseRef):
        print("Error: specify -InfoBasePath or -InfoBaseServer + -InfoBaseRef", file=sys.stderr)
        sys.exit(1)

    exit_code = 0
    if args.Mode in ("config", "all"):
        code = run_check(v8path, args, "/CheckConfig", args.ConfigArgs)
        print("CheckConfig: OK" if code == 0 else f"CheckConfig: FAILED (code {code})")
        exit_code = exit_code or code
    if args.Mode in ("modules", "all"):
        code = run_check(v8path, args, "/CheckModules", args.ModulesArgs)
        print("CheckModules: OK" if code == 0 else f"CheckModules: FAILED (code {code})")
        exit_code = exit_code or code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
