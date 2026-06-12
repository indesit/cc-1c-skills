---
name: cf-check
description: Проверка конфигурации 1С средствами платформы (/CheckConfig, /CheckModules) — синтаксис модулей, целостность, ссылки. Используй перед загрузкой изменений в базу, после правок BSL, перед обновлением
argument-hint: "[database] [config|modules|all] [расширение]"
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /cf-check — Платформенная проверка конфигурации

Запускает штатные проверки Конфигуратора: `/CheckConfig` (целостность, ссылки, расширенная проверка модулей) и `/CheckModules` (синтаксический контроль для клиент-серверных контекстов). Операция **read-only** — базу не изменяет.

## Usage

```
/cf-check                       — база по умолчанию, обе проверки
/cf-check dev modules           — только синтаксис модулей
/cf-check bas all КассирАвтоКасса — проверка расширения
```

## Параметры подключения

Прочитай `.v8-project.json` из корня проекта. Возьми `v8path` и разреши базу (id → alias → name → ветка Git → default). Если у базы задано `passwordEnv` — передавай `-PasswordEnv <имя>` вместо `-Password`.

## Команда

```powershell
powershell.exe -NoProfile -File .claude/skills/cf-check/scripts/cf-check.ps1 <параметры>
```

### Параметры скрипта

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `-V8Path <путь>` | нет | Каталог bin платформы |
| `-InfoBasePath <путь>` | * | Файловая база |
| `-InfoBaseServer <сервер>` | * | Сервер 1С |
| `-InfoBaseRef <имя>` | * | Имя базы на сервере |
| `-UserName <имя>` | нет | Имя пользователя |
| `-Password <пароль>` | нет | Пароль |
| `-PasswordEnv <имя>` | нет | Имя переменной окружения с паролем — вместо `-Password` |
| `-Mode <config\|modules\|all>` | нет | Какие проверки запускать (по умолчанию `all`) |
| `-Extension <имя>` | нет | Проверять расширение вместо основной конфигурации |
| `-ConfigArgs <строка>` | нет | Переопределить набор флагов `/CheckConfig` |
| `-ModulesArgs <строка>` | нет | Переопределить набор флагов `/CheckModules` |

> `*` — нужен либо `-InfoBasePath`, либо пара `-InfoBaseServer` + `-InfoBaseRef`

### Наборы проверок по умолчанию

- `/CheckConfig`: `-ConfigLogIntegrity -IncorrectReferences -ExtendedModulesCheck`
- `/CheckModules`: `-ThinClient -Server`

## Коды возврата

| Код | Описание |
|-----|----------|
| 0 | Проверки пройдены |
| ≠0 | Найдены ошибки — покажи лог пользователю полностью |

## После выполнения

Лог печатается скриптом. Если код ≠ 0 — выведи список ошибок и предложи исправления. Не загружай конфигурацию в базу, пока проверка не проходит.

## Примеры

```powershell
# Полная проверка основной конфигурации (пароль из переменной окружения)
powershell.exe -NoProfile -File .claude/skills/cf-check/scripts/cf-check.ps1 -InfoBaseServer "srv01" -InfoBaseRef "MyApp" -UserName "Admin" -PasswordEnv "MYAPP_PASSWORD"

# Только синтаксис модулей расширения
powershell.exe -NoProfile -File .claude/skills/cf-check/scripts/cf-check.ps1 -InfoBaseServer "srv01" -InfoBaseRef "MyApp" -UserName "Admin" -PasswordEnv "MYAPP_PASSWORD" -Mode modules -Extension "МоёРасширение"
```
