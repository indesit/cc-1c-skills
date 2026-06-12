#!/usr/bin/env python3
# srv-info v1.0 — Read-only 1C cluster overview via rac: cluster, infobases, processes, sessions.

import argparse
import glob
import os
import re
import subprocess
import sys


def resolve_rac(v8path):
    candidates = []
    if v8path:
        base = v8path if os.path.isdir(v8path) else os.path.dirname(v8path)
        candidates.append(os.path.join(base, "rac.exe"))
    candidates.extend(sorted(glob.glob(r"C:\Program Files\1cv8\*\bin\rac.exe"), reverse=True))
    candidates.extend(sorted(glob.glob(r"C:\Program Files\BAF\*\bin\rac.exe"), reverse=True))
    for c in candidates:
        if os.path.isfile(c):
            return c
    print("Error: rac.exe not found. Specify -V8Path", file=sys.stderr)
    sys.exit(1)


def resolve_env(value, env_name):
    if value or not env_name:
        return value
    value = os.environ.get(env_name, "")
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
                        value = str(winreg.QueryValueEx(key, env_name)[0])
                        if value:
                            break
                except OSError:
                    continue
        except ImportError:
            pass
    return value


def run_rac(rac, ras_address, rac_args):
    result = subprocess.run([rac] + rac_args + [ras_address],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip()
        if re.search(r"No connection|refused|відмов|отказ|соедин|з.єднання", msg, re.I):
            print(f"Error: cannot connect to RAS at {ras_address}. "
                  f"Start the RAS service first (see SKILL.md). Details: {msg}", file=sys.stderr)
        else:
            print(f"Error: rac failed: {msg}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="1C cluster overview via rac", allow_abbrev=False)
    parser.add_argument("-V8Path", default="")
    parser.add_argument("-RasAddress", default="localhost:1545")
    parser.add_argument("-Mode", default="all", choices=["cluster", "infobases", "processes", "all"])
    parser.add_argument("-ClusterUser", default="")
    parser.add_argument("-ClusterPwd", default="")
    parser.add_argument("-ClusterPwdEnv", default="")
    args = parser.parse_args()

    rac = resolve_rac(args.V8Path)
    pwd = resolve_env(args.ClusterPwd, args.ClusterPwdEnv)
    auth = []
    if args.ClusterUser:
        auth.append(f"--cluster-user={args.ClusterUser}")
        if pwd:
            auth.append(f"--cluster-pwd={pwd}")

    cluster_out = run_rac(rac, args.RasAddress, ["cluster", "list"])
    print("=== Clusters ===")
    print(cluster_out)
    cluster_ids = re.findall(r"^cluster\s*:\s*(\S+)", cluster_out, re.M)
    if not cluster_ids:
        print("Error: no clusters found", file=sys.stderr)
        sys.exit(1)

    for cl in cluster_ids:
        if args.Mode in ("infobases", "all"):
            print(f"=== Infobases (cluster {cl}) ===")
            print(run_rac(rac, args.RasAddress, ["infobase", "summary", "list", f"--cluster={cl}"] + auth))
        if args.Mode in ("processes", "all"):
            print(f"=== Working processes (cluster {cl}) ===")
            out = run_rac(rac, args.RasAddress, ["process", "list", f"--cluster={cl}"] + auth)
            keys = ("process", "host", "port", "pid", "running", "memory-size", "connections", "started-at")
            for line in out.splitlines():
                if re.match(r"^({})\s*:".format("|".join(keys)), line.strip()):
                    print(line)
            print()
        if args.Mode == "all":
            out = run_rac(rac, args.RasAddress, ["session", "list", f"--cluster={cl}"] + auth)
            count = len(re.findall(r"^session\s*:", out, re.M))
            print(f"=== Sessions (cluster {cl}): {count} active ===")
    sys.exit(0)


if __name__ == "__main__":
    main()
