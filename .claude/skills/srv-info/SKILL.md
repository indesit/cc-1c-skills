---
name: srv-info
description: Стан кластера серверов 1С через rac — кластер, информационные базы, рабочие процессы, сводка сеансов. Используй когда пользователь спрашивает про состояние сервера 1С, кластер, список баз на сервере, рабочие процессы
argument-hint: "[cluster|infobases|processes|all]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /srv-info — Состояние кластера серверов 1С

Read-only обзор кластера через утилиту администрирования `rac`: параметры кластера, зарегистрированные информационные базы, рабочие процессы, количество сеансов.

## Предусловие: RAS

`rac` подключается к серверу администрирования (`ras`), который по умолчанию НЕ запущен. Если соединение отказано — установи RAS как службу Windows (однократно, от администратора):

```powershell
sc.exe --% create "1C RAS <версия>" binPath= "\"<bin>\ras.exe\" cluster --service --port=1545 localhost:1540" start= auto DisplayName= "1C Remote Administration Server (1545)"
sc.exe start "1C RAS <версия>"
```

где `<bin>` — каталог bin платформы (тот же `v8path` из `.v8-project.json`), `localhost:1540` — адрес агента кластера.

## Команда

```powershell
powershell.exe -NoProfile -File .claude/skills/srv-info/scripts/srv-info.ps1 <параметры>
```

### Параметры скрипта

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `-V8Path <путь>` | нет | Каталог bin платформы (для поиска rac.exe) |
| `-RasAddress <host:port>` | нет | Адрес RAS (по умолчанию `localhost:1545`) |
| `-Mode <cluster\|infobases\|processes\|all>` | нет | Что показать (по умолчанию `all`) |
| `-ClusterUser <имя>` | нет | Администратор кластера (если задан) |
| `-ClusterPwd <пароль>` | нет | Пароль администратора кластера |
| `-ClusterPwdEnv <имя>` | нет | Переменная окружения с паролем кластера |

## После выполнения

Покажи результат компактно. Если соединение отказано — приведи инструкцию установки RAS из раздела «Предусловие».

## Примеры

```powershell
powershell.exe -NoProfile -File .claude/skills/srv-info/scripts/srv-info.ps1 -V8Path "C:\Program Files\1cv8\8.3.25.1257\bin"
powershell.exe -NoProfile -File .claude/skills/srv-info/scripts/srv-info.ps1 -Mode infobases
```
