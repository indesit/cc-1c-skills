---
name: srv-sessions
description: Сеансы кластера 1С через rac — список активных сеансов, завершение сеанса или всех сеансов базы. Используй когда нужно посмотреть кто работает в базе, завершить зависший сеанс, освободить базу перед обновлением
argument-hint: "[list|terminate] [база] [session-id]"
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /srv-sessions — Сеансы кластера 1С

Список и завершение сеансов через `rac`. Завершение сеанса **разрывает работу пользователя** — для `terminate` обязательно подтверждение пользователя (AskUserQuestion), скрипт требует `-IAmSure`.

Типовой сценарий «освободить базу перед db-update / restore»:
1. `list` по базе — показать пользователю, кто внутри.
2. После подтверждения: `terminate -All -Infobase <база> -IAmSure`.
3. Повторный `list` — убедиться, что база свободна.

## Предусловие

Нужен работающий RAS (см. `/srv-info`, раздел «Предусловие: RAS»).

## Команда

```powershell
powershell.exe -NoProfile -File .claude/skills/srv-sessions/scripts/srv-sessions.ps1 <параметры>
```

### Параметры скрипта

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `-Action <list\|terminate>` | нет | По умолчанию `list` |
| `-V8Path <путь>` | нет | Каталог bin платформы (для поиска rac.exe) |
| `-RasAddress <host:port>` | нет | Адрес RAS (по умолчанию `localhost:1545`) |
| `-Infobase <имя>` | нет | Фильтр по имени информационной базы (как в кластере) |
| `-SessionId <uuid>` | terminate* | Конкретный сеанс |
| `-All` | terminate* | Все сеансы (в сочетании с `-Infobase` — все сеансы базы) |
| `-IAmSure` | для terminate | Подтверждение (только после согласия пользователя!) |
| `-ClusterUser / -ClusterPwd / -ClusterPwdEnv` | нет | Администратор кластера |

> `*` — для `terminate` нужен либо `-SessionId`, либо `-All`

## Коды возврата

| Код | Описание |
|-----|----------|
| 0 | Успешно |
| 1 | Ошибка rac / RAS недоступен |
| 2 | terminate без `-IAmSure` |

## Примеры

```powershell
# Кто сейчас в базе
powershell.exe -NoProfile -File .claude/skills/srv-sessions/scripts/srv-sessions.ps1 -Infobase "MyApp_Prod"

# Завершить все сеансы базы перед обновлением (после подтверждения!)
powershell.exe -NoProfile -File .claude/skills/srv-sessions/scripts/srv-sessions.ps1 -Action terminate -All -Infobase "MyApp_Prod" -IAmSure
```
