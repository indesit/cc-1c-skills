#!/usr/bin/env python3
# cfe-compat v1.0 — Check 1C extension (CFE XML sources) compatibility against a base
# configuration dump: borrowed objects exist, intercepted methods exist with matching
# signatures, called base-module symbols still resolve.

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

MD_NS = "{http://v8.1c.ru/8.3/MDClasses}"

ANNOTATION_RE = re.compile(
    r'&(Перед|После|Вместо|ИзменениеИКонтроль|Before|After|Around|ChangeAndValidate)'
    r'\s*\(\s*"([^"]+)"\s*\)', re.IGNORECASE)

PROC_DEF_RE = re.compile(
    r'^\s*(?:Процедура|Функция|Procedure|Function)\s+'
    r'([\wА-Яа-яЁё_][\wА-Яа-яЁё0-9_]*)\s*\(([^)]*)\)', re.IGNORECASE | re.MULTILINE)

CALL_RE = re.compile(r'(?<![.\wА-Яа-яЁё_])([\wА-Яа-яЁё_][\wА-Яа-яЁё0-9_]*)\s*\(')

BSL_KEYWORDS = {
    "если", "тогда", "иначеесли", "пока", "для", "возврат", "новый", "не", "и", "или",
    "if", "while", "for", "return", "new", "not", "and", "or", "elsif",
}

# Common platform builtins (lowercased) — called without a dot, defined nowhere in sources.
BSL_BUILTINS = {
    "стрдлина", "сокрл", "сокрп", "сокрлп", "лев", "прав", "сред", "стрнайти", "врег",
    "нрег", "трег", "пустаястрока", "стрзаменить", "стрчислострок", "стрполучитьстроку",
    "стрчисловхождений", "стрсравнить", "стрначинаетсяс", "стрзаканчиваетсяна",
    "стрразделить", "стрсоединить", "стршаблон", "символ", "кодсимвола", "число",
    "строка", "дата", "булево", "цел", "окр", "макс", "мин", "log", "log10", "exp",
    "sqrt", "pow", "sin", "cos", "tan", "текущаядата", "годчисло", "месяц", "день",
    "час", "минута", "секунда", "началогода", "началомесяца", "началодня",
    "началонедели", "началоквартала", "конецгода", "конецмесяца", "конецдня",
    "конецнедели", "конецквартала", "добавитьмесяц", "деньгода", "деньнедели",
    "неделягода", "типзнч", "тип", "значениезаполнено", "заполнитьзначениясвойств",
    "получитьидентификаторвременногофайла", "сообщить", "вопрос", "предупреждение",
    "оповестить", "обработкапрерыванияпользователя", "состояние",
    "показатьвопрос", "показатьпредупреждение", "показатьзначение",
    "показатьоповещениепользователя", "открытьформу", "открытьзначение",
    "получитьформу", "закрытьсправку", "поместитьфайл", "начатьпомещениефайла",
    "переключитьинтерфейс", "установитькраткийзаголовокприложения",
    "найти", "найтипозначению", "вычислить", "выполнить", "значениевстрокувнутр",
    "значениеизстрокивнутр", "значениевфайл", "значениеизфайла",
    "xmlстрока", "xmlзначение", "xmlтип", "xmlтипзнч", "изxmlтипа",
    "возможностьчтенияxml", "прочитатьxml", "записатьxml", "прочитатьjson",
    "записатьjson", "текущаядатасеанса", "текущаяуниверсальнаядата",
    "текущаяуниверсальнаядатавмиллисекундах", "местноевремя", "универсальноевремя",
    "часовойпояс", "представлениепериода", "форматироватьчисло", "формат",
    "числопрописью", "нстр", "стрформат", "предопределенноезначение",
    "получитьполноеимяпредопределенногозначения", "начатьтранзакцию",
    "зафиксироватьтранзакцию", "отменитьтранзакцию", "транзакцияактивна",
    "установитьпривилегированныйрежим", "привилегированныйрежим",
    "обновитьповторноиспользуемыезначения", "подключитьобработчикожидания",
    "отключитьобработчикожидания", "подключитьобработчикоповещения",
    "отключитьобработчикоповещения", "оповеститьобизменении",
    "заблокироватьработупользователя", "получитьссылки", "установитьсоответствиеобъектовприобмене",
    "errorinfo", "raise", "информацияобошибке", "краткоепредставлениеошибки",
    "подробноепредставлениеошибки", "категорияошибки",
}


def report_add(report, severity, kind, message, **details):
    report[severity].append({"kind": kind, "message": message, **details})


def parse_object_belonging(xml_path):
    """Return 'Adopted'/'Native'/None for a metadata object XML file."""
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return None
    for el in tree.iter():
        if el.tag.endswith("}ObjectBelonging") or el.tag == "ObjectBelonging":
            return el.text
    return None


def find_metadata_files(root_dir):
    """Yield (relpath, abspath) for top-level metadata object XML files: <Type>/<Name>.xml."""
    for type_dir in sorted(os.listdir(root_dir)):
        type_path = os.path.join(root_dir, type_dir)
        if not os.path.isdir(type_path) or type_dir in ("Ext",):
            continue
        for entry in sorted(os.listdir(type_path)):
            if entry.lower().endswith(".xml"):
                yield (f"{type_dir}/{entry}", os.path.join(type_path, entry))


def strip_strings_and_comments(code):
    code = re.sub(r"//[^\n]*", "", code)
    code = re.sub(r'"(?:[^"]|"")*"', '""', code)
    # annotation/preprocessor lines (&Перед(...), #Если ...) are not calls
    code = re.sub(r"(?m)^\s*[&#].*$", "", code)
    # `Новый Тип(...)` / `New Type(...)` — constructor, not a function call
    code = re.sub(r"(?i)\b(Новый|New)\s+[\wА-Яа-яЁё_][\wА-Яа-яЁё0-9_]*\s*\(", "(", code)
    return code


def collect_defs(code):
    return {m.group(1).lower(): len([p for p in m.group(2).split(",") if p.strip()])
            for m in PROC_DEF_RE.finditer(code)}


def read_text(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def check_modules(ext_path, cfg_path, report):
    """Walk extension .bsl modules; verify interceptors and called symbols against base."""
    checked_modules = 0
    for dirpath, _dirnames, filenames in os.walk(ext_path):
        for fn in filenames:
            if not fn.lower().endswith(".bsl"):
                continue
            ext_module = os.path.join(dirpath, fn)
            rel = os.path.relpath(ext_module, ext_path).replace("\\", "/")
            base_module = os.path.join(cfg_path, rel.replace("/", os.sep))

            ext_code = strip_strings_and_comments(read_text(ext_module))
            ext_defs = collect_defs(ext_code)
            annotations = ANNOTATION_RE.findall(read_text(ext_module))

            if not os.path.isfile(base_module):
                if annotations:
                    report_add(report, "errors", "missing-base-module",
                               f"{rel}: модуль перехватывает методы, но базовый модуль не найден",
                               module=rel)
                continue

            checked_modules += 1
            base_code = strip_strings_and_comments(read_text(base_module))
            base_defs = collect_defs(base_code)

            # 1. Interceptor targets must exist in the base module
            for ann_type, target in annotations:
                t = target.lower()
                if t not in base_defs:
                    report_add(report, "errors", "missing-intercept-target",
                               f"{rel}: &{ann_type}(\"{target}\") — метод не найден в базовом модуле",
                               module=rel, target=target, annotation=ann_type)
                    continue
                # signature: interceptor proc params vs base proc params
                base_params = base_defs[t]
                # find the interceptor procedure that follows this annotation in source
                src = read_text(ext_module)
                ann_pos = src.lower().find(f'"{t}"')
                if ann_pos >= 0:
                    m = PROC_DEF_RE.search(src, ann_pos)
                    if m:
                        own_params = len([p for p in m.group(2).split(",") if p.strip()])
                        if own_params != base_params:
                            report_add(report, "warnings", "signature-mismatch",
                                       f"{rel}: &{ann_type}(\"{target}\") — параметров у перехватчика "
                                       f"{own_params}, у базового метода {base_params}",
                                       module=rel, target=target,
                                       interceptor_params=own_params, base_params=base_params)

            # 2. Called symbols that resolve neither locally nor in base nor builtins
            calls = {c.lower() for c in CALL_RE.findall(ext_code)}
            for call in sorted(calls):
                if (call in ext_defs or call in base_defs or call in BSL_BUILTINS
                        or call in BSL_KEYWORDS or len(call) < 3):
                    continue
                report_add(report, "warnings", "unresolved-call",
                           f"{rel}: вызов {call}() не найден ни в расширении, ни в базовом модуле "
                           f"(возможно платформенный/общий метод — проверь вручную)",
                           module=rel, symbol=call)
    return checked_modules


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Check 1C extension compatibility against a base configuration dump",
        allow_abbrev=False)
    parser.add_argument("-ExtensionPath", required=True, help="Extension XML sources dir")
    parser.add_argument("-ConfigPath", required=True, help="Base configuration dump dir")
    parser.add_argument("-Json", default="", help="Optional path for JSON report")
    parser.add_argument("-Strict", action="store_true", help="Warnings also fail (exit 1)")
    args = parser.parse_args()

    for p, label in ((args.ExtensionPath, "ExtensionPath"), (args.ConfigPath, "ConfigPath")):
        if not os.path.isfile(os.path.join(p, "Configuration.xml")):
            print(f"Error: {label} '{p}' has no Configuration.xml", file=sys.stderr)
            sys.exit(1)

    report = {"errors": [], "warnings": [], "summary": {}}

    # --- Borrowed top-level objects must exist in base ---
    borrowed, native = [], []
    for rel, abspath in find_metadata_files(args.ExtensionPath):
        belonging = parse_object_belonging(abspath)
        if belonging == "Adopted":
            borrowed.append(rel)
            if not os.path.isfile(os.path.join(args.ConfigPath, rel.replace("/", os.sep))):
                report_add(report, "errors", "missing-borrowed-object",
                           f"{rel}: заимствованный объект отсутствует в базовой конфигурации",
                           object=rel)
        else:
            native.append(rel)

    # --- Borrowed forms must exist in base ---
    form_count = 0
    for dirpath, dirnames, filenames in os.walk(args.ExtensionPath):
        if os.path.basename(dirpath) != "Forms":
            continue
        for fn in filenames:
            if not fn.lower().endswith(".xml"):
                continue
            form_xml = os.path.join(dirpath, fn)
            rel = os.path.relpath(form_xml, args.ExtensionPath).replace("\\", "/")
            if parse_object_belonging(form_xml) == "Adopted":
                form_count += 1
                if not os.path.isfile(os.path.join(args.ConfigPath, rel.replace("/", os.sep))):
                    report_add(report, "errors", "missing-borrowed-form",
                               f"{rel}: заимствованная форма отсутствует в базовой конфигурации",
                               form=rel)

    checked_modules = check_modules(args.ExtensionPath, args.ConfigPath, report)

    report["summary"] = {
        "extension": args.ExtensionPath,
        "config": args.ConfigPath,
        "borrowedObjects": len(borrowed),
        "ownObjects": len(native),
        "borrowedForms": form_count,
        "checkedModules": checked_modules,
        "errors": len(report["errors"]),
        "warnings": len(report["warnings"]),
    }

    # --- Output ---
    s = report["summary"]
    print(f"Extension : {s['extension']}")
    print(f"Base      : {s['config']}")
    print(f"Borrowed objects: {s['borrowedObjects']}, own: {s['ownObjects']}, "
          f"borrowed forms: {s['borrowedForms']}, modules checked: {s['checkedModules']}")
    if report["errors"]:
        print(f"\n=== ERRORS ({len(report['errors'])}) ===")
        for e in report["errors"]:
            print(f"  [{e['kind']}] {e['message']}")
    if report["warnings"]:
        print(f"\n=== WARNINGS ({len(report['warnings'])}) ===")
        for w in report["warnings"]:
            print(f"  [{w['kind']}] {w['message']}")
    verdict = "INCOMPATIBLE" if report["errors"] else (
        "COMPATIBLE (with warnings)" if report["warnings"] else "COMPATIBLE")
    print(f"\nVerdict: {verdict}")

    if args.Json:
        with open(args.Json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"JSON report: {args.Json}")

    if report["errors"] or (args.Strict and report["warnings"]):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
