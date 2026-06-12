#!/usr/bin/env python3
# srv-sessions v1.0 — 1C cluster sessions via rac: list and terminate (with safeguards).

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
        print(f"Error: rac failed (is RAS running at {ras_address}? see /srv-info SKILL.md): {msg}",
              file=sys.stderr)
        sys.exit(1)
    return result.stdout


def parse_blocks(text):
    blocks, current = [], {}
    for line in text.splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = {}
            continue
        m = re.match(r"^\s*([\w-]+)\s*:\s*(.*)$", line)
        if m:
            current[m.group(1)] = m.group(2).strip().strip('"')
    if current:
        blocks.append(current)
    return blocks


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="1C cluster sessions via rac", allow_abbrev=False)
    parser.add_argument("-Action", default="list", choices=["list", "terminate"])
    parser.add_argument("-V8Path", default="")
    parser.add_argument("-RasAddress", default="localhost:1545")
    parser.add_argument("-Infobase", default="")
    parser.add_argument("-SessionId", default="")
    parser.add_argument("-All", action="store_true")
    parser.add_argument("-IAmSure", action="store_true")
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
    m = re.search(r"^cluster\s*:\s*(\S+)", cluster_out, re.M)
    if not m:
        print("Error: no cluster found", file=sys.stderr)
        sys.exit(1)
    cl = m.group(1)

    ib_filter = []
    if args.Infobase:
        ib_out = run_rac(rac, args.RasAddress, ["infobase", "summary", "list", f"--cluster={cl}"] + auth)
        ibs = parse_blocks(ib_out)
        match = next((b for b in ibs if b.get("name", "").lower() == args.Infobase.lower()), None)
        if not match:
            known = ", ".join(b.get("name", "?") for b in ibs)
            print(f"Error: infobase '{args.Infobase}' not found in cluster. Known: {known}", file=sys.stderr)
            sys.exit(1)
        ib_filter = [f"--infobase={match['infobase']}"]

    sessions = parse_blocks(run_rac(rac, args.RasAddress,
                                    ["session", "list", f"--cluster={cl}"] + ib_filter + auth))

    if args.Action == "list":
        if not sessions:
            print("No active sessions.")
            return
        print(f"{'SESSION':<38} {'USER':<20} {'APP':<16} {'HOST':<12} STARTED")
        for s in sessions:
            print(f"{s.get('session', ''):<38} {s.get('user-name', ''):<20} "
                  f"{s.get('app-id', ''):<16} {s.get('host', ''):<12} {s.get('started-at', '')}")
        print(f"Total: {len(sessions)}")
        return

    # terminate
    if not args.SessionId and not args.All:
        print("Error: terminate requires -SessionId or -All", file=sys.stderr)
        sys.exit(1)
    if not args.IAmSure:
        print("Refusing to terminate sessions: this disconnects users. "
              "Re-run with -IAmSure after the user explicitly confirmed.", file=sys.stderr)
        sys.exit(2)

    targets = ([s for s in sessions if s.get("session") == args.SessionId]
               if args.SessionId else sessions)
    if not targets:
        print("Nothing to terminate (no matching sessions).")
        return

    failed = 0
    for s in targets:
        result = subprocess.run(
            [rac, "session", "terminate", f"--cluster={cl}", f"--session={s['session']}"]
            + auth + [args.RasAddress],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            failed += 1
            print(f"Failed: {s['session']}: {(result.stderr or result.stdout).strip()}", file=sys.stderr)
        else:
            print(f"Terminated: {s['session']} ({s.get('user-name', '?')}, {s.get('app-id', '?')})")
    print(f"Terminated {len(targets) - failed} of {len(targets)} session(s).")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
