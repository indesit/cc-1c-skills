#!/usr/bin/env python3
# cf-drift v1.0 — Detect drift between two 1C configuration XML dumps
# (e.g. local reference sources vs a fresh live dump). Read-only.

import argparse
import hashlib
import json
import os
import sys

DEFAULT_IGNORE = {"configdumpinfo.xml"}


def walk_tree(root):
    files = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            files[rel] = full
    return files


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Detect drift between two 1C configuration XML dump trees",
        allow_abbrev=False)
    parser.add_argument("-Reference", required=True, help="Reference tree (e.g. configSrc)")
    parser.add_argument("-Actual", required=True, help="Actual tree (e.g. fresh live dump)")
    parser.add_argument("-Json", default="")
    parser.add_argument("-MaxList", type=int, default=50, help="Max paths to print per category")
    parser.add_argument("-NoDefaultIgnore", action="store_true",
                        help="Do not ignore ConfigDumpInfo.xml")
    args = parser.parse_args()

    for p, label in ((args.Reference, "Reference"), (args.Actual, "Actual")):
        if not os.path.isdir(p):
            print(f"Error: {label} dir not found: {p}", file=sys.stderr)
            sys.exit(2)

    ignore = set() if args.NoDefaultIgnore else DEFAULT_IGNORE
    ref = {k: v for k, v in walk_tree(args.Reference).items()
           if os.path.basename(k).lower() not in ignore}
    act = {k: v for k, v in walk_tree(args.Actual).items()
           if os.path.basename(k).lower() not in ignore}

    added = sorted(set(act) - set(ref))
    removed = sorted(set(ref) - set(act))
    common = sorted(set(ref) & set(act))

    changed = []
    for rel in common:
        if os.path.getsize(ref[rel]) != os.path.getsize(act[rel]) or \
                sha256(ref[rel]) != sha256(act[rel]):
            changed.append(rel)

    drift = bool(added or removed or changed)
    print(f"Reference: {args.Reference} ({len(ref)} files)")
    print(f"Actual   : {args.Actual} ({len(act)} files)")
    print(f"Added: {len(added)}, removed: {len(removed)}, changed: {len(changed)}")

    for title, items in (("ADDED (in actual, not in reference)", added),
                         ("REMOVED (in reference, not in actual)", removed),
                         ("CHANGED (content differs)", changed)):
        if items:
            print(f"\n=== {title}: {len(items)} ===")
            for rel in items[:args.MaxList]:
                print(f"  {rel}")
            if len(items) > args.MaxList:
                print(f"  ... and {len(items) - args.MaxList} more")

    print(f"\nVerdict: {'DRIFT DETECTED' if drift else 'NO DRIFT'}")

    if args.Json:
        with open(args.Json, "w", encoding="utf-8") as f:
            json.dump({"reference": args.Reference, "actual": args.Actual,
                       "added": added, "removed": removed, "changed": changed,
                       "drift": drift}, f, ensure_ascii=False, indent=2)
        print(f"JSON report: {args.Json}")

    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    main()
