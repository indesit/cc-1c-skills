#!/usr/bin/env python3
# log-analyze v1.1 — Analyze the 1C event log (журнал регистрации, old text format:
# 1Cv8.lgf dictionary + daily *.lgp files). Read-only.

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta

SEVERITY_NAMES = {"I": "Information", "E": "Error", "W": "Warning", "N": "Note"}


def find_log_dirs(infobase):
    """Discover 1Cv8Log dirs under srvinfo of any installed platform."""
    patterns = [
        r"C:\Program Files\1cv8\srvinfo\reg_*\*\1Cv8Log",
        r"C:\Program Files\BAF\srvinfo\reg_*\*\1Cv8Log",
        r"C:\Program Files (x86)\1cv8\srvinfo\reg_*\*\1Cv8Log",
    ]
    found = []
    for p in patterns:
        found.extend(glob.glob(p))
    if infobase:
        found = [f for f in found if infobase.lower() in f.lower()]
    return found


def parse_lgf(lgf_path):
    """Parse the dictionary: users, computers, apps, events, metadata."""
    text = ""
    with open(lgf_path, "r", encoding="utf-8-sig", errors="replace") as f:
        text = f.read()
    dicts = {"users": {0: "<система>"}, "computers": {0: ""}, "apps": {0: ""},
             "events": {0: ""}, "metadata": {0: ""}}
    for name, idx in re.findall(r'\{1,[0-9a-fA-F-]+,"((?:[^"]|"")*)",(\d+)\}', text):
        dicts["users"][int(idx)] = name or "<анонимно>"
    for name, idx in re.findall(r'\{2,"((?:[^"]|"")*)",(\d+)\}', text):
        dicts["computers"][int(idx)] = name
    for name, idx in re.findall(r'\{3,"((?:[^"]|"")*)",(\d+)\}', text):
        dicts["apps"][int(idx)] = name
    for name, idx in re.findall(r'\{4,"((?:[^"]|"")*)",(\d+)\}', text):
        dicts["events"][int(idx)] = name
    for name, idx in re.findall(r'\{9,[0-9a-fA-F-]+,"((?:[^"]|"")*)",(\d+)\}', text):
        dicts["metadata"][int(idx)] = name
    return dicts


def split_top_level(body):
    """Split record body into top-level comma-separated fields (brace/quote aware)."""
    fields, depth, in_str, cur = [], 0, False, []
    i = 0
    while i < len(body):
        ch = body[i]
        if in_str:
            if ch == '"':
                if i + 1 < len(body) and body[i + 1] == '"':
                    cur.append('""')
                    i += 2
                    continue
                in_str = False
            cur.append(ch)
        elif ch == '"':
            in_str = True
            cur.append(ch)
        elif ch == "{":
            depth += 1
            cur.append(ch)
        elif ch == "}":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            fields.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    if cur:
        fields.append("".join(cur).strip())
    return fields


RECORD_START_RE = re.compile(r"^\{(\d{14}),", re.M)


def iter_records(lgp_path):
    """Yield (timestamp_str, fields) per record."""
    with open(lgp_path, "r", encoding="utf-8-sig", errors="replace") as f:
        text = f.read()
    starts = [m for m in RECORD_START_RE.finditer(text)]
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        chunk = text[m.end():end]
        # trim trailing "},\n"
        chunk = chunk.rstrip()
        if chunk.endswith("},"):
            chunk = chunk[:-2]
        elif chunk.endswith("}"):
            chunk = chunk[:-1]
        yield m.group(1), split_top_level(chunk)


def unquote(s):
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace('""', '"')
    return s


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Analyze 1C event log (old text format)",
                                     allow_abbrev=False)
    parser.add_argument("-LogDir", default="", help="1Cv8Log directory (auto-discover if omitted)")
    parser.add_argument("-Infobase", default="", help="Infobase UUID filter for auto-discovery")
    parser.add_argument("-From", dest="From", default="", help="yyyy-mm-dd (default: last 7 days)")
    parser.add_argument("-To", dest="To", default="", help="yyyy-mm-dd (default: today)")
    parser.add_argument("-Severity", default="E,W", help="Comma list of I,E,W,N (default E,W)")
    parser.add_argument("-Top", type=int, default=10)
    parser.add_argument("-Details", type=int, default=20, help="How many newest records to print")
    parser.add_argument("-Json", default="")
    args = parser.parse_args()

    log_dir = args.LogDir
    if not log_dir:
        dirs = find_log_dirs(args.Infobase)
        if not dirs:
            print("Error: no 1Cv8Log directories found; specify -LogDir", file=sys.stderr)
            sys.exit(1)
        if len(dirs) > 1 and not args.Infobase:
            print("Multiple event logs found, using the first; narrow with -Infobase or -LogDir:",
                  file=sys.stderr)
            for d in dirs:
                print(f"  {d}", file=sys.stderr)
        log_dir = dirs[0]

    lgf = os.path.join(log_dir, "1Cv8.lgf")
    if not os.path.isfile(lgf):
        print(f"Error: {lgf} not found (new .lgd SQLite format is not supported by this skill yet)",
              file=sys.stderr)
        sys.exit(1)
    dicts = parse_lgf(lgf)

    to_date = datetime.strptime(args.To, "%Y-%m-%d") if args.To else datetime.now()
    from_date = (datetime.strptime(args.From, "%Y-%m-%d") if args.From
                 else to_date - timedelta(days=7))
    sev_filter = {s.strip().upper() for s in args.Severity.split(",") if s.strip()}

    lo, hi = from_date.strftime("%Y%m%d%H%M%S"), to_date.strftime("%Y%m%d") + "235959"

    by_severity, by_event, by_user = Counter(), Counter(), Counter()
    details = []
    files_used = 0
    all_lgps = sorted(glob.glob(os.path.join(log_dir, "*.lgp")))
    # Always include the last .lgp file: when log rotation stopped, all newer events
    # accumulate in it regardless of the date in its filename.
    files_to_scan = [lgp for lgp in all_lgps if lo[:8] <= os.path.basename(lgp)[:8] <= hi[:8]]
    if all_lgps and all_lgps[-1] not in files_to_scan:
        files_to_scan.append(all_lgps[-1])
        files_to_scan.sort()
    for lgp in files_to_scan:
        files_used += 1
        for ts, fields in iter_records(lgp):
            if ts < lo or ts > hi or len(fields) < 11:
                continue
            severity = fields[7].strip()
            if severity not in SEVERITY_NAMES:
                continue
            by_severity[severity] += 1
            if severity not in sev_filter:
                continue
            event = dicts["events"].get(int(fields[6]) if fields[6].isdigit() else -1, fields[6])
            user = dicts["users"].get(int(fields[2]) if fields[2].isdigit() else -1, fields[2])
            meta_idx = fields[9]
            metadata = dicts["metadata"].get(int(meta_idx) if meta_idx.isdigit() else -1, "")
            by_event[event] += 1
            by_user[user] += 1
            details.append({
                "time": f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]} {ts[8:10]}:{ts[10:12]}:{ts[12:14]}",
                "severity": SEVERITY_NAMES[severity],
                "event": event,
                "user": user,
                "metadata": metadata,
                "comment": unquote(fields[8])[:500],
            })

    print(f"Log dir : {log_dir}")
    print(f"Period  : {from_date:%Y-%m-%d} .. {to_date:%Y-%m-%d}  (files scanned: {files_used})")
    print(f"All records by severity: " +
          ", ".join(f"{SEVERITY_NAMES[k]}={v}" for k, v in sorted(by_severity.items())) or "none")
    print(f"Filtered ({','.join(sorted(sev_filter))}): {len(details)} records")

    if by_event:
        print(f"\n=== Top events ===")
        for ev, n in by_event.most_common(args.Top):
            print(f"  {n:6}  {ev}")
        print(f"\n=== Top users ===")
        for u, n in by_user.most_common(args.Top):
            print(f"  {n:6}  {u}")
        print(f"\n=== Newest {min(args.Details, len(details))} records ===")
        for d in sorted(details, key=lambda x: x["time"], reverse=True)[:args.Details]:
            line = f"  {d['time']} [{d['severity']}] {d['event']} | {d['user']}"
            if d["metadata"]:
                line += f" | {d['metadata']}"
            print(line)
            if d["comment"]:
                print(f"      {d['comment'][:300]}")

    if args.Json:
        with open(args.Json, "w", encoding="utf-8") as f:
            json.dump({"summary": {str(k): v for k, v in by_severity.items()},
                       "events": dict(by_event), "users": dict(by_user),
                       "records": details}, f, ensure_ascii=False, indent=2)
        print(f"\nJSON report: {args.Json}")
    sys.exit(0)


if __name__ == "__main__":
    main()
