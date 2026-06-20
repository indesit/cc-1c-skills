---
name: db-backup
description: Резервное копирование информационной базы 1С — выгрузка .dt через Конфигуратор или online-бэкап MS SQL. Используй когда пользователь просит сделать бэкап базы, резервную копию, перед обновлением или загрузкой изменений
argument-hint: "[database] [dt|sql] [выходной файл]"
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /db-backup — Резервное копирование информационной базы

Два режима:

| Режим | Механизм | Когда использовать |
|-------|----------|--------------------|
| `dt` | Конфигуратор `/DumpIB` | Файловые базы; серверные — только без активных сеансов (нужен монопольный доступ) |
| `sql` | `BACKUP DATABASE ... WITH COPY_ONLY` через `sqlcmd` | Серверные базы на MS SQL — **работает online**, не мешает пользователям. Предпочтительный режим для рабочих баз |

Рядом с бэкапом пишется манифест `<файл>.manifest.json` (время, режим, база, размер).

## Параметры подключения

Прочитай `.v8-project.json`, разреши базу (id → alias → name → ветка → default). Если задано `passwordEnv` — передавай `-PasswordEnv`. Для режима `sql` имя базы MS SQL часто совпадает с `ref` серверной базы — уточни у пользователя при первом использовании и предложи сохранить в реестре (поле `sqlDatabase`).

## Команда

```powershell
powershell.exe -NoProfile -File .claude/skills/db-backup/scripts/db-backup.ps1 <параметры>
```

### Параметры скрипта

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `-Mode <dt\|sql>` | да | Режим бэкапа |
| `-OutputFile <путь>` | да | Файл бэкапа (`.dt` или `.bak`) |
| `-V8Path <путь>` | dt | Каталог bin платформы |
| `-InfoBasePath <путь>` | dt* | Файловая база |
| `-InfoBaseServer <сервер>` | dt* | Сервер 1С |
| `-InfoBaseRef <имя>` | dt* | Имя базы на сервере 1С |
| `-UserName <имя>` | нет | Пользователь 1С (dt) |
| `-Password <пароль>` | нет | Пароль (dt) |
| `-PasswordEnv <имя>` | нет | Переменная окружения с паролем — вместо `-Password` |
| `-SqlServer <адрес>` | нет | Сервер MS SQL (по умолчанию `localhost`, Windows-аутентификация) |
| `-SqlDatabase <имя>` | sql | Имя базы данных MS SQL |
| `-Compress` | нет | (sql) добавить `WITH COMPRESSION` — меньший `.bak`; полезно, когда на диске мало места (типично сжатие 3–4×) |

> `*` — для `dt`: либо `-InfoBasePath`, либо `-InfoBaseServer` + `-InfoBaseRef`

## Важно

- Режим `sql` использует `COPY_ONLY` — не ломает существующую цепочку бэкапов DBA.
- Режим `dt` на серверной базе с активными сеансами завершится ошибкой — это нормально; предложи режим `sql` или завершение сеансов.
- Путь `-OutputFile` для `sql` — путь **на машине MS SQL сервера**.
- `.dt` — не средство долговременного архива (привязан к версии платформы); для регулярных бэкапов рекомендуй `sql`.

## После выполнения

Покажи путь, размер из манифеста и статус. При ошибке — лог целиком.

## Примеры

```powershell
# Online-бэкап MS SQL (рекомендуется для рабочих серверных баз)
powershell.exe -NoProfile -File .claude/skills/db-backup/scripts/db-backup.ps1 -Mode sql -SqlDatabase "MyApp_Prod" -OutputFile "D:\backups\MyApp_Prod_20260612.bak"

# Выгрузка .dt файловой базы
powershell.exe -NoProfile -File .claude/skills/db-backup/scripts/db-backup.ps1 -Mode dt -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -PasswordEnv "MYDB_PASSWORD" -OutputFile "D:\backups\MyDB.dt"
```
