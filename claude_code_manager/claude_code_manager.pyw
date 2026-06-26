"""
=====================================================
 Claude Code Manager — PySide6 Edition
 Управление Omniroute и Claude Code
-----------------------------------------------------
 Автор / Author: on1felix
   Discord:  on1felix
   GitHub:   https://github.com/on1felix/claude_code_manager
 © 2026 on1felix. Приватная утилита, без публичной лицензии.
=====================================================
"""

# Контакты автора (используются в логах при старте и в футере)
AUTHOR_NAME = "on1felix"
AUTHOR_DISCORD = "on1felix"
AUTHOR_GITHUB = "https://github.com/on1felix/claude_code_manager"
import sys, subprocess, os, threading, time, json, socket, math, ssl, random
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QFrame,
                               QComboBox, QLineEdit, QDialog, QScrollArea, QTextEdit, QFileDialog, QStyledItemDelegate, QMessageBox, QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QProgressBar, QCheckBox, QSizePolicy)
from PySide6.QtCore import Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, QAbstractListModel, QModelIndex, Property, QObject, QThread, QSize
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QBrush, QTextCursor, QIcon, QPixmap, QLinearGradient, QRadialGradient, QPainterPath, QFontMetrics
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtSvg import QSvgRenderer

APP_VERSION = "5.6"  # Для обновлений
REQUIRED_CLAUDE_VERSION = "2.1.173"  # Последняя стабильная версия Claude Code: новее может работать нестабильно или не работать, а с 2.1.181 Anthropic блокирует сторонние Base URL и API ключи.
OMNIROUTE_PORT = 20128
SETTINGS_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "ClaudeManager")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
GITHUB_API_URL = "https://api.github.com/repos/on1felix/claude_code_manager/releases/latest"

# ВСТРОЕННЫЙ status line. Раньше лежал в C:\cc\statusline-command.sh — теперь
# вшит в .exe, чтобы дистрибутив был самодостаточным. При установке записывается
# в ~/.claude/statusline-command.sh БИНАРНО (LF, без CR), иначе bash в Git-Bash
# на Windows падает на шебанге.
STATUSLINE_SCRIPT = r"""#!/bin/bash

# Читаем JSON из stdin
input=$(cat)

# Для отладки - сохраняем входные данные
echo "$input" > /tmp/statusline-debug.json 2>/dev/null || true

# Парсим JSON с помощью grep и sed (без jq)
model=$(echo "$input" | grep -o '"display_name":"[^"]*"' | head -1 | sed 's/"display_name":"\([^"]*\)"/\1/')
used_pct=$(echo "$input" | grep -o '"used_percentage":[0-9.]*' | sed 's/"used_percentage"://')
cwd=$(echo "$input" | grep -o '"current_dir":"[^"]*"' | sed 's/"current_dir":"\([^"]*\)"/\1/' | sed 's/\\\\/\//g')
session_id=$(echo "$input" | grep -o '"session_id":"[^"]*"' | sed 's/"session_id":"\([^"]*\)"/\1/')
total_cost=$(echo "$input" | grep -o '"total_cost_usd":[0-9.]*' | sed 's/"total_cost_usd"://')
transcript_path=$(echo "$input" | grep -o '"transcript_path":"[^"]*"' | sed 's/"transcript_path":"\([^"]*\)"/\1/' | sed 's/\\\\/\//g')

# Получаем только output токены последнего ответа из transcript
output_tokens=""
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
    last_assistant=$(grep '"type":"assistant"' "$transcript_path" | tail -1)
    if [ -n "$last_assistant" ]; then
        output_tokens=$(echo "$last_assistant" | grep -o '"output_tokens":[0-9]*' | head -1 | sed 's/"output_tokens"://')
    fi
fi


# Значения по умолчанию
if [ -z "$model" ]; then
    model="Claude"
fi

# Получаем git репозиторий
git_repo=""
if [ -n "$cwd" ] && [ -d "$cwd/.git" ]; then
    git_repo=$(cd "$cwd" && git config --get remote.origin.url 2>/dev/null | sed 's/.*github\.com[:/]\(.*\)\.git/\1/' | sed 's/.*github\.com[:/]\(.*\)/\1/')
fi

# Функция для получения цвета на основе процента (плавный градиент)
get_color() {
    local pct=$1
    local used_int=$(printf "%.0f" "$pct")

    if [ "$used_int" -lt 10 ]; then
        # 0-9%: ярко-зелёный
        echo "\033[38;2;0;255;0m"
    elif [ "$used_int" -lt 20 ]; then
        # 10-19%: зелёный
        echo "\033[38;2;50;255;0m"
    elif [ "$used_int" -lt 30 ]; then
        # 20-29%: жёлто-зелёный
        echo "\033[38;2;150;255;0m"
    elif [ "$used_int" -lt 40 ]; then
        # 30-39%: лимонный
        echo "\033[38;2;200;255;0m"
    elif [ "$used_int" -lt 50 ]; then
        # 40-49%: жёлто-зелёный
        echo "\033[38;2;255;255;0m"
    elif [ "$used_int" -lt 60 ]; then
        # 50-59%: жёлтый
        echo "\033[38;2;255;200;0m"
    elif [ "$used_int" -lt 70 ]; then
        # 60-69%: оранжевый
        echo "\033[38;2;255;150;0m"
    elif [ "$used_int" -lt 80 ]; then
        # 70-79%: тёмно-оранжевый
        echo "\033[38;2;255;100;0m"
    elif [ "$used_int" -lt 90 ]; then
        # 80-89%: красно-оранжевый
        echo "\033[38;2;255;50;0m"
    else
        # 90-100%: красный
        echo "\033[38;2;255;0;0m"
    fi
}

# Создаем полоску контекста
context_bar=""
if [ -n "$used_pct" ]; then
    # Округляем процент
    used_int=$(printf "%.0f" "$used_pct")

    # Создаем полоску из 20 сегментов
    filled=$((used_int / 5))
    empty=$((20 - filled))

    context_bar="["
    for ((i=0; i<filled; i++)); do
        context_bar="${context_bar}="
    done
    for ((i=0; i<empty; i++)); do
        context_bar="${context_bar}-"
    done
    context_bar="${context_bar}]"
fi

# Формируем вывод
output=""

# Модель (зелёный цвет)
if [ -n "$model" ]; then
    output="\033[32m$model\033[0m"
fi

# Контекст (процент и полоска с цветом в зависимости от процента)
if [ -n "$used_pct" ]; then
    used_display=$(printf "%.1f" "$used_pct")
    color=$(get_color "$used_pct")

    if [ -n "$output" ]; then
        output="$output | ${color}${used_display}% ${context_bar}\033[0m"
    else
        output="${color}${used_display}% ${context_bar}\033[0m"
    fi
fi

# Session ID (синий цвет, как у модели)
if [ -n "$session_id" ]; then
    short_id=$(echo "$session_id" | cut -c1-8)
    if [ -n "$output" ]; then
        output="$output | \033[36m($short_id)\033[0m"
    else
        output="\033[36m($short_id)\033[0m"
    fi
fi

# Git репозиторий (фиолетовый цвет)
if [ -n "$git_repo" ]; then
    if [ -n "$output" ]; then
        output="$output | \033[35m$git_repo\033[0m"
    else
        output="\033[35m$git_repo\033[0m"
    fi
fi

echo -e "$output"
"""

try:
    _ssl_context = ssl.create_default_context()
    _ssl_context.check_hostname = False
    _ssl_context.verify_mode = ssl.CERT_NONE
except:
    _ssl_context = ssl._create_unverified_context()

def ensure_settings_dir():
    if not os.path.exists(SETTINGS_DIR):
        try:
            os.makedirs(SETTINGS_DIR)
        except:
            pass

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)

                # Дописываем недостающие поля для совместимости
                if "custom_base_urls" not in loaded or not loaded.get("custom_base_urls"):
                    loaded["custom_base_urls"] = ["https://cc.freemodel.dev"]
                else:
                    for u in ["https://cc.freemodel.dev"]:
                        if u not in loaded["custom_base_urls"]:
                            loaded["custom_base_urls"].insert(0, u)
                if not loaded.get("custom_base_url"):
                    loaded["custom_base_url"] = loaded["custom_base_urls"][0]
                # Язык интерфейса: по умолчанию ru, перезаписывается LangManager
                if "app_language" not in loaded:
                    loaded["app_language"] = "ru"
                return loaded
    except:
        pass
    return {
        "models": [
            "kr/claude-sonnet-4.5"
        ],
        "selected_model": "kr/claude-sonnet-4.5",
        "omniroute_path": "omniroute",
        "working_directory": "",
        "auth_token": "",
        "use_custom_token": False,
        "custom_api_key": "",
        "custom_base_url": "https://cc.freemodel.dev",
        "custom_base_urls": [
            "https://cc.freemodel.dev"
        ],
        "custom_model": "",
        "custom_endpoint": "",
        "app_language": "ru"
    }

DEFAULT_BASE_URLS = ["https://cc.freemodel.dev"]

def migrate_settings(settings):
    """Дописывает недостающие поля в старые настройки"""
    if "custom_base_urls" not in settings or not settings.get("custom_base_urls"):
        settings["custom_base_urls"] = list(DEFAULT_BASE_URLS)
    else:
        # Гарантируем что дефолтные URL всегда присутствуют
        for u in DEFAULT_BASE_URLS:
            if u not in settings["custom_base_urls"]:
                settings["custom_base_urls"].insert(0, u)
    if not settings.get("custom_base_url"):
        settings["custom_base_url"] = settings["custom_base_urls"][0]
    return settings

def save_settings(settings):
    ensure_settings_dir()
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except:
        pass


# ============================================================
# i18n — РУС/АНГ переводы
# ============================================================
# Принцип: tr("Русская строка") — если выбран EN, ищет в TRANSLATIONS и
# возвращает английский вариант; если язык RU или ключа нет — отдаёт исходник.
# Это позволяет постепенно покрывать строки переводами без рефакторинга всего
# кода.

TRANSLATIONS = {
    # ── главное окно: кнопки шапки
    "Установить Claude Code": "Install Claude Code",
    "Удалить Claude Code": "Uninstall Claude Code",
    "Status line": "Status line",
    "Fix Claude": "Fix Claude",
    "Запустить Omniroute": "Start Omniroute",
    "Остановить Omniroute": "Stop Omniroute",
    "Запустить Claude Code": "Start Claude Code",
    "Остановить Claude Code": "Stop Claude Code",
    "Добавить модель": "Add model",
    "Удалить модель": "Remove model",
    "Выбор модели Omniroute": "Select Omniroute model",
    "Выбор Base URL": "Select Base URL",
    "Выбор модели": "Select model",
    # ── главное окно: подписи статусов
    "Не запущен": "Not running",
    "Подключен": "Connected",
    "Не установлен": "Not installed",
    "Проверка версии…": "Checking version…",
    "Проверяю версию…": "Checking version…",
    "Установлен": "Installed",
    "нужна": "need",
    "запуск заблокирован": "launch blocked",
    # ── метки секций
    "Модель:": "Model:",
    "API ключ:": "API key:",
    "Директория:": "Directory:",
    "Не выбрана (будет запрошена)": "Not selected (will be prompted)",
    # ── общие кнопки
    "Добавить": "Add",
    "Отмена": "Cancel",
    "Сохранить": "Save",
    "Изменить": "Edit",
    "Удалить": "Delete",
    "Показать": "Show",
    "Скрыть": "Hide",
    "Обновить": "Update",
    "Открыть папку": "Open folder",
    "Управление": "Manage",
    "Настроить": "Configure",
    "Обзор": "Browse",
    "Очистить": "Clear",
    "Готово": "Done",
    "Понятно": "Got it",
    "Установить": "Install",
    "Переустановить": "Reinstall",
    "Исправить": "Fix",
    # ── диалоги: заголовки
    "Добавить модель": "Add model",
    "Введите название модели:": "Enter model name:",
    "Например: kr/claude-sonnet-4.5": "Example: kr/claude-sonnet-4.5",
    "Управление Base URL": "Manage Base URL",
    "Добавьте или удалите URL из списка": "Add or remove URL from the list",
    "Добавить новый URL:": "Add new URL:",
    "Базовый URL нельзя удалить": "Default URL can't be removed",
    "Удалить выбранный URL": "Remove selected URL",
    "Настройки кастомного токена": "Custom token settings",
    "Доступно обновление!": "Update available!",
    "Внимание": "Attention",
    "Установка status line": "Installing status line",
    "Подготовка…": "Preparing…",
    "Status line установлен ✓": "Status line installed ✓",
    "Не удалось установить": "Installation failed",
    "Скачивание обновления": "Downloading update",
    "Обновление скачано!": "Update downloaded!",
    "Завершаем обновление…": "Finalizing update…",
    "Ошибка скачивания": "Download error",
    "Удаление status line": "Removing status line",
    "Status line удалён ✓": "Status line removed ✓",
    "Claude исправлен ✓": "Claude fixed ✓",
    "Claude Code обновлён ✓": "Claude Code updated ✓",
    "Claude Code установлен ✓": "Claude Code installed ✓",
    # ── баннеры
    "Fable 5 временно недоступна": "Fable 5 temporarily unavailable",
    "Модель заблокирована\nправительством США": "Model blocked\nby the US government",
    "Источник: официальное заявление правительства США": "Source: official US government statement",
    "Запуск без прав администратора": "Running without administrator rights",
    "Рекомендуется запустить\nот имени администратора": "Recommended to run\nas administrator",
    # ── freemodel dialog
    "freemodel.dev — статус и латентность": "freemodel.dev — status & latency",
    "источник: freemodel-status-mirror-jzmw.vercel.app": "source: freemodel-status-mirror-jzmw.vercel.app",
    "Нет данных по этому endpoint.": "No data for this endpoint.",
    "Нет связи": "No connection",
    # ── разное
    "Пример отображения в Claude Code": "Preview in Claude Code",
    "модель  •  контекст  •  session ID  •  git-репозиторий":
        "model  •  context  •  session ID  •  git repo",
    # ── мульти-строчные тексты диалогов
    "Обновление завершено успешно.\n"
    "Перезапустите Claude Code для применения изменений.":
        "Update completed successfully.\n"
        "Restart Claude Code to apply the changes.",
    "Установка завершена успешно.\n"
    "Если команда claude не найдена — открой новое окно консоли\n"
    "(npm обычно сам прописывает её в PATH).":
        "Installation completed successfully.\n"
        "If the `claude` command is not found — open a new console window\n"
        "(npm usually adds it to PATH automatically).",
    "Обновление отменено": "Update cancelled",
    "Установка отменена": "Installation cancelled",
    "Окно PowerShell было закрыто до завершения.\n"
    "Можете попробовать снова в любой момент.":
        "PowerShell window was closed before completion.\n"
        "You can try again any time.",
    "Обновление не завершено": "Update not completed",
    "Установка не завершена": "Installation not completed",
    "Окно PowerShell было закрыто до завершения операции.\n"
    "Попробуйте ещё раз.":
        "PowerShell window was closed before the operation completed.\n"
        "Please try again.",
    "Неизвестная ошибка": "Unknown error",
    "Версия": "Version",
    "Установить v": "Install v",
    "клик": "click",
    # ── console banner
    "Приложение запущено": "Application started",
    "Порт Omniroute:": "Omniroute port:",
    "Автор:": "Author:",
    "Для работы с Base URL (freemodel и др.):": "To work with Base URL (freemodel etc.):",
    "Если впервые — запустите Claude Code и введите /logout.":
        "On first run — launch Claude Code and type /logout.",
    "Это нужно сделать только один раз. Даже если вы":
        "You only need to do this once. Even if you",
    "поменяете API ключ — повторно вводить /logout не нужно.":
        "change the API key — no need to type /logout again.",
    "Приложение автоматически подставит ключ и Base URL.":
        "The app will automatically inject the key and Base URL.",
    # ── console log messages
    "Omniroute подключен": "Omniroute connected",
    "Omniroute не запущен": "Omniroute is not running",
    "Omniroute успешно подключен": "Omniroute connected successfully",
    "Omniroute остановлен": "Omniroute stopped",
    "Запуск Omniroute...": "Starting Omniroute...",
    "Остановка Omniroute...": "Stopping Omniroute...",
    "Ожидание подключения...": "Waiting for connection...",
    "Таймаут ожидания подключения. Проверьте, что Omniroute установлен и путь к нему правильный.":
        "Connection timeout. Make sure Omniroute is installed and the path is correct.",
    "Директория очищена": "Directory cleared",
    "API ключ не может быть пустым": "API key cannot be empty",
    "API ключ сохранен": "API key saved",
    "API ключ обновлён": "API key updated",
    "Режим редактирования API ключа": "API key edit mode",
    "Кастомные настройки сохранены": "Custom settings saved",
    "Запуск отменен - директория не выбрана": "Launch cancelled — no directory selected",
    "Кастомный API ключ не установлен": "Custom API key is not set",
    "installMethod в ~/.claude.json: native → global":
        "installMethod in ~/.claude.json: native → global",
    "Status line установлен в ~/.claude/settings.json":
        "Status line installed in ~/.claude/settings.json",
    "Status line удалён из ~/.claude/settings.json":
        "Status line removed from ~/.claude/settings.json",
    "Переустановка status line отменена": "Status line reinstall cancelled",
    "Удаление status line отменено": "Status line removal cancelled",
    "Действие со status line отменено": "Status line action cancelled",
    "Fix Claude отменён": "Fix Claude cancelled",
    "Fix Claude: файл ~/.claude.json не найден — ничего не делаем":
        "Fix Claude: ~/.claude.json not found — nothing to do",
    "Операция отменена": "Operation cancelled",
    "Удаление отменено": "Removal cancelled",
    "Claude Code не установлен": "Claude Code is not installed",
    "Запускаю удаление Claude Code через npm...":
        "Starting Claude Code removal via npm...",
    "Запускаю установку Node.js LTS через winget...":
        "Starting Node.js LTS installation via winget...",
    "Node.js (npm) не найден — открываю окно с инструкцией":
        "Node.js (npm) not found — opening the instruction dialog",
    "Текущая команда:": "Current command:",
    "Скрипт скопирован в ~/.claude/statusline-command.sh,\n"
    "блок statusLine прописан в ~/.claude/settings.json.\n"
    "Запусти Claude Code — строка появится внизу окна.":
        "The script was copied to ~/.claude/statusline-command.sh,\n"
        "the statusLine block was added to ~/.claude/settings.json.\n"
        "Launch Claude Code — the line will appear at the bottom of the window.",
    "Блок statusLine удалён из ~/.claude/settings.json,\n"
    "файл ~/.claude/statusline-command.sh стёрт.":
        "The statusLine block has been removed from ~/.claude/settings.json,\n"
        "the file ~/.claude/statusline-command.sh has been erased.",
    "Не удалось получить /api/status. Повторим через несколько секунд.":
        "Failed to fetch /api/status. We'll retry in a few seconds.",
    # ── Fable 5
    "По официальному заявлению правительства США, доступ\n"
    "к модели Fable 5 временно приостановлен на территории\n"
    "всех юрисдикций.\n\n"
    "Согласно решению, Fable 5 признана настолько мощной,\n"
    "что — по словам представителей правительства — способна\n"
    "взломать защищённые системы Пентагона. На этом основании\n"
    "модель отнесена к технологиям двойного назначения\n"
    "и временно изъята из публичного оборота.\n\n"
    "Доступ будет восстановлен после завершения проверки\n"
    "и установки регулирующих ограничений Anthropic.":
        "By official statement of the US government, access to\n"
        "the Fable 5 model is temporarily suspended in every\n"
        "jurisdiction.\n\n"
        "According to the ruling, Fable 5 is considered so powerful\n"
        "that — in the words of government officials — it is capable\n"
        "of breaking into the Pentagon's secured systems. On that\n"
        "basis the model is classified as a dual-use technology and\n"
        "withdrawn from public circulation.\n\n"
        "Access will be restored once Anthropic completes the review\n"
        "and installs the regulating restrictions.",
    # ── Admin warning
    "Сейчас приложение работает в обычном режиме и часть\n"
    "операций может завершаться ошибкой PermissionDenied.\n\n"
    "Без   дмин-прав могут не сработать:\n"
    "  •  установка Node.js (инсталлятор пишет в %ProgramFiles%)\n"
    "  •  установка Claude Code (npm i -g в системные папки)\n"
    "  •  полное удаление Claude Code и чистка залоченных файлов\n"
    "  •  запись в системные папки (%ProgramFiles%, %ProgramData%)\n"
    "  •  правки в чужих профилях и общих директориях\n\n"
    "Базовые сценарии — Fix Claude, смена модели и API-ключа —\n"
    "работают и без админа.":
        "The application is currently running in standard user mode,\n"
        "so some operations may fail with PermissionDenied.\n\n"
        "Without administrator rights these may not work:\n"
        "  •  installing Node.js (the installer writes to %ProgramFiles%)\n"
        "  •  installing Claude Code (npm i -g into system folders)\n"
        "  •  fully uninstalling Claude Code and cleaning locked files\n"
        "  •  writing into system folders (%ProgramFiles%, %ProgramData%)\n"
        "  •  editing other users' profiles and shared directories\n\n"
        "Basic scenarios — Fix Claude, model switching, and changing\n"
        "the API key — work without administrator rights too.",
    "Совет:  закройте приложение и запустите от имени администратора":
        "Tip: close the app and run it as administrator",
    # ── Status line install dialog
    '<span style="color:#F5C850;"><b>● Сейчас status line установлен.</b></span><br>'
    "Можно <b>переустановить</b> его (наш скрипт перезапишет твой) "
    "или <b>удалить</b> — тогда блок <code>statusLine</code> уйдёт "
    "из <code>~/.claude/settings.json</code>, а файл "
    "<code>~/.claude/statusline-command.sh</code> будет стёрт.<br><br>":
        '<span style="color:#F5C850;"><b>● A status line is currently installed.</b></span><br>'
        "You can <b>reinstall</b> it (our script will overwrite yours) "
        "or <b>remove</b> it — the <code>statusLine</code> block will then be "
        "removed from <code>~/.claude/settings.json</code> and the file "
        "<code>~/.claude/statusline-command.sh</code> will be erased.<br><br>",
    '<span style="color:rgba(200,200,205,0.7);">● Сейчас status line не настроен.</span><br>'
    "Менеджер скопирует <code>statusline-command.sh</code> в "
    "<code>~/.claude/</code> и пропишет блок <code>statusLine</code> "
    "в <code>~/.claude/settings.json</code>.<br>"
    "Кнопка <b>«Удалить»</b> сейчас неактивна — удалять пока нечего.<br><br>":
        '<span style="color:rgba(200,200,205,0.7);">● No status line is currently set up.</span><br>'
        "The manager will copy <code>statusline-command.sh</code> to "
        "<code>~/.claude/</code> and add the <code>statusLine</code> block "
        "to <code>~/.claude/settings.json</code>.<br>"
        "The <b>«Remove»</b> button is currently disabled — there is nothing to remove yet.<br><br>",
    "Status line — это строка внизу окна Claude Code, в которой видно "
    "текущую модель, заполненность контекста, ID сессии и git-репозиторий "
    "рабочей папки. Ниже — как именно он будет выглядеть.":
        "The status line is a single line at the bottom of the Claude Code window "
        "that shows the current model, context usage, session ID and git repository "
        "of the working folder. Below is exactly how it will look.",
    # ── Fix Claude dialog
    '<span style="color:#EB5A5A;"><b>● Найден файл ~/.claude.json.</b></span><br>'
    "У многих пользователей старые/несовместимые настройки из этого файла "
    "ломают первый запуск Claude Code: <b>ошибки API</b>, "
    "<b>Claude вообще не отвечает</b>, странные сбои авторизации. "
    "Особенно если ты раньше пользовался Claude Code через другие способы.<br><br>":
        '<span style="color:#EB5A5A;"><b>● ~/.claude.json file found.</b></span><br>'
        "For many users old/incompatible settings in this file break "
        "the first launch of Claude Code: <b>API errors</b>, "
        "<b>Claude not responding at all</b>, strange authentication failures. "
        "Especially if you previously used Claude Code through other methods.<br><br>",
    '<span style="color:rgba(200,200,205,0.7);">● Файл ~/.claude.json не найден.</span><br>'
    "Исправлять нечего — этот фикс нужен только когда Claude Code "
    "не отвечает или возвращает ошибки API при первом запуске "
    "именно из-за старого <code>~/.claude.json</code>.<br><br>":
        '<span style="color:rgba(200,200,205,0.7);">● ~/.claude.json file not found.</span><br>'
        "Nothing to fix — this fix is only needed when Claude Code "
        "is not responding or returns API errors on first launch "
        "because of an old <code>~/.claude.json</code>.<br><br>",
    "<b>Что сделает кнопка «Исправить»:</b><br>":
        "<b>What the «Fix» button does:</b><br>",
    "переименует": "renames",
    "• оригинал <code>~/.claude.json</code> <b>не удаляется</b> — "
    "остаётся как <code>.bak</code>, можно вернуть.<br>"
    "• создаст свежий <code>~/.claude.json</code> с "
    "<code>installMethod=global</code> и <code>autoUpdates=false</code>.<br>"
    "• <b>пересоздаст</b> <code>~/.claude/settings.json</code> с нуля, "
    "оставив только <code>env.DISABLE_UPDATES=1</code>. "
    "Это убирает «зависшие» ключи вроде <code>apiKeyHelper</code>, "
    "которые ломают авторизацию (Claude ругается «auth may not work» "
    "и виснет на Retrying). Модель, эффорт и токен приложение "
    "пропишет туда обратно само — настройки лежат в нём отдельно "
    "и не теряются.<br>"
    "• <code>DISABLE_UPDATES=1</code> — официальный способ выключить "
    "автообновление Claude Code; без него CLI рано или поздно "
    "обновится с зафиксированной v":
        "• the original <code>~/.claude.json</code> is <b>not deleted</b> — "
        "it stays as <code>.bak</code> and can be restored.<br>"
        "• a fresh <code>~/.claude.json</code> will be created with "
        "<code>installMethod=global</code> and <code>autoUpdates=false</code>.<br>"
        "• <b>recreates</b> <code>~/.claude/settings.json</code> from scratch, "
        "leaving only <code>env.DISABLE_UPDATES=1</code>. "
        "This removes «stuck» keys like <code>apiKeyHelper</code> "
        "that break authentication (Claude complains «auth may not work» "
        "and hangs at Retrying). Model, effort and token are written back "
        "by the app itself — those settings live separately and are not lost.<br>"
        "• <code>DISABLE_UPDATES=1</code> is the official way to disable "
        "automatic updates of Claude Code; without it the CLI will "
        "sooner or later update from the pinned v",
    " до более новой версии, где FreeModel / Omniroute / прокси "
    "уже не работают.":
        " to a newer version where FreeModel / Omniroute / proxy no longer work.",
    "Нажимай, только если у тебя реально проблемы: "
    "Claude Code не отвечает, выдаёт ошибки API, или ведёт себя странно "
    "после смены способа авторизации.":
        "Press this only if you really have problems: "
        "Claude Code is not responding, gives API errors, or behaves strangely "
        "after switching authorization method.",
    # ── Install dialog texts
    "Откат Claude Code до": "Rollback Claude Code to",
    "Установка Claude Code": "Install Claude Code",
    "У тебя установлена": "You currently have installed",
    "последняя стабильная версия, "
    "на которой приложение проверено целиком. Более новые версии могут работать "
    "нестабильно или вовсе не запускаться, а начиная с v2.1.181 Anthropic "
    "заблокировала сторонние Base URL и API ключи — все запросы уходят тол  ко "
    "в официальный сервис Anthropic, и FreeModel / Omniroute / прокси не работают.\n\n"
    "npm переустановит пакет на нужную версию. Настройки в %USERPROFILE%\\.claude "
    "не пострадают.":
        "the last stable version on which the app was fully tested. "
        "Newer versions may work unstably or not start at all, and starting from v2.1.181 "
        "Anthropic blocked third-party Base URLs and API keys — all requests now go only "
        "to the official Anthropic service, and FreeModel / Omniroute / proxy don't work.\n\n"
        "npm will reinstall the package to the required version. Settings in %USERPROFILE%\\.claude "
        "will not be affected.",
    "Будет установлена фиксированная": "A pinned version will be installed",
    "последняя стабильная версия, с которой это приложение работает гарантированно. "
    "Более новые версии могут работать нестабильно или совсем не запускаться.":
        "the last stable version with which this app is guaranteed to work. "
        "Newer versions may work unstably or not start at all.",
    "Будет установлена фиксированная версия": "A pinned version will be installed",
    "через npm — "
    "последняя стабильная, на которой проверено это приложение. "
    "Более новые версии могут работать нестабильно или вовсе не запускаться, "
    "а версии с 2.1.181 Anthropic блокирует сторонние Base URL и API ключи.\n\n"
    "Откроется окно PowerShell, где пойдёт установка.":
        "via npm — "
        "the last stable version this app was tested on. "
        "Newer versions may work unstably or not start at all, "
        "and versions starting from 2.1.181 Anthropic blocks third-party Base URLs and API keys.\n\n"
        "A PowerShell window will open where the installation will happen.",
    "Откатить": "Rollback",
    "Продолжить": "Continue",
    "Откатить до": "Rollback to",
    "установлен": "installed",
    "Обновить до": "Update to",
    "Устаревшая версия Claude Code": "Outdated Claude Code version",
    "У тебя установлена Claude Code": "You have Claude Code installed",
    "это устаревшая версия.": "this is an outdated version.",
    "Проверенная и стабильная версия, на которой это приложение работает гарантированно, — ":
        "The tested and stable version that this app is guaranteed to work with is ",
    "На более старых версиях возможны "
    "несовместимости (изменения в формате settings.json, путях, флагах CLI), "
    "из-за которых запуск через Omniroute / FreeModel может вести себя нестабильно.\n\n":
        "Older versions may have incompatibilities "
        "(changes in the settings.json format, paths, CLI flags) "
        "that can make startup via Omniroute / FreeModel behave unreliably.\n\n",
    "Рекомендуем обновить до": "We recommend updating to",
    "npm переустановит пакет, "
    "настройки в %USERPROFILE%\\.claude не пострадают.":
        "npm will reinstall the package, "
        "settings in %USERPROFILE%\\.claude will not be affected.",
    # ── version block dialog
    "Запуск заблокирован": "Launch blocked",
    "а приложение работает только с": "but the app only works with",
    "Нажми «Откатить» — npm переустановит CLI на":
        "Press «Rollback» — npm will reinstall the CLI to",
    "и запуск снова заработает.": "and launch will work again.",
    # ── npm dialog
    "В системе не найден npm — он входит в состав Node.js. "
    "Без npm Claude Code установить нельзя.\n\n"
    "Нажми «Установить Node.js» — откроется окно PowerShell, "
    "в котором winget автоматически скачает и поставит Node.js LTS "
    "с официального источника (OpenJS.NodeJS.LTS).\n\n"
    "После окончания установки закрой и заново открой это приложение, "
    "чтобы оно увидело npm в обновлённом PATH.":
        "npm was not found on the system — it ships with Node.js. "
        "Without npm Claude Code cannot be installed.\n\n"
        "Press «Install Node.js» — a PowerShell window will open "
        "in which winget will automatically download and install Node.js LTS "
        "from the official source (OpenJS.NodeJS.LTS).\n\n"
        "After installation completes, close and reopen this app "
        "so it picks up npm in the updated PATH.",
    "В системе не найден npm — он входит в состав Node.js. "
    "Без npm Claude Code установить нельзя.\n\n"
    "На твоей системе нет winget, поэтому установить автоматически не получится. "
    "Нажми «Скачать Node.js» — откроется официальная страница "
    "nodejs.org/en/download. Скачай Windows Installer (.msi) LTS, "
    "поставь его и перезапусти это приложение.":
        "npm was not found on the system — it ships with Node.js. "
        "Without npm Claude Code cannot be installed.\n\n"
        "Your system has no winget, so automatic install is not possible. "
        "Press «Download Node.js» — the official "
        "nodejs.org/en/download page will open. Download the Windows Installer (.msi) LTS, "
        "install it, and restart this app.",
    "Установить Node.js": "Install Node.js",
    "Скачать Node.js": "Download Node.js",
    "Нужен Node.js (npm)": "Node.js required (npm)",
    # ── status line confirmations
    "Переустановить status line?": "Reinstall status line?",
    "Удалить status line?": "Remove status line?",
    "Вы действительно хотите переустановить status line? "
    "Ваш текущий блок statusLine в ~/.claude/settings.json "
    "и файл ~/.claude/statusline-command.sh будут полностью "
    "перезаписаны нашей версией. Откатить это нельзя.":
        "Are you sure you want to reinstall the status line? "
        "Your current statusLine block in ~/.claude/settings.json "
        "and the file ~/.claude/statusline-command.sh will be fully "
        "overwritten with our version. This cannot be undone.",
    "Вы действительно хотите удалить status line? "
    "Блок statusLine уйдёт из ~/.claude/settings.json, "
    "а файл ~/.claude/statusline-command.sh — будет стёрт. "
    "Остальные настройки Claude Code останутся как есть.":
        "Are you sure you want to remove the status line? "
        "The statusLine block will be removed from ~/.claude/settings.json, "
        "and the file ~/.claude/statusline-command.sh will be erased. "
        "Other Claude Code settings will remain untouched.",
    "Да, переустановить": "Yes, reinstall",
    "Да, удалить": "Yes, remove",
    # ── uninstall claude
    "Будет удалён глобальный npm-пакет Claude Code": "The global npm package Claude Code will be removed",
    "Настройки в %USERPROFILE%\\.claude не пострадают — удалится только бинарь.":
        "Settings in %USERPROFILE%\\.claude won't be affected — only the binary is removed.",
}


def _load_lang_setting():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
                lang = d.get("app_language", "ru")
                if lang in ("ru", "en"):
                    return lang
    except:
        pass
    return "ru"


class LanguageManager(QObject):
    """Глобальный singleton для текущего языка интерфейса.
    Сигнал language_changed эмитится при смене языка — виджеты подписываются
    и пересоздают свои тексты через retranslate_ui()."""
    language_changed = Signal(str)  # 'ru' или 'en'

    def __init__(self):
        super().__init__()
        self._lang = _load_lang_setting()

    @property
    def lang(self):
        return self._lang

    def set_lang(self, code):
        if code not in ("ru", "en"):
            return
        if code == self._lang:
            return
        self._lang = code
        try:
            s = load_settings()
            s["app_language"] = code
            save_settings(s)
        except:
            pass
        self.language_changed.emit(code)


# Создаётся после QApplication в main()
LANG = None


def tr(ru_text):
    """Возвращает английский перевод, если выбран EN и перевод существует;
    иначе — исходную русскую строку."""
    if LANG is None or LANG.lang == "ru":
        return ru_text
    return TRANSLATIONS.get(ru_text, ru_text)


def check_omniroute_status():
    """Проверяет, запущен ли Omniroute"""
    try:
        # Проверка через socket - самый надежный способ
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex(('127.0.0.1', OMNIROUTE_PORT))
        sock.close()
        return result == 0
    except Exception as e:
        return False

def check_app_update():
    """Проверяет наличие обновлений приложения через GitHub API"""
    try:
        req = Request(GITHUB_API_URL, headers={'User-Agent': 'ClaudeManager-Updater'})
        with urlopen(req, timeout=10, context=_ssl_context) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        # Очищаем версию от префиксов (v, claude_code_manager_, и т.д.)
        latest_version = data.get('tag_name', '')
        latest_version = latest_version.replace('v', '').replace('claude_code_manager_', '').replace('claude_manager_', '').replace('ClaudeManager_', '').replace('ClaudeCodeManager_', '')

        download_url = None
        for asset in data.get('assets', []):
            if asset['name'].endswith('.exe'):
                download_url = asset['browser_download_url']
                break

        is_update = latest_version and latest_version != APP_VERSION and compare_versions(latest_version, APP_VERSION) > 0
        return {
            'current': APP_VERSION,
            'latest': latest_version,
            'update_available': is_update,
            'download_url': download_url,
            'release_notes': data.get('body', ''),
            'release_name': data.get('name', '')
        }
    except:
        return None

def compare_versions(v1, v2):
    """Сравнивает две версии (возвращает 1 если v1 > v2, -1 если v1 < v2, 0 если равны)"""
    try:
        parts1 = [int(x) for x in v1.split('.')]
        parts2 = [int(x) for x in v2.split('.')]
        while len(parts1) < len(parts2):
            parts1.append(0)
        while len(parts2) < len(parts1):
            parts2.append(0)
        for p1, p2 in zip(parts1, parts2):
            if p1 > p2:
                return 1
            elif p1 < p2:
                return -1
        return 0
    except:
        return 0

# ============================================================
# ИНДИКАТОР СТАТУСА (ТОЧКА)
# ============================================================

class StatusIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self._is_active = False
        self._state = "off"  # "off" (red), "on" (green), "warn" (yellow), "neutral" (grey)
        self._pulse_time = 0.0
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._animate_pulse)
        self._pulse_timer.start(16)  # ~60 FPS
        self.setMouseTracking(True)

    def set_active(self, active):
        self._is_active = active
        self._state = "on" if active else "off"
        self.update()

    def set_state(self, state):
        """state: 'on' (зелёный), 'off' (крас      ы  ), 'warn' (жёлтый), 'neutral' (серый)"""
        self._state = state
        self._is_active = (state == "on")
        self.update()

    def _animate_pulse(self):
        self._pulse_time += 0.05
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        center = QPointF(w / 2, h / 2)
        pulse = 0.75 + 0.25 * math.sin(self._pulse_time)
        scale = min(w, h) / 20.0  # базовый размер — 20×20

        # Цвет точки и свечения по состоянию
        if self._state == "on":
            glow = (0, 255, 100, int(60 * pulse))
            brightness = int(180 + 75 * pulse)
            core = (0, brightness, int(brightness * 0.4))
        elif self._state == "fm_ok":
            # Зелёный точно как текст «freemodel» (#34d399) — для бейджа freemodel.dev
            glow = (52, 211, 153, int(70 * pulse))
            t = 0.85 + 0.15 * pulse
            core = (int(52 * t), int(211 * t), int(153 * t))
        elif self._state == "warn":
            # жёлто-оранжевый
            glow = (255, 170, 30, int(70 * pulse))
            brightness = int(180 + 75 * pulse)
            core = (brightness, int(brightness * 0.62), int(brightness * 0.10))
        elif self._state == "neutral":
            # серый, мягкая пульсация
            glow = (156, 163, 175, int(28 * pulse))
            brightness = int(140 + 25 * pulse)
            core = (int(brightness * 0.72), int(brightness * 0.76), int(brightness * 0.85))
        else:
            glow = (255, 50, 50, int(50 * pulse))
            brightness = int(180 + 75 * pulse)
            core = (brightness, 50, 50)

        glow_radius = (5.0 + 2.5 * pulse) * scale
        painter.setBrush(QColor(*glow))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, glow_radius, glow_radius)

        painter.setBrush(QColor(*core))
        painter.drawEllipse(center, 4.5 * scale, 4.5 * scale)

# ============================================================
# БЕЙДЖ freemodel.dev (логотип + индикатор статуса сервиса)
# ============================================================

class FreemodelBrand(QWidget):
    """Логотип «freemodel.dev» + индикатор-точка справа.
    «freemodel» — зелёный (#34d399, как на сайте fm.bluealitas.com),
    «.dev» — мягкий белый (#d1d5db). Цвет точки управляется через
    set_status(overall) по значениям API /api/status.
    Клик по бейджу эмитит сигнал `clicked` — главное окно открывает
    модальный диалог со статистикой freemodel.dev в реальном времени."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.dot = StatusIndicator()
        self.dot.setFixedSize(19, 19)
        self.dot.set_state("neutral")
        # Прижимаем к нижней кромке, чтобы точка вставала по базовой линии текста,
        # а не «висела» выше — иначе индикатор выглядит выше глифов.
        layout.addWidget(self.dot, 0, Qt.AlignBottom)

        self.label = QLabel()
        self.label.setFont(QFont("Segoe UI", 12, QFont.DemiBold))
        self.label.setTextFormat(Qt.RichText)
        self.label.setText(
            '<span style="color:#34d399; font-weight:700;">freemodel</span>'
            '<span style="color:#d1d5db; font-weight:500;">.dev</span>'
        )
        self.label.setStyleSheet("background: transparent;")
        layout.addWidget(self.label, 0, Qt.AlignBottom)

        self.adjustSize()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_status(self, overall):
        """overall: 'ok' | 'warn' | 'confirming' | 'bad' | 'down' | 'unknown' | None
        'confirming' трактуем как warn — сайт делает то же самое."""
        if overall == "ok":
            # «ok» — в цвет текста freemodel (#34d399)
            self.dot.set_state("fm_ok")
        elif overall in ("warn", "confirming"):
            self.dot.set_state("warn")
        elif overall in ("bad", "down"):
            self.dot.set_state("off")
        else:
            self.dot.set_state("neutral")

# ============================================================
# ПОДСКАЗКА «клик» с изогнутой стрелкой, указывает на бейдж freemodel.dev
# ============================================================

class _FmClickHint(QWidget):
    """Короткая изогнутая серая стрелка с подписью «клик», указывает на
    бейдж freemodel.dev. Виджет прозрачен для мыши, поэтому не перехватывает
    клики по самому бейджу. Изгиб уходит снизу-влево и возвращается к тексту,
    наконечник упирается под низ текста freemodel.dev."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(150, 70)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        line_color = QColor("#6a6a72")
        text_color = QColor("#7d7d85")

        # Подпись «клик» — справа-снизу, рядом с хвостом стрелки
        font = QFont("Segoe UI", 9)
        font.setItalic(True)
        p.setFont(font)
        p.setPen(text_color)
        p.drawText(QRectF(96, 38, 60, 22), Qt.AlignLeft | Qt.AlignVCenter, tr("клик"))

        # Изогнутая стрелка: начинается слева от слова «клик», уходит вниз-влево,
        # выгибается через левую сторону и упирается наконечником вверх в бейдж.
        pen = QPen(line_color, 1.4)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        start = QPointF(92, 47)
        c1 = QPointF(55, 62)
        c2 = QPointF(8, 38)
        end = QPointF(45, 8)

        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(c1, c2, end)
        p.drawPath(path)

        # Наконечник стрелки. Касательная в конце пути ≈ направление (c2 → end).
        dx = end.x() - c2.x()
        dy = end.y() - c2.y()
        angle = math.atan2(dy, dx)
        head = 7.5
        spread = math.pi / 7
        a1 = QPointF(
            end.x() - head * math.cos(angle - spread),
            end.y() - head * math.sin(angle - spread),
        )
        a2 = QPointF(
            end.x() - head * math.cos(angle + spread),
            end.y() - head * math.sin(angle + spread),
        )
        p.drawLine(end, a1)
        p.drawLine(end, a2)

# ============================================================
# ДИАЛОГ СТАТИСТИКИ freemodel.dev (открывается по клику на бейдж)
# ============================================================

# Цветовая палитра — взята 1:1 с CSS-переменных сайта fm.bluealitas.com.
_FM_COLORS = {
    "bg":         "#0d0d0d",
    "bg_warm":    "#161616",
    "bg_card":    "#1a1a1a",
    "ink":        "#f3f4f6",
    "ink_soft":   "#d1d5db",
    "ink_muted":  "#9ca3af",
    "line":       "#2a2a2a",
    "line_soft":  "#1f1f1f",
    "ok":         "#34d399",
    "warn":       "#fbbf24",
    "bad":        "#f87171",
    "down":       "#ef4444",
    "slow":       "#60a5fa",
    "very_slow":  "#fbbf24",
    # 'failed' пробы — красные. Ключа не было → бары падали в ink_muted (серый),
    # из-за чего пользователю казалось, что красных шкал нет.
    "failed":     "#f87171",
}

def _fm_classify_probe(probe):
    """Категория пробы: 'failed' | 'very_slow' | 'slow' | 'ok'.
    Пороги взяты 1:1 из JS сайта fm.bluealitas.com:
       latency > 4000  → very_slow (жёлтый)
       latency > 1500  → slow      (голубой)
       иначе           → ok        (зелёный)
       !ok             → failed    (красный)"""
    if not probe or not probe.get("ok", False):
        return "failed"
    lat = probe.get("latency") or 0
    if lat > 4000:
        return "very_slow"
    if lat > 1500:
        return "slow"
    return "ok"

def _fm_fmt_eta(ms_remaining):
    """5_271_000 ms → '1h 27m 51s' / '23m 11s' / '45s'."""
    if ms_remaining is None or ms_remaining < 0:
        ms_remaining = 0
    total_s = int(ms_remaining // 1000)
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"

def _fm_fmt_age(ms_age):
    """Сколько назад: '6m ago', '23s ago', '1h 12m ago'."""
    if ms_age is None or ms_age < 0:
        return "—"
    total_s = int(ms_age // 1000)
    if total_s < 60:
        return f"{total_s}s ago"
    h, rem = divmod(total_s, 3600)
    m, _ = divmod(rem, 60)
    if h:
        return f"{h}h {m}m ago"
    return f"{m}m ago"

def _fm_fmt_ms(value):
    """5276.123 → '5 276'. Тысячи разделены пробелом — как на сайте."""
    if value is None:
        return "—"
    try:
        return f"{int(round(float(value))):,}".replace(",", " ")
    except Exception:
        return "—"


def _fm_sanitize_error(text):
    """Иногда промежуточный прокси/шлюз отдаёт ошибки иероглифами (часто
    китайский — стандартные «упс» от китайских CDN/firewall'ов, например
    «此页面无法访问» и т.п.). В UI это просто шум — пользователь не прочитает.

    Логика: считаем долю CJK-символов среди значимых (не-whitespace).
    Если >25% — заменяем строку на короткое читаемое объяснение."""
    if not text:
        return ""
    s = str(text).strip()
    if not s:
        return ""
    cjk = 0
    counted = 0
    for ch in s:
        if ch.isspace():
            continue
        counted += 1
        c = ord(ch)
        if ((0x4E00 <= c <= 0x9FFF) or  # CJK Unified Ideographs
            (0x3400 <= c <= 0x4DBF) or  # CJK Ext A
            (0x3040 <= c <= 0x309F) or  # Hiragana
            (0x30A0 <= c <= 0x30FF) or  # Katakana
            (0xAC00 <= c <= 0xD7AF)):   # Hangul
            cjk += 1
    if counted and cjk / counted > 0.25:
        return ("upstream вернул нечитаемую ошибку "
                "(обычно ответ промежуточного прокси/шлюза)")
    # На всякий случай отрезаем длинные «портянки» от стектрейсов.
    return s[:160]


class LatencyHistogram(QWidget):
    """Гистограмма последних N проб freemodel.dev — бар на каждый probe.
    Цвет по категории. Бары рисуются с лёгким вертикальным градиентом сверху-вниз
    и тонкой базовой линией для визуального якоря."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Прозрачный фон, чтобы под виджетом просвечивала карточка-родитель —
        # иначе Windows зальёт виджет дефолтной серой подложкой.
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumHeight(118)
        self._samples = []

    def set_samples(self, samples):
        # Срез -96, как на сайте fm.bluealitas.com (renderProbeChart):
        #   const recent = points.slice(-96)
        # Раньше брали -110 — на Aggregate (там >96 проб) бары шли с лишним
        # запасом, и визуальное распределение не совпадало с сайтом.
        self._samples = samples[-96:]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()

        # Базовая линия — едва заметная горизонталь под барами
        baseline_y = h - 4
        p.setPen(QPen(QColor(_FM_COLORS["line_soft"]), 1))
        p.drawLine(0, int(baseline_y) + 1, w, int(baseline_y) + 1)

        if not self._samples:
            p.setPen(QColor(_FM_COLORS["ink_muted"]))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(self.rect(), Qt.AlignCenter, "нет данных")
            return

        max_lat = max((s[2] for s in self._samples if s[2]), default=1.0) or 1.0
        max_lat *= 1.05
        gap = 2.0
        n = len(self._samples)
        bar_w = max(1.5, (w - gap * (n - 1)) / n)

        for i, (ts, cat, lat) in enumerate(self._samples):
            base_color = QColor(_FM_COLORS.get(cat, _FM_COLORS["ink_muted"]))
            # Высота всех баров — пропорциональна latency, ровно как на сайте:
            #   h_ = max(5, round((lat / max) * 78))
            # У failed-проб latency тоже есть (время до отлупа), поэтому жёстко
            # обрезать их до 8px — неправильно: на сайте видны разные высоты.
            bar_h = max(3.0, (lat / max_lat) * (h - 10))
            x = i * (bar_w + gap)
            y = baseline_y - bar_h

            # Вертикальный градиент: вверху чуть ярче, внизу чуть глуше
            grad = QLinearGradient(0, y, 0, baseline_y)
            top = QColor(base_color)
            bot = QColor(base_color)
            bot.setAlphaF(0.78)
            grad.setColorAt(0, top)
            grad.setColorAt(1, bot)
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.4, 1.4)


# ─── Кастомное окно (только для FreemodelStatsDialog) ─────────────


class _FmBgGlow(QWidget):
    """Bottom glow layer - 2-layer crossfade, exactly like the website bgA/bgB."""

    _ACCENTS = {
        'ok':         (52, 211, 153, 0.04),
        'warn':       (251, 191, 36, 0.04),
        'confirming': (251, 191, 36, 0.04),
        'bad':        (239, 68, 68, 0.06),
        'down':       (239, 68, 68, 0.06),
        'unknown':    (156, 163, 175, 0.02),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._col_a = QColor(0, 0, 0, 0)
        self._col_b = QColor(0, 0, 0, 0)
        self._alpha_a = 0.0
        self._alpha_b = 0.0
        self._active = 'A'
        self._anim_a = None
        self._anim_b = None

    def set_status(self, effective):
        r, g, b, base_a = self._ACCENTS.get(effective, self._ACCENTS['unknown'])
        target = QColor(r, g, b)
        target.setAlphaF(base_a)
        if self._active == 'A':
            self._col_b = target
            self._anim_b = QPropertyAnimation(self, b'_alpha_b_prop', self)
            self._anim_b.setDuration(1500)
            self._anim_b.setStartValue(self._alpha_b)
            self._anim_b.setEndValue(1.0)
            self._anim_b.setEasingCurve(QEasingCurve.OutCubic)
            self._anim_a = QPropertyAnimation(self, b'_alpha_a_prop', self)
            self._anim_a.setDuration(1500)
            self._anim_a.setStartValue(self._alpha_a)
            self._anim_a.setEndValue(0.0)
            self._anim_a.setEasingCurve(QEasingCurve.OutCubic)
            self._anim_a.start()
            self._anim_b.start()
            self._active = 'B'
        else:
            self._col_a = target
            self._anim_a = QPropertyAnimation(self, b'_alpha_a_prop', self)
            self._anim_a.setDuration(1500)
            self._anim_a.setStartValue(self._alpha_a)
            self._anim_a.setEndValue(1.0)
            self._anim_a.setEasingCurve(QEasingCurve.OutCubic)
            self._anim_b = QPropertyAnimation(self, b'_alpha_b_prop', self)
            self._anim_b.setDuration(1500)
            self._anim_b.setStartValue(self._alpha_b)
            self._anim_b.setEndValue(0.0)
            self._anim_b.setEasingCurve(QEasingCurve.OutCubic)
            self._anim_a.start()
            self._anim_b.start()
            self._active = 'A'
        self.update()

    def _get_a(self): return self._alpha_a
    def _set_a(self, v): self._alpha_a = v; self.update()
    _alpha_a_prop = Property(float, _get_a, _set_a)

    def _get_b(self): return self._alpha_b
    def _set_b(self, v): self._alpha_b = v; self.update()
    _alpha_b_prop = Property(float, _get_b, _set_b)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        for col, alpha in ((self._col_a, self._alpha_a), (self._col_b, self._alpha_b)):
            if alpha <= 0.001:
                continue
            grad = QLinearGradient(0, h, 0, int(h * 0.35))
            c0 = QColor(col)
            c0.setAlphaF(col.alphaF() * alpha)
            c1 = QColor(col)
            c1.setAlphaF(0.0)
            grad.setColorAt(0, c0)
            grad.setColorAt(1, c1)
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(0, 0, w, h), 16, 16)


class _FmBgDots(QWidget):
    """Background dot pattern - 2-layer crossfade, exactly like the website."""

    _DOT_ALPHAS = {
        'ok': 0.025, 'warn': 0.025, 'confirming': 0.025,
        'bad': 0.03, 'down': 0.03, 'unknown': 0.015,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._col_a = QColor(255, 255, 255, 6)
        self._col_b = QColor(255, 255, 255, 6)
        self._alpha_a = 0.0
        self._alpha_b = 0.0
        self._active = None
        self._cur_key = None
        self._anim_a = None
        self._anim_b = None

    def set_status(self, effective, color_hex):
        r = int(color_hex[1:3], 16) if color_hex and len(color_hex) >= 7 else 156
        g = int(color_hex[3:5], 16) if color_hex and len(color_hex) >= 7 else 163
        b = int(color_hex[5:7], 16) if color_hex and len(color_hex) >= 7 else 175
        a = self._DOT_ALPHAS.get(effective, 0.015)
        key = (r, g, b, round(a, 4))
        if self._cur_key == key:
            return
        self._cur_key = key
        target = QColor(r, g, b)
        target.setAlphaF(a)
        if self._active is None:
            self._col_a = target
            self._anim_a = QPropertyAnimation(self, b'_alpha_a_prop', self)
            self._anim_a.setDuration(1500)
            self._anim_a.setStartValue(self._alpha_a)
            self._anim_a.setEndValue(1.0)
            self._anim_a.setEasingCurve(QEasingCurve.OutCubic)
            self._anim_a.start()
            self._active = 'A'
        elif self._active == 'A':
            self._col_b = target
            self._anim_b = QPropertyAnimation(self, b'_alpha_b_prop', self)
            self._anim_b.setDuration(1500)
            self._anim_b.setStartValue(self._alpha_b)
            self._anim_b.setEndValue(1.0)
            self._anim_b.setEasingCurve(QEasingCurve.OutCubic)
            self._anim_a = QPropertyAnimation(self, b'_alpha_a_prop', self)
            self._anim_a.setDuration(1500)
            self._anim_a.setStartValue(self._alpha_a)
            self._anim_a.setEndValue(0.0)
            self._anim_a.setEasingCurve(QEasingCurve.OutCubic)
            self._anim_b.start()
            self._anim_a.start()
            self._active = 'B'
        else:
            self._col_a = target
            self._anim_a = QPropertyAnimation(self, b'_alpha_a_prop', self)
            self._anim_a.setDuration(1500)
            self._anim_a.setStartValue(self._alpha_a)
            self._anim_a.setEndValue(1.0)
            self._anim_a.setEasingCurve(QEasingCurve.OutCubic)
            self._anim_b = QPropertyAnimation(self, b'_alpha_b_prop', self)
            self._anim_b.setDuration(1500)
            self._anim_b.setStartValue(self._alpha_b)
            self._anim_b.setEndValue(0.0)
            self._anim_b.setEasingCurve(QEasingCurve.OutCubic)
            self._anim_a.start()
            self._anim_b.start()
            self._active = 'A'
        self.update()

    def _get_a(self): return self._alpha_a
    def _set_a(self, v): self._alpha_a = v; self.update()
    _alpha_a_prop = Property(float, _get_a, _set_a)

    def _get_b(self): return self._alpha_b
    def _set_b(self, v): self._alpha_b = v; self.update()
    _alpha_b_prop = Property(float, _get_b, _set_b)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        for col, alpha_mul in ((self._col_a, self._alpha_a), (self._col_b, self._alpha_b)):
            if alpha_mul <= 0.001:
                continue
            r, g, b = col.red(), col.green(), col.blue()
            final_a = int(col.alphaF() * alpha_mul * 255)
            dot_color = QColor(r, g, b, final_a)
            p.setPen(Qt.NoPen)
            p.setBrush(dot_color)
            step = 40
            y = 0
            row = 0
            while y < h:
                x = 0
                col_idx = 0
                while x < w:
                    if row % 3 == 0 and col_idx % 4 == 0:
                        p.drawEllipse(QPointF(x, y), 1.0, 1.0)
                    x += step
                    col_idx += 1
                y += step
                row += 1


class _FmHeroCard(QFrame):
    """Карточка-герой с лёгким радиальным глоу из верхнего-левого угла.
    Глоу «дышит» — амплитуда альфа-канала колеблется по синусоиде. Скорость
    дыхания зависит от состояния: спокойно при ok, быстрее при warn/bad/down."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._glow_color = None       # текущий (отображаемый) цвет
        self._target_color = None     # целевой цвет (куда плавно переходим)
        self._glow_state = "unknown"
        self._target_state = "unknown"
        # Целевые «пиковая альфа» и «множитель радиуса» — плавно интерполируются.
        self._peak_alpha = 0.08
        self._target_peak_alpha = 0.08
        self._anim_phase = 0.0
        # Сама карточка рисует свой фон в paintEvent; запрещаем дефолтную
        # заливку — иначе бывает «двойной» фон и заметные швы по бордюру.
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # Breathing-таймер для пульсации glow на hero-карточке
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(33)

    _PEAK_ALPHA_BY_STATE = {
        "ok":         0.18,
        "unknown":    0.08,
        "warn":       0.26,
        "confirming": 0.26,
        "bad":        0.30,
        "down":       0.34,
    }

    def set_glow(self, color_hex, state="ok"):
        # Целевые значения — текущие плавно интерполируются к ним в _tick().
        self._target_color = QColor(color_hex) if color_hex else None
        self._target_state = state or "unknown"
        self._target_peak_alpha = self._PEAK_ALPHA_BY_STATE.get(self._target_state, 0.18)
        # Если ещё нет начального цвета — стартуем с целевого, чтобы при
        # первом показе не было артефакта «фейда из чёрного».
        if self._glow_color is None and self._target_color is not None:
            self._glow_color = QColor(self._target_color)
            self._peak_alpha = self._target_peak_alpha
            self._glow_state = self._target_state
        self.update()

    @staticmethod
    def _lerp(a, b, t):
        return a + (b - a) * t

    def _tick(self):
        # Плавная интерполяция цвета к целевому (~1 сек на полный переход).
        # 0.05 за тик 33 мс ≈ ~0.66 сек на ~95% перехода — близко к CSS-«ease 1s».
        smooth = 0.05
        if self._target_color is not None:
            if self._glow_color is None:
                self._glow_color = QColor(self._target_color)
            else:
                cr = int(round(self._lerp(self._glow_color.red(),   self._target_color.red(),   smooth)))
                cg = int(round(self._lerp(self._glow_color.green(), self._target_color.green(), smooth)))
                cb = int(round(self._lerp(self._glow_color.blue(),  self._target_color.blue(),  smooth)))
                self._glow_color = QColor(cr, cg, cb)
        # Плавная интерполяция peak alpha
        self._peak_alpha = self._lerp(self._peak_alpha, self._target_peak_alpha, smooth)
        # Скорость пульсации — берём по «целевому» состоянию: при смене статуса
        # дыхание сразу подхватывает новый ритм, цвет догоняет плавно.
        self._glow_state = self._target_state
        step = {
            "ok":         0.018,
            "unknown":    0.012,
            "warn":       0.040,
            "confirming": 0.040,
            "bad":        0.075,
            "down":       0.090,
        }.get(self._glow_state, 0.020)
        self._anim_phase += step
        if self._anim_phase > 1e6:
            self._anim_phase = 0.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        # Базовый фон карточки
        p.setBrush(QColor(0x16, 0x16, 0x16, 184))
        p.setPen(QPen(QColor(_FM_COLORS["line"]), 1))
        p.drawRoundedRect(r, 14, 14)

        if self._glow_color is None:
            return

        # Дыхание: коэффициент колеблется в [0.35 … 1.0]
        breath = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(self._anim_phase))
        # peak_alpha — плавно интерполируется в _tick() между состояниями,
        # чтобы переход цвет/яркость свечения был мягким, как CSS-transition.
        peak_alpha = self._peak_alpha
        radius_mul = 0.62 + 0.06 * (0.5 + 0.5 * math.sin(self._anim_phase + 0.7))
        radius = max(r.width(), r.height()) * radius_mul

        gr = QRadialGradient(QPointF(r.left() + r.width() * 0.20,
                                     r.top() - r.height() * 0.18), radius)
        c0 = QColor(self._glow_color)
        c0.setAlphaF(peak_alpha * breath)
        c1 = QColor(self._glow_color)
        c1.setAlphaF(0.0)
        gr.setColorAt(0.0, c0)
        gr.setColorAt(1.0, c1)
        p.setBrush(QBrush(gr))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 14, 14)


class _FmFlatCard(QFrame):
    """Простая карточка со скру  лё  н  м фоном и рамкой, нарисованными в
    paintEvent (а не через QSS). Это важно: при stylesheet-фоне на обычном
    QFrame дочерние QLabel на Windows получают «родной» серый квадрат-подложку.
    Самоотрисовка + WA_TranslucentBackground убирает этот артефакт — так же,
    как сделано в _FmHeroCard (у которой квадратов нет)."""

    def __init__(self, bg_hex, border_hex, radius=12, parent=None):
        super().__init__(parent)
        self._bg = QColor(bg_hex)
        self._bg.setAlphaF(0.72)
        self._border = QColor(border_hex)
        self._radius = radius
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(self._bg)
        p.setPen(QPen(self._border, 1))
        p.drawRoundedRect(r, self._radius, self._radius)


class _FmStatTile(QFrame):
    """Маленькая плитка статистики для блока «recent probes»: цветная акцент-
    полоска слева, крупное значение сверху и тонкий uppercase-лейбл снизу.
    Самоотрисовка фона/границы (как в _FmFlatCard) — без QSS-фона, иначе под
    дочерними QLabel на Windows видна системная серая подложка."""

    def __init__(self, accent_hex, parent=None):
        super().__init__(parent)
        self._accent = QColor(accent_hex)
        self._bg = QColor(_FM_COLORS["bg_warm"])
        self._bg.setAlphaF(0.72)
        self._border = QColor(_FM_COLORS["line_soft"])
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumHeight(62)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 9, 14, 10)
        lay.setSpacing(3)

        self.value_lbl = QLabel("—")
        vf = QFont("Segoe UI", 16, QFont.DemiBold)
        self.value_lbl.setFont(vf)
        self.value_lbl.setTextFormat(Qt.RichText)
        self.value_lbl.setStyleSheet(f"color: {_FM_COLORS['ink']}; background: transparent;")
        lay.addWidget(self.value_lbl)

        self.label_lbl = QLabel("—")
        lf = QFont("Segoe UI", 8, QFont.DemiBold)
        lf.setLetterSpacing(QFont.PercentageSpacing, 120)
        self.label_lbl.setFont(lf)
        self.label_lbl.setStyleSheet(f"color: {_FM_COLORS['ink_muted']}; background: transparent;")
        lay.addWidget(self.label_lbl)

    def set_data(self, value_html, label_text, value_color_hex=None):
        self.value_lbl.setText(value_html)
        if value_color_hex:
            self.value_lbl.setStyleSheet(
                f"color: {value_color_hex}; background: transparent;"
            )
        self.label_lbl.setText(label_text)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(self._bg)
        p.setPen(QPen(self._border, 1))
        p.drawRoundedRect(r, 11, 11)

        # Тонкая вертикальная акцент-полоска слева
        accent_w = 3.0
        ar = QRectF(r.left() + 1.5, r.top() + 9, accent_w, r.height() - 18)
        p.setBrush(self._accent)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(ar, accent_w / 2, accent_w / 2)


class _FmRateBar(QWidget):
    """Тонкая горизонтальная стек-полоска, показывает доли ok / slow / failed
    в последних N пробах. Просто визуальный якорь поверх плиток."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedHeight(6)
        self._n_ok_clean = 0   # ok минус slow — чисто зелёный сегмент
        self._n_slow = 0
        self._n_failed = 0
        self._n_total = 0

    def set_counts(self, n_ok, n_slow, n_failed, n_total):
        # n_ok на сайте включает slow (любая проба с ok=True). Чтобы стек был
        # читаемый, выделяем «чистый ok» = ok минус slow.
        self._n_ok_clean = max(0, n_ok - n_slow)
        self._n_slow = max(0, n_slow)
        self._n_failed = max(0, n_failed)
        self._n_total = max(1, n_total)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        radius = h / 2.0

        # Фоновая дорожка
        p.setBrush(QColor(_FM_COLORS["line_soft"]))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        if self._n_total <= 0:
            return

        segments = [
            (self._n_ok_clean, QColor(_FM_COLORS["ok"])),
            (self._n_slow,     QColor(_FM_COLORS["slow"])),
            (self._n_failed,   QColor(_FM_COLORS["failed"])),
        ]
        x = 0.0
        for count, color in segments:
            if count <= 0:
                continue
            seg_w = (count / self._n_total) * w
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, 0, seg_w + 0.5, h), radius, radius)
            x += seg_w


class _FmSegmentedControl(QWidget):
    """Сегментированный переключатель для выбора scope: All / host1 / host2 / …
    Один активный сегмент, остальные приглушены. Опции задаются динамически
    из списка таргетов в /api/status."""

    selectionChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._options = []        # list of (key, label)
        self._buttons = []        # list of (key, QPushButton)
        self._current_key = None

        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(6)
        self._lay.addStretch()

    def _button_style(self):
        return (
            "QPushButton {"
            f" background-color: {_FM_COLORS['bg_warm']};"
            f" color: {_FM_COLORS['ink_soft']};"
            f" border: 1px solid {_FM_COLORS['line']};"
            "  border-radius: 8px;"
            "  padding: 6px 14px;"
            "}"
            "QPushButton:hover {"
            f" color: {_FM_COLORS['ink']};"
            f" border-color: {_FM_COLORS['ink_muted']};"
            "}"
            "QPushButton:checked {"
            "  background-color: #052e1a;"
            f" color: {_FM_COLORS['ok']};"
            f" border-color: {_FM_COLORS['ok']};"
            "}"
        )

    def set_options(self, options):
        """options — список (key, label). Если состав ключей не изменился,
        ничего не пересобираем (чтобы не моргала вёрстка на каждом тике)."""
        new_keys = [o[0] for o in options]
        old_keys = [o[0] for o in self._options]
        if new_keys == old_keys:
            # Обновим лейблы на всякий случай
            for (key, btn), (_, label) in zip(self._buttons, options):
                btn.setText(label)
            self._options = list(options)
            return

        prev_key = self._current_key
        # Снести старые
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self._buttons = []
        self._options = list(options)

        for key, label in options:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            btn.setStyleSheet(self._button_style())
            btn.setFlat(True)
            btn.clicked.connect(lambda _checked, k=key: self._on_clicked(k))
            self._buttons.append((key, btn))
            self._lay.addWidget(btn)
        self._lay.addStretch()

        # Восстановить выбор
        if prev_key and prev_key in new_keys:
            self._set_checked(prev_key)
        elif new_keys:
            self._current_key = new_keys[0]
            self._set_checked(new_keys[0])

    def _on_clicked(self, key):
        if key == self._current_key:
            # Кликнули по уже активному — оставляем как есть (не даём «отжать»)
            self._set_checked(self._current_key)
            return
        self._current_key = key
        self._set_checked(key)
        self.selectionChanged.emit(key)

    def _set_checked(self, key):
        for k, btn in self._buttons:
            btn.setChecked(k == key)

    def set_current(self, key, emit=True):
        if not any(k == key for k, _ in self._options):
            return
        if key == self._current_key:
            self._set_checked(key)
            return
        self._current_key = key
        self._set_checked(key)
        if emit:
            self.selectionChanged.emit(key)

    def current_key(self):
        return self._current_key


class _FmUptimeChip(QFrame):
    """Виджет-пилюля с анимированной точкой-индикатором и текстом «UPTIME N%».
    Точка дышит за счёт собственного QTimer-а в StatusIndicator (60 FPS).
    Состояние индикатора:
      • ≥85%  → 'fm_ok' (зелёный как на сайте)
      • 50-85 → 'warn'  (жёлтый)
      • <50   → 'off'   (красный)
      • None  → 'neutral' (серый, спокойная пульсация)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FmUptimeChip")
        self.setAttribute(Qt.WA_StyledBackground, True)
        # QSS на сам QFrame; дочерним виджетам ставим прозрачный фон.
        self.setStyleSheet(
            "QFrame#FmUptimeChip {"
            f"  background: {_FM_COLORS['bg_warm']};"
            f"  border: 1px solid {_FM_COLORS['line_soft']};"
            "  border-radius: 10px;"
            "}"
            "QFrame#FmUptimeChip QLabel {"
            "  background: transparent;"
            "  border: 0;"
            "}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(7, 2, 11, 2)
        lay.setSpacing(6)

        # Анимированная точка — переиспользуем StatusIndicator (уже
        # умеет дышать и переключать цвет через set_state).
        self.dot = StatusIndicator()
        self.dot.setFixedSize(14, 14)
        self.dot.set_state("neutral")
        lay.addWidget(self.dot, 0, Qt.AlignVCenter)

        self.lbl = QLabel(
            f"<span style='color:{_FM_COLORS['ink_muted']};'>UPTIME —</span>"
        )
        self.lbl.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.lbl.setTextFormat(Qt.RichText)
        lay.addWidget(self.lbl, 0, Qt.AlignVCenter)

    def set_uptime(self, pct):
        """pct — float 0..100 (или None если данных нет)."""
        if pct is None or not isinstance(pct, (int, float)) or not math.isfinite(pct):
            self.dot.set_state("neutral")
            self.lbl.setText(
                f"<span style='color:{_FM_COLORS['ink_muted']};'>UPTIME —</span>"
            )
            return
        if pct < 50:
            state, col = "off", _FM_COLORS["bad"]
        elif pct < 85:
            state, col = "warn", _FM_COLORS["warn"]
        else:
            state, col = "fm_ok", _FM_COLORS["ok"]
        self.dot.set_state(state)
        txt = "100%" if pct >= 99.95 else f"{pct:.1f}%"
        self.lbl.setText(
            f"<span style='color:{_FM_COLORS['ink_muted']};'>UPTIME </span>"
            f"<span style='color:{col};'>{txt}</span>"
        )


class _FmFormatChip(QFrame):
    """Виджет-пилюля «format <Provider>» — стиль как у UPTIME chip.
    Provider: 'anthropic' (оранжевый) или 'openai' (зелёный)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FmFormatChip")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "QFrame#FmFormatChip {"
            f"  background: {_FM_COLORS['bg_warm']};"
            f"  border: 1px solid {_FM_COLORS['line_soft']};"
            "  border-radius: 10px;"
            "}"
            "QFrame#FmFormatChip QLabel {"
            "  background: transparent;"
            "  border: 0;"
            "}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 2, 4, 2)
        lay.setSpacing(6)

        self.lbl = QLabel("")
        self.lbl.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.lbl.setTextFormat(Qt.RichText)
        lay.addWidget(self.lbl, 0, Qt.AlignVCenter)

        self.badge = QLabel("")
        self.badge.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.badge.setTextFormat(Qt.RichText)
        self.badge.setAttribute(Qt.WA_StyledBackground, True)
        lay.addWidget(self.badge, 0, Qt.AlignVCenter)

    def set_format(self, fmt):
        if fmt == "anthropic":
            self.lbl.setText(
                f"<span style='color:{_FM_COLORS['ink_muted']};'>format</span>"
            )
            self.badge.setStyleSheet(
                "background:#3a1f0f; border:1px solid #d97706;"
                "border-radius:6px; padding:2px 8px; color:#f59e0b;"
            )
            self.badge.setText("Anthropic")
            self.setVisible(True)
        else:
            self.setVisible(False)


class _FmScopeView(QWidget):
    """Сабблок статистики для одного scope. Два режима:
       • compact=False — полноразмерный: заголовок, 4 п  итки stat-tiles,
         стек-полоска, гистограмма. Исп  льзуется когда выбран конкретный
         endpoint (только 1 сабблок в карточке).
       • compact=True — компактный: заголовок c inline-сводкой справа,
         стек-полоска, тонкая гистограмма. Используется в режиме All,
         где таких сабблоков 3 (агрегат + 2 endpoint'а) — иначе они бы
         не уместились в окне без скролла."""

    def __init__(self, compact=False, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._compact = compact

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6 if compact else 10)

        # Заголовок сабблока. Слева — название scope, справа — inline-сводка
        # (только в compact-режиме). В non-compact справа всегда пусто, потому
        # что там ниже идут полноценные плитки.
        head_row = QHBoxLayout()
        head_row.setSpacing(8)
        self.title_lbl = QLabel("—")
        title_pt = 9 if compact else 10
        self.title_lbl.setFont(QFont("Segoe UI", title_pt, QFont.DemiBold))
        # Тонкий виджет-пилюля вокруг названия эндпоинта — как на сайте, но мягче.
        self.title_lbl.setStyleSheet(
            f"color: {_FM_COLORS['ink']};"
            f"background: {_FM_COLORS['bg_warm']};"
            f"border: 1px solid {_FM_COLORS['line_soft']};"
            f"border-radius: 9px; padding: 3px 10px;"
        )
        head_row.addWidget(self.title_lbl)
        # Бейдж формата API (Anthropic / OpenAI) — рядом с названием эндпоинта.
        self.format_chip = _FmFormatChip()
        self.format_chip.setVisible(False)
        head_row.addWidget(self.format_chip)
        # Чип uptime — анимированная точка + проценты. Берёт uptime24
        # из API (как на сайте), а не считает локально из последних проб.
        self.uptime_chip = _FmUptimeChip()
        head_row.addWidget(self.uptime_chip)
        head_row.addStretch()
        self.summary_lbl = QLabel("")
        self.summary_lbl.setFont(QFont("Segoe UI", 9))
        self.summary_lbl.setTextFormat(Qt.RichText)
        self.summary_lbl.setStyleSheet(
            f"color: {_FM_COLORS['ink_muted']}; background: transparent;"
        )
        # В полноразмерном виде сводка лишняя — те же цифры уже в stat-плитках.
        # Скрываем её, чтобы не было визуального дубля.
        if not compact:
            self.summary_lbl.setVisible(False)
        head_row.addWidget(self.summary_lbl)
        lay.addLayout(head_row)

        # Плитки — только в non-compact
        self.stat_ok = self.stat_slow = self.stat_failed = self.stat_latest = None
        if not compact:
            stat_row = QHBoxLayout()
            stat_row.setSpacing(10)
            self.stat_ok     = _FmStatTile(_FM_COLORS["ok"])
            self.stat_slow   = _FmStatTile(_FM_COLORS["slow"])
            self.stat_failed = _FmStatTile(_FM_COLORS["failed"])
            self.stat_latest = _FmStatTile(_FM_COLORS["ink_muted"])
            for tile in (self.stat_ok, self.stat_slow, self.stat_failed, self.stat_latest):
                stat_row.addWidget(tile, 1)
            lay.addLayout(stat_row)

        self.rate_bar = _FmRateBar()
        lay.addSpacing(1)
        lay.addWidget(self.rate_bar)

        self.histogram = LatencyHistogram()
        if compact:
            self.histogram.setMinimumHeight(78)
            self.histogram.setMaximumHeight(78)
        lay.addWidget(self.histogram, 1)

    def set_title(self, text, fmt=None):
        self.title_lbl.setText(text)
        self.format_chip.set_format(fmt)

    def update_from_samples(self, samples_with_ok, now_ms, explicit_up=None):
        """samples_with_ok — отсортированный по ts список (ts, cat, lat, is_ok).
        explicit_up — uptime24 в процентах (взвешенный по samples1h из API).
        Если передан, используется вместо локального подсчёта по recent."""
        self.histogram.set_samples([(t, c, l) for (t, c, l, _) in samples_with_ok])

        recent = samples_with_ok[-96:]
        if not recent:
            if self.stat_ok is not None:
                for tile, label in (
                    (self.stat_ok, "OK"), (self.stat_slow, "SLOW"),
                    (self.stat_failed, "FAILED"), (self.stat_latest, "LATEST"),
                ):
                    tile.set_data("—", label, _FM_COLORS["ink_muted"])
            self.rate_bar.set_counts(0, 0, 0, 0)
            self.summary_lbl.setText("нет данных")
            self.uptime_chip.set_uptime(explicit_up)
            return

        n_total = len(recent)
        n_ok     = sum(1 for _, _, _, ok in recent if ok)
        n_failed = n_total - n_ok
        n_slow   = sum(1 for _, c, _, _ in recent if c in ("slow", "very_slow"))
        latest_ts = recent[-1][0]
        latest_age = now_ms - latest_ts if latest_ts else None
        ok_pct = (n_ok * 100.0 / n_total) if n_total else 0.0

        ink_soft = _FM_COLORS["ink_soft"]
        ok_color = _FM_COLORS["ok"]
        if ok_pct < 50:
            ok_color = _FM_COLORS["bad"]
        elif ok_pct < 85:
            ok_color = _FM_COLORS["warn"]

        # Uptime-чип берёт значение из uptime24 (если есть), иначе fallback
        # на локально посчитанный процент по recent. Это сразу даёт «правдо-
        # подобные» проценты как на сайте — 4.0% / 60.5% и т.д.
        self.uptime_chip.set_uptime(
            explicit_up if explicit_up is not None else ok_pct
        )

        if self.stat_ok is not None:
            self.stat_ok.set_data(
                f"{n_ok}<span style='color:{ink_soft}; font-size:12pt;'>/{n_total}</span>",
                f"OK  •  {ok_pct:.0f}%",
                ok_color,
            )
            self.stat_slow.set_data(
                f"{n_slow}", "SLOW",
                _FM_COLORS["slow"] if n_slow else _FM_COLORS["ink_muted"],
            )
            self.stat_failed.set_data(
                f"{n_failed}", "FAILED",
                _FM_COLORS["failed"] if n_failed else _FM_COLORS["ink_muted"],
            )
            self.stat_latest.set_data(
                _fm_fmt_age(latest_age), "LATEST PROBE", _FM_COLORS["ink"],
            )
        self.rate_bar.set_counts(n_ok, n_slow, n_failed, n_total)

        # Inline-сводка для compact: «87/96 ok · 12 slow · 9 failed · 6m ago»
        slow_part = (f"  •  <span style='color:{_FM_COLORS['slow']};'>{n_slow}</span> slow"
                     if n_slow else "")
        failed_part = (f"  •  <span style='color:{_FM_COLORS['failed']};'>{n_failed}</span> failed"
                       if n_failed else "")
        self.summary_lbl.setText(
            f"<span style='color:{ok_color};'>{n_ok}</span>/"
            f"<span style='color:{ink_soft};'>{n_total}</span> ok"
            f"{slow_part}{failed_part}"
            f"  •  latest {_fm_fmt_age(latest_age)}"
        )


class _FmTitleBarButton(QPushButton):
    """Кнопка в шапке окна — минимизация/закрытие. Рисует крестик/минус QPainter'ом
    с мягким hover-фоном."""

    def __init__(self, kind="close", parent=None):
        super().__init__(parent)
        self._kind = kind  # 'close' | 'min'
        self.setFixedSize(38, 28)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False
        # Кнопка — кастомная отрисовка только глифа и hover-фона. Дефолтную
        # native-подложку отключаем, иначе по углам видны «коробки».
        self.setFlat(True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(2, 2, -2, -2)

        if self._hover:
            if self._kind == "close":
                bg = QColor("#e74c3c")
                bg.setAlphaF(0.18)
            else:
                bg = QColor("#ffffff")
                bg.setAlphaF(0.06)
            p.setBrush(bg)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r, 6, 6)

        cx, cy = self.width() / 2, self.height() / 2
        pen_color = QColor(_FM_COLORS["ink"]) if self._hover else QColor(_FM_COLORS["ink_muted"])
        pen = QPen(pen_color, 1.4)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)

        if self._kind == "close":
            s = 4.5
            p.drawLine(QPointF(cx - s, cy - s), QPointF(cx + s, cy + s))
            p.drawLine(QPointF(cx + s, cy - s), QPointF(cx - s, cy + s))
        else:  # min
            s = 5.0
            p.drawLine(QPointF(cx - s, cy + 0.5), QPointF(cx + s, cy + 0.5))


class _FmTitleBar(QWidget):
    """Кастомная шапка окна freemodel.dev: индикатор + бренд слева, кнопки справа.
    Перетаскивание окна — за свободную область шапки."""

    close_clicked = Signal()
    minimize_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        # Сама шапка рисует только нижнюю линию — фон даёт родительский
        # контейнер. WA_TranslucentBackground убирает дефолтную системную
        # заливку, которая иначе видна по углам.
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 8, 8, 8)
        lay.setSpacing(10)

        # Точка-статус слева
        self.dot = StatusIndicator()
        self.dot.setFixedSize(14, 14)
        self.dot.set_state("neutral")
        lay.addWidget(self.dot, 0, Qt.AlignVCenter)

        # Бренд
        self.title = QLabel(
            '<span style="color:#34d399; font-weight:700;">freemodel</span>'
            '<span style="color:#d1d5db; font-weight:500;">.dev</span>'
            '<span style="color:#5b5f66; font-weight:400;">   •   live status</span>'
        )
        self.title.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        self.title.setTextFormat(Qt.RichText)
        lay.addWidget(self.title, 0, Qt.AlignVCenter)

        lay.addStretch()

        self.btn_min = _FmTitleBarButton("min")
        self.btn_min.clicked.connect(self.minimize_clicked.emit)
        lay.addWidget(self.btn_min)

        self.btn_close = _FmTitleBarButton("close")
        self.btn_close.clicked.connect(self.close_clicked.emit)
        lay.addWidget(self.btn_close)

        self._drag_offset = None

    def paintEvent(self, event):
        # Тонкая разделительная линия снизу
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setPen(QPen(QColor(_FM_COLORS["line_soft"]), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.window().pos()
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and (e.buttons() & Qt.LeftButton):
            self.window().move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_offset = None
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        # Двойной клик по шапке — ничего не делает (нет максимизации),
        # перехватываем чтобы не сработал ничего нежелательного.
        e.accept()


class _FmLegendDot(QLabel):
    """Маленькая цветная точка для легенды. Раньше рисовалась через QPainter
    в QWidget — но на Windows под кастомным paintEvent протекала дефолтная
    системная заливка, из-за чего вокруг точки был виден серый квадра  .
    Теперь это QLabel с круглым фоном через CSS (border-radius) — никакой
    собственной отрисовки, неоткуда взяться квадрату."""

    def __init__(self, color_hex, parent=None):
        super().__init__(parent)
        self._size = 10
        self.setFixedSize(self._size, self._size)
        self.set_color(color_hex)

    def set_color(self, color_hex):
        r = self._size / 2
        self.setStyleSheet(
            f"QLabel {{ background-color: {color_hex};"
            f" border: none; border-radius: {r:.1f}px; }}"
        )


def _fm_make_legend(parent=None):
    """Горизонтальная легенда «● ok ● slow ● very slow ● failed» —
    точки нарисованы QPainter'ом, тексты — обычные QLabel."""
    w = QWidget(parent)
    w.setAttribute(Qt.WA_StyledBackground, False)
    w.setAttribute(Qt.WA_TranslucentBackground, True)
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(16)
    items = [
        (_FM_COLORS["ok"],        "ok"),
        (_FM_COLORS["slow"],      "slow"),
        (_FM_COLORS["very_slow"], "very slow"),
        (_FM_COLORS["bad"],       "failed"),
    ]
    for color, label_text in items:
        cell = QHBoxLayout()
        cell.setContentsMargins(0, 0, 0, 0)
        cell.setSpacing(6)
        cell.addWidget(_FmLegendDot(color), 0, Qt.AlignVCenter)
        lbl = QLabel(label_text)
        lbl.setFont(QFont("Segoe UI", 9))
        lbl.setStyleSheet(f"color: {_FM_COLORS['ink_muted']}; background: transparent;")
        cell.addWidget(lbl, 0, Qt.AlignVCenter)
        lay.addLayout(cell)
    return w


class FreemodelStatsDialog(QDialog):
    """Кастомное frameless-окно со статистикой freemodel.dev в реальном времени.
    Единственное окно в приложении с собственной шапкой, перемещаемое за неё."""

    data_updated = Signal(dict)
    fetch_failed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("freemodel.dev — статус и латентность"))
        # Frameless + полупрозрачный фон под drop-shadow контейнера
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(False)
        # В режиме All в карточке проб три сабблока (агрегат + 2 endpoint'а)
        # плюс hero/selector/next_bar. Если высота меньше нужной — низ
        # гистограмм   резается родительским layout'ом и короткие бары
        # (min_height = 3px) уходят под клипинг. Поэтому дефолт с запасом.
        self.setMinimumSize(820, 780)
        self.resize(940, 900)

        try:
            for p in (
                os.path.join(os.path.dirname(__file__), "icon.ico"),
                os.path.join(os.path.dirname(sys.executable), "icon.ico"),
            ):
                if os.path.exists(p):
                    self.setWindowIcon(QIcon(p))
                    break
        except Exception:
            pass

        self._last_data = None
        self._next_check_at_ms = None
        self._stop = False
        self._current_overall = "unknown"

        self._build_ui()

        self.data_updated.connect(self._apply_data)
        self.fetch_failed.connect(self._apply_failure)

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._update_countdown)
        self._tick_timer.start(1000)

        self._fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self._fetch_thread.start()

    # ─── UI ─────────────────────────────────────────────────────────
    def _build_ui(self):
        # Внешний layout — поля под drop-shadow
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(0)

        # Контейнер-«окно» с реальной рамкой и фоном
        self.container = QFrame()
        self.container.setObjectName("fm_window")
        self.container.setStyleSheet(f"""
            QFrame#fm_window {{
                background-color: #0a0a0f;
                border: 1px solid {_FM_COLORS['line']};
                border-radius: 16px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(48)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 10)
        self.container.setGraphicsEffect(shadow)
        outer.addWidget(self.container)

        # ── Фоновые слои: свечение снизу + точки (2-layer crossfade) ──
        self._bg_glow = _FmBgGlow(self.container)
        self._bg_dots = _FmBgDots(self.container)
        self._bg_glow.lower()
        self._bg_dots.lower()

        # Внутренний layout контейнера
        inner = QVBoxLayout(self.container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        # Кастомная шапка
        self.title_bar = _FmTitleBar()
        self.title_bar.close_clicked.connect(self.close)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        inner.addWidget(self.title_bar)

        # Контент
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 20, 24, 22)
        cl.setSpacing(16)

        # ─    Hero: ALL SYSTEMS + GATEWAY LATENCY ──────────────  ──────
        self.hero_frame = _FmHeroCard()
        hero_lay = QHBoxLayout(self.hero_frame)
        hero_lay.setContentsMargins(28, 22, 28, 22)
        hero_lay.setSpacing(24)

        left_col = QVBoxLayout()
        left_col.setSpacing(8)
        self.lbl_all_systems = self._eyebrow("ALL SYSTEMS")
        self.lbl_status_word = QLabel("—")
        self.lbl_status_word.setFont(self._numeric_font(34, QFont.DemiBold))
        self.lbl_status_word.setStyleSheet(f"color: {_FM_COLORS['ink_muted']}; background: transparent;")
        self.lbl_status_sub = QLabel("Awaiting data…")
        self.lbl_status_sub.setFont(QFont("Segoe UI", 10))
        self.lbl_status_sub.setStyleSheet(f"color: {_FM_COLORS['ink_soft']}; background: transparent;")
        self.lbl_status_sub.setWordWrap(True)
        left_col.addWidget(self.lbl_all_systems)
        left_col.addWidget(self.lbl_status_word)
        left_col.addSpacing(2)
        left_col.addWidget(self.lbl_status_sub)
        left_col.addStretch()
        hero_lay.addLayout(left_col, 13)

        # Тонкий вертикальный разделитель
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {_FM_COLORS['line_soft']};")
        hero_lay.addWidget(sep)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)
        self.lbl_lat_eyebrow = self._eyebrow("GATEWAY LATENCY  •  LAST HOUR")
        right_col.addWidget(self.lbl_lat_eyebrow)

        lat_row = QHBoxLayout()
        lat_row.setSpacing(6)
        self.lbl_lat_big = QLabel("—")
        self.lbl_lat_big.setFont(self._numeric_font(36, QFont.DemiBold))
        self.lbl_lat_big.setStyleSheet(f"color: {_FM_COLORS['ink']}; background: transparent;")
        self.lbl_lat_unit = QLabel("ms")
        self.lbl_lat_unit.setFont(QFont("Segoe UI", 14, QFont.Normal))
        self.lbl_lat_unit.setStyleSheet(f"color: {_FM_COLORS['ink_muted']}; background: transparent;")
        lat_row.addWidget(self.lbl_lat_big, 0, Qt.AlignBottom)
        lat_row.addWidget(self.lbl_lat_unit, 0, Qt.AlignBottom)
        lat_row.addStretch()
        right_col.addLayout(lat_row)

        self.lbl_lat_meta = QLabel("p10 — · p90 — · p99 —")
        self.lbl_lat_meta.setFont(self._numeric_font(10, QFont.Normal))
        self.lbl_lat_meta.setStyleSheet(f"color: {_FM_COLORS['ink_muted']}; background: transparent;")
        self.lbl_lat_meta.setTextFormat(Qt.RichText)
        right_col.addWidget(self.lbl_lat_meta)
        right_col.addStretch()
        hero_lay.addLayout(right_col, 10)

        cl.addWidget(self.hero_frame)

        # ── Полоска next check + mode ───────────────────────────────
        # Карточка рисует фон сама (_FmFlatCard) — иначе дочерние QLabel на
        # Windows получают серый квадрат-подложку.
        self.next_bar = _FmFlatCard(_FM_COLORS['bg_warm'], _FM_COLORS['line_soft'], radius=11)
        nb = QHBoxLayout(self.next_bar)
        nb.setContentsMargins(16, 11, 16, 11)
        nb.setSpacing(10)
        self.lbl_next_check = QLabel("next check in —")
        self.lbl_next_check.setFont(self._numeric_font(10, QFont.Normal))
        self.lbl_next_check.setTextFormat(Qt.RichText)
        self.lbl_next_check.setStyleSheet(f"color: {_FM_COLORS['ink_muted']}; background: transparent;")

        # «mode pill» справа — нарисованная точка + текст (без unicode-bullet'а)
        self.mode_dot = _FmLegendDot(_FM_COLORS["ok"])
        self.lbl_mode = QLabel("—")
        self.lbl_mode.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        self.lbl_mode.setStyleSheet(f"color: {_FM_COLORS['ok']}; background: transparent;")

        nb.addWidget(self.lbl_next_check)
        nb.addStretch()
        nb.addWidget(self.mode_dot, 0, Qt.AlignVCenter)
        nb.addSpacing(6)
        nb.addWidget(self.lbl_mode, 0, Qt.AlignVCenter)
        cl.addWidget(self.next_bar)

        # ── Селектор scope: All / endpoint1 / endpoint2 / … ──────────
        # Опции подставляются динамически в _apply_data, когда придут targets.
        # До первой загрузки данных селектор пуст и не показывается.
        self.scope_selector = _FmSegmentedControl()
        self.scope_selector.selectionChanged.connect(self._on_scope_changed)
        cl.addWidget(self.scope_selector)

        # ── Карточка с гистограммой проб ─────────────────────────────
        self.probes_frame = _FmFlatCard(_FM_COLORS['bg_card'], _FM_COLORS['line'], radius=14)
        pf = QVBoxLayout(self.probes_frame)
        pf.setContentsMargins(22, 18, 22, 18)
        pf.setSpacing(10)

        head_row = QHBoxLayout()
        self.probes_title = QLabel("freemodel.dev model probes")
        self.probes_title.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        # Виджет-пилюля вокруг общего заголовка карточки проб.
        self.probes_title.setStyleSheet(
            f"color: {_FM_COLORS['ink']};"
            f"background: {_FM_COLORS['bg_warm']};"
            f"border: 1px solid {_FM_COLORS['line_soft']};"
            f"border-radius: 10px; padding: 4px 12px;"
        )
        head_row.addWidget(self.probes_title)
        head_row.addStretch()
        head_row.addWidget(_fm_make_legend(), 0, Qt.AlignVCenter)
        pf.addLayout(head_row)

        # Контейнер под scope-views. Заполняется/перестраивается в _apply_data
        # в зависимости от выбранного режима (All — 1+N компактных блоков,
        # конкретный таргет — один полноразмерный).
        self.scope_container = QVBoxLayout()
        self.scope_container.setSpacing(11)
        self.scope_container.setContentsMargins(0, 4, 0, 0)
        pf.addLayout(self.scope_container, 1)

        # Кэш scope-view виджетов по ключу ('all' | host). Не пересоздаём при
        # каждом тике — переиспользуем, чтобы не моргала вёрстка.
        self._scope_views = {}
        self._scope_mode = "all"  # текущий выбранный scope-key
        self._known_target_hosts = ()  # tuple — для отслеживания изменений

        cl.addWidget(self.probes_frame, 1)

        # Подпись внизу — кликабельная ссылка «источник: <url>»
        src_url = "https://freemodel-status-mirror-jzmw.vercel.app"
        src_text = tr("источник: freemodel-status-mirror-jzmw.vercel.app")
        src = QLabel(
            f'<span style="color:{_FM_COLORS["ink_muted"]};">{src_text.split(":")[0]}: </span>'
            f'<a href="{src_url}" style="color:#34d399; text-decoration:none;">'
            f'{src_url[len("https://"):]}</a>'
        )
        src.setFont(QFont("Segoe UI", 8))
        src.setTextFormat(Qt.RichText)
        src.setOpenExternalLinks(True)
        src.setStyleSheet("background: transparent;")
        src.setAlignment(Qt.AlignCenter)
        src.setCursor(Qt.PointingHandCursor)
        cl.addWidget(src)

        inner.addWidget(content, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_bg_glow') and self._bg_glow:
            cw = self.container.width()
            ch = self.container.height()
            self._bg_glow.setGeometry(0, 0, cw, ch)
            self._bg_dots.setGeometry(0, 0, cw, ch)
            self._bg_glow.lower()
            self._bg_dots.lower()
            self._bg_glow.update()
            self._bg_dots.update()

    def _host_of(self, url):
        """Нормализованный хост из URL: 'https://cc.freemodel.dev/v1/' → 'cc.freemodel.dev'.
        Чтобы можно было сравнивать с url'ами таргетов независимо от схемы и пути."""
        if not url:
            return ""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url if "://" in url else f"https://{url}")
            host = (parsed.hostname or "").lower().strip()
            return host
        except Exception:
            return ""

    def _eyebrow(self, text):
        lbl = QLabel(text)
        f = QFont("Segoe UI", 8, QFont.DemiBold)
        f.setLetterSpacing(QFont.PercentageSpacing, 118)
        lbl.setFont(f)
        lbl.setStyleSheet(f"color: {_FM_COLORS['ink_muted']}; background: transparent;")
        return lbl

    def _numeric_font(self, pt, weight=QFont.Normal):
        """Шрифт с включёнными tabular-цифрами — большие числа не «прыгают» при апдейте."""
        f = QFont("Segoe UI", pt, weight)
        try:
            f.setStyleStrategy(QFont.PreferAntialias)
            # Tabular figures — Qt6 поддерживает font features через setFeature на QFont 6.7+,
            # как fallback используем стандартный шрифт. Главное — фикс-ширина у цифр у Segoe UI.
        except Exception:
            pass
        return f

    # ─── Фоновый поллер ────────────────────────────────────────────
    def _fetch_loop(self):
        url = "https://fm.bluealitas.com/api/status"
        ctx = ssl.create_default_context()
        while not self._stop:
            try:
                req = Request(url, headers={"User-Agent": f"ClaudeCodeManager/{APP_VERSION}"})
                with urlopen(req, timeout=8, context=ctx) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                self.data_updated.emit(data)
            except Exception:
                self.fetch_failed.emit()
            # пауза с проверкой stop — чтобы окно быстро закрывалось
            for _ in range(60):  # 60 × 0.1с = 6 секунд
                if self._stop:
                    return
                time.sleep(0.1)

    # ─── Применение данных ─────────────────────────────────────────
    def _apply_data(self, data):
        self._last_data = data
        now_ms = int(time.time() * 1000)

        # Мод-бар (cadence/mode) — всегда серверный общий, не зависит от scope
        self._update_mode_bar(data)
        self._next_check_at_ms = data.get("nextCheckAt")
        self._update_countdown()

        # Собираем пробы по таргетам (только enabled+не removed модели).
        # Параллельно считаем взвешенный uptime24 (по samples1h) — те же
        # цифры что и на сайте: «4.0%», «60.5%» и пр.
        targets = data.get("targets") or []
        targets_with_host = []
        by_host = {}
        aggregate_samples = []
        up_by_host = {}
        up_agg_num = 0.0
        up_agg_den = 0
        for tgt in targets:
            host = self._host_of(tgt.get("url") or "")
            if not host:
                continue
            samples = []
            up_num = 0.0
            up_den = 0
            for m in (tgt.get("models") or []):
                if not m.get("enabled") or m.get("removedAt"):
                    continue
                for h in (m.get("history48") or []):
                    ts = h.get("ts") or 0
                    cat = _fm_classify_probe(h)
                    lat = h.get("latency") or 0
                    is_ok = bool(h.get("ok"))
                    samples.append((ts, cat, lat, is_ok))
                # uptime24 берётся в виде float процента, samples1h — вес.
                up_raw = m.get("uptime24")
                s1h = m.get("samples1h") or 0
                if up_raw is not None and s1h:
                    try:
                        up_f = float(up_raw)
                        if math.isfinite(up_f):
                            up_num += up_f * s1h
                            up_den += s1h
                    except (TypeError, ValueError):
                        pass
            samples.sort(key=lambda x: x[0])
            by_host[host] = samples
            aggregate_samples.extend(samples)
            targets_with_host.append((host, tgt))
            if up_den > 0:
                up_by_host[host] = up_num / up_den
                up_agg_num += up_num
                up_agg_den += up_den
        aggregate_samples.sort(key=lambda x: x[0])
        up_agg = (up_agg_num / up_agg_den) if up_agg_den > 0 else None
        self._up_by_host = up_by_host
        self._up_agg = up_agg

        # Опции селектора: All + по одному на каждый таргет.
        # Пересобираем только если состав ключей изменился.
        host_tuple = tuple(h for h, _ in targets_with_host)
        if host_tuple != self._known_target_hosts:
            self._known_target_hosts = host_tuple
            # Подписываем endpoint-ы тегами (t0)/(t1)/… в порядке возврата
            # сервером — синхронно с подписями в карточке probes ниже.
            options = [("all", "All")] + [
                (h, f"{h}  (t{i})") for i, h in enumerate(host_tuple)
            ]
            self.scope_selector.set_options(options)
            # Если активный ключ исчез из опций — selector сам перейдёт на «all»;
            # синхронизируем _scope_mode.
            sel = self.scope_selector.current_key() or "all"
            if sel != self._scope_mode:
                self._scope_mode = sel

        sel = self.scope_selector.current_key() or "all"
        self._scope_mode = sel

        # ── Hero (верхняя панель) — обновляем под выбранный scope ────
        if sel == "all":
            self._apply_hero_aggregate(data, now_ms)
            lat_pool = aggregate_samples
        else:
            tgt = next((t for h, t in targets_with_host if h == sel), None)
            self._apply_hero_for_target(tgt, data, now_ms)
            lat_pool = by_host.get(sel, [])

        last_hour_lats = [l for (t, _c, l, ok) in lat_pool
                          if ok and t >= now_ms - 3600 * 1000]
        self._apply_hero_latency(last_hour_lats)

        # ── Probes-карточка — пересобираем сабблоки под текущий scope ─
        # Для All-режима подписываем endpoint-ы тегами (t0)/(t1)/… в порядке,
        # в котором их отдаёт сервер — это помогает быстро ссылаться на
        # «первый» / «второй» endpoint в логах и обсуждениях.
        def _fmt_for(host, idx):
            return "anthropic"

        if sel == "all":
            desired = [("__all__", "Aggregate (all endpoints)", aggregate_samples, True, None)]
            for idx, host in enumerate(host_tuple):
                tag = f"(t{idx})"
                desired.append((host, f"{host}  {tag}", by_host.get(host, []), True, _fmt_for(host, idx)))
            self.probes_title.setText("freemodel.dev model probes  •  all scopes")
        else:
            # В single-endpoint режиме тоже добавляем тег, чтобы пользователь
            # видел, какой именно endpoint открыт.
            try:
                idx = host_tuple.index(sel)
                tag = f" (t{idx})"
                fmt = _fmt_for(sel, idx)
            except ValueError:
                tag = ""
                fmt = None
            desired = [(sel, f"{sel}{tag}", by_host.get(sel, []), False, fmt)]
            self.probes_title.setText(f"freemodel.dev model probes  •  {sel}")

        self._rebuild_scope_layout([(k, c) for (k, _t, _s, c, _f) in desired])
        for key, title, samples, _compact, fmt in desired:
            view = self._scope_views.get(key)
            if view is not None:
                view.set_title(title, fmt)
                up = self._up_agg if key == "__all__" else self._up_by_host.get(key)
                view.update_from_samples(samples, now_ms, up)

    # ─── Hero / mode-bar помощники ─────────────────────────────────
    def _status_color(self, effective):
        return {
            "ok":         _FM_COLORS["ok"],
            "warn":       _FM_COLORS["warn"],
            "confirming": _FM_COLORS["warn"],
            "bad":        _FM_COLORS["bad"],
            "down":       _FM_COLORS["down"],
            "unknown":    _FM_COLORS["ink_muted"],
        }.get(effective, _FM_COLORS["ink_muted"])

    def _update_title_dot(self, effective):
        if effective == "ok":
            self.title_bar.dot.set_state("fm_ok")
        elif effective in ("warn", "confirming"):
            self.title_bar.dot.set_state("warn")
        elif effective in ("bad", "down"):
            self.title_bar.dot.set_state("off")
        else:
            self.title_bar.dot.set_state("neutral")

    def _apply_hero_aggregate(self, data, now_ms):
        """Hero в режиме All — берёт серверные overall/mode/lastOkOverall,
        ровно как было до селектора."""
        overall = str(data.get("overall") or "unknown").lower()
        mode = str(data.get("mode") or "").lower()
        labels = data.get("statusLabels") or {}

        if mode == "confirming":
            effective = "confirming"
            word = "Confirming…"
        else:
            effective = overall
            word = labels.get(overall) or {
                "ok": "Operational", "warn": "Degraded", "bad": "Disrupted",
                "down": "Down", "unknown": "Awaiting probes…"
            }.get(overall, "—")

        word_color = self._status_color(effective)
        self.lbl_status_word.setText(word)
        self.lbl_status_word.setStyleSheet(
            f"color: {word_color}; background: transparent;"
        )
        self.hero_frame.set_glow(word_color, effective)
        self._update_title_dot(effective)
        if self._current_overall != effective:
            self._current_overall = effective
            self._bg_glow.set_status(effective)
            self._bg_dots.set_status(effective, word_color)
        self.lbl_all_systems.setText("ALL SYSTEMS")

        last_ok = data.get("lastOkOverall")
        age = (now_ms - last_ok) if last_ok else None
        if overall == "ok":
            sub = f"All tested models are responding. Last successful check {_fm_fmt_age(age)}."
        elif overall == "warn":
            sub = f"Some models are degraded. Last successful check {_fm_fmt_age(age)}."
        elif overall in ("bad", "down"):
            sub = f"Service is disrupted. Last successful check {_fm_fmt_age(age)}."
        else:
            sub = "Awaiting probes…"
        self.lbl_status_sub.setText(sub)

    def _apply_hero_for_target(self, tgt, data, now_ms):
        """Hero в режиме конкретного endpoint — статус и lastOk берём из
        самого таргета (data.targets[i].status / lastOk)."""
        if tgt is None:
            self.lbl_all_systems.setText("ENDPOINT")
            self.lbl_status_word.setText("—")
            self.lbl_status_word.setStyleSheet(
                f"color: {_FM_COLORS['ink_muted']}; background: transparent;"
            )
            self.hero_frame.set_glow(None, "unknown")
            self._update_title_dot("unknown")
            if self._current_overall != "unknown":
                self._current_overall = "unknown"
                self._bg_glow.set_status("unknown")
                self._bg_dots.set_status("unknown", _FM_COLORS["ink_muted"])
            self.lbl_status_sub.setText(tr("Нет данных по этому endpoint."))
            return

        target_status = str(tgt.get("status") or "unknown").lower()
        # Серверный режим confirming тоже отражаем — индикатор бейджа
        # тогда жёлтый, как и на сайте.
        if str(data.get("mode") or "").lower() == "confirming" and target_status == "ok":
            effective = "confirming"
            word = "Confirming…"
        elif target_status in ("ok", "warn", "bad", "down"):
            effective = target_status
            word = {
                "ok": "Operational", "warn": "Degraded",
                "bad": "Disrupted", "down": "Down",
            }[target_status]
        else:
            effective = "unknown"
            word = "Awaiting probes…"

        word_color = self._status_color(effective)
        self.lbl_status_word.setText(word)
        self.lbl_status_word.setStyleSheet(
            f"color: {word_color}; background: transparent;"
        )
        self.hero_frame.set_glow(word_color, effective)
        self._update_title_dot(effective)
        if self._current_overall != effective:
            self._current_overall = effective
            self._bg_glow.set_status(effective)
            self._bg_dots.set_status(effective, word_color)

        host = self._host_of(tgt.get("url") or "") or "ENDPOINT"
        self.lbl_all_systems.setText(host.upper())

        last_ok = tgt.get("lastOk")
        age = (now_ms - last_ok) if last_ok else None
        if effective == "ok":
            sub = f"Endpoint responding. Last successful probe {_fm_fmt_age(age)}."
        elif effective in ("warn", "confirming"):
            sub = f"Endpoint degraded. Last successful probe {_fm_fmt_age(age)}."
        elif effective in ("bad", "down"):
            err = _fm_sanitize_error((tgt.get("lastError") or {}).get("error") or "")
            sub = f"Endpoint disrupted. Last successful probe {_fm_fmt_age(age)}."
            if err:
                sub += f"  •  {err}"
        else:
            sub = "Awaiting probes…"
        self.lbl_status_sub.setText(sub)

    def _apply_hero_latency(self, last_hour_lats):
        if last_hour_lats:
            last_hour_lats.sort()
            n = len(last_hour_lats)
            def pct(p):
                if n == 1:
                    return last_hour_lats[0]
                idx = max(0, min(n - 1, int(round((p / 100) * (n - 1)))))
                return last_hour_lats[idx]
            self.lbl_lat_big.setText(_fm_fmt_ms(pct(50)))
            self.lbl_lat_meta.setText(
                f"p10 <b style='color:{_FM_COLORS['ink_soft']};'>{_fm_fmt_ms(pct(10))}</b>"
                f"   p90 <b style='color:{_FM_COLORS['ink_soft']};'>{_fm_fmt_ms(pct(90))}</b>"
                f"   p99 <b style='color:{_FM_COLORS['ink_soft']};'>{_fm_fmt_ms(pct(99))}</b>"
            )
        else:
            self.lbl_lat_big.setText("—")
            self.lbl_lat_meta.setText("p10 — · p90 — · p99 —")

    def _update_mode_bar(self, data):
        mode = str(data.get("mode") or "").lower()
        cadence_ms = data.get("cadenceMs") or 0
        cadence_min = max(1, int(round(cadence_ms / 60000))) if cadence_ms else 0
        mode_color = {
            "healthy": _FM_COLORS["ok"],
            "rapid": _FM_COLORS["warn"],
            "confirming": _FM_COLORS["warn"],
        }.get(mode, _FM_COLORS["ink_soft"])
        mode_text = f"{mode or '—'}  •  probing every {cadence_min}m" if cadence_min else (mode or "—")
        self.lbl_mode.setText(mode_text)
        self.lbl_mode.setStyleSheet(f"color: {mode_color}; background: transparent;")
        self.mode_dot.set_color(mode_color)

    # ─── Менеджмент scope-views ────────────────────────────────────
    def _rebuild_scope_layout(self, desired):
        """desired — список (key, compact_flag) в порядке отображения.
        Пересоздаёт виджеты только если ключ новый или поменялся compact-флаг.
        Все лишние сносит. В контейнере раскладывает в заданном порядке."""
        desired_keys = [k for k, _ in desired]

        # Создать/пересоздать view'и, где нужно
        for key, compact in desired:
            existing = self._scope_views.get(key)
            if existing is None or existing._compact != compact:
                if existing is not None:
                    existing.setParent(None)
                    existing.deleteLater()
                self._scope_views[key] = _FmScopeView(compact=compact)

        # Снести лишние
        for key in list(self._scope_views.keys()):
            if key not in desired_keys:
                view = self._scope_views.pop(key)
                view.setParent(None)
                view.deleteLater()

        # Пере-выложить контейнер
        while self.scope_container.count():
            item = self.scope_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        for key, _ in desired:
            view = self._scope_views[key]
            view.setParent(self.probes_frame)
            self.scope_container.addWidget(view, 1)
            view.show()

    def _on_scope_changed(self, key):
        self._scope_mode = key
        if self._last_data is not None:
            self._apply_data(self._last_data)

    def _apply_failure(self):
        if self._last_data is None:
            self.lbl_status_word.setText(tr("Нет связи"))
            self.lbl_status_word.setStyleSheet(
                f"color: {_FM_COLORS['ink_muted']}; background: transparent;"
            )
            self.lbl_status_sub.setText(tr(
                "Не удалось получить /api/status. Повторим через несколько секунд."
            ))

    def _update_countdown(self):
        if not self._next_check_at_ms:
            self.lbl_next_check.setText("next check in —")
            return
        now_ms = int(time.time() * 1000)
        remaining = self._next_check_at_ms - now_ms
        self.lbl_next_check.setText(
            f'<span style="color:{_FM_COLORS["ink_muted"]};">next check in </span>'
            f'<span style="color:{_FM_COLORS["ink"]};">{_fm_fmt_eta(remaining)}</span>'
        )

    def closeEvent(self, event):
        self._stop = True
        try:
            self._tick_timer.stop()
        except Exception:
            pass
        super().closeEvent(event)

# ============================================================
# ИНДИКАТОР ОБНОВЛЕНИЯ (ГОЛУБАЯ ПУЛЬСИРУЮЩАЯ ТОЧКА)
# ============================================================

class UpdateIndicator(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)
        self._scale = 1.0
        self._target_scale = 1.0
        self._press_scale = 1.0
        self._is_hovered = False

        self._scale_timer = QTimer()
        self._scale_timer.timeout.connect(self._animate_scale)
        self._scale_timer.start(16)

        self.setVisible(False)

        # Загружаем синюю SVG
        base_dir = os.path.dirname(os.path.abspath(__file__))
        svg_path = os.path.join(base_dir, "icon-download-blue.svg")

        # Если не нашли, пробуем текущую директорию
        if not os.path.exists(svg_path):
            svg_path = "icon-download-blue.svg"

        self._svg_renderer = QSvgRenderer(svg_path)
        self._icon_valid = self._svg_renderer.isValid()

    def _animate_scale(self):
        diff = self._target_scale - self._scale
        if abs(diff) > 0.01:
            self._scale += diff * 0.15
            self.update()

        # Анимация нажатия
        press_diff = 1.0 - self._press_scale
        if abs(press_diff) > 0.01:
            self._press_scale += press_diff * 0.2
            self.update()

    def enterEvent(self, event):
        self._target_scale = 1.15
        self._is_hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._target_scale = 1.0
        self._is_hovered = False
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()

        # Вычисляем размер с учетом масштаба
        total_scale = self._scale * self._press_scale
        base_size = min(w, h) * 0.75
        scaled_size = base_size * total_scale
        offset = (w - scaled_size) / 2

        # Рисуем SVG
        if self._icon_valid:
            self._svg_renderer.render(painter, QRectF(offset, offset, scaled_size, scaled_size))
        else:
            # Fallback - синяя точка
            painter.setBrush(QColor(100, 180, 255))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(w/2, h/2), 8 * total_scale, 8 * total_scale)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_scale = 0.9
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._press_scale = 1.0
        super().mouseReleaseEvent(event)

        if self._is_active:
            # Зеле  ое свечение с плавной пульсацией (уменьшил радиус)
            glow_radius = 5.0 + 2.5 * pulse
            glow_alpha = int(60 * pulse)
            painter.setBrush(QColor(0, 255, 100, glow_alpha))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center, glow_radius, glow_radius)

            # Основная точка с плавной пульсацией яркости
            brightness = int(180 + 75 * pulse)
            painter.setBrush(QColor(0, brightness, int(brightness * 0.4)))
            painter.drawEllipse(center, 4.5, 4.5)
        else:
            # Красная точка с плавной пульсацией
            glow_radius = 5.0 + 2.5 * pulse
            glow_alpha = int(50 * pulse)
            painter.setBrush(QColor(255, 50, 50, glow_alpha))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center, glow_radius, glow_radius)

            # Основная красная точка с пульсацией яркости
            brightness = int(180 + 75 * pulse)
            painter.setBrush(QColor(brightness, 50, 50))
            painter.drawEllipse(center, 4.5, 4.5)

# ============================================================
# КНОПКА С ЭФФЕКТОМ НАВЕДЕНИЯ
# ============================================================

class StyledButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self._hover_progress = 0.0
        self._hover_color = (60, 140, 200)  # default — голубой
        self._hover_timer = QTimer()
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.start(20)
        self._is_hovered = False
        self.setMouseTracking(True)
        self._update_style()

    def set_hover_color(self, r, g, b):
        self._hover_color = (r, g, b)
        self._update_style()

    def enterEvent(self, event):
        self._is_hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        super().leaveEvent(event)

    def _animate_hover(self):
        if self._is_hovered and self.isEnabled():
            if self._hover_progress < 1.0:
                self._hover_progress = min(1.0, self._hover_progress + 0.1)
                self._update_style()
        else:
            if self._hover_progress > 0.0:
                self._hover_progress = max(0.0, self._hover_progress - 0.1)
                self._update_style()

    def _update_style(self):
        base_r, base_g, base_b = 60, 60, 65
        hover_r, hover_g, hover_b = self._hover_color

        r = int(base_r + (hover_r - base_r) * self._hover_progress)
        g = int(base_g + (hover_g - base_g) * self._hover_progress)
        b = int(base_b + (hover_b - base_b) * self._hover_progress)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(40, 40, 45, 200);
                color: rgb(200, 200, 200);
                border: 2px solid rgb({r}, {g}, {b});
                border-radius: 6px;
                padding: 8px;
            }}
            QPushButton:pressed {{
                background-color: rgba(30, 30, 35, 200);
            }}
            QPushButton:disabled {{
                background-color: rgba(30, 30, 35, 150);
                color: rgb(100, 100, 100);
                border: 2px solid rgb(40, 40, 45);
            }}
        """)

# ============================================================
# КНОПКА С ЗЕЛЕНЫМ ЭФФЕКТОМ (ДЛЯ ЗАПУСКА)
# ============================================================

class GreenButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self._hover_progress = 0.0
        self._hover_timer = QTimer()
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.start(20)
        self._is_hovered = False
        self.setMouseTracking(True)
        self._update_style()
        self.ensurePolished()

    def enterEvent(self, event):
        self._is_hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        super().leaveEvent(event)

    def _animate_hover(self):
        if self._is_hovered and self.isEnabled():
            if self._hover_progress < 1.0:
                self._hover_progress = min(1.0, self._hover_progress + 0.1)
                self._update_style()
        else:
            if self._hover_progress > 0.0:
                self._hover_progress = max(0.0, self._hover_progress - 0.1)
                self._update_style()

    def _update_style(self):
        base_r, base_g, base_b = 60, 60, 65
        hover_r, hover_g, hover_b = 50, 180, 100

        r = int(base_r + (hover_r - base_r) * self._hover_progress)
        g = int(base_g + (hover_g - base_g) * self._hover_progress)
        b = int(base_b + (hover_b - base_b) * self._hover_progress)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(40, 40, 45, 200);
                color: rgb(200, 200, 200);
                border: 2px solid rgb({r}, {g}, {b});
                border-radius: 6px;
                padding: 8px;
            }}
            QPushButton:pressed {{
                background-color: rgba(30, 30, 35, 200);
            }}
            QPushButton:disabled {{
                background-color: rgba(30, 30, 35, 150);
                color: rgb(100, 100, 100);
                border: 2px solid rgb(40, 40, 45);
            }}
        """)

# ============================================================
# КНОПКА С ГОЛУБЫМ ЭФФЕКТОМ (ДЛЯ ОБНОВЛЕНИЯ)
# ============================================================

class BlueButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self._hover_progress = 0.0
        self._hover_timer = QTimer()
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.start(20)
        self._is_hovered = False
        self.setMouseTracking(True)
        self._update_style()
        self.ensurePolished()

    def enterEvent(self, event):
        self._is_hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        super().leaveEvent(event)

    def _animate_hover(self):
        if self._is_hovered and self.isEnabled():
            if self._hover_progress < 1.0:
                self._hover_progress = min(1.0, self._hover_progress + 0.1)
                self._update_style()
        else:
            if self._hover_progress > 0.0:
                self._hover_progress = max(0.0, self._hover_progress - 0.1)
                self._update_style()

    def _update_style(self):
        base_r, base_g, base_b = 60, 60, 65
        hover_r, hover_g, hover_b = 100, 180, 255

        r = int(base_r + (hover_r - base_r) * self._hover_progress)
        g = int(base_g + (hover_g - base_g) * self._hover_progress)
        b = int(base_b + (hover_b - base_b) * self._hover_progress)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(40, 40, 45, 200);
                color: rgb(200, 200, 200);
                border: 2px solid rgb({r}, {g}, {b});
                border-radius: 6px;
                padding: 8px;
            }}
            QPushButton:pressed {{
                background-color: rgba(30, 30, 35, 200);
            }}
            QPushButton:disabled {{
                background-color: rgba(30, 30, 35, 150);
                color: rgb(100, 100, 100);
                border: 2px solid rgb(40, 40, 45);
            }}
        """)

# ============================================================
# КНОПКА С КРАСНЫМ ЭФФЕКТОМ (ДЛЯ УДАЛЕНИЯ)
# ============================================================

class RedButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self._hover_progress = 0.0
        self._hover_timer = QTimer()
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.start(20)
        self._is_hovered = False
        self.setMouseTracking(True)
        self._update_style()
        self.ensurePolished()

    def enterEvent(self, event):
        self._is_hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        super().leaveEvent(event)

    def _animate_hover(self):
        if self._is_hovered and self.isEnabled():
            if self._hover_progress < 1.0:
                self._hover_progress = min(1.0, self._hover_progress + 0.1)
                self._update_style()
        else:
            if self._hover_progress > 0.0:
                self._hover_progress = max(0.0, self._hover_progress - 0.1)
                self._update_style()

    def _update_style(self):
        base_r, base_g, base_b = 60, 60, 65
        hover_r, hover_g, hover_b = 200, 60, 60

        r = int(base_r + (hover_r - base_r) * self._hover_progress)
        g = int(base_g + (hover_g - base_g) * self._hover_progress)
        b = int(base_b + (hover_b - base_b) * self._hover_progress)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(40, 40, 45, 200);
                color: rgb(200, 200, 200);
                border: 2px solid rgb({r}, {g}, {b});
                border-radius: 6px;
                padding: 8px;
            }}
            QPushButton:pressed {{
                background-color: rgba(30, 30, 35, 200);
            }}
            QPushButton:disabled {{
                background-color: rgba(30, 30, 35, 150);
                color: rgb(100, 100, 100);
                border: 2px solid rgb(40, 40, 45);
            }}
        """)

# Lucide-style eye icons — мягкие, симметричные, не растянутые.
# {C} подменяется на текущий цвет (hex) перед рендером.
_LUCIDE_EYE_OPEN = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{C}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/>'
    '<circle cx="12" cy="12" r="3"/>'
    '</svg>'
)
_LUCIDE_EYE_OFF = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{C}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>'
    '<path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/>'
    '<path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/>'
    '<line x1="2" y1="2" x2="22" y2="22"/>'
    '</svg>'
)

class EyeToggleButton(QPushButton):
    """Кнопка-глаз для скрытия/показа значения поля ввода.

    Иконка — Lucide eye / eye-off, ренденится через QSvgRenderer:
    выглядит гораздо мягче и аккуратнее, чем рисованный QPainter-овал.
    Рамка 2px, hover плавно подсвечивается голубым, как у StyledButton.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setText("")
        self.setFixedSize(40, 36)
        self._revealed = False
        self._hover_progress = 0.0
        self._is_hovered = False
        self.setMouseTracking(True)
        self._hover_timer = QTimer(self)
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.start(20)

    def setRevealed(self, revealed: bool):
        if self._revealed != bool(revealed):
            self._revealed = bool(revealed)
            self.update()

    def isRevealed(self) -> bool:
        return self._revealed

    def enterEvent(self, e):
        self._is_hovered = True
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._is_hovered = False
        super().leaveEvent(e)

    def _animate_hover(self):
        target = 1.0 if (self._is_hovered and self.isEnabled()) else 0.0
        if self._hover_progress != target:
            step = 0.1 if target > self._hover_progress else -0.1
            self._hover_progress = max(0.0, min(1.0, self._hover_progress + step))
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = self._hover_progress

        # Рамка 2px, при hover плавно уходит в голубой
        base = (60, 60, 65)
        hover = (100, 180, 255)
        r = int(base[0] + (hover[0] - base[0]) * t)
        g = int(base[1] + (hover[1] - base[1]) * t)
        b = int(base[2] + (hover[2] - base[2]) * t)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(40, 40, 45, 200))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 6, 6)

        pen = QPen(QColor(r, g, b))
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(1, 1, w - 2, h - 2, 6, 6)

        # SVG-глаз: светло-серый, ярче при hover
        eye_bright = int(170 + 60 * t)
        color_hex = f"#{eye_bright:02x}{eye_bright:02x}{eye_bright:02x}"

        svg_template = _LUCIDE_EYE_OPEN if self._revealed else _LUCIDE_EYE_OFF
        svg_bytes = svg_template.format(C=color_hex).encode("utf-8")
        renderer = QSvgRenderer(svg_bytes)

        # Иконка 16×16 в центре кнопки — компактно, не растянуто
        icon_size = 16
        icon_x = (w - icon_size) / 2.0
        icon_y = (h - icon_size) / 2.0
        renderer.render(p, QRectF(icon_x, icon_y, icon_size, icon_size))

        p.end()

class StyledComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 10))
        self._hover_progress = 0.0
        self._hover_timer = QTimer()
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.start(20)
        self._is_hovered = False
        self._text_color = "rgb(200, 200, 200)"
        self._accent_color = None  # (r,g,b) — если задан, рамка всегда окрашена в этот цвет
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        # Колесо мыши НЕ должно перебирать пункты, когда юзер просто наводит курсор
        # на комбобокс и крутит скролл главного окна — иначе случайно меняется модель/URL/effort.
        # Поставим политику фокуса StrongFocus, чтобы комбо не реагировал на wheel без клика.
        self.setFocusPolicy(Qt.StrongFocus)

        self.setStyleSheet("""
            QComboBox {
                background-color: rgba(40, 40, 45, 200);
                color: %s;
                border: 2px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 6px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: rgb(30, 30, 35);
                color: rgb(200, 200, 200);
                selection-background-color: rgb(50, 50, 55);
            }
            QComboBox QAbstractItemView::item {
                min-height: 30px;
            }
            QComboBox QAbstractItemView QScrollBar:vertical {
                width: 8px;
                background: rgba(20, 20, 25, 200);
                border-radius: 4px;
            }
            QComboBox QAbstractItemView QScrollBar::handle:vertical {
                background: rgba(80, 200, 255, 150);
                border-radius: 4px;
            }
            QComboBox QAbstractItemView QScrollBar::handle:vertical:hover {
                background: rgba(80, 200, 255, 200);
            }
        """ % self._text_color)

    def wheelEvent(self, event):
        # Игнорируем колесо мыши, чтобы случайный скролл не менял выбранный пункт.
        # event.ignore() пробрасывает событие дальше — родительский ScrollArea/окно
        # сможет проскроллиться нормально.
        event.ignore()

    def enterEvent(self, event):
        self._is_hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        super().leaveEvent(event)

    def _animate_hover(self):
        if self._is_hovered:
            if self._hover_progress < 1.0:
                self._hover_progress = min(1.0, self._hover_progress + 0.1)
                self._update_style()
        else:
            if self._hover_progress > 0.0:
                self._hover_progress = max(0.0, self._hover_progress - 0.1)
                self._update_style()

    def _update_style(self):
        if self._accent_color is not None:
            # Рамка всегда в цвете акцента (тусклая), при наведении — ярче
            ar, ag, ab = self._accent_color
            dim = 0.45
            base_r, base_g, base_b = int(ar * dim), int(ag * dim), int(ab * dim)
            hover_r, hover_g, hover_b = ar, ag, ab
        else:
            # Поведение по умолчанию: серый → голубой
            base_r, base_g, base_b = 60, 60, 65
            hover_r, hover_g, hover_b = 60, 140, 200

        r = int(base_r + (hover_r - base_r) * self._hover_progress)
        g = int(base_g + (hover_g - base_g) * self._hover_progress)
        b = int(base_b + (hover_b - base_b) * self._hover_progress)

        self.setStyleSheet(f"""
            QComboBox {{
                background-color: rgba(40, 40, 45, 200);
                color: {self._text_color};
                border: 2px solid rgb({r}, {g}, {b});
                border-radius: 4px;
                padding: 6px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: rgb(30, 30, 35);
                color: rgb(200, 200, 200);
                selection-background-color: rgb(50, 50, 55);
            }}
        """)

    def setAccentColor(self, color):
        """Установить акцентный цвет рамки (обычно цвет модели). None — вернуть дефолт."""
        if color is None:
            self._accent_color = None
        elif isinstance(color, QColor):
            self._accent_color = (color.red(), color.green(), color.blue())
        else:
            self._accent_color = color
        self._update_style()

    def setTextColor(self, color):
        """Установить цвет отображаемого текста (для свёрнутого состояния)."""
        if isinstance(color, QColor):
            self._text_color = f"rgb({color.red()}, {color.green()}, {color.blue()})"
        else:
            self._text_color = color
        self._update_style()


# ============================================================
# КАСТОМНЫЙ ПИКЕР: МОДАЛЬНОЕ ОКНО С КАРТОЧКАМИ ВМЕСТО DROPDOWN
# ============================================================

class PickerCard(QPushButton):
    """Одна карточка-виджет в окне выбора."""

    def __init__(self, text, color=None, tooltip=None, is_current=False,
                 is_disabled=False, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 10, QFont.Medium))
        self.setMinimumHeight(42)
        self._full_text = text
        self._is_disabled = is_disabled
        # Тултип показываем только если явно передан (нужен для длинных URL).
        # У пикера моделей tooltip=None — всплывашек быть не должно.
        if tooltip:
            self.setToolTip(tooltip)
        # Запретить кнопке растягиваться по ширине текста — иначе длинный URL раздует layout
        # и elide перестанет срабатывать на коротких карточках
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        # Цвет текста и целевой цвет рамки — под модель.
        # Если цвета нет (например, у URL) — рамка голубая по умолчанию.
        if color is not None:
            if is_disabled:
                # Затемняем цвет, но оставляем красный оттенок различимым
                r = int(color.red() * 0.55)
                g = int(color.green() * 0.55)
                b = int(color.blue() * 0.55)
                self._text_color_str = f"rgb({r}, {g}, {b})"
                self._hover_rgb = (r, g, b)
            else:
                self._text_color_str = f"rgb({color.red()}, {color.green()}, {color.blue()})"
                self._hover_rgb = (color.red(), color.green(), color.blue())
        else:
            self._text_color_str = "rgb(220, 220, 220)"
            self._hover_rgb = (60, 140, 200)

        # Постоянный фон одинаков для всех карточек; у заблокированной — темнее
        if is_disabled:
            self._bg_str = "rgba(28, 24, 26, 200)"
        else:
            self._bg_str = "rgba(40, 40, 45, 180)"

        self._is_current = is_current
        # Анимация только рамки
        self._hover_progress = 1.0 if is_current else 0.0
        self._is_hovered = False
        self._hover_timer = QTimer(self)
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.start(16)
        self._update_style()

    def enterEvent(self, event):
        self._is_hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        super().leaveEvent(event)

    def _animate_hover(self):
        target = 1.0 if (self._is_hovered or self._is_current) else 0.0
        if abs(self._hover_progress - target) < 0.005:
            return
        # Плавно — около 200мс к цели
        step = 0.08
        if self._hover_progress < target:
            self._hover_progress = min(target, self._hover_progress + step)
        else:
            self._hover_progress = max(target, self._hover_progress - step)
        self._update_style()

    def _update_style(self):
        base_r, base_g, base_b = 60, 60, 65
        hov_r, hov_g, hov_b = self._hover_rgb
        p = self._hover_progress
        r = int(base_r + (hov_r - base_r) * p)
        g = int(base_g + (hov_g - base_g) * p)
        b = int(base_b + (hov_b - base_b) * p)
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: center;
                background-color: {self._bg_str};
                color: {self._text_color_str};
                border: 2px solid rgb({r}, {g}, {b});
                border-radius: 8px;
                padding: 7px 10px;
            }}
            QPushButton:pressed {{
                background-color: {self._bg_str};
            }}
        """)

    def sizeHint(self):
        # Не зависим от длины текста по горизонтали
        return QSize(0, max(42, super().sizeHint().height()))

    def minimumSizeHint(self):
        return QSize(0, max(42, super().minimumSizeHint().height()))

    def _update_elided_text(self):
        fm = QFontMetrics(self.font())
        # Доступная ширина = ширина кнопки минус padding 10+10 и небольшой запас
        avail = max(0, self.width() - 24)
        if avail <= 0:
            return
        elided = fm.elidedText(self._full_text, Qt.ElideRight, avail)
        if elided != self.text():
            super().setText(elided)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_text()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_elided_text()


class PickerDialog(QDialog):
    """Окно выбора со списком карточек (popup, не блокирующее)."""

    picked = Signal(str)
    blockedPicked = Signal(str)

    def __init__(self, items, current, parent=None, item_colors=None,
                 item_tooltips=None, title="Выбор", disabled_items=None):
        super().__init__(parent)
        # Dialog + WindowModal — блокирует родительское окно, не закрывается при клике вне
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowModality(Qt.ApplicationModal)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        self.container = DottedFrame()
        self.container.setObjectName("pickerContainer")
        self.container.setStyleSheet("""
            QFrame#pickerContainer {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgba(110, 110, 120, 0.7);
                border-radius: 14px;
            }
        """)
        outer.addWidget(self.container)

        # Тень на контейнере
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 6)
        self.container.setGraphicsEffect(shadow)

        inner = QVBoxLayout(self.container)
        inner.setSpacing(8)
        inner.setContentsMargins(16, 14, 16, 16)

        # Заголовок + крестик
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title_lbl.setStyleSheet("color: rgb(200, 200, 210); border: none; background: transparent;")
        head.addWidget(title_lbl)
        head.addStretch()
        close_btn = _CloseButton(parent=self.container)
        close_btn.setFixedSize(26, 26)
        close_btn.clicked.connect(self.close)
        head.addWidget(close_btn)
        inner.addLayout(head)

        # Прокручиваемая область — ровно 4 карточки
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                width: 4px;
                background: transparent;
                border-radius: 2px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(140, 140, 145, 160);
                border-radius: 2px;
                min-height: 28px;
            }
            QScrollBar::handle:vertical:hover { background: rgba(170, 170, 175, 200); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cards_layout = QVBoxLayout(content)
        cards_layout.setSpacing(8)
        cards_layout.setContentsMargins(2, 2, 6, 2)

        colors = item_colors or {}
        tooltips = item_tooltips or {}
        disabled = set(disabled_items or ())
        self._disabled_items = disabled

        for item in items:
            card = PickerCard(
                item,
                color=colors.get(item),
                tooltip=tooltips.get(item),
                is_current=(item == current),
                is_disabled=(item in disabled),
            )
            card.clicked.connect(lambda _checked=False, v=item: self._pick(v))
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(content)
        scroll.setFixedHeight(200)  # 4 × 41 + 3 × 8
        inner.addWidget(scroll, 0)

        self.setFixedWidth(300)
        self.adjustSize()

        # Плавное появление через windowOpacity (без QGraphicsOpacityEffect на самом окне —
        # на Windows + WA_TranslucentBackground оно тормозит / зависает)
        self.setWindowOpacity(0.0)
        self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in.setDuration(220)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self._closing = False

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_in.start()

    def closeEvent(self, event):
        if self._closing:
            super().closeEvent(event)
            return
        self._closing = True
        event.ignore()
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(220)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(self.close)
        fade.start()
        self._fade_out = fade

    def _pick(self, value):
        if value in getattr(self, "_disabled_items", set()):
            self.blockedPicked.emit(value)
            self.close()
            return
        self.picked.emit(value)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)


class PickerComboBox(StyledComboBox):
    """ComboBox, который при клике открывает PickerDialog вместо нативного списка."""

    blockedPicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pick_colors = {}
        self._pick_tooltips = {}
        self._pick_title = "Выбор"
        self._pick_disabled = set()
        self._picker_dlg = None

    def set_picker(self, colors=None, tooltips=None, title=None, disabled=None):
        if colors is not None:
            self._pick_colors = colors
        if tooltips is not None:
            self._pick_tooltips = tooltips
        if title:
            self._pick_title = title
        if disabled is not None:
            self._pick_disabled = set(disabled)

    def showPopup(self):
        # Если уже открыт — игнорируем повторный вызов
        if self._picker_dlg is not None:
            return
        items = [self.itemText(i) for i in range(self.count())]
        if not items:
            return
        # Если для конкретного combo тултипы не заданы вручную — подставляем
        # полный текст элемента (нужно для длинных URL).
        tooltips = self._pick_tooltips
        if not tooltips and self._pick_title == "Выбор Base URL":
            tooltips = {item: item for item in items}
        dlg = PickerDialog(
            items,
            current=self.currentText(),
            parent=self.window(),
            item_colors=self._pick_colors,
            item_tooltips=tooltips,
            title=self._pick_title,
            disabled_items=self._pick_disabled,
        )
        dlg.picked.connect(self._on_picked)
        dlg.blockedPicked.connect(self.blockedPicked)
        dlg.destroyed.connect(self._on_picker_destroyed)
        self._picker_dlg = dlg

        def _show_and_position():
            dlg.show()
            dlg.adjustSize()
            dw = dlg.width()
            dh = dlg.height()
            parent_win = self.window()
            try:
                if parent_win is not None:
                    pg = parent_win.frameGeometry()
                    center = pg.center()
                    x = center.x() - dw // 2 - 2
                    y = center.y() - dh // 2
                else:
                    from PySide6.QtGui import QGuiApplication
                    screen = QGuiApplication.primaryScreen().availableGeometry()
                    x = screen.x() + (screen.width() - dw) // 2
                    y = screen.y() + (screen.height() - dh) // 2
                dlg.move(x, y)
            except Exception:
                pass

        QTimer.singleShot(0, _show_and_position)

    def hidePopup(self):
        # Нативный popup не используется
        pass

    def _on_picker_destroyed(self):
        self._picker_dlg = None

    def _on_picked(self, value):
        if value and value != self.currentText():
            self.setCurrentText(value)


# ============================================================
# МОДЕЛЬ ДЛЯ КОМБОБОКСА С КАСТОМНЫМИ ЦВЕТАМИ
# ============================================================

class ModelListModel(QAbstractListModel):
    def __init__(self, models, parent=None):
        super().__init__(parent)
        self._models = models

    def rowCount(self, parent=QModelIndex()):
        return len(self._models)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        model_name = self._models[index.row()]

        if role == Qt.DisplayRole:
            return model_name
        elif role == Qt.BackgroundRole:
            # Базовая модель - темный фон
            if model_name == "kr/claude-sonnet-4.5":
                return QColor(20, 20, 25)
            else:
                return QColor(30, 30, 35)
        elif role == Qt.ForegroundRole:
            return QColor(200, 200, 200)

        return None

    def update_models(self, models):
        self.beginResetModel()
        self._models = models
        self.endResetModel()

# ============================================================
# ДИАЛОГ ДОБАВЛЕНИЯ МОДЕЛИ
# ============================================================

class AddModelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setObjectName("addModelContainer")
        container.setStyleSheet("""
            QFrame#addModelContainer {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        # Заголовок
        title = QLabel(tr("Добавить модель"))
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #CCCCCC; background: transparent; border: none;")
        layout.addWidget(title)

        label = QLabel(tr("Введите название модели:"))
        label.setFont(QFont("Segoe UI", 11))
        label.setStyleSheet("color: rgb(180, 180, 180); background: transparent; border: none;")
        layout.addWidget(label)

        self.input = QLineEdit()
        self.input.setPlaceholderText(tr("Например: kr/claude-sonnet-4.5"))
        self.input.setFont(QFont("Segoe UI", 10))
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 35, 200);
                color: rgb(200, 200, 200);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 6px;
                padding: 10px;
            }
            QLineEdit:focus {
                border: 2px solid rgb(80, 80, 85);
            }
        """)
        layout.addWidget(self.input)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_cancel = RedButton(tr("Отмена"))
        btn_cancel.setMinimumHeight(40)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = GreenButton(tr("Добавить"))
        btn_ok.setMinimumHeight(40)
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedSize(400, 240)

        # Анимация появления
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        """Плавное закрытие при принятии"""
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(AddModelDialog, self).accept())
        fade.start()
        self._fade = fade

    def reject(self):
        """Плавное закрытие при отмене"""
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(AddModelDialog, self).reject())
        fade.start()
        self._fade = fade

    def get_model_name(self):
        return self.input.text().strip()

# ============================================================
# ДИАЛОГ ПОДТВЕРЖДЕНИЯ УДАЛЕНИЯ
# ============================================================

class ConfirmDeleteDialog(QDialog):
    def __init__(self, model_name, parent=None, question_text=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setObjectName("confirmDeleteContainer")
        container.setStyleSheet("""
            QFrame#confirmDeleteContainer {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        # Иконка предупреждения
        warning_label = QLabel("⚠")
        warning_label.setFont(QFont("Segoe UI", 32))
        warning_label.setStyleSheet("""
            QLabel {
                color: rgb(255, 170, 0);
                background: transparent;
                border: none;
            }
        """)
        warning_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(warning_label)

        # Текст вопроса
        question_label = QLabel(question_text if question_text else "Вы уверены, что хотите удалить модель?")
        question_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        question_label.setStyleSheet("color: #CCCCCC; background: transparent; border: none;")
        question_label.setAlignment(Qt.AlignCenter)
        question_label.setWordWrap(True)
        layout.addWidget(question_label)

        # Название модели
        model_label = QLabel(model_name)
        model_label.setFont(QFont("Segoe UI", 11))
        model_label.setStyleSheet("""
            QLabel {
                color: #E0E0E0;
                background: rgba(100, 100, 105, 0.1);
                border: 1.5px solid rgba(100, 100, 105, 0.4);
                border-radius: 8px;
                padding: 8px 12px;
            }
        """)
        model_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(model_label)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_no = GreenButton("Отмена")
        btn_no.setMinimumHeight(40)
        btn_no.clicked.connect(self.reject)
        btn_layout.addWidget(btn_no)

        btn_yes = RedButton("Да, удалить")
        btn_yes.setMinimumHeight(40)
        btn_yes.clicked.connect(self.accept)
        btn_layout.addWidget(btn_yes)

        layout.addLayout(btn_layout)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedSize(400, 280)

        # Анимация появления
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        """Плавное закрытие при принятии"""
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(ConfirmDeleteDialog, self).accept())
        fade.start()
        self._fade = fade

    def reject(self):
        """Плавное закрытие при отмене"""
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(ConfirmDeleteDialog, self).reject())
        fade.start()
        self._fade = fade

# ============================================================
# ПРЕДУПРЕЖДЕНИЕ О МОДЕЛИ FABLE 5
# ============================================================

class Fable5WarningDialog(QDialog):
    """Сообщение о блокировке модели Fable 5 правительством США."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowModality(Qt.ApplicationModal)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName("fable5Container")
        container.setStyleSheet("""
            QFrame#fable5Container {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(28, 12, 12, 0.99),
                    stop:1 rgba(20, 8, 8, 0.99));
                border: 2px solid rgba(235, 60, 60, 0.75);
                border-radius: 18px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(12)

        # Верхняя плашка-заголовок
        top_banner = QLabel(tr("Fable 5 временно недоступна"))
        top_banner.setFont(QFont("Segoe UI", 10, QFont.Bold))
        top_banner.setStyleSheet("""
            QLabel {
                color: rgb(255, 220, 220);
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(180, 30, 30, 0.55),
                    stop:1 rgba(140, 20, 20, 0.55));
                border: 1px solid rgba(255, 100, 100, 0.45);
                border-radius: 8px;
                padding: 7px 12px;
                letter-spacing: 0.5px;
            }
        """)
        top_banner.setAlignment(Qt.AlignCenter)
        layout.addWidget(top_banner)

        # Иконка — замок
        icon_label = QLabel("🔒")
        icon_label.setFont(QFont("Segoe UI Emoji", 38))
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Главный заголовок
        title_label = QLabel(tr("Модель заблокирована\nправительством США"))
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: rgb(245, 95, 95);
                background: transparent;
                border: none;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: rgba(235, 60, 60, 0.3); background: rgba(235, 60, 60, 0.3); border: none; max-height: 1px;")
        layout.addWidget(sep)

        # Основное описание
        desc_label = QLabel(tr(
            "По официальному заявлению правительства США, доступ\n"
            "к модели Fable 5 временно приостановлен на территории\n"
            "всех юрисдикций.\n\n"
            "Согласно решению, Fable 5 признана настолько мощной,\n"
            "что — по словам представителей правительства — способна\n"
            "  зломать защищённые системы Пентагона. На этом основании\n"
            "модель отнесена к технологиям двойного назначения\n"
            "и временно изъята из публичного оборота.\n\n"
            "Доступ будет восстановлен после завершения проверки\n"
            "и установки регулирующих ограничений Anthropic."
        ))
        desc_label.setFont(QFont("Segoe UI", 10))
        desc_label.setStyleSheet("""
            QLabel {
                color: rgba(225, 205, 205, 0.92);
                background: transparent;
                border: none;
            }
        """)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Плашка-источник
        source_label = QLabel(tr("Источник: официальное заявление правительства США"))
        source_label.setFont(QFont("Segoe UI", 9))
        source_label.setStyleSheet("""
            QLabel {
                color: rgba(235, 90, 90, 0.85);
                background: rgba(235, 60, 60, 0.1);
                border: 1px solid rgba(235, 60, 60, 0.28);
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        source_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(source_label)

        layout.addSpacing(4)

        # Кнопка OK — не на всю ширину, по центру
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_ok = GlowDialogButton(tr("Понятно"),
                                  base_rgb=(235, 70, 70),
                                  hover_rgb=(245, 100, 100))
        btn_ok.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedWidth(450)

        # Анимация появления через windowOpacity (не конфликтует с дочерними виджетами)
        self.setWindowOpacity(0.0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(Fable5WarningDialog, self).accept())
        fade.start()
        self._fade = fade

    def reject(self):
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(Fable5WarningDialog, self).reject())
        fade.start()
        self._fade = fade


# ============================================================
# ОКНО-ПРЕДУПРЕЖДЕНИЕ «НЕТ ПРАВ АДМИНИСТРАТОРА»
# ============================================================

class AdminWarningDialog(QDialog):
    """Показывается при запуске, если приложение запущено БЕЗ прав админа.

    Цель — заранее предупредить пользователя: часть операций (удаление CLI,
    запись в %ProgramFiles%, чистка залоченных файлов) требует админ-прав
    и без них может падать с PermissionDenied.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowModality(Qt.ApplicationModal)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName("adminWarnContainer")
        container.setStyleSheet("""
            QFrame#adminWarnContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(30, 24, 14, 0.99),
                    stop:1 rgba(22, 18, 10, 0.99));
                border: 2px solid rgba(245, 196, 74, 0.7);
                border-radius: 18px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(12)

        # Верхняя плашка-заголовок
        top_banner = QLabel(tr("Запуск без прав администратора"))
        top_banner.setFont(QFont("Segoe UI", 10, QFont.Bold))
        top_banner.setStyleSheet("""
            QLabel {
                color: rgb(255, 235, 190);
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(170, 120, 30, 0.55),
                    stop:1 rgba(130, 90, 20, 0.55));
                border: 1px solid rgba(245, 196, 74, 0.45);
                border-radius: 8px;
                padding: 7px 12px;
                letter-spacing: 0.5px;
            }
        """)
        top_banner.setAlignment(Qt.AlignCenter)
        layout.addWidget(top_banner)

        # Иконка — щит с восклицательным знаком
        icon_label = QLabel("🛡")
        icon_label.setFont(QFont("Segoe UI Emoji", 38))
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Главный заголовок
        title_label = QLabel(tr("Рекомендуется запустить\nот имени администратора"))
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: rgb(245, 196, 74);
                background: transparent;
                border: none;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(
            "color: rgba(245, 196, 74, 0.3); "
            "background: rgba(245, 196, 74, 0.3); "
            "border: none; max-height: 1px;"
        )
        layout.addWidget(sep)

        # Основное описание
        desc_label = QLabel(tr(
            "Сейчас приложение работает в обычном режиме и часть\n"
            "операций может завершаться ошибкой PermissionDenied.\n\n"
            "Без админ-прав могут не сработать:\n"
            "  •  установка Node.js (инсталлятор пишет в %ProgramFiles%)\n"
            "  •  установка Claude Code (npm i -g в системные папки)\n"
            "  •  полное удаление Claude Code и чистка залоченных файлов\n"
            "  •  запись в системные папки (%ProgramFiles%, %ProgramData%)\n"
            "  •  правки в чужих профилях и общих директориях\n\n"
            "Базовые сценарии — Fix Claude, смена модели и API-ключа —\n"
            "работают и без админа."
        ))
        desc_label.setFont(QFont("Segoe UI", 10))
        desc_label.setStyleSheet("""
            QLabel {
                color: rgba(230, 215, 185, 0.92);
                background: transparent;
                border: none;
            }
        """)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Плашка-совет внизу
        hint_label = QLabel(tr(
            "Совет:  закройте приложение и запустите от имени администратора"
        ))
        hint_label.setFont(QFont("Segoe UI", 9))
        hint_label.setStyleSheet("""
            QLabel {
                color: rgba(245, 196, 74, 0.9);
                background: rgba(245, 196, 74, 0.1);
                border: 1px solid rgba(245, 196, 74, 0.28);
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint_label)

        layout.addSpacing(4)

        # Кнопка «Понятно» — янтарная, по центру
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_ok = GlowDialogButton(tr("Понятно"),
                                  base_rgb=(210, 160, 60),
                                  hover_rgb=(245, 196, 74))
        btn_ok.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedWidth(480)

        # Fade-in: меняем windowOpacity, не конфликтует с дочерними виджетами.
        self.setWindowOpacity(0.0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(AdminWarningDialog, self).accept())
        fade.start()
        self._fade = fade

    def reject(self):
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(AdminWarningDialog, self).reject())
        fade.start()
        self._fade = fade


# ============================================================
# КАСТОМНОЕ ОКНО ПОДТВЕРЖДЕНИЯ ДЕЙСТВИЯ
# ============================================================

class ConfirmActionDialog(QDialog):
    """Универсальное окно подтверждения с кастомным заголовком и текстом."""
    def __init__(self, title, message, detail=None, confirm_text=None,
                 icon="⚙", icon_color=(100, 150, 255), parent=None):
        if confirm_text is None:
            confirm_text = tr("Продолжить")
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setObjectName("confirmActionContainer")
        container.setStyleSheet("""
            QFrame#confirmActionContainer {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(14)

        ir, ig, ib = icon_color
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                color: rgb({ir}, {ig}, {ib});
                font-size: 28px;
                font-weight: bold;
                background: rgba({ir}, {ig}, {ib}, 0.15);
                border: 2px solid rgba({ir}, {ig}, {ib}, 0.4);
                border-radius: 25px;
                min-width: 50px;
                max-width: 50px;
                min-height: 50px;
                max-height: 50px;
            }}
        """)
        icon_row = QHBoxLayout()
        icon_row.addStretch()
        icon_row.addWidget(icon_label)
        icon_row.addStretch()
        layout.addLayout(icon_row)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title_label.setStyleSheet("color: #DDDDDD; background: transparent; border: none;")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        message_label = QLabel(message)
        message_label.setFont(QFont("Segoe UI", 10))
        message_label.setStyleSheet("color: #B5B5B5; background: transparent; border: none;")
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        if detail:
            detail_label = QLabel(detail)
            detail_label.setFont(QFont("Consolas", 9))
            detail_label.setStyleSheet("""
                QLabel {
                    color: #E0E0E0;
                    background: rgba(100, 100, 105, 0.1);
                    border: 1.5px solid rgba(100, 100, 105, 0.4);
                    border-radius: 8px;
                    padding: 8px 12px;
                }
            """)
            detail_label.setAlignment(Qt.AlignLeft)
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.cancel_btn = RedButton(tr("Отмена"))
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.confirm_btn = GreenButton(confirm_text)
        self.confirm_btn.setMinimumHeight(40)
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.adjustSize()
        self.setMinimumWidth(440)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(ConfirmActionDialog, self).accept())
        fade.start()
        self._fade = fade

    def reject(self):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(ConfirmActionDialog, self).reject())
        fade.start()
        self._fade = fade

# ============================================================
# ПРОГРЕСС БАР ДЛЯ ОБНОВЛЕНИЯ
# ============================================================

class AnimatedProgressBar(QWidget):
    def __init__(self, color="#64B4FF", parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self._progress = 0
        self._downloaded_mb = 0.0
        self._total_mb = 0.0
        self._color = color
        self._shimmer_offset = 0.0

        # Таймер для шиммера
        self._shimmer_timer = QTimer()
        self._shimmer_timer.timeout.connect(self._animate_shimmer)
        self._shimmer_timer.start(30)

    def _animate_shimmer(self):
        if self._progress > 0 and self._progress < 100:
            self._shimmer_offset += 0.02
            if self._shimmer_offset > 1.0:
                self._shimmer_offset = -0.3
            self.update()

    def set_progress(self, percent):
        self._progress = max(0, min(100, percent))
        self.update()

    def set_size(self, downloaded_mb, total_mb):
        self._downloaded_mb = downloaded_mb
        self._total_mb = total_mb
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Фон
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 30, 35))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 8, 8)

        # Прогресс
        progress_width = 0
        if self._progress > 0:
            progress_width = int(self.width() * self._progress / 100)

            # Базовый цвет прогресса
            base_color = QColor(self._color)
            painter.setBrush(base_color)
            painter.drawRoundedRect(0, 0, progress_width, self.height(), 8, 8)

            # Шиммер эффект (светлая полоса)
            if self._progress < 100:
                shimmer_pos = self._shimmer_offset * progress_width
                shimmer_width = progress_width * 0.3

                gradient = QLinearGradient(shimmer_pos - shimmer_width/2, 0,
                                          shimmer_pos + shimmer_width/2, 0)

                # Прозрачный -> белый -> прозрачный
                gradient.setColorAt(0.0, QColor(255, 255, 255, 0))
                gradient.setColorAt(0.5, QColor(255, 255, 255, 60))
                gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

                painter.setBrush(gradient)
                painter.drawRoundedRect(0, 0, progress_width, self.height(), 8, 8)

        # Текст - сначала белый на темном фоне (не накрытая часть)
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        if self._total_mb > 0:
            text = f"{self._progress}%  •  {self._downloaded_mb:.1f} / {self._total_mb:.1f} МБ"
        else:
            text = f"{self._progress}%"

        # Рисуем белый текст на всей области
        painter.setPen(QColor(220, 220, 220))
        painter.drawText(self.rect(), Qt.AlignCenter, text)

        # Рисуем   емный текст только на области прогресса (clipping)
        if progress_width > 0:
            painter.setClipRect(0, 0, progress_width, self.height())
            painter.setPen(QColor(30, 30, 35))  # Темный текст на синем фоне
            painter.drawText(self.rect(), Qt.AlignCenter, text)
            painter.setClipping(False)

# ============================================================
# АНИМИРОВАННЫЙ ПЕРЕКЛЮЧАТЕЛЬ (TOGGLE SWITCH)
# ============================================================

class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(42, 22)
        self._checked = checked
        self._progress = 1.0 if checked else 0.0
        self._target = 1.0 if checked else 0.0

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60fps

    def isChecked(self):
        return self._checked

    def setChecked(self, val):
        if val != self._checked:
            self._checked = val
            self._target = 1.0 if val else 0.0

    def _tick(self):
        diff = self._target - self._progress
        if abs(diff) > 0.004:
            self._progress += diff * 0.2  # expo ease-out
            self.update()
        elif self._progress != self._target:
            self._progress = self._target
            self.update()

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self._target = 1.0 if self._checked else 0.0
        self.toggled.emit(self._checked)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        t = self._progress  # 0.0 = OFF, 1.0 = ON (плавно)
        w, h = self.width(), self.height()

        # Трек — всегда тёмный, только тонкая синяя обводка появляется при ON
        br = int(55 + 5 * t)
        bg = int(55 + 25 * t)
        bb = int(62 + 48 * t)
        p.setBrush(QColor(36, 36, 42))
        p.setPen(QPen(QColor(br, bg, bb), 1))
        p.drawRoundedRect(0, 0, w, h, 5, 5)

        # Геометрия квадратика
        thumb_sz = h - 6  # 16px
        thumb_x = 3.0 + (w - 6 - thumb_sz) * t  # 3 → 23
        thumb_y = 3.0

        # Свечение вокруг квадратика (только когда ON)
        if t > 0.01:
            for i in range(1, 4):
                alpha = int(70 * t * (1.0 - (i - 1) / 3.5))
                p.setPen(QPen(QColor(80, 155, 255, alpha), 1))
                p.setBrush(Qt.NoBrush)
                ex = i * 1.8
                p.drawRoundedRect(
                    QRectF(thumb_x - ex, thumb_y - ex,
                           thumb_sz + ex * 2, thumb_sz + ex * 2),
                    3 + ex, 3 + ex
                )

        # Квадратик: серый при OFF → голубой при ON
        r = int(138 - 18 * t)   # 138 → 120
        g = int(138 + 47 * t)   # 138 → 185
        b = int(145 + 110 * t)  # 145 → 255
        p.setBrush(QColor(r, g, b))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(thumb_x, thumb_y, thumb_sz, thumb_sz), 3, 3)

        p.end()

# ============================================================
# ШИРОКИЙ ПЕРЕКЛЮЧАТЕЛЬ РЕЖИМОВ (FreeModel ↔ Omniroute)
# ============================================================

class ModeToggle(QWidget):
    """Левое положение = FreeModel (оранжевый), Правое = Omniroute (синий)"""
    toggled = Signal(bool)  # True = Omniroute, False = FreeModel

    def __init__(self, omniroute_mode=True, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 38)
        self.setCursor(Qt.PointingHandCursor)
        self._omniroute = omniroute_mode
        self._progress = 1.0 if omniroute_mode else 0.0
        self._target = self._progress

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # 60fps

    def isOmniroute(self):
        return self._omniroute

    def setOmniroute(self, val, animate=True):
        if val != self._omniroute:
            self._omniroute = val
            self._target = 1.0 if val else 0.0
            if not animate:
                self._progress = self._target
                self.update()

    def _tick(self):
        diff = self._target - self._progress
        if abs(diff) > 0.004:
            self._progress += diff * 0.18
            self.update()
        elif self._progress != self._target:
            self._progress = self._target
            self.update()

    def mousePressEvent(self, event):
        new_mode = event.pos().x() >= self.width() / 2
        if new_mode != self._omniroute:
            self._omniroute = new_mode
            self._target = 1.0 if self._omniroute else 0.0
            self.toggled.emit(self._omniroute)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self._progress
        w, h = self.width(), self.height()

        # Трек
        p.setBrush(QColor(28, 28, 33))
        p.setPen(QPen(QColor(60, 60, 65), 2))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 9, 9)

        # Активная "таблетка" (скользящая половина)
        pill_w = w / 2 - 4
        pill_x = 2 + (w / 2) * t  # 2 → w/2 + 2

        # Цвет: оранжевый (FreeModel) → синий (Omniroute)
        r = int(255 + (100 - 255) * t)   # 255 → 100
        g = int(170 + (150 - 170) * t)   # 170 → 150
        b = int(40 + (255 - 40) * t)     # 40  → 255

        # Свечение вокруг таблетки (клипом обрезаем по внутренней области трека)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(2, 2, w - 4, h - 4), 8, 8)
        p.save()
        p.setClipPath(clip_path)
        for i in range(1, 4):
            alpha = int(55 * (1 - (i - 1) / 3.5))
            p.setPen(QPen(QColor(r, g, b, alpha), 1))
            p.setBrush(Qt.NoBrush)
            ex = i * 1.6
            p.drawRoundedRect(
                QRectF(pill_x - ex, 2 - ex, pill_w + ex * 2, h - 4 + ex * 2),
                7 + ex, 7 + ex
            )
        p.restore()

        # Сама таблетка
        p.setBrush(QColor(r, g, b, 235))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(pill_x, 2, pill_w, h - 4), 7, 7)

        # Текст
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))

        # Левая половина: FreeModel — яркая когда t=0
        left_b = int(235 - 120 * t)
        p.setPen(QColor(left_b, left_b, left_b))
        p.drawText(QRectF(0, 0, w / 2, h), Qt.AlignCenter, "BaseURL")

        # Правая половина: Omniroute — яркая когда t=1
        right_b = int(115 + 120 * t)
        p.setPen(QColor(right_b, right_b, right_b))
        p.drawText(QRectF(w / 2, 0, w / 2, h), Qt.AlignCenter, "Omniroute")

        p.end()


class LanguageToggle(QWidget):
    """Компактный переключатель языка интерфейса EN / RU.

    Стилистика: слегка скруглённый прямоугольник (radius ~6, не «таблетка»).
    EN активен → подсветка зелёная (#34d399, цвет «freemodel» с сайта).
    RU активен → подсветка холодная голубоватая (#6aa9ff).
    Плавная анимация цвета пилюли и яркости лейблов между состояниями.
    """
    toggled = Signal(str)  # 'ru' | 'en'

    # Цвета берутся из брендинга freemodel.dev (#34d399) и подбираются
    # к нему по контрасту для RU.
    _EN_COL = (52, 211, 153)   # #34d399
    _RU_COL = (106, 169, 255)  # #6aa9ff

    def __init__(self, lang="ru", parent=None):
        super().__init__(parent)
        self.setFixedSize(96, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self._lang = lang
        # 0.0 = RU, 1.0 = EN
        self._progress = 1.0 if lang == "en" else 0.0
        self._target = self._progress

        # Hover-подсветка неактивной стороны: при наведении на «другую»
        # половину её буквы плавно «загораются» цветом соответствующего
        # языка (RU = голубой, EN = зелёный) — как превью того, что будет
        # после клика.
        self._hover_ru = 0.0  # 0..1
        self._hover_en = 0.0
        self._hover_ru_target = 0.0
        self._hover_en_target = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_lang(self, code, animate=True):
        if code not in ("ru", "en"):
            return
        if code == self._lang:
            return
        self._lang = code
        self._target = 1.0 if code == "en" else 0.0
        if not animate:
            self._progress = self._target
        self.update()

    def _tick(self):
        changed = False
        diff = self._target - self._progress
        if abs(diff) > 0.004:
            self._progress += diff * 0.18
            changed = True
        elif self._progress != self._target:
            self._progress = self._target
            changed = True
        # Hover-fade каждой половины (мягко 0↔1).
        # Низкий коэффициент = более медленный, плавный «прогрев» цвета.
        # 0.07 даёт ~250-300 мс на полный переход — мягко, как у спокойного
        # easing-in/out, без рывка в конце.
        for name in ("_hover_ru", "_hover_en"):
            cur = getattr(self, name)
            tgt = getattr(self, name + "_target")
            d = tgt - cur
            if abs(d) > 0.003:
                setattr(self, name, cur + d * 0.07)
                changed = True
            elif cur != tgt:
                setattr(self, name, tgt)
                changed = True
        if changed:
            self.update()

    def mousePressEvent(self, event):
        # Любая половина переключает в свой режим (без deselect активного).
        is_right = event.pos().x() >= self.width() / 2
        new_lang = "en" if is_right else "ru"
        if new_lang != self._lang:
            self._lang = new_lang
            self._target = 1.0 if new_lang == "en" else 0.0
            self.toggled.emit(new_lang)
            self.update()

    def mouseMoveEvent(self, event):
        # Подсвечиваем ТОЛЬКО неактивную половину при наведении.
        is_right = event.pos().x() >= self.width() / 2
        if is_right:
            # курсор справа — превью «EN»
            self._hover_en_target = 0.0 if self._lang == "en" else 1.0
            self._hover_ru_target = 0.0
        else:
            self._hover_ru_target = 0.0 if self._lang == "ru" else 1.0
            self._hover_en_target = 0.0
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_ru_target = 0.0
        self._hover_en_target = 0.0
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self._progress
        w, h = self.width(), self.height()

        # Слегка квадратный радиус — 6 px (не «таблетка»).
        track_r = 6.0
        pill_r = 5.0

        # Трек
        p.setBrush(QColor(28, 28, 33))
        p.setPen(QPen(QColor(60, 60, 65), 1.4))
        p.drawRoundedRect(QRectF(0.7, 0.7, w - 1.4, h - 1.4), track_r, track_r)

        # Цвет пилюли — интерполяция RU → EN
        r0, g0, b0 = self._RU_COL
        r1, g1, b1 = self._EN_COL
        r = int(r0 + (r1 - r0) * t)
        g = int(g0 + (g1 - g0) * t)
        b = int(b0 + (b1 - b0) * t)

        # Пилюля скользит между левой и правой по  овиной
        pad = 2.5
        pill_w = w / 2 - pad
        pill_x = pad / 2 + (w / 2) * t

        # Мягкое свечение по периметру пилюли (внутри клипа трека).
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1.4, 1.4, w - 2.8, h - 2.8), track_r - 1, track_r - 1)
        p.save()
        p.setClipPath(clip)
        for i in range(1, 4):
            alpha = int(48 * (1 - (i - 1) / 3.2))
            p.setPen(QPen(QColor(r, g, b, alpha), 1))
            p.setBrush(Qt.NoBrush)
            ex = i * 1.4
            p.drawRoundedRect(
                QRectF(pill_x - ex, pad - ex, pill_w + ex * 2, h - pad * 2 + ex * 2),
                pill_r + ex, pill_r + ex
            )
        p.restore()

        # Сама пилюля — лёгкий вертикальный градиент для объёма
        grad = QLinearGradient(QPointF(0, pad), QPointF(0, h - pad))
        grad.setColorAt(0.0, QColor(min(255, r + 18), min(255, g + 18), min(255, b + 18), 240))
        grad.setColorAt(1.0, QColor(max(0, r - 10), max(0, g - 10), max(0, b - 10), 240))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(pill_x, pad, pill_w, h - pad * 2), pill_r, pill_r)

        # Текст
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))

        # Левая половина — RU. Яркая когда t=0.
        ru_active = 1.0 - t
        if ru_active > 0.5:
            # На активной пилюле — тёмный текст, для контраста
            ru_pen = QColor(20, 22, 28)
        else:
            # Неактивный — мягко-серый, при ховере плавно подсвечивается
            # в цвет RU (#6aa9ff). Альфа hover_ru интерполирует от серого
            # к полному цвету RU.
            shade = int(130 + 25 * (1 - t))
            base = QColor(shade, shade, shade + 5)
            hr, hg, hb = self._RU_COL
            hover = self._hover_ru
            ru_pen = QColor(
                int(base.red()   + (hr - base.red())   * hover),
                int(base.green() + (hg - base.green()) * hover),
                int(base.blue()  + (hb - base.blue())  * hover),
            )
        p.setPen(ru_pen)
        p.drawText(QRectF(0, 0, w / 2, h), Qt.AlignCenter, "RU")

        # Правая половина — EN. Яркая когда t=1.
        if t > 0.5:
            en_pen = QColor(15, 28, 22)
        else:
            shade = int(130 + 25 * t)
            base = QColor(shade, shade + 5, shade)
            hr, hg, hb = self._EN_COL
            hover = self._hover_en
            en_pen = QColor(
                int(base.red()   + (hr - base.red())   * hover),
                int(base.green() + (hg - base.green()) * hover),
                int(base.blue()  + (hb - base.blue())  * hover),
            )
        p.setPen(en_pen)
        p.drawText(QRectF(w / 2, 0, w / 2, h), Qt.AlignCenter, "EN")

        p.end()


# ============================================================
# ДИАЛОГ УПРАВЛЕНИЯ BASE URL
# ============================================================

class AnimatedComboBox(QComboBox):
    """QComboBox с плавной анимацией рамки при наведении (как StyledButton)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover_progress = 0.0
        self._is_hovered = False
        self.setMouseTracking(True)
        self._hover_timer = QTimer()
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.start(20)
        self._apply_style()

    def enterEvent(self, event):
        self._is_hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        super().leaveEvent(event)

    def _animate_hover(self):
        if self._is_hovered:
            if self._hover_progress < 1.0:
                self._hover_progress = min(1.0, self._hover_progress + 0.1)
                self._apply_style()
        else:
            if self._hover_progress > 0.0:
                self._hover_progress = max(0.0, self._hover_progress - 0.1)
                self._apply_style()

    def _apply_style(self):
        p = self._hover_progress
        r = int(60 + (60 - 60) * p)
        g = int(60 + (140 - 60) * p)
        b = int(65 + (200 - 65) * p)
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: rgba(40, 40, 45, 200);
                color: rgb(200, 200, 200);
                border: 2px solid rgb({r}, {g}, {b});
                border-radius: 6px;
                padding: 8px 12px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background-color: rgb(30, 30, 35);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 4px;
                outline: none;
                selection-background-color: rgba(60, 140, 200, 140);
                selection-color: rgb(240, 240, 240);
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 10px;
                min-height: 24px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: rgba(60, 140, 200, 100);
            }}
        """)


class _CloseButton(QPushButton):
    """Крестик с плавной анимацией рамки и фона при наведении."""

    def __init__(self, parent=None):
        super().__init__("✕", parent)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")
        self._progress = 0.0
        self._is_hovered = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(20)

    def enterEvent(self, event):
        self._is_hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        super().leaveEvent(event)

    def _tick(self):
        target = 1.0 if self._is_hovered else 0.0
        if abs(self._progress - target) > 0.01:
            self._progress += 0.1 if target > self._progress else -0.1
            self._progress = max(0.0, min(1.0, self._progress))
            self.update()

    def paintEvent(self, event):
        p = self._progress
        r = int(60 + (200 - 60) * p)
        g = int(60 + (50 - 60) * p)
        b = int(65 + (50 - 65) * p)
        bg_alpha = int(0 + 140 * p)
        txt_alpha = int(120 + (255 - 120) * p)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QColor(r, g, b, bg_alpha))
        painter.setPen(QPen(QColor(r, g, b, int(80 + 175 * p)), 2))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor(txt_alpha, txt_alpha, txt_alpha))
        painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, "✕")


class BaseUrlManagerDialog(QDialog):
    DEFAULT_URLS = ("https://cc.freemodel.dev",)

    def __init__(self, urls, current, parent=None):
        super().__init__(parent)
        self.urls = list(urls)
        self.current = current
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setObjectName("baseUrlManagerContainer")
        container.setStyleSheet("""
            QFrame#baseUrlManagerContainer {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 20, 30, 25)
        layout.setSpacing(12)

        # Заголовок + крестик закрытия
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        # Спейсер слева чтобы заголовок был по центру
        left_spacer = QWidget()
        left_spacer.setFixedSize(28, 28)
        left_spacer.setStyleSheet("background: transparent; border: none;")
        title_row.addWidget(left_spacer)

        title = QLabel(tr("Управление Base URL"))
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #CCCCCC; background: transparent; border: none;")
        title_row.addWidget(title, 1)

        self.btn_close = _CloseButton(parent=container)
        self.btn_close.clicked.connect(self.accept)
        title_row.addWidget(self.btn_close)
        layout.addLayout(title_row)

        info = QLabel(tr("Добавьте или удалите URL из списка"))
        info.setFont(QFont("Segoe UI", 9))
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color: rgb(120, 120, 120); background: transparent; border: none;")
        layout.addWidget(info)

        # Combo со списком URL — с плавной анимацией рамки
        self.url_combo = AnimatedComboBox()
        self.url_combo.setCursor(Qt.PointingHandCursor)
        self.url_combo.setFont(QFont("Segoe UI", 9))
        self.url_combo.setMaxVisibleItems(3)
        self.url_combo.addItems(self.urls)
        if self.current in self.urls:
            self.url_combo.setCurrentText(self.current)
        layout.addWidget(self.url_combo)

        # Кнопка удалить выбранный URL
        self.btn_remove_url = RedButton(tr("Удалить выбранный URL"))
        self.btn_remove_url.setMinimumHeight(32)
        self.btn_remove_url.clicked.connect(self.remove_url)
        layout.addWidget(self.btn_remove_url)

        # Разделитель — добавление нового
        add_label = QLabel(tr("Добавить новый URL:"))
        add_label.setFont(QFont("Segoe UI", 10))
        add_label.setStyleSheet("color: rgb(180, 180, 180); background: transparent; border: none;")
        layout.addWidget(add_label)

        add_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        self.url_input.setFont(QFont("Segoe UI", 9))
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 35, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 8px;
            }
        """)
        add_row.addWidget(self.url_input, 1)

        self.btn_add_url = GreenButton(tr("Добавить"))
        self.btn_add_url.setMinimumHeight(32)
        self.btn_add_url.setMaximumWidth(110)
        self.btn_add_url.clicked.connect(self.add_url)
        add_row.addWidget(self.btn_add_url)

        layout.addLayout(add_row)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedWidth(440)

        self._update_remove_button()
        self.url_combo.currentTextChanged.connect(lambda _: self._update_remove_button())

        # Плавное появление
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(220)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_anim.start()

    def accept(self):
        fade = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        fade.setDuration(220)
        fade.setStartValue(self._opacity_effect.opacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(BaseUrlManagerDialog, self).accept())
        fade.start()
        self._fade_out = fade

    def reject(self):
        fade = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        fade.setDuration(220)
        fade.setStartValue(self._opacity_effect.opacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(BaseUrlManagerDialog, self).reject())
        fade.start()
        self._fade_out = fade

    def _update_remove_button(self):
        """Запрещает удалять дефолтные URL"""
        sel = self.url_combo.currentText()
        is_default = sel in self.DEFAULT_URLS
        self.btn_remove_url.setEnabled(not is_default)
        if is_default:
            self.btn_remove_url.setText(tr("Базовый URL нельзя удалить"))
        else:
            self.btn_remove_url.setText(tr("Удалить выбранный URL"))

    def add_url(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            QMessageBox.warning(self, "Ошибка", "URL должен начинаться с http:// или https://")
            return
        if url in self.urls:
            QMessageBox.information(self, "Информация", "Такой URL уже есть в списке")
            self.url_combo.setCurrentText(url)
            return
        self.urls.append(url)
        self.url_combo.addItem(url)
        self.url_combo.setCurrentText(url)
        self.url_input.clear()

    def remove_url(self):
        sel = self.url_combo.currentText()
        if sel in self.DEFAULT_URLS:
            return
        if sel not in self.urls:
            return
        # Подтверждение удаления
        confirm = ConfirmDeleteDialog(sel, self, question_text="Вы уверены, что хотите удалить Base URL?")
        if confirm.exec() != QDialog.Accepted:
            return
        self.urls.remove(sel)
        idx = self.url_combo.currentIndex()
        self.url_combo.removeItem(idx)

    def get_result(self):
        # Переключение селектора в диалоге игнорируется — возвращаем исходный
        # выбранный URL. Но если он был удалён, фолбэк на первый из списка,
        # чтобы Claude не запускался с уже несуществующим URL.
        if self.current in self.urls:
            return list(self.urls), self.current
        return list(self.urls), (self.urls[0] if self.urls else "")

# ============================================================
# ДИАЛОГ КАСТОМНЫХ НАСТРОЕК ТОКЕНА
# ============================================================

class CustomTokenDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setObjectName("customTokenContainer")
        container.setStyleSheet("""
            QFrame#customTokenContainer {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        # Заголовок
        title = QLabel(tr("Настройки кастомного токена"))
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #CCCCCC; background: transparent; border: none;")
        layout.addWidget(title)

        # Base URL — выбор + кнопка управления
        url_label = QLabel("Base URL:")
        url_label.setFont(QFont("Segoe UI", 10))
        url_label.setStyleSheet("color: rgb(180, 180, 180);")
        layout.addWidget(url_label)

        url_layout = QHBoxLayout()
        url_layout.setSpacing(8)
        self.url_combo = QComboBox()
        self.url_combo.setCursor(Qt.PointingHandCursor)
        self.url_combo.setFont(QFont("Segoe UI", 9))
        self.url_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(30, 30, 35, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 8px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: rgb(30, 30, 35);
                color: rgb(200, 200, 200);
                selection-background-color: rgb(50, 50, 55);
            }
        """)
        self.base_urls = list(settings.get("custom_base_urls", ["https://cc.freemodel.dev"]))
        self.url_combo.addItems(self.base_urls)
        saved_url = settings.get("custom_base_url", self.base_urls[0])
        if saved_url in self.base_urls:
            self.url_combo.setCurrentText(saved_url)
        url_layout.addWidget(self.url_combo, 1)

        self.btn_manage_urls = StyledButton(tr("Управление"))
        self.btn_manage_urls.setMaximumWidth(120)
        self.btn_manage_urls.setMinimumHeight(0)
        self.btn_manage_urls.setFixedHeight(36)
        self.btn_manage_urls.setFont(QFont("Segoe UI", 9))
        self.btn_manage_urls.clicked.connect(self.open_url_manager)
        url_layout.addWidget(self.btn_manage_urls)

        layout.addLayout(url_layout)

        # API ключ
        key_label = QLabel(tr("API ключ:"))
        key_label.setFont(QFont("Segoe UI", 10))
        key_label.setStyleSheet("color: rgb(180, 180, 180);")
        layout.addWidget(key_label)

        key_layout = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("fe_oa_xxxxx...")
        self.key_input.setText(settings.get("custom_api_key", ""))
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setFont(QFont("Segoe UI", 9))
        self.key_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 35, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 8px;
            }
        """)
        key_layout.addWidget(self.key_input)

        self.btn_toggle_key = StyledButton(tr("Показать"))
        self.btn_toggle_key.setMaximumWidth(100)
        self.btn_toggle_key.clicked.connect(self.toggle_key_visibility)
        key_layout.addWidget(self.btn_toggle_key)

        layout.addLayout(key_layout)

        # Модель
        model_label = QLabel(tr("Модель:"))
        model_label.setFont(QFont("Segoe UI", 10))
        model_label.setStyleSheet(
            "color: rgb(180, 180, 180); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 6px; padding: 4px 8px;"
        )
        layout.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.setCursor(Qt.PointingHandCursor)
        self.model_combo.setFont(QFont("Segoe UI", 9))
        self.model_combo.setMaxVisibleItems(4)
        self.model_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(30, 30, 35, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 8px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: rgb(30, 30, 35);
                color: rgb(200, 200, 200);
                selection-background-color: rgb(50, 50, 55);
            }
        """)
        models = ["Fable 5", "Opus 4.8", "Opus 4.7", "Opus 4.6", "Sonnet 4.6", "Sonnet 4"]
        self.model_combo.addItems(models)
        # Цвета для каждой модели (от зелёного к красному)
        _sd_model_colors = {
            "Sonnet 4":     QColor(120, 220, 120),
            "Sonnet 4.6":   QColor(100, 230, 100),
            "Opus 4.6":     QColor(230, 220, 130),
            "Opus 4.7":     QColor(235, 180, 110),
            "Opus 4.8":     QColor(235, 150, 130),
            "Fable 5":   QColor(235, 90, 90),
        }
        for i in range(self.model_combo.count()):
            txt = self.model_combo.itemText(i)
            if txt in _sd_model_colors:
                if txt == "Fable 5":
                    # Затемнённый красный — модель видно, но она помечена как недоступная
                    c = _sd_model_colors[txt]
                    dim = QColor(int(c.red() * 0.55), int(c.green() * 0.55), int(c.blue() * 0.55))
                    self.model_combo.setItemData(i, dim, Qt.ForegroundRole)
                else:
                    self.model_combo.setItemData(i, _sd_model_colors[txt], Qt.ForegroundRole)
            pass
        # Fable 5 заблокирована правительством США — нельзя выбрать
        self._fable5_index = models.index("Fable 5") if "Fable 5" in models else -1
        # Маппинг старых сохранённых значений на новые метки
        model_remap = {
            "default (claude-opus-4-8)": "Opus 4.8",
            "Opus 4.8 (default)": "Opus 4.8",
            "claude-sonnet-4-6 (/model → 2)": "Sonnet 4.6",
            "claude-sonnet-4-6": "Sonnet 4.6",
            "claude-opus-4-7": "Opus 4.7",
            "claude-opus-4-6": "Opus 4.6",
            "claude-fable-5": "Fable 5",
        }
        saved_model = settings.get("custom_model", "Opus 4.8")
        saved_model = model_remap.get(saved_model, saved_model)
        if saved_model == "Fable 5":
            saved_model = "Opus 4.8"
        if saved_model in models:
            self.model_combo.setCurrentText(saved_model)
        self._last_valid_model = self.model_combo.currentText()
        self.model_combo.activated.connect(self._on_model_activated)
        layout.addWidget(self.model_combo)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_cancel = RedButton(tr("Отмена"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = GreenButton(tr("Сохранить"))
        btn_save.clicked.connect(self.save_settings)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        main_layout.addWidget(container)
        self.setLayout(main_layout)

        # Плавное появление и закрытие
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        fade.setDuration(220)
        fade.setStartValue(self.opacity_effect.opacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(CustomTokenDialog, self).accept())
        fade.start()
        self._fade = fade

    def reject(self):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        fade.setDuration(220)
        fade.setStartValue(self.opacity_effect.opacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(CustomTokenDialog, self).reject())
        fade.start()
        self._fade = fade

    def toggle_key_visibility(self):
        """Переключает видимость ключа"""
        if self.key_input.echoMode() == QLineEdit.Password:
            self.key_input.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_key.setText(tr("Скрыть"))
        else:
            self.key_input.setEchoMode(QLineEdit.Password)
            self.btn_toggle_key.setText(tr("Показать"))

    def open_url_manager(self):
        """Открывает отдельное окно управления Base URL"""
        current_url = self.url_combo.currentText()
        dialog = BaseUrlManagerDialog(self.base_urls, current_url, self)
        if dialog.exec() == QDialog.Accepted:
            self.base_urls, new_current = dialog.get_result()
            # Перестраиваем combo
            self.url_combo.blockSignals(True)
            self.url_combo.clear()
            self.url_combo.addItems(self.base_urls)
            if new_current in self.base_urls:
                self.url_combo.setCurrentText(new_current)
            self.url_combo.blockSignals(False)
            # Сразу сохраняем список URL в settings (даже если основной диалог закроют отменой)
            self.settings["custom_base_urls"] = list(self.base_urls)
            save_settings(self.settings)

    def _on_model_activated(self, idx):
        """Блокирует выбор Fable 5 и показывает окно о блокировке."""
        if idx == self._fable5_index:
            # Откатываем на предыдущее валидное значение
            prev = self._last_valid_model if self._last_valid_model != "Fable 5" else "Opus 4.8"
            self.model_combo.blockSignals(True)
            self.model_combo.setCurrentText(prev)
            self.model_combo.blockSignals(False)
            dlg = Fable5WarningDialog(self)
            dlg.exec()
            return
        self._last_valid_model = self.model_combo.itemText(idx)

    def save_settings(self):
        """Сохраняет настройки"""
        api_key = self.key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Ошибка", "API ключ не может быть пустым")
            return

        chosen_model = self.model_combo.currentText()
        if chosen_model == "Fable 5":
            chosen_model = "Opus 4.8"

        self.settings["custom_api_key"] = api_key
        self.settings["custom_base_url"] = self.url_combo.currentText()
        self.settings["custom_base_urls"] = list(self.base_urls)
        self.settings["custom_model"] = chosen_model
        self.settings["custom_endpoint"] = ""

        self.accept()

# ============================================================
# ДИАЛОГ ОБНОВЛЕНИЯ ПРИЛОЖЕНИЯ
# ============================================================

class UpdateAppDialog(QDialog):
    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.confirmed = False

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = DottedFrame()
        self.container.setObjectName("updateAppContainer")
        self.container.setStyleSheet("""
            QFrame#updateAppContainer {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgba(100, 180, 255, 0.6);
                border-radius: 16px;
            }
        """)

        cl = QVBoxLayout()
        cl.setContentsMargins(30, 25, 30, 25)
        cl.setSpacing(15)

        # Иконка
        icon = QLabel("↑")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("""
            QLabel {
                color: #64B4FF;
                font-size: 28px;
                font-weight: bold;
                background: rgba(100, 180, 255, 0.15);
                border: 2px solid rgba(100, 180, 255, 0.4);
                border-radius: 25px;
                min-width: 50px;
                max-width: 50px;
                min-height: 50px;
                max-height: 50px;
            }
        """)
        ic = QHBoxLayout()
        ic.addStretch()
        ic.addWidget(icon)
        ic.addStretch()

        # Заголовок
        title = QLabel(tr("Доступно обновление!"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: #64B4FF;
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)

        # Название приложения
        name = QLabel("Claude Code Manager")
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)

        # Версии
        ver = QLabel(f"v{update_info['current']}  →  v{update_info['latest']}")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("""
            QLabel {
                color: #E0E0E0;
                font-size: 13px;
                background: rgba(100, 180, 255, 0.1);
                border: 1.5px solid rgba(100, 180, 255, 0.4);
                border-radius: 8px;
                padding: 8px 12px;
            }
        """)

        # Кнопки
        bl = QHBoxLayout()
        bl.setSpacing(12)

        self.cancel_btn = RedButton(tr("Отмена"))
        self.cancel_btn.clicked.connect(self.reject_animated)

        self.update_btn = GreenButton(tr("Обновить"))
        self.update_btn.clicked.connect(self.accept_animated)

        bl.addWidget(self.cancel_btn)
        bl.addWidget(self.update_btn)

        cl.addLayout(ic)
        cl.addWidget(title)
        cl.addWidget(name)
        cl.addWidget(ver)
        cl.addLayout(bl)

        self.container.setLayout(cl)
        main_layout.addWidget(self.container)
        self.setLayout(main_layout)
        self.setFixedSize(380, 260)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept_animated(self):
        self.confirmed = True
        self.close_animated()

    def reject_animated(self):
        self.confirmed = False
        self.close_animated()

    def close_animated(self):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(UpdateAppDialog, self).accept() if self.confirmed else super(UpdateAppDialog, self).reject())
        fade.start()
        self._fade = fade

# ============================================================
# ДИАЛОГ СКАЧИВАНИЯ ОБНОВЛЕНИЯ
# ============================================================

# ============================================================
# КНОПКА С ПЛАВНЫМ HOVER-СВЕЧЕНИЕМ (для диалогов)
# ============================================================

class GlowDialogButton(QPushButton):
    """Кнопка с плавной анимацией цвета при наведении.

    Использует paintEvent + QPropertyAnimation: не зависит от QSS-полировки,
    которая первый раз срабатывает с задержкой (отсюда "вспышка" на первом ховере),
    и анимация интегрирована с Qt animation framework — не "отвисает" во время
    fade-in диалога.
    """
    def __init__(self, text, base_rgb, hover_rgb, parent=None):
        super().__init__(text, parent)
        self._base = base_rgb
        self._hover = hover_rgb
        self._progress = 0.0
        self._text = text
        self.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.setFixedWidth(140)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover, True)
        # Убираем дефолтный QPushButton-стиль — рисуем всё вручную
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _get_progress(self):
        return self._progress

    def _set_progress(self, value):
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    progress = Property(float, _get_progress, _set_progress)

    def _start_anim(self, target):
        self._anim.stop()
        self._anim.setStartValue(self._progress)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, event):
        self._start_anim(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._start_anim(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = self._progress
        br, bg, bb = self._base
        hr, hg, hb = self._hover
        r = int(br + (hr - br) * p)
        g = int(bg + (hg - bg) * p)
        b = int(bb + (hb - bb) * p)
        bg_alpha = int(0.15 * 255 + (0.32 - 0.15) * 255 * p)
        border_alpha = int(0.50 * 255 + (0.85 - 0.50) * 255 * p)
        if self.isDown():
            bg_alpha = 35

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        # Фон
        painter.setBrush(QColor(r, g, b, bg_alpha))
        painter.setPen(QPen(QColor(r, g, b, border_alpha), 2))
        painter.drawRoundedRect(rect, 8, 8)
        # Текст
        painter.setPen(QColor(r, g, b))
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignCenter, self.text())


# ============================================================
# АНИМАЦИЯ-СЕТКА 3×3 (sk-cube-grid стиль)
# ============================================================

class CubeGridSpinner(QWidget):
    """Анимация — 3×3 сетки кубиков с волной (стиль из spicetify_manager)."""
    _DELAYS = [0.2, 0.3, 0.4,
               0.1, 0.2, 0.3,
               0.0, 0.1, 0.2]
    _PERIOD = 1.3

    def __init__(self, color=(120, 200, 130), size=72, parent=None):
        super().__init__(parent)
        if isinstance(color, QColor):
            self._color = color
        else:
            self._color = QColor(*color)
        self._size = size
        self.setFixedSize(size, size)
        self._time = 0.0
        self._stopped = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(13)  # ~75 FPS

    def setColor(self, color):
        if isinstance(color, QColor):
            self._color = color
        else:
            self._color = QColor(*color)
        self.update()

    def _animate(self):
        if self._stopped:
            return
        self._time = (self._time + 0.016) % self._PERIOD
        self.update()

    def stop(self):
        self._stopped = True
        self._timer.stop()

    def paintEvent(self, event):
        if self._stopped:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        cube_size = self.width() / 3.0
        for i in range(9):
            t = (self._time - self._DELAYS[i]) % self._PERIOD
            phase = t / self._PERIOD
            if phase < 0.35:
                scale = 1.0 - phase / 0.35
            elif phase < 0.70:
                scale = (phase - 0.35) / 0.35
            else:
                scale = 1.0
            # smoothstep
            scale = max(0.0, min(1.0, scale * scale * (3 - 2 * scale)))
            sz = (cube_size - 1) * scale
            if sz <= 0.5:
                continue
            cx = (i % 3) * cube_size + cube_size / 2.0
            cy = (i // 3) * cube_size + cube_size / 2.0
            alpha = int(180 + 75 * scale)
            p.setBrush(QColor(self._color.red(), self._color.green(), self._color.blue(), alpha))
            p.drawRoundedRect(QRectF(cx - sz / 2, cy - sz / 2, sz, sz), 2, 2)


# ============================================================
# МОДАЛЬНОЕ ОКНО ПРОЦЕССА УСТАНОВКИ / ОБНОВЛЕНИЯ CLAUDE CODE
# ============================================================

class ClaudeInstallProgressDialog(QDialog):
    """Показывает прогресс установки/обновления, ждёт закрытия PowerShell."""

    def __init__(self, is_update=False, old_version="", new_version="", parent=None):
        super().__init__(parent)
        self._is_update = is_update
        self._old_version = old_version
        self._new_version = new_version
        self._finished = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowModality(Qt.ApplicationModal)

        if is_update:
            self._accent = (245, 180, 60)   # жёлто-оранжевый
            self._title_text = "Обновление Claude Code"
            self._action_word = "обновление"
        else:
            self._accent = (120, 200, 130)  # зелёный
            self._title_text = "Установка Claude Code"
            self._action_word = "установка"

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setObjectName("installContainer")
        r, g, b = self._accent
        container.setStyleSheet(f"""
            QFrame#installContainer {{
                background-color: rgb(20, 20, 25);
                border: 2px solid rgba({r}, {g}, {b}, 0.55);
                border-radius: 18px;
            }}
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(34, 28, 34, 26)
        layout.setSpacing(14)

        # Заголовок
        self.title_lbl = QLabel(self._title_text)
        self.title_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.title_lbl.setStyleSheet(
            f"color: rgb({r}, {g}, {b}); background: transparent; border: none;"
        )
        self.title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_lbl)

        # Версии (если есть)
        sub_text = ""
        if is_update and old_version and new_version:
            sub_text = f"v{old_version}  →  v{new_version}"
        elif new_version:
            sub_text = f"v{new_version}"
        self.sub_lbl = QLabel(sub_text)
        self.sub_lbl.setFont(QFont("Segoe UI", 10))
        self.sub_lbl.setStyleSheet(
            f"color: rgba({r}, {g}, {b}, 0.7); background: transparent; border: none;"
        )
        self.sub_lbl.setAlignment(Qt.AlignCenter)
        if sub_text:
            layout.addWidget(self.sub_lbl)

        # Спиннер
        spinner_row = QHBoxLayout()
        spinner_row.addStretch()
        self.spinner = CubeGridSpinner(color=self._accent, size=72)
        spinner_row.addWidget(self.spinner)
        spinner_row.addStretch()
        layout.addSpacing(6)
        layout.addLayout(spinner_row)
        layout.addSpacing(6)

        # Статус
        self.status_lbl = QLabel(
            f"Идёт {self._action_word}…\nНе закрывайте окно PowerShell."
        )
        self.status_lbl.setFont(QFont("Segoe UI", 10))
        self.status_lbl.setStyleSheet(
            "color: rgba(210, 210, 215, 0.9); background: transparent; border: none;"
        )
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        # Кнопка OK (скрыта до завершения)
        self.btn_ok = GlowDialogButton("Понятно",
                                       base_rgb=self._accent,
                                       hover_rgb=tuple(min(255, c + 30) for c in self._accent))
        self.btn_ok.clicked.connect(self.accept)
        self.btn_ok.hide()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.btn_ok)
        btn_row.addStretch()
        layout.addSpacing(4)
        layout.addLayout(btn_row)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedWidth(420)

        # Появление
        self.setWindowOpacity(0.0)
        self._fade_in = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in.setDuration(220)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_in.start()

    def accept(self):
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(220)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(ClaudeInstallProgressDialog, self).accept())
        fade.start()
        self._fade_out = fade

    def reject(self):
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(220)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(ClaudeInstallProgressDialog, self).reject())
        fade.start()
        self._fade_out = fade

    def mark_finished(self, actual_version=""):
        """Вызывается когда PowerShell закрылся — переключает окно в режим успеха."""
        if self._finished:
            return
        self._finished = True
        # Остановить спиннер
        self.spinner.stop()
        self.spinner.hide()
        # Обновить тексты
        if self._is_update:
            ver = actual_version or self._new_version
            self.title_lbl.setText(tr("Claude Code обновлён ✓"))
            if ver:
                self.sub_lbl.setText(tr("Версия") + f" v{ver}")
            else:
                self.sub_lbl.setText("")
            self.status_lbl.setText(tr(
                "Обновление завершено успешно.\n"
                "Перезапустите Claude Code для применения изменений."
            ))
        else:
            ver = actual_version or self._new_version
            self.title_lbl.setText(tr("Claude Code установлен ✓"))
            if ver:
                self.sub_lbl.setText(tr("Версия") + f" v{ver}")
            else:
                self.sub_lbl.setText("")
            self.status_lbl.setText(tr(
                "Установка завершена успешно.\n"
                "Если команда claude не найдена — открой новое окно консоли\n"
                "(npm обычно сам прописывает её в PATH)."
            ))
        self.btn_ok.show()

    def mark_cancelled(self):
        if self._finished:
            return
        self._finished = True
        self.spinner.stop()
        self.spinner.hide()
        self.title_lbl.setText(
            tr("Обновление отменено") if self._is_update else tr("Установка отменена")
        )
        self.title_lbl.setStyleSheet(
            "color: rgba(200, 180, 80, 0.9); background: transparent; border: none;"
        )
        self.sub_lbl.setText("")
        self.status_lbl.setText(tr(
            "Окно PowerShell было закрыто до завершения.\n"
            "Можете попробовать снова в любой момент."
        ))
        self.btn_ok.show()

    def mark_failed(self, message=""):
        if self._finished:
            return
        self._finished = True
        self.spinner.stop()
        self.spinner.hide()
        self.title_lbl.setText(
            tr("Обновление не завершено") if self._is_update else tr("Установка не завершена")
        )
        self.title_lbl.setStyleSheet(
            "color: rgb(235, 110, 110); background: transparent; border: none;"
        )
        self.sub_lbl.setText("")
        self.status_lbl.setText(
            message or tr("Окно PowerShell было закрыто до завершения операции.\n"
                          "Попробуйте ещё раз.")
        )
        self.btn_ok.show()


# ============================================================
# ПРЕВЬЮ STATUS LINE (мини-имитация терминала)
# ============================================================

class StatusLinePreview(QFrame):
    """Маленький чёрный «терминал», в котором нарисован пример того,
    как будет выглядеть наш status line внизу окна Claude Code."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusLinePreview")
        self.setStyleSheet("""
            QFrame#statusLinePreview {
                background-color: rgb(12, 12, 14);
                border: 1.5px solid rgba(110, 200, 130, 0.35);
                border-radius: 8px;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)

        caption = QLabel(tr("Пример отображения в Claude Code"))
        caption.setFont(QFont("Segoe UI", 8))
        caption.setStyleSheet("color: rgba(180, 180, 185, 0.65); background: transparent; border: none;")
        caption.setAlignment(Qt.AlignLeft)
        lay.addWidget(caption)

        # Стилизованный «текст терминала» через rich-text HTML
        # Цвета подобраны под реальные ANSI из statusline-command.sh
        line = QLabel(
            '<span style="color:#7ED88A;">claude-opus-4-7</span>'
            '<span style="color:#888;"> | </span>'
            '<span style="color:#C8E060;">14.2% [====----------------]</span>'
            '<span style="color:#888;"> | </span>'
            '<span style="color:#5BC8E0;">(a1b2c3d4)</span>'
            '<span style="color:#888;"> | </span>'
            '<span style="color:#C66BD8;">user/project</span>'
        )
        line.setFont(QFont("Consolas", 10))
        line.setStyleSheet("background: transparent; border: none;")
        line.setTextFormat(Qt.RichText)
        line.setAlignment(Qt.AlignLeft)
        lay.addWidget(line)

        # Подпись — что отображается слева направо
        legend = QLabel(tr("модель  •  контекст  •  session ID  •  git-репозиторий"))
        legend.setFont(QFont("Segoe UI", 8))
        legend.setStyleSheet("color: rgba(150, 150, 155, 0.55); background: transparent; border: none;")
        lay.addWidget(legend)


# ============================================================
# ДИАЛОГ ПОДТВЕРЖДЕНИЯ УСТАНОВКИ STATUS LINE
# ============================================================

class StatusLineInstallDialog(QDialog):
    """Жёлтое «Внимание» с превью status line. Два режима — свежая установка
    и замена существующего."""
    # Коды результата: Accepted = установка, Rejected = отмена, ACTION_REMOVE = удалить
    ACTION_REMOVE = 2

    def __init__(self, has_existing=False, existing_command="", parent=None):
        super().__init__(parent)
        self._has_existing = has_existing

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        accent = (245, 200, 80)  # жёлтый
        r, g, b = accent

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setObjectName("statusLineInstallContainer")
        container.setStyleSheet(f"""
            QFrame#statusLineInstallContainer {{
                background-color: rgb(20, 20, 25);
                border: 2px solid rgba({r}, {g}, {b}, 0.55);
                border-radius: 16px;
            }}
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(14)

        # Иконка-восклицание
        icon_label = QLabel("!")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                color: rgb({r}, {g}, {b});
                font-size: 28px;
                font-weight: bold;
                background: rgba({r}, {g}, {b}, 0.15);
                border: 2px solid rgba({r}, {g}, {b}, 0.4);
                border-radius: 25px;
                min-width: 50px; max-width: 50px;
                min-height: 50px; max-height: 50px;
            }}
        """)
        ic = QHBoxLayout()
        ic.addStretch(); ic.addWidget(icon_label); ic.addStretch()
        layout.addLayout(ic)

        # Заголовок «Внимание» жёлтым
        title_label = QLabel(tr("Внимание"))
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet(
            f"color: rgb({r}, {g}, {b}); background: transparent; border: none;"
        )
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Единый текст с пометкой текущего состояния
        if has_existing:
            state_line = tr(
                '<span style="color:#F5C850;"><b>● Сейчас status line установлен.</b></span><br>'
                "Можно <b>переустановить</b> его (наш скрипт перезапишет твой) "
                "или <b>удалить</b> — тогда блок <code>statusLine</code> уйдёт "
                "из <code>~/.claude/settings.json</code>, а файл "
                "<code>~/.claude/statusline-command.sh</code> будет стёрт.<br><br>"
            )
        else:
            state_line = tr(
                '<span style="color:rgba(200,200,205,0.7);">● Сейчас status line не настроен.</span><br>'
                "Менеджер скопирует <code>statusline-command.sh</code> в "
                "<code>~/.claude/</code> и пропишет блок <code>statusLine</code> "
                "в <code>~/.claude/settings.json</code>.<br>"
                "Кнопка <b>«Удалить»</b> сейчас неактивна — удалять пока нечего.<br><br>"
            )

        message = (
            state_line +
            tr("Status line — это строка внизу окна Claude Code, в которой видно "
               "текущую модель, заполненность контекста, ID сессии и git-репозиторий "
               "рабочей папки. Ниже — как именно он будет выглядеть.")
        )

        message_label = QLabel(message)
        message_label.setFont(QFont("Segoe UI", 10))
        message_label.setStyleSheet("color: #B5B5B5; background: transparent; border: none;")
        message_label.setAlignment(Qt.AlignLeft)
        message_label.setWordWrap(True)
        message_label.setTextFormat(Qt.RichText)
        layout.addWidget(message_label)

        # Если установлен — показываем текущую команду
        if has_existing and existing_command:
            existing_label = QLabel(tr("Текущая команда:") + f"\n{existing_command}")
            existing_label.setFont(QFont("Consolas", 8))
            existing_label.setStyleSheet("""
                QLabel {
                    color: rgba(220, 180, 100, 0.85);
                    background: rgba(245, 200, 80, 0.08);
                    border: 1px dashed rgba(245, 200, 80, 0.35);
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)
            existing_label.setWordWrap(True)
            layout.addWidget(existing_label)

        # Превью status line
        preview = StatusLinePreview()
        layout.addWidget(preview)

        # Кнопки: Отмена · Удалить · Установить
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.cancel_btn = StyledButton(tr("Отмена"))
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.remove_btn = StyledButton(tr("Удалить"))
        self.remove_btn.setMinimumHeight(40)
        self.remove_btn.set_hover_color(235, 90, 90)
        self.remove_btn.setEnabled(has_existing)
        self.remove_btn.clicked.connect(lambda: self.done(self.ACTION_REMOVE))
        btn_layout.addWidget(self.remove_btn)

        self.confirm_btn = GreenButton(tr("Переустановить") if has_existing else tr("Установить"))
        self.confirm_btn.setMinimumHeight(40)
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.adjustSize()
        self.setMinimumWidth(500)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        self._fade_out_and(lambda: super(StatusLineInstallDialog, self).accept())

    def reject(self):
        self._fade_out_and(lambda: super(StatusLineInstallDialog, self).reject())

    def done(self, code):
        # Поддержка кастомного кода (ACTION_REMOVE) с той же fade-анимацией
        if code == self.ACTION_REMOVE:
            self._fade_out_and(lambda: QDialog.done(self, self.ACTION_REMOVE))
        else:
            super().done(code)

    def _fade_out_and(self, then):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0); fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(then)
        fade.start(); self._fade = fade


# ============================================================
# ДИАЛОГ ПРОГРЕССА УСТАНОВКИ STATUS LINE
# ============================================================

class StatusLineProgressDialog(QDialog):
    """Окно с анимированным процент-баром: копирование sh-скрипта,
    запись settings.json. После 100% превращается в окно «Успешно установлено»."""
    progress_signal = Signal(int)
    finished_signal = Signal(bool, str)   # ok, error_message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._done = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        accent = (120, 200, 130)  # зелёный
        r, g, b = accent

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setObjectName("statusLineProgressContainer")
        container.setStyleSheet(f"""
            QFrame#statusLineProgressContainer {{
                background-color: rgb(20, 20, 25);
                border: 2px solid rgba({r}, {g}, {b}, 0.55);
                border-radius: 16px;
            }}
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(34, 28, 34, 26)
        layout.setSpacing(14)

        self.icon_label = QLabel("⌁")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                color: rgb({r}, {g}, {b});
                font-size: 26px; font-weight: bold;
                background: rgba({r}, {g}, {b}, 0.15);
                border: 2px solid rgba({r}, {g}, {b}, 0.4);
                border-radius: 25px;
                min-width: 50px; max-width: 50px;
                min-height: 50px; max-height: 50px;
            }}
        """)
        ic = QHBoxLayout()
        ic.addStretch(); ic.addWidget(self.icon_label); ic.addStretch()
        layout.addLayout(ic)

        self.title_lbl = QLabel(tr("Установка status line"))
        self.title_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.title_lbl.setStyleSheet(
            f"color: rgb({r}, {g}, {b}); background: transparent; border: none;"
        )
        self.title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_lbl)

        self.progress_bar = AnimatedProgressBar("#78C882")
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel(tr("Подготовка…"))
        self.status_lbl.setFont(QFont("Segoe UI", 10))
        self.status_lbl.setStyleSheet(
            "color: rgba(210, 210, 215, 0.9); background: transparent; border: none;"
        )
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        self.btn_ok = GreenButton(tr("Готово"))
        self.btn_ok.setMinimumHeight(38)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_ok.hide()
        btn_row = QHBoxLayout()
        btn_row.addStretch(); btn_row.addWidget(self.btn_ok); btn_row.addStretch()
        layout.addLayout(btn_row)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedWidth(420)

        self.progress_signal.connect(self._on_progress)
        self.finished_signal.connect(self._on_finished)

        # Плавная анимация процентов: тикаем сами, чтобы пользователь видел движение
        self._target_pct = 0
        self._pending_success = False
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._anim_tick)
        self._tick.start(20)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        self._tick.stop()
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0); fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(StatusLineProgressDialog, self).accept())
        fade.start(); self._fade = fade

    def reject(self):
        self._tick.stop()
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0); fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(StatusLineProgressDialog, self).reject())
        fade.start(); self._fade = fade

    def set_target(self, pct, status_text=None):
        self._target_pct = max(0, min(100, pct))
        if status_text is not None:
            self.status_lbl.setText(status_text)

    def _anim_tick(self):
        cur = self.progress_bar._progress
        if cur < self._target_pct:
            # Финал — догоняем быстрее, чтобы success-state не показывался при 46%
            step = 4 if self._target_pct >= 100 else 2
            cur = min(self._target_pct, cur + step)
            self.progress_bar.set_progress(cur)
        # Когда воркер уже завершился и бар добил до 100 — переключаем в success
        if self._pending_success and cur >= 100:
            self._pending_success = False
            self._show_success_state()

    def _on_progress(self, pct):
        self.set_target(pct)

    def mark_success(self):
        if self._done: return
        self._done = True
        self.set_target(100)
        # Не по фиксированному таймауту, а по факту: ждём пока бар реально дойдёт до 100
        self._pending_success = True

    def _show_success_state(self):
        self._tick.stop()
        self.icon_label.setText("✓")
        self.title_lbl.setText(tr("Status line установлен ✓"))
        self.status_lbl.setText(tr(
            "Скрипт скопирован в ~/.claude/statusline-command.sh,\n"
            "блок statusLine прописан в ~/.claude/settings.json.\n"
            "Запусти Claude Code — строка появится внизу окна."
        ))
        self.btn_ok.show()

    def mark_failed(self, message):
        if self._done: return
        self._done = True
        self._tick.stop()
        accent = (235, 110, 110)
        r, g, b = accent
        self.icon_label.setText("✗")
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                color: rgb({r}, {g}, {b});
                font-size: 26px; font-weight: bold;
                background: rgba({r}, {g}, {b}, 0.15);
                border: 2px solid rgba({r}, {g}, {b}, 0.4);
                border-radius: 25px;
                min-width: 50px; max-width: 50px;
                min-height: 50px; max-height: 50px;
            }}
        """)
        self.title_lbl.setText(tr("Не удалось установить"))
        self.title_lbl.setStyleSheet(
            f"color: rgb({r}, {g}, {b}); background: transparent; border: none;"
        )
        self.status_lbl.setText(message or tr("Неизвестная ошибка"))
        self.btn_ok.show()

    def _on_finished(self, ok, err):
        if ok:
            self.mark_success()
        else:
            self.mark_failed(err)


# ============================================================
# ДИАЛОГ «FIX CLAUDE» — переименование ~/.claude.json в .bak
# ============================================================

class ClaudeJsonFixDialog(QDialog):
    """Красное окно «Внимание» с описанием проблемы ~/.claude.json и кнопкой
    исправления. Файл не удаляется — переименовывается в .bak, можно откатить."""

    def __init__(self, json_path, json_exists, backup_target, parent=None):
        super().__init__(parent)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        accent = (235, 90, 90)  # красная рамка, как просили
        r, g, b = accent

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setObjectName("claudeJsonFixContainer")
        container.setStyleSheet(f"""
            QFrame#claudeJsonFixContainer {{
                background-color: rgb(20, 20, 25);
                border: 2px solid rgba({r}, {g}, {b}, 0.65);
                border-radius: 16px;
            }}
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(14)

        # Иконка-восклицание (красная)
        icon_label = QLabel("!")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                color: rgb({r}, {g}, {b});
                font-size: 28px;
                font-weight: bold;
                background: rgba({r}, {g}, {b}, 0.15);
                border: 2px solid rgba({r}, {g}, {b}, 0.4);
                border-radius: 25px;
                min-width: 50px; max-width: 50px;
                min-height: 50px; max-height: 50px;
            }}
        """)
        ic = QHBoxLayout()
        ic.addStretch(); ic.addWidget(icon_label); ic.addStretch()
        layout.addLayout(ic)

        # Заголовок «Внимание» красным
        title_label = QLabel(tr("Внимание"))
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet(
            f"color: rgb({r}, {g}, {b}); background: transparent; border: none;"
        )
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        #   екст с описанием проблемы и тем, что произойдёт
        if json_exists:
            state_line = tr(
                '<span style="color:#EB5A5A;"><b>● Найден файл ~/.claude.json.</b></span><br>'
                "У многих пользователей старые/несовместимые настройки из этого файла "
                "ломают первый запуск Claude Code: <b>ошибки API</b>, "
                "<b>Claude вообще не отвечает</b>, странные сбои авторизации. "
                "Особенно если ты раньше пользовался Claude Code через другие способы.<br><br>"
            )
        else:
            state_line = tr(
                '<span style="color:rgba(200,200,205,0.7);">● Файл ~/.claude.json не найден.</span><br>'
                "Исправлять нечего — этот фикс нужен только когда Claude Code "
                "не отвечает или возвращает ошибки API при первом запуске "
                "именно из-за старого <code>~/.claude.json</code>.<br><br>"
            )

        message = (
            state_line +
            tr("<b>Что сделает кнопка «Исправить»:</b><br>") +
            f"• " + tr("переименует") + f" <code>{self._short(json_path)}</code> "
            f"→ <code>{self._short(backup_target)}</code><br>"
            + tr("• оригинал <code>~/.claude.json</code> <b>не удаляется</b> — "
                 "остаётся как <code>.bak</code>, можно вернуть.<br>"
                 "• создаст свежий <code>~/.claude.json</code> с "
                 "<code>installMethod=global</code> и <code>autoUpdates=false</code>.<br>"
                 "• <b>пересоздаст</b> <code>~/.claude/settings.json</code> с нуля, "
                 "оставив только <code>env.DISABLE_UPDATES=1</code>. "
                 "Это убирает «зависшие» ключи вроде <code>apiKeyHelper</code>, "
                 "которые ломают авторизацию (Claude ругается «auth may not work» "
                 "и виснет на Retrying). Модель, эффорт и токен приложение "
                 "пропишет туда обратно само — настройки лежат в нём отдельно "
                 "и не теряются.<br>"
                 "• <code>DISABLE_UPDATES=1</code> — официальный способ выключить "
                 "автообновление Claude Code; без него CLI рано или поздно "
                 "обновится с зафиксированной v") + REQUIRED_CLAUDE_VERSION +
            tr(" до более новой версии, где FreeModel / Omniroute / прокси "
               "уже не работают.")
        )

        message_label = QLabel(message)
        message_label.setFont(QFont("Segoe UI", 10))
        message_label.setStyleSheet("color: #B5B5B5; background: transparent; border: none;")
        message_label.setAlignment(Qt.AlignLeft)
        message_label.setWordWrap(True)
        message_label.setTextFormat(Qt.RichText)
        layout.addWidget(message_label)

        # Подсказка «когда нажимать»
        hint_label = QLabel(tr(
            "Нажимай, только если у тебя реально проблемы: "
            "Claude Code не отвечает, выдаёт ошибки API, или ведёт себя странно "
            "после смены способа авторизации."
        ))
        hint_label.setFont(QFont("Segoe UI", 9))
        hint_label.setStyleSheet(f"""
            QLabel {{
                color: rgba(235, 140, 140, 0.95);
                background: rgba({r}, {g}, {b}, 0.08);
                border: 1px dashed rgba({r}, {g}, {b}, 0.35);
                border-radius: 6px;
                padding: 8px 12px;
            }}
        """)
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.cancel_btn = StyledButton(tr("Отмена"))
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.set_hover_color(235, 90, 90)  # красный hover — согласуется с акцентом окна
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.confirm_btn = GreenButton(tr("Исправить"))
        self.confirm_btn.setMinimumHeight(40)
        self.confirm_btn.setEnabled(json_exists)
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.adjustSize()
        self.setMinimumWidth(520)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    @staticmethod
    def _short(path):
        """~ вместо домашней папки + прямые слэши — компактно для текста."""
        try:
            home = os.path.expanduser("~")
            if path.lower().startswith(home.lower()):
                path = "~" + path[len(home):]
        except Exception:
            pass
        return path.replace("\\", "/")

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        self._fade_out_and(lambda: super(ClaudeJsonFixDialog, self).accept())

    def reject(self):
        self._fade_out_and(lambda: super(ClaudeJsonFixDialog, self).reject())

    def _fade_out_and(self, then):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0); fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(then)
        fade.start(); self._fade = fade


# ============================================================
# ОТСЛЕЖИВАНИЕ ЗАВЕРШЕНИЯ ПРОЦЕССА POWERSHELL
# ============================================================

class _ProcessWaiter(QObject):
    finished = Signal()

    def __init__(self, popen, parent=None):
        super().__init__(parent)
        self._popen = popen

    def run(self):
        try:
            self._popen.wait()
        except Exception:
            pass
        self.finished.emit()


# ============================================================
# МОДАЛЬНОЕ ОКНО РЕЗУЛЬТАТА ДОБАВЛЕНИЯ В PATH
# ============================================================

class DownloadUpdateDialog(QDialog):
    progress_updated = Signal(int, float, float)
    download_finished = Signal(bool, str)

    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.download_success = False
        self.downloaded_path = ""
        self._cancelled = False

        self.progress_updated.connect(self._update_progress)
        self.download_finished.connect(self._on_download_finished)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = DottedFrame()
        self.container.setObjectName("downloadUpdateContainer")
        self.container.setStyleSheet("""
            QFrame#downloadUpdateContainer {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgba(100, 180, 255, 0.6);
                border-radius: 16px;
            }
        """)

        cl = QVBoxLayout()
        cl.setContentsMargins(28, 20, 28, 20)
        cl.setSpacing(10)

        # Иконка
        self.icon_label = QLabel("↓")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("""
            QLabel {
                color: #64B4FF;
                font-size: 28px;
                font-weight: bold;
                background: rgba(100, 180, 255, 0.15);
                border: 2px solid rgba(100, 180, 255, 0.4);
                border-radius: 25px;
                min-width: 50px;
                max-width: 50px;
                min-height: 50px;
                max-height: 50px;
            }
        """)
        ic = QHBoxLayout()
        ic.addStretch()
        ic.addWidget(self.icon_label)
        ic.addStretch()

        # Заголовок
        self.title_label = QLabel("Скачивание обновления")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            QLabel {
                color: #64B4FF;
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)

        # Версия
        self.version_label = QLabel(f"Claude Code Manager v{update_info['latest']}")
        self.version_label.setAlignment(Qt.AlignCenter)
        self.version_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)

        # Прогресс бар
        self.progress_bar = AnimatedProgressBar("#5B9BD5")  # Мягкий синий

        # Сообщение
        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("""
            QLabel {
                color: #AAAAAA;
                font-size: 11px;
                background: transparent;
                border: none;
            }
        """)
        self.message_label.hide()

        # Горизонтальный layout для кнопок после скачивания
        self.success_buttons_layout = QHBoxLayout()
        self.success_buttons_layout.setSpacing(12)

        self.open_folder_btn = GreenButton("Открыть папку")
        self.open_folder_btn.setMinimumHeight(35)
        self.open_folder_btn.clicked.connect(self._open_folder)

        self.delete_old_btn = RedButton("Удалить старую")
        self.delete_old_btn.setMinimumHeight(35)
        self.delete_old_btn.clicked.connect(self._delete_old_and_open)

        self.success_buttons_layout.addWidget(self.open_folder_btn)
        self.success_buttons_layout.addWidget(self.delete_old_btn)

        # Контейнер для кнопок успеха
        self.success_buttons_widget = QWidget()
        self.success_buttons_widget.setLayout(self.success_buttons_layout)
        self.success_buttons_widget.hide()

        cl.addLayout(ic)
        cl.addWidget(self.title_label)
        cl.addWidget(self.version_label)
        cl.addWidget(self.progress_bar)
        cl.addWidget(self.message_label)
        cl.addWidget(self.success_buttons_widget)

        self.container.setLayout(cl)
        main_layout.addWidget(self.container)
        self.setLayout(main_layout)
        self.setFixedSize(360, 270)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(self.opacity_effect.opacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(DownloadUpdateDialog, self).accept())
        fade.start()
        self._fade_out = fade

    def reject(self):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(self.opacity_effect.opacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(DownloadUpdateDialog, self).reject())
        fade.start()
        self._fade_out = fade

    def start_download(self):
        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        new_exe_path = None
        try:
            # По умолчанию складываем рядом со старым .exe — так пользователь
            # увидит обновление в той же папке, где запускал приложение раньше.
            # Если запущены из python.exe (не скомпилировано) — fallback в Downloads.
            current_exe = sys.executable
            is_compiled = current_exe.lower().endswith('.exe') and 'python' not in current_exe.lower()
            if is_compiled and os.path.exists(current_exe):
                target_dir = os.path.dirname(current_exe)
            else:
                target_dir = os.path.join(os.path.expanduser("~"), "Downloads")

            # Имя нового файла содержит новую версию — НЕ совпадает с именем
            # запущенного .exe, чтобы не пытаться писать в файл, открытый ОС.
            # Это и было причиной "Could not load PKG archive" в прошлых попытках.
            new_exe_path = os.path.join(target_dir, f"ClaudeCodeManager_v{self.update_info['latest']}.exe")
            url = self.update_info['download_url']

            req = Request(url, headers={'User-Agent': 'ClaudeManager-Updater'})
            with urlopen(req, timeout=300, context=_ssl_context) as resp:
                total = int(resp.headers.get('Content-Length', 0))
                total_mb = total / (1024 * 1024)
                downloaded = 0

                with open(new_exe_path, 'wb') as f:
                    while True:
                        if self._cancelled:
                            f.close()
                            os.remove(new_exe_path)
                            return
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress_updated.emit(
                                int(downloaded * 100 / total),
                                downloaded / (1024 * 1024),
                                total_mb
                            )

            if self._cancelled:
                os.remove(new_exe_path)
                return

            self.downloaded_path = new_exe_path
            self.download_finished.emit(True, new_exe_path)

        except Exception as e:
            if self._cancelled and new_exe_path and os.path.exists(new_exe_path):
                try:
                    os.remove(new_exe_path)
                except:
                    pass
                return
            self.download_finished.emit(False, str(e))

    def _update_progress(self, percent, downloaded_mb, total_mb):
        self.progress_bar.set_progress(percent)
        self.progress_bar.set_size(downloaded_mb, total_mb)

    def _on_download_finished(self, success, message):
        if success:
            self.download_success = True
            self.title_label.setText("Обновление скачано!")
            self.icon_label.setText("✓")
            self.icon_label.setStyleSheet("""
                QLabel {
                    color: #64DC82;
                    font-size: 28px;
                    font-weight: bold;
                    background: rgba(100, 220, 130, 0.15);
                    border: 2px solid rgba(100, 220, 130, 0.4);
                    border-radius: 25px;
                    min-width: 50px;
                    max-width: 50px;
                    min-height: 50px;
                    max-height: 50px;
                }
            """)
            self.title_label.setStyleSheet("""
                QLabel {
                    color: #64DC82;
                    font-size: 16px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }
            """)

            # Кнопки выбора больше не нужны — финал авто-завершается:
            # старый .exe удаляется, открывается папка с новым файлом.
            self.message_label.setText("Завершаем обновление…")
            self.message_label.show()
            self.success_buttons_widget.hide()

            # Небольшая задержка, чтобы пользователь успел увидеть «Обновление скачано!»
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1200, self._delete_old_and_open)
        else:
            self.title_label.setText("Ошибка скачивания")
            self.icon_label.setText("✗")
            self.icon_label.setStyleSheet("""
                QLabel {
                    color: #FF5050;
                    font-size: 28px;
                    font-weight: bold;
                    background: rgba(255, 80, 80, 0.15);
                    border: 2px solid rgba(255, 80, 80, 0.4);
                    border-radius: 25px;
                    min-width: 50px;
                    max-width: 50px;
                    min-height: 50px;
                    max-height: 50px;
                }
            """)
            self.title_label.setStyleSheet("""
                QLabel {
                    color: #FF5050;
                    font-size: 16px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }
            """)
            self.message_label.setText(f"Ошибка: {message}")
            self.message_label.show()

    def _open_folder(self):
        """Просто открывает папку с новой версией"""
        subprocess.Popen(f'explorer /select,"{self.downloaded_path}"')
        self.accept()

    def _delete_old_and_open(self):
        """Завершает старый процесс, удаляет его .exe в фоне и запускает новую версию.

        Поток событий:
        1. Этот процесс пишет batch и **жёстко** убивает себя через os._exit() —
           QApplication.quit() не помогает, потому что мы внутри nested event
           loop модального диалога: quit() не разрывает его, процесс продолжает
           жить, файл .exe остаётся залоченным, batch ждёт PID впустую.
        2. Batch активно опрашивает tasklist по PID; как только процесса нет —
           ждёт ещё 2 секунды (на освобождение _MEI-папки PyInstaller),
           удаляет старый .exe, запускает новый и стирает сам себя.
        3. Если процесс почему-то не умер за 30 секунд — batch добивает его
           taskkill /F. Без этого fallback'а старый .exe навсегда залип бы
           на диске, как и сообщил пользователь.
        """
        current_exe = sys.executable
        is_compiled = current_exe.lower().endswith('.exe') and 'python' not in current_exe.lower()

        if not (is_compiled and os.path.exists(current_exe)):
            # Не скомпилировано (запуск из python) — нечего удалять,
            # просто открываем папку с новым файлом и закрываем диалог.
            try:
                subprocess.Popen(f'explorer /select,"{self.downloaded_path}"')
            except Exception:
                pass
            self.accept()
            return

        try:
            temp_dir = os.path.join(os.getenv('TEMP'), 'claude_update')
            os.makedirs(temp_dir, exist_ok=True)
            batch_path = os.path.join(temp_dir, "update_claude_code_manager.bat")
            vbs_path = os.path.join(temp_dir, "run_update.vbs")
            log_path = os.path.join(temp_dir, "update.log")
            pid = os.getpid()

            # Batch использует ping вместо timeout: timeout требует консольный
            # ввод и валится в detached/no-window режиме, из-за чего пауза не
            # срабатывала и файл не успевал разлочиться. ping -n N localhost
            # надёжно ждёт N-1 секунд без зависимости от консоли.
            script = (
                '@echo off\r\n'
                'setlocal\r\n'
                f'set "PID={pid}"\r\n'
                f'set "OLD_EXE={current_exe}"\r\n'
                f'set "NEW_EXE={self.downloaded_path}"\r\n'
                f'set "LOG={log_path}"\r\n'
                'echo [start] PID=%PID% OLD=%OLD_EXE% NEW=%NEW_EXE% > "%LOG%"\r\n'
                'set /a TRIES=0\r\n'
                ':wait_loop\r\n'
                'tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL\r\n'
                'if errorlevel 1 goto proc_dead\r\n'
                'set /a TRIES+=1\r\n'
                'if %TRIES% GEQ 30 goto force_kill\r\n'
                'ping -n 2 127.0.0.1 >NUL\r\n'
                'goto wait_loop\r\n'
                ':force_kill\r\n'
                'echo [force_kill] PID still alive, killing >> "%LOG%"\r\n'
                'taskkill /F /PID %PID% >>"%LOG%" 2>&1\r\n'
                'ping -n 3 127.0.0.1 >NUL\r\n'
                ':proc_dead\r\n'
                'echo [proc_dead] waiting for file unlock >> "%LOG%"\r\n'
                # 3 секунды на освобождение .exe и cleanup _MEI у PyInstaller
                'ping -n 4 127.0.0.1 >NUL\r\n'
                'echo [del] deleting old exe >> "%LOG%"\r\n'
                'del /f /q "%OLD_EXE%" >>"%LOG%" 2>&1\r\n'
                # Если первая попытка не сработала (Windows ещё держит handle),
                # ждём ещё и пробуем повторно. Раньше старый .exe оставался на
                # диске именно из-за этого race condition.
                'if exist "%OLD_EXE%" (\r\n'
                '  echo [del] retry after wait >> "%LOG%"\r\n'
                '  ping -n 4 127.0.0.1 >NUL\r\n'
                '  del /f /q "%OLD_EXE%" >>"%LOG%" 2>&1\r\n'
                ')\r\n'
                'echo [launch] starting new exe >> "%LOG%"\r\n'
                'start "" "%NEW_EXE%"\r\n'
                'echo [done] >> "%LOG%"\r\n'
                'endlocal\r\n'
                '(goto) 2>NUL & del /f /q "%~f0"\r\n'
            )
            with open(batch_path, 'w', encoding='cp866', errors='replace') as f:
                f.write(script)

            # VBS-обёртка: WScript.Shell.Run с флагом 0 запускает batch
            # абсолютно невидимо — никакого мелька консоли. Это
            # самый надёжный способ скрыть процесс на Windows; CREATE_NO_WINDOW
            # на cmd.exe всё равно даёт миллисекундную вспышку.
            # В VBS Chr(34) — это символ ", им обрамляем путь к .bat,
            # чтобы корректно отработать на путях с пробелами.
            vbs_content = (
                'Set oShell = CreateObject("WScript.Shell")\r\n'
                f'oShell.Run "cmd /c " & Chr(34) & "{batch_path}" & Chr(34), 0, False\r\n'
            )
            with open(vbs_path, 'w', encoding='ascii', errors='replace') as f:
                f.write(vbs_content)

            # wscript.exe — оконный хост скриптов: не создаёт консоль вообще,
            # никаких терминалов мелькать не будет.
            subprocess.Popen(
                ['wscript.exe', vbs_path],
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True,
            )

            # Жёсткий выход — QApplication.quit() застревает в nested event
            # loop модального диалога и процесс продолжает жить, держа .exe
            # залоченным. os._exit гарантирует мгновенную смерть процесса.
            os._exit(0)
        except Exception as e:
            self.message_label.setText(f"Ошибка: {e}")
            self.accept()

# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================


_ICON_SOURCE_CACHE = {"pixmap": None, "tried": False}
_TINTED_ICON_CACHE = {}
# Сид сессии — генерируется один раз при запуске, чтобы при каждом старте
# приложения иконки на фоне ложились в новых позициях, но в пределах
# одной сессии оставались стабильны (без "прыжков" при resize).
_PATTERN_SESSION_SEED = random.randint(0, 0xFFFFFFFF)


def _load_icon_source_pixmap():
    """Загружает icon.png один раз и кэширует."""
    if _ICON_SOURCE_CACHE["tried"]:
        return _ICON_SOURCE_CACHE["pixmap"]
    _ICON_SOURCE_CACHE["tried"] = True
    paths = [
        os.path.join(os.path.dirname(__file__), "icon.png"),
        os.path.join(os.path.dirname(sys.executable), "icon.png"),
        "icon.png",
    ]
    for p in paths:
        if os.path.exists(p):
            pm = QPixmap(p)
            if not pm.isNull():
                _ICON_SOURCE_CACHE["pixmap"] = pm
                return pm
    return None


def _get_tinted_icon(size, color):
    """Возвращает кэшированную иконку нужного размера, перекрашенную в `color`
    (сохраняя альфу оригинала)."""
    key = (size, color.rgba())
    if key in _TINTED_ICON_CACHE:
        return _TINTED_ICON_CACHE[key]
    src = _load_icon_source_pixmap()
    if src is None:
        _TINTED_ICON_CACHE[key] = None
        return None
    scaled = src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    tinted = QPixmap(scaled.size())
    tinted.fill(Qt.transparent)
    p = QPainter(tinted)
    p.setRenderHint(QPainter.Antialiasing)
    p.fillRect(tinted.rect(), color)
    p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    p.drawPixmap(0, 0, scaled)
    p.end()
    _TINTED_ICON_CACHE[key] = tinted
    return tinted


def _compute_icon_placements(width, height, icon_size, grid_step, instance_seed):
    """Считает позиции иконок без пересечений (Poisson-disk rejection sampling).

    Возвращает список `(x, y, rot_deg, scale)`. Использует общий
    `_PATTERN_SESSION_SEED` + `instance_seed` — поэтому при каждом запуске
    приложения и для каждого окна расклад уникальный, но в пределах одной
    сессии стабильный.

    Тяжёлая функция — результат должен быть закэширован вызывающим виджетом
    (поэтому здесь нет painter'а и QPixmap'а).
    """
    step = grid_step
    pad = step
    ext_w = width + 2 * pad
    ext_h = height + 2 * pad
    target_count = max(1, (ext_w * ext_h) // (step * step))

    rng = random.Random((_PATTERN_SESSION_SEED ^ instance_seed) & 0xFFFFFFFF)

    placements = []
    # Для быстрой проверки пересечений: каждая запись — (x, y, radius).
    placed = []
    max_attempts = 25
    half_icon = icon_size / 2.0

    for _ in range(target_count):
        for _attempt in range(max_attempts):
            x = rng.uniform(-pad, width + pad)
            y = rng.uniform(-pad, height + pad)
            scale = rng.uniform(0.75, 1.1)
            # Радиус ограничивающей окружности иконки с учётом масштаба.
            # Чуть-чуть уменьшаем (×0.92) — иконка не круглая, лучи можно
            # подпустить ближе чем строгая окружность позволила бы.
            r = half_icon * scale * 0.92
            ok = True
            for (px, py, pr) in placed:
                dx = x - px
                dy = y - py
                min_d = r + pr
                if dx * dx + dy * dy < min_d * min_d:
                    ok = False
                    break
            if ok:
                rot = rng.uniform(0, 360)
                placements.append((x, y, rot, scale))
                placed.append((x, y, r))
                break
            # rejected — rng уже сдвинулся, следующий attempt возьмёт новые числа
    return placements


def _paint_icon_placements(painter, placements, icon):
    """Рисует ранее посчитанный список позиций. Быстро, без RNG."""
    iw = icon.width()
    ih = icon.height()
    hx = iw // 2
    hy = ih // 2
    for (x, y, rot, scale) in placements:
        painter.save()
        painter.translate(x, y)
        painter.rotate(rot)
        painter.scale(scale, scale)
        painter.drawPixmap(-hx, -hy, icon)
        painter.restore()


class DottedBackground(QWidget):
    """Тёмный фон с разбросанными едва заметными иконками приложения."""

    BASE_COLOR = QColor(20, 20, 25)
    ICON_COLOR = QColor(38, 38, 46)  # чуть светлее фона
    ICON_SIZE = 56
    GRID_STEP = 130

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pattern_seed = random.randint(0, 0xFFFFFFFF)
        self._cached_size = None
        self._cached_placements = None

    def _get_placements(self, w, h):
        key = (w, h)
        if self._cached_size != key:
            self._cached_placements = _compute_icon_placements(
                w, h, self.ICON_SIZE, self.GRID_STEP, self._pattern_seed,
            )
            self._cached_size = key
        return self._cached_placements

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), self.BASE_COLOR)
        icon = _get_tinted_icon(self.ICON_SIZE, self.ICON_COLOR)
        if icon is None or icon.isNull():
            return
        _paint_icon_placements(painter, self._get_placements(self.width(), self.height()), icon)


class DottedFrame(QFrame):
    """QFrame, поверх styled background которого отрисованы иконки приложения.
    Сохраняет существующий QSS (border, border-radius) и добавляет паттерн внутрь.

    У каждого экземпляра свой `_pattern_seed`, поэтому каждое окно при открытии
    получает уникальный расклад иконок. Позиции пересчитываются только при
    изменении размера.
    """

    ICON_COLOR = QColor(38, 38, 46)
    ICON_SIZE = 44
    GRID_STEP = 100
    MARGIN = 14  # отступ от краёв, чтобы иконки не цеплялись за скруглённый бордер

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pattern_seed = random.randint(0, 0xFFFFFFFF)
        self._cached_size = None
        self._cached_placements = None

    def _get_placements(self, w, h):
        key = (w, h)
        if self._cached_size != key:
            self._cached_placements = _compute_icon_placements(
                w, h, self.ICON_SIZE, self.GRID_STEP, self._pattern_seed,
            )
            self._cached_size = key
        return self._cached_placements

    def paintEvent(self, event):
        super().paintEvent(event)  # стиль рисует background + border
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        m = self.MARGIN
        inner_w = max(0, self.width() - m * 2)
        inner_h = max(0, self.height() - m * 2)
        if inner_w == 0 or inner_h == 0:
            return
        icon = _get_tinted_icon(self.ICON_SIZE, self.ICON_COLOR)
        if icon is None or icon.isNull():
            return
        painter.setClipRect(m, m, inner_w, inner_h)
        painter.translate(m, m)
        _paint_icon_placements(painter, self._get_placements(inner_w, inner_h), icon)


class ClaudeManager(QMainWindow):
    status_changed = Signal(bool)
    update_available = Signal(dict)  # Новый сигнал для обновлений
    claude_version_checked = Signal(str, str, str)  # local_version, latest_version, latest_date_iso
    claude_install_finished = Signal(object)  # context dict
    freemodel_status_signal = Signal(str)  # overall статус freemodel.dev сервиса

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claude Code Manager")
        self.setFixedWidth(700)
        # Стартовая высота — зависит от сохранённого режима
        _is_fm = self.settings.get("use_custom_token", False) if False else False
        # Будет переустановлено в toggle_custom_token_fields()
        self.resize(700, 905)

        # Устанавливаем иконку - ищем в разных местах
        icon_paths = [
            os.path.join(os.path.dirname(__file__), "icon.ico"),
            os.path.join(os.path.dirname(sys.executable), "icon.ico"),
            "icon.ico"
        ]

        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                break

        self.settings = load_settings()
        self.omniroute_process = None

        # Подключаем сигналы к слотам
        self.status_changed.connect(self.update_status)
        self.update_available.connect(self._show_update_notification)

        # Центральный виджет — фон в крапинку
        central = DottedBackground()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Заголовок с иконкой
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)

        # Добавляем растяжку слева для центрирования
        title_layout.addStretch()

        # Иконка
        icon_label = QLabel()
        icon_paths = [
            os.path.join(os.path.dirname(__file__), "icon.png"),
            os.path.join(os.path.dirname(sys.executable), "icon.png"),
            "icon.png"
        ]

        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                icon_pixmap = QPixmap(icon_path)
                if not icon_pixmap.isNull():
                    icon_label.setPixmap(icon_pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                break

        title_layout.addWidget(icon_label)

        # Текст заголовка с шиммером
        self.title = QLabel()
        self.title.setFont(QFont("Consolas", 17, QFont.Bold))
        self.title.setAlignment(Qt.AlignCenter)
        # Сразу устанавливаем HTML чтобы не было прыжков
        text = "CLAUDE CODE MANAGER"
        html = ''.join([f'<span style="color: rgb(140, 140, 145);">{char}</span>' for char in text])
        self.title.setText(html)
        self.title.setFixedHeight(30)
        title_layout.addWidget(self.title)

        # Балансир под иконку: пустой виджет той же ширины (48px) справа от текста.
        # Без него иконка слева оптически сдвигает текст вправо относительно центра
        # окна — с балансиром тайтл стоит строго по центру.
        title_balance = QWidget()
        title_balance.setFixedWidth(48)
        title_balance.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title_layout.addWidget(title_balance)

        # Растяжка справа
        title_layout.addStretch()

        # Таймер для шиммера
        self._shimmer_offset = -0.3
        self._shimmer_timer = QTimer()
        self._shimmer_timer.timeout.connect(self._animate_shimmer)
        self._shimmer_timer.start(30)

        # Проверка обновлений в фоне
        self.update_info = None
        threading.Thread(target=self._check_for_updates, daemon=True).start()

        # Один общий лок на чтение-запись ~/.claude.json и ~/.claude/settings.json.
        # Берётся стартовыми стражами и Fix Claude — чтобы не было «last write wins»,
        # если пользователь нажмёт Fix Claude в первые миллисекунды после старта,
        # когда стартовый страж ещё не закончил мержить settings.json.
        self._claude_files_lock = threading.Lock()

        # Тихо подстраховываемся: дописываем env.DISABLE_UPDATES=1 в
        # ~/.claude/settings.json, если его там нет. Без этого Claude Code
        # рано или поздно самообновится и сломает FreeModel/Omniroute.
        threading.Thread(target=self._ensure_disable_updates_in_settings, daemon=True).start()

        # Дублирующая подстраховка: дописываем autoUpdates=false в ~/.claude.json,
        # если его там нет. Этот ключ официально не задокументирован и часто
        # игнорируется CLI, но если вдруг его уважает — нам ничего не стоит
        # его поставить. Основное выключение всё равно идёт через DISABLE_UPDATES.
        threading.Thread(target=self._ensure_auto_updates_false_in_claude_json, daemon=True).start()

        main_layout.addLayout(title_layout)

        # Переключатель режимов FreeModel ↔ Omniroute (под заголовком, по центру)
        mode_row = QHBoxLayout()
        mode_row.addStretch()
        self.mode_toggle = ModeToggle(omniroute_mode=not self.settings.get("use_custom_token", False))
        self.mode_toggle.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_toggle)
        mode_row.addStretch()
        main_layout.addLayout(mode_row)

        # Ряд кнопок: установка фиксированной версии Claude Code + удаление
        install_row = QHBoxLayout()
        install_row.addStretch()

        self.btn_install_claude = StyledButton(tr("Установить Claude Code") + f" v{REQUIRED_CLAUDE_VERSION}")
        self.btn_install_claude.setFixedHeight(34)
        self.btn_install_claude.clicked.connect(self._install_claude_code)
        install_row.addWidget(self.btn_install_claude)

        self.btn_uninstall_claude = StyledButton(tr("Удалить Claude Code"))
        self.btn_uninstall_claude.setFixedHeight(34)
        self.btn_uninstall_claude.set_hover_color(235, 90, 90)  # красный hover
        self.btn_uninstall_claude.clicked.connect(self._uninstall_claude_code)
        install_row.addWidget(self.btn_uninstall_claude)

        self.btn_install_statusline = StyledButton(tr("Status line"))
        self.btn_install_statusline.setFixedHeight(34)
        self.btn_install_statusline.set_hover_color(120, 180, 230)  # нейтральный голубоватый hover
        self.btn_install_statusline.clicked.connect(self._on_statusline_button_clicked)
        install_row.addWidget(self.btn_install_statusline)

        # Fix Claude — переименовывает проблемный ~/.claude.json в .bak.
        # Нужен пользователям, у которых Claude Code не отвечает / выдаёт ошибки API
        # после миграции с других способов запуска.
        self.btn_fix_claude = StyledButton(tr("Fix Claude"))
        self.btn_fix_claude.setFixedHeight(34)
        self.btn_fix_claude.set_hover_color(235, 90, 90)  # красный hover — это «лечебное» действие
        self.btn_fix_claude.clicked.connect(self._on_fix_claude_button_clicked)
        install_row.addWidget(self.btn_fix_claude)

        install_row.addStretch()
        main_layout.addLayout(install_row)

        # Индикатор обновления (абсолютная позиция в правом верхнем углу)
        self.update_indicator = UpdateIndicator(self)
        self.update_indicator.clicked.connect(self._on_update_indicator_clicked)
        self.update_indicator.move(self.width() - 45, 10)  # 10px от верха, 45px от правого края
        self.update_indicator.raise_()

        # Переключатель языка интерфейса EN / RU — абсолютная позиция в правом
        # верхнем углу, чуть левее индикатора обновлений. Цвет пилюли меняется
        # плавно: EN — зелёный (#34d399, цвет «freemodel»), RU — голубоватый.
        self.language_toggle = LanguageToggle(LANG.lang if LANG else "ru", self)
        self.language_toggle.move(self.width() - 45 - 96 - 10, 16)
        self.language_toggle.raise_()
        self.language_toggle.toggled.connect(self._on_language_toggled)
        if LANG is not None:
            LANG.language_changed.connect(self._on_language_changed)

        # Бейдж freemodel.dev — абсолютная позиция в левом верхнем углу.
        # Точка справа от текста меняет цвет в зависимости от состояния сервиса.
        self.freemodel_brand = FreemodelBrand(self)
        self.freemodel_brand.move(12, 22)
        self.freemodel_brand.raise_()
        self.freemodel_status_signal.connect(self.freemodel_brand.set_status)
        self.freemodel_brand.clicked.connect(self._open_freemodel_stats)
        # Серая подсказка-стрелка «клик» → указывает на бейдж. Размещаем так,
        # чтобы остриё стрелки приходилось чуть ниже текста freemodel.dev,
        # а «клик» был справа-снизу. Прозрачен для мыши — не мешает клику.
        self.freemodel_click_hint = _FmClickHint(self)
        self.freemodel_click_hint.move(0, 36)
        self.freemodel_click_hint.raise_()
        # Фоновый поллер API статуса freemodel.dev — 60с между запросами,
        # ошибки сети откатывают индикатор в нейтральное состояние.
        threading.Thread(target=self._poll_freemodel_status, daemon=True).start()
        # Бейдж виден только когда выбран freemodel-эндпоинт.
        QTimer.singleShot(0, self._refresh_freemodel_brand_visibility)

        # Секция Omniroute
        omniroute_frame = QFrame()
        omniroute_frame.setObjectName("omniroute_frame")
        self.omniroute_frame = omniroute_frame
        omniroute_frame.setStyleSheet("""
            QFrame#omniroute_frame {
                background-color: rgba(30, 30, 35, 200);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 8px;
            }
        """)
        omniroute_layout = QVBoxLayout(omniroute_frame)

        # Заголовок с индикатором
        header_layout = QHBoxLayout()
        omniroute_label = QLabel("Omniroute")
        omniroute_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        omniroute_label.setStyleSheet(
            "color: rgb(200, 200, 200); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 8px; padding: 4px 10px;"
        )
        header_layout.addWidget(omniroute_label)

        self.status_indicator = StatusIndicator()
        header_layout.addWidget(self.status_indicator)

        self.status_label = QLabel(tr("Не запущен"))
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet("color: rgb(150, 150, 150);")
        header_layout.addWidget(self.status_label)
        header_layout.addStretch()

        omniroute_layout.addLayout(header_layout)

        # Кнопки управления Omniroute
        omniroute_btn_layout = QHBoxLayout()

        self.btn_start_omniroute = GreenButton(tr("Запустить Omniroute"))
        self.btn_start_omniroute.clicked.connect(self.start_omniroute)
        self._btn_start_omniroute_dim = QGraphicsOpacityEffect()
        self._btn_start_omniroute_dim.setOpacity(1.0)
        self.btn_start_omniroute.setGraphicsEffect(self._btn_start_omniroute_dim)
        omniroute_btn_layout.addWidget(self.btn_start_omniroute)

        self.btn_stop_omniroute = RedButton(tr("Остановить Omniroute"))
        self.btn_stop_omniroute.clicked.connect(self.stop_omniroute)
        self.btn_stop_omniroute.setEnabled(False)
        omniroute_btn_layout.addWidget(self.btn_stop_omniroute)

        omniroute_layout.addLayout(omniroute_btn_layout)

        # Opacity-эффект на весь блок Omniroute (для плавного затемнения в FreeModel режиме)
        self._omniroute_frame_dim = QGraphicsOpacityEffect()
        self._omniroute_frame_dim.setOpacity(1.0)
        omniroute_frame.setGraphicsEffect(self._omniroute_frame_dim)

        main_layout.addWidget(omniroute_frame)

        # Секция Claude Code
        claude_frame = QFrame()
        claude_frame.setObjectName("claude_frame")
        claude_frame.setStyleSheet("""
            QFrame#claude_frame {
                background-color: rgba(30, 30, 35, 200);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 8px;
            }
        """)
        claude_layout = QVBoxLayout(claude_frame)

        claude_header_chip = QFrame()
        claude_header_chip.setObjectName("claude_header_chip")
        claude_header_chip.setStyleSheet(
            "QFrame#claude_header_chip { background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 8px; }"
        )
        claude_header_inner = QHBoxLayout(claude_header_chip)
        claude_header_inner.setContentsMargins(10, 4, 10, 4)
        claude_header_inner.setSpacing(8)

        claude_label = QLabel("Claude Code")
        claude_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        claude_label.setStyleSheet("color: rgb(200, 200, 200); background: transparent; border: none;")
        claude_header_inner.addWidget(claude_label)

        self.claude_install_indicator = StatusIndicator()
        claude_header_inner.addWidget(self.claude_install_indicator)

        self.claude_install_status_label = QLabel(tr("Не установлен"))
        self.claude_install_status_label.setFont(QFont("Segoe UI", 10))
        self.claude_install_status_label.setStyleSheet("color: rgb(150, 150, 150); background: transparent; border: none;")
        claude_header_inner.addWidget(self.claude_install_status_label)

        claude_header_inner.addStretch()
        claude_layout.addWidget(claude_header_chip)

        # Выбор модели — обёрнут в контейнер чтобы можно было скрыть целиком
        self.model_section_widget = QWidget()
        model_section_layout = QVBoxLayout(self.model_section_widget)
        model_section_layout.setContentsMargins(0, 0, 0, 0)
        model_section_layout.setSpacing(8)

        model_layout = QHBoxLayout()
        model_label = QLabel(tr("Модель:"))
        model_label.setFont(QFont("Segoe UI", 10))
        model_label.setStyleSheet(
            "color: rgb(180, 180, 180); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 6px; padding: 4px 8px;"
        )
        model_layout.addWidget(model_label)
        self._track_tr(model_label, "Модель:")

        self.model_combo = PickerComboBox()
        self.model_list_model = ModelListModel(self.settings["models"])
        self.model_combo.setModel(self.model_list_model)
        self.model_combo.setCurrentText(self.settings["selected_model"])
        self.model_combo.setMaxVisibleItems(4)
        self.model_combo.set_picker(title=tr("Выбор модели Omniroute"))
        model_layout.addWidget(self.model_combo, 1)

        model_section_layout.addLayout(model_layout)

        # Кнопки управления моделями
        model_btn_layout = QHBoxLayout()

        self.btn_add_model = GreenButton(tr("Добавить модель"))
        self.btn_add_model.clicked.connect(self.add_model)
        model_btn_layout.addWidget(self.btn_add_model)

        self.btn_remove_model = RedButton(tr("Удалить модель"))
        self.btn_remove_model.clicked.connect(self.remove_model)
        model_btn_layout.addWidget(self.btn_remove_model)

        model_section_layout.addLayout(model_btn_layout)
        claude_layout.addWidget(self.model_section_widget)

        # Opacity effects для модели (применяем к комбо и кнопкам)
        self._model_combo_dim = QGraphicsOpacityEffect(); self._model_combo_dim.setOpacity(1.0)
        self._btn_add_dim = QGraphicsOpacityEffect(); self._btn_add_dim.setOpacity(1.0)
        self._btn_remove_dim = QGraphicsOpacityEffect(); self._btn_remove_dim.setOpacity(1.0)
        self.model_combo.setGraphicsEffect(self._model_combo_dim)
        self.btn_add_model.setGraphicsEffect(self._btn_add_dim)
        self.btn_remove_model.setGraphicsEffect(self._btn_remove_dim)

        # Токен авторизации — обёрнут в контейнер
        self.token_section_widget = QWidget()
        token_section_outer = QVBoxLayout(self.token_section_widget)
        token_section_outer.setContentsMargins(0, 0, 0, 0)
        token_section_outer.setSpacing(0)
        self.token_layout = QHBoxLayout()

        self.token_label = QLabel(tr("API ключ:"))
        self.token_label.setFont(QFont("Segoe UI", 10))
        self.token_label.setStyleSheet(
            "color: rgb(180, 180, 180); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 6px; padding: 4px 8px;"
        )
        self.token_layout.addWidget(self.token_label)

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("sk-xxxxxxxx...")
        self.token_input.setText(self.settings.get("auth_token", ""))
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setFont(QFont("Segoe UI", 9))
        # Если токен уже сохранен, делаем поле только для чтения
        if self.settings.get("auth_token", ""):
            self.token_input.setReadOnly(True)
            self.token_input.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(20, 20, 25, 200);
                    color: rgb(200, 200, 200);
                    border: 1px solid rgb(60, 60, 65);
                    border-radius: 4px;
                    padding: 6px;
                }
            """)
        else:
            self.token_input.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(30, 30, 35, 200);
                    color: rgb(200, 200, 200);
                    border: 1px solid rgb(60, 60, 65);
                    border-radius: 4px;
                    padding: 6px;
                }
            """)
        self.token_layout.addWidget(self.token_input, 1)

        self.btn_toggle_token = EyeToggleButton()
        self.btn_toggle_token.clicked.connect(self.toggle_token_visibility)
        self.token_layout.addWidget(self.btn_toggle_token)

        self.btn_save_token = StyledButton(tr("Сохранить"))
        self.btn_save_token.setMaximumWidth(100)
        self.btn_save_token.clicked.connect(self.save_token)
        # Если токен уже сохранен, скрываем кнопку сохранить
        if self.settings.get("auth_token", ""):
            self.btn_save_token.hide()
        self.token_layout.addWidget(self.btn_save_token)

        self.btn_edit_token = StyledButton(tr("Изменить"))
        self.btn_edit_token.setMaximumWidth(100)
        self.btn_edit_token.clicked.connect(self.edit_token)
        # Если токен не сохранен, скрываем кнопку изменить
        if not self.settings.get("auth_token", ""):
            self.btn_edit_token.hide()
        self.token_layout.addWidget(self.btn_edit_token)

        token_section_outer.addLayout(self.token_layout)
        claude_layout.addWidget(self.token_section_widget)

        # Opacity effects для токена
        self._token_label_dim = QGraphicsOpacityEffect(); self._token_label_dim.setOpacity(1.0)
        self._token_input_dim = QGraphicsOpacityEffect(); self._token_input_dim.setOpacity(1.0)
        self._btn_toggle_token_dim = QGraphicsOpacityEffect(); self._btn_toggle_token_dim.setOpacity(1.0)
        self._btn_save_token_dim = QGraphicsOpacityEffect(); self._btn_save_token_dim.setOpacity(1.0)
        self._btn_edit_token_dim = QGraphicsOpacityEffect(); self._btn_edit_token_dim.setOpacity(1.0)
        self.token_label.setGraphicsEffect(self._token_label_dim)
        self.token_input.setGraphicsEffect(self._token_input_dim)
        self.btn_toggle_token.setGraphicsEffect(self._btn_toggle_token_dim)
        self.btn_save_token.setGraphicsEffect(self._btn_save_token_dim)
        self.btn_edit_token.setGraphicsEffect(self._btn_edit_token_dim)

        # Скрытый старый toggle (для совместимости логики)
        self.use_custom_token_checkbox = ToggleSwitch(checked=self.settings.get("use_custom_token", False))
        self.use_custom_token_checkbox.toggled.connect(self.toggle_custom_token_fields)
        self.use_custom_token_checkbox.hide()

        # Секция FreeModel — все настройки inline
        self.freemodel_section_widget = QWidget()
        freemodel_layout = QVBoxLayout(self.freemodel_section_widget)
        freemodel_layout.setContentsMargins(0, 0, 0, 0)
        freemodel_layout.setSpacing(8)

        # Base URL: label + combo + manage button
        url_row = QHBoxLayout()
        url_lbl = QLabel("Base URL:")
        url_lbl.setFont(QFont("Segoe UI", 10))
        url_lbl.setStyleSheet(
            "color: rgb(180, 180, 180); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 6px; padding: 4px 8px;"
        )
        url_lbl.setFixedWidth(90)
        url_row.addWidget(url_lbl)

        self.fm_url_combo = PickerComboBox()
        self.fm_url_combo.setFont(QFont("Segoe UI", 9))
        self.fm_url_combo.setMaxVisibleItems(4)
        self.fm_url_combo.addItems(self.settings.get("custom_base_urls", []))
        if self.settings.get("custom_base_url"):
            self.fm_url_combo.setCurrentText(self.settings["custom_base_url"])
        self.fm_url_combo.set_picker(title=tr("Выбор Base URL"))
        self.fm_url_combo.currentTextChanged.connect(self._fm_url_changed)
        url_row.addWidget(self.fm_url_combo, 1)

        self.fm_btn_manage = StyledButton(tr("Управление"))
        self.fm_btn_manage.setMinimumHeight(0)
        self.fm_btn_manage.setFixedHeight(36)
        self.fm_btn_manage.setFixedWidth(130)
        self.fm_btn_manage.clicked.connect(self._fm_manage_urls)
        url_row.addWidget(self.fm_btn_manage)
        freemodel_layout.addLayout(url_row)

        # API key: label + input + show/save
        key_row = QHBoxLayout()
        key_lbl = QLabel(tr("API ключ:"))
        key_lbl.setFont(QFont("Segoe UI", 10))
        key_lbl.setStyleSheet(
            "color: rgb(180, 180, 180); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 6px; padding: 4px 8px;"
        )
        key_lbl.setFixedWidth(90)
        self._track_tr(key_lbl, "API ключ:")
        key_row.addWidget(key_lbl)

        self.fm_key_input = QLineEdit()
        self.fm_key_input.setPlaceholderText("fe_oa_xxxxx...")
        self.fm_key_input.setText(self.settings.get("custom_api_key", ""))
        self.fm_key_input.setEchoMode(QLineEdit.Password)
        self.fm_key_input.setFont(QFont("Segoe UI", 9))
        _has_fm_key = bool(self.settings.get("custom_api_key", ""))
        if _has_fm_key:
            self.fm_key_input.setReadOnly(True)
            self.fm_key_input.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(20, 20, 25, 200);
                    color: rgb(200, 200, 200);
                    border: 1px solid rgb(60, 60, 65);
                    border-radius: 4px;
                    padding: 8px;
                }
            """)
        else:
            self.fm_key_input.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(30, 30, 35, 200);
                    color: rgb(200, 200, 200);
                    border: 1px solid rgb(60, 60, 65);
                    border-radius: 4px;
                    padding: 8px;
                }
            """)
        key_row.addWidget(self.fm_key_input, 1)

        self.fm_btn_toggle_key = EyeToggleButton()
        self.fm_btn_toggle_key.clicked.connect(self._fm_toggle_key)
        key_row.addWidget(self.fm_btn_toggle_key)

        self.fm_btn_save_key = StyledButton(tr("Сохранить"))
        self.fm_btn_save_key.setMinimumHeight(0)
        self.fm_btn_save_key.setFixedHeight(36)
        self.fm_btn_save_key.setFixedWidth(110)
        self.fm_btn_save_key.clicked.connect(self._fm_save_key)
        if _has_fm_key:
            self.fm_btn_save_key.hide()
        key_row.addWidget(self.fm_btn_save_key)

        self.fm_btn_edit_key = StyledButton(tr("Изменить"))
        self.fm_btn_edit_key.setMinimumHeight(0)
        self.fm_btn_edit_key.setFixedHeight(36)
        self.fm_btn_edit_key.setFixedWidth(110)
        self.fm_btn_edit_key.clicked.connect(self._fm_edit_key)
        if not _has_fm_key:
            self.fm_btn_edit_key.hide()
        key_row.addWidget(self.fm_btn_edit_key)
        freemodel_layout.addLayout(key_row)

        # Model: label + combo
        model_row = QHBoxLayout()
        model_lbl = QLabel(tr("Модель:"))
        model_lbl.setFont(QFont("Segoe UI", 10))
        model_lbl.setStyleSheet(
            "color: rgb(180, 180, 180); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 6px; padding: 4px 8px;"
        )
        self._track_tr(model_lbl, "Модель:")
        model_lbl.setFixedWidth(90)
        model_row.addWidget(model_lbl)

        self.fm_model_combo = PickerComboBox()
        self.fm_model_combo.setFont(QFont("Segoe UI", 9))
        self.fm_model_combo.setMaxVisibleItems(4)
        fm_models = ["Fable 5", "Opus 4.8", "Opus 4.7", "Opus 4.6", "Sonnet 4.6"]
        self.fm_model_combo.addItems(fm_models)
        # Цвета для каждой модели (от зелёного к красному — по «дороговизне»)
        model_colors = {
            "Sonnet 4":     QColor(120, 220, 120),  # зелёный
            "Sonnet 4.6":   QColor(180, 235, 150),  # светло-зелёный
            "Opus 4.6":     QColor(230, 220, 130),  # слегка жёлтый
            "Opus 4.7":     QColor(235, 180, 110),  # жёлтый с переходом в красноватый
            "Opus 4.8":     QColor(235, 150, 130),  # слабо красноватый
            "Fable 5":   QColor(235, 90, 90),    # красный
        }
        self._fm_model_colors = model_colors
        model_tooltips = {}
        for i in range(self.fm_model_combo.count()):
            txt = self.fm_model_combo.itemText(i)
            if txt in model_colors:
                self.fm_model_combo.setItemData(i, model_colors[txt], Qt.ForegroundRole)
            if txt in model_tooltips:
                self.fm_model_combo.setItemData(i, model_tooltips[txt], Qt.ToolTipRole)
        self.fm_model_combo.set_picker(
            colors=model_colors,
            tooltips=model_tooltips,
            title=tr("Выбор модели"),
            disabled=["Fable 5"],
        )
        self.fm_model_combo.blockedPicked.connect(self._fm_show_fable5_blocked)
        saved_m = self.settings.get("custom_model", "Opus 4.8")
        remap = {
            "default (claude-opus-4-8)": "Opus 4.8",
            "Opus 4.8 (default)": "Opus 4.8",
            "claude-sonnet-4-6 (/model → 2)": "Sonnet 4.6",
            "claude-sonnet-4-6": "Sonnet 4.6",
            "claude-opus-4-7": "Opus 4.7",
            "claude-opus-4-6": "Opus 4.6",
            "claude-fable-5": "Fable 5",
        }
        saved_m = remap.get(saved_m, saved_m)
        # Fable 5 заблокирована — нельзя оставлять её как сохранённую выбранную модель
        if saved_m == "Fable 5":
            saved_m = "Opus 4.8"
            self.settings["custom_model"] = saved_m
            save_settings(self.settings)
        if saved_m in fm_models:
            self.fm_model_combo.setCurrentText(saved_m)
        # Начальный цвет текста и рамки под выбранную модель
        if saved_m in model_colors:
            self.fm_model_combo.setTextColor(model_colors[saved_m])
            self.fm_model_combo.setAccentColor(model_colors[saved_m])
        self.fm_model_combo.currentTextChanged.connect(self._fm_model_changed)
        model_row.addWidget(self.fm_model_combo, 1)

        # Effort selector для FreeModel (без отдельного лейбла — сам комбобокс показывает уровень)
        self.fm_effort_combo = PickerComboBox()
        self.fm_effort_combo.setFont(QFont("Segoe UI", 9))
        fm_efforts = ["low", "medium", "high", "xhigh", "max"]
        self.fm_effort_combo.addItems(fm_efforts)
        saved_fm_effort = self.settings.get("reasoning_effort", "high")
        if saved_fm_effort in fm_efforts:
            self.fm_effort_combo.setCurrentText(saved_fm_effort)
        else:
            self.fm_effort_combo.setCurrentText("high")
        self.fm_effort_combo.setMaxVisibleItems(5)
        fm_effort_colors = {
            "low": QColor(120, 220, 120),
            "medium": QColor(180, 210, 130),
            "high": QColor(235, 180, 110),
            "xhigh": QColor(235, 150, 130),
            "max": QColor(235, 90, 90),
        }
        self._fm_effort_colors = fm_effort_colors
        self.fm_effort_combo.set_picker(
            colors=fm_effort_colors,
            title="Reasoning Effort"
        )
        # Начальный цвет текста и рамки под выбранный effort
        if saved_fm_effort in fm_effort_colors:
            self.fm_effort_combo.setTextColor(fm_effort_colors[saved_fm_effort])
            self.fm_effort_combo.setAccentColor(fm_effort_colors[saved_fm_effort])
        self.fm_effort_combo.currentTextChanged.connect(self._on_effort_changed)
        model_row.addWidget(self.fm_effort_combo, 0)

        freemodel_layout.addLayout(model_row)

        # Скрытая кнопка для совместимости со старым кодом
        self.btn_configure_custom = StyledButton(tr("Настроить"))
        self.btn_configure_custom.hide()
        self._btn_configure_custom_dim = QGraphicsOpacityEffect()
        self._btn_configure_custom_dim.setOpacity(1.0)

        claude_layout.addWidget(self.freemodel_section_widget)

        # Применяем начальное состояние видимости секций
        self.toggle_custom_token_fields()

        # Выбор рабочей директории
        dir_layout = QHBoxLayout()

        dir_label = QLabel(tr("Директория:"))
        self._track_tr(dir_label, "Директория:")
        dir_label.setFont(QFont("Segoe UI", 10))
        dir_label.setStyleSheet(
            "color: rgb(180, 180, 180); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 6px; padding: 4px 8px;"
        )
        dir_layout.addWidget(dir_label)

        self.dir_input = QLineEdit()
        self.dir_input.setReadOnly(True)
        self.dir_input.setPlaceholderText(tr("Не выбрана (будет запрошена)"))
        self.dir_input.setText(self.settings.get("working_directory", ""))
        self.dir_input.setFont(QFont("Segoe UI", 9))
        self.dir_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 35, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 6px;
            }
        """)
        dir_layout.addWidget(self.dir_input, 1)

        btn_browse = StyledButton(tr("Обзор"))
        btn_browse.setMaximumWidth(80)
        btn_browse.clicked.connect(self.browse_directory)
        dir_layout.addWidget(btn_browse)
        self._track_tr(btn_browse, "Обзор")

        btn_clear = StyledButton(tr("Очистить"))
        btn_clear.setMaximumWidth(80)
        btn_clear.clicked.connect(self.clear_directory)
        dir_layout.addWidget(btn_clear)
        self._track_tr(btn_clear, "Очистить")

        claude_layout.addLayout(dir_layout)

        # Кнопка запуска Claude Code
        self.btn_claude = GreenButton(tr("Запустить Claude Code"))
        self.btn_claude.clicked.connect(self.launch_claude)
        self.btn_claude.setEnabled(False)
        claude_layout.addWidget(self.btn_claude)

        main_layout.addWidget(claude_frame)

        # ═══ Консоль ═══════════════════════════════════════════════
        console_frame = QFrame()
        console_frame.setObjectName("console_frame")
        console_frame.setStyleSheet("""
            QFrame#console_frame {
                background-color: #1c1c21;
                border: 2px solid #3c3c41;
                border-radius: 10px;
            }
        """)
        console_layout = QVBoxLayout(console_frame)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)

        # ── Верхний бар ──
        console_bar = QFrame()
        console_bar.setFixedHeight(30)
        console_bar.setStyleSheet("""
            QFrame {
                background-color: #22222a;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border-bottom: 1px solid #3c3c41;
            }
        """)
        bar_layout = QHBoxLayout(console_bar)
        bar_layout.setContentsMargins(14, 0, 14, 0)

        bar_title = QLabel("Console")
        bar_title.setFont(QFont("Cascadia Mono", 10))
        bar_title.setStyleSheet("color: #6b6e75; background: transparent; border: none;")
        bar_layout.addWidget(bar_title)
        bar_layout.addStretch()

        self._console_msg_count = 0
        console_layout.addWidget(console_bar)

        # ── Тело консоли ──
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        f = QFont("Cascadia Mono", 8)
        f.setPointSizeF(9.4)
        self.console.setFont(f)
        self.console.setMaximumHeight(160)
        self.console.setMinimumHeight(160)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a20;
                color: #e8e8ec;
                border: none;
                padding: 10px 14px;
                selection-background-color: #3c4f6e;
            }
            QScrollBar:vertical {
                background: #1c1c21;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #3c3c41;
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #505058;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        console_layout.addWidget(self.console)

        # ── Нижний бар (как верхний, но тоньше) ──
        console_bottom = QFrame()
        console_bottom.setFixedHeight(22)
        console_bottom.setStyleSheet("""
            QFrame {
                background-color: #22222a;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
                border-top: 1px solid #3c3c41;
            }
        """)
        console_layout.addWidget(console_bottom)

        console_frame.setMaximumHeight(212)
        main_layout.addWidget(console_frame)

        main_layout.addSpacing(10)

        # Футер
        footer = QLabel(
            f"© 2026 Claude Code Manager v{APP_VERSION}   •   "
            f"by {AUTHOR_NAME}   •   Discord: {AUTHOR_DISCORD}"
        )
        footer.setFont(QFont("Segoe UI", 8))
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: rgb(100, 100, 100);")
        footer.setToolTip(
            f"Автор: {AUTHOR_NAME}\n"
            f"Discord: {AUTHOR_DISCORD}\n"
            f"GitHub: {AUTHOR_GITHUB}"
        )
        main_layout.addWidget(footer)

        # Стиль окна
        self.setStyleSheet("QMainWindow { background-color: rgb(20, 20, 25); }")

        # Таймер проверки статуса (в фоновом потоке)
        self._last_status = None
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.check_status_async)
        self.status_timer.start(3000)

        # Состояние версии Claude Code (заполняется фоновой проверкой)
        self._claude_local_version = ""
        self._claude_latest_version = ""
        self._claude_latest_date = ""
        self.claude_version_checked.connect(self._on_claude_version_checked)

        # Стартовая проверка состояния кнопки Установить Claude
        self._update_install_button_state()

        # Тихо чиним installMethod в ~/.claude.json (native → global), чтобы
        # Claude Code при запуске не ругался на отсутствующий ~/.local/bin/claude.exe
        try:
            self._fix_claude_install_method()
        except Exception:
            pass

        # Подпись текущего бинарника (путь + mtime + size) — чтобы дёшево детектить
        # внешнюю установку/обновление/удаление без ежесекундного запуска `claude --version`
        self._claude_binary_signature = self._compute_claude_binary_signature()
        self._version_check_running = False

        # Периодическая проверка (на случай если поставили вручную):
        # обновляем UI + смотрим, не поменялся ли бинарь — если да, перечитываем версию
        self._install_check_timer = QTimer(self)
        self._install_check_timer.timeout.connect(self._poll_claude_binary)
        self._install_check_timer.start(3000)

        # Стартовая фоновая проверка версии + редкий backstop раз в час
        # (на случай если бинарь подменили без изменения mtime — крайне маловероятно)
        threading.Thread(target=self._check_claude_version, daemon=True).start()
        self._claude_version_timer = QTimer(self)
        self._claude_version_timer.timeout.connect(
            lambda: threading.Thread(target=self._check_claude_version, daemon=True).start()
        )
        self._claude_version_timer.start(60 * 60 * 1000)  # 1 час

        # Первая проверка
        self._print_console_banner()
        self.check_status_async()

        # Проверка наличия Node.js/npm — если нет, показываем окно с прямой ссылкой
        # на скачивание. Через singleShot, чтобы UI успел полностью отрисоваться.
        QTimer.singleShot(400, self._check_nodejs_on_startup)

    def _check_nodejs_on_startup(self):
        """Однократная проверка npm при старте. Если npm нет — показывает окно
        со ссылкой на nodejs.org. Срабатывает не чаще одного раза за сессию."""
        if getattr(self, "_node_missing_shown", False):
            return
        try:
            if self._is_npm_installed():
                return
        except Exception:
            return
        self._node_missing_shown = True
        self.log("Node.js (npm) не найден — открываю окно с инструкцией", "warning")
        try:
            self._show_npm_missing_dialog()
        except Exception:
            pass

    def _print_console_banner(self):
        """Стартовый баннер в консоль. Вынесено отдельно, чтобы перепечатать
        его на актуальном языке после смены EN/RU."""
        self.log(tr("Приложение запущено"), "info")
        self.log(tr("Порт Omniroute:") + f" {OMNIROUTE_PORT}", "info")
        self.log(tr("Автор:") + f" {AUTHOR_NAME}  •  Discord: {AUTHOR_DISCORD}", "info")
        self.log(f"GitHub: {AUTHOR_GITHUB}", "info")
        self.log("─" * 50, "info")
        self.log(tr("Для работы с Base URL (freemodel и др.):"), "warning")
        self.log(tr("Если впервые — запустите Claude Code и введите /logout."), "warning")
        self.log(tr("Это нужно сделать только один раз. Даже если вы"), "warning")
        self.log(tr("поменяете API ключ — повторно вводить /logout не нужно."), "warning")
        self.log(tr("Приложение автоматически подставит ключ и Base URL."), "warning")
        self.log("─" * 50, "info")

    def log(self, message, level="info"):
        """Терминальный вывод: цветная точка + сообщение.
        Сообщение автоматически прогоняется через tr() — если в TRANSLATIONS
        есть точное совпадение, выводим перевод; иначе строка остаётся как
        есть. Это позволяет существующим вызовам self.log("Русский текст")
        локализоваться автоматически без правок каждой точки вызова."""
        timestamp = time.strftime("%H:%M:%S")

        if level == "success":
            color = "#00ff64"
        elif level == "error":
            color = "#ff3232"
        elif level == "warning":
            color = "#ffaa00"
        else:
            color = "#b4b4b4"

        try:
            translated = tr(str(message))
        except Exception:
            translated = message

        self._console_msg_count += 1
        formatted = (
            f'<span style="color:#888888;">{timestamp}</span>'
            f'  <span style="color:{color};">●  {translated}</span>'
        )
        self.console.append(formatted)
        self.console.moveCursor(QTextCursor.End)

    def _animate_shimmer(self):
        """Анимирует шиммер слева направо"""
        # Двигаем волну слева направо
        self._shimmer_offset += 0.015  # Средняя скорость

        # Когда волна прошла   есь текст, ждем 2 секунды и начинаем снова
        if self._shimmer_offset > 1.3:
            self._shimmer_offset = -0.3
            # Пауза 2 секунды
            self._shimmer_timer.stop()
            QTimer.singleShot(2000, lambda: self._shimmer_timer.start(30))

        # Создаем HTML с градиентом
        text = "CLAUDE CODE MANAGER"
        html = ""

        for i, char in enumerate(text):
            # Позиция символа (0.0 - 1.0)
            pos = i / len(text)

            # Расстояние от волны
            distance = abs(pos - self._shimmer_offset)

            # Яркость (волна шириной 0.2)
            if distance < 0.2:
                brightness = int(140 + 70 * (1 - distance / 0.2))
            else:
                brightness = 140

            html += f'<span style="color: rgb({brightness}, {brightness}, {brightness + 5});">{char}</span>'

        self.title.setText(html)

    def check_status_async(self):
        """Проверяет статус в фоновом потоке"""
        threading.Thread(target=self._check_and_update_status, daemon=True).start()

    def _check_and_update_status(self):
        """Проверяет статус и обновляет UI"""
        is_running = check_omniroute_status()
        # Отправляем сигнал в главный поток
        self.status_changed.emit(is_running)

    def update_status(self, is_running):
        """Обновляет статус Omniroute"""
        # Логируем только при изменении статуса
        if not hasattr(self, '_last_status') or self._last_status != is_running:
            if is_running:
                self.log("Omniroute подключен", "success")
            else:
                self.log("Omniroute не запущен", "error")
            self._last_status = is_running

        self.status_indicator.set_active(is_running)

        # Проверяем используется ли кастомный токен
        use_custom = self.settings.get("use_custom_token", False)

        if is_running:
            self.status_label.setText(tr("Подключен"))
            self.status_label.setStyleSheet("color: rgb(0, 255, 100);")
            self.btn_start_omniroute.setEnabled(False)
            self.btn_stop_omniroute.setEnabled(True)
            self.btn_claude.setEnabled(True)
        else:
            self.status_label.setText(tr("Не запущен"))
            self.status_label.setStyleSheet("color: rgb(255, 50, 50);")
            # При кастомном токене кнопка запуска Omniroute заблокирована
            self.btn_start_omniroute.setEnabled(not use_custom)
            self.btn_stop_omniroute.setEnabled(False)
            self.btn_claude.setEnabled(use_custom)

    def start_omniroute(self):
        """Запускает Omniroute"""
        self.log("Запуск Omniroute...", "info")
        try:
            omniroute_path = self.settings.get("omniroute_path", "omniroute")

            # Запускаем команду (если просто "omniroute", то через PATH)
            self.omniroute_process = subprocess.Popen(
                omniroute_path,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.log("Ожидание подключения...", "info")
            # Ждем запуска в фоне
            threading.Thread(target=self._wait_for_omniroute, daemon=True).start()
        except Exception as e:
            error_msg = f"Ошибка запуска: {e}"
            self.log(error_msg, "error")

    def stop_omniroute(self):
        """Останавливает Omniroute"""
        self.log("Остановка Omniroute...", "info")
        try:
            # Убиваем процесс по имени
            subprocess.run(["taskkill", "/F", "/IM", "node.exe", "/FI", "WINDOWTITLE eq omniroute*"],
                          capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            # Альтернативный способ - убить все node процессы с omniroute
            subprocess.run(["taskkill", "/F", "/IM", "node.exe"],
                          capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.omniroute_process = None
            self.log("Omniroute остановлен", "success")
            # Принудительная проверка статуса
            time.sleep(0.5)
            self.check_status_async()
        except Exception as e:
            self.log(f"Ошибка остановки: {e}", "error")

    def _wait_for_omniroute(self):
        """Ожидает запуска Omniroute"""
        for i in range(60):  # Увеличили до 30 секунд
            if check_omniroute_status():
                QTimer.singleShot(0, lambda: self.log("Omniroute успешно подключен", "success"))
                QTimer.singleShot(0, self._on_omniroute_connected)
                return
            time.sleep(0.5)
        QTimer.singleShot(0, lambda: self.log("Таймаут ожидания подключения. Проверьте, что Omniroute установлен и путь к нему правильный.", "error"))

    def _on_omniroute_connected(self):
        """Вызывается когда Omniroute успешно подключен"""
        # Обновляем UI
        self.btn_start_omniroute.setEnabled(False)
        self.btn_stop_omniroute.setEnabled(True)
        self.btn_claude.setEnabled(True)

        # Открываем браузер
        try:
            import webbrowser
            webbrowser.open("http://localhost:20128")
        except:
            pass

    def browse_directory(self):
        """Открывает диалог выбора директории"""
        current_dir = self.settings.get("working_directory", "")
        directory = QFileDialog.getExistingDirectory(
            self,
            "Выберите рабочую директорию для Claude Code",
            current_dir if current_dir else os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if directory:
            self.settings["working_directory"] = directory
            self.dir_input.setText(directory)
            save_settings(self.settings)
            self.log(f"Установлена директория: {directory}", "success")

    def clear_directory(self):
        """Очищает сохраненную директорию"""
        self.settings["working_directory"] = ""
        self.dir_input.setText("")
        save_settings(self.settings)
        self.log("Директория очищена", "info")

    def save_token(self):
        """Сохраняет API ключ в настройки"""
        token = self.token_input.text().strip()
        if not token:
            self.log("API ключ не может быть пустым", "warning")
            return

        self.settings["auth_token"] = token
        save_settings(self.settings)
        self.log("API ключ сохранен", "success")

        # Делаем поле только для чтения, темнее и переключаем кнопки
        self.token_input.setReadOnly(True)
        self.token_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(20, 20, 25, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 6px;
            }
        """)
        self.btn_save_token.hide()
        self.btn_edit_token.show()

        # После сохранения автоматически прячем значение, как просил пользователь
        self.token_input.setEchoMode(QLineEdit.Password)
        if hasattr(self, "btn_toggle_token") and hasattr(self.btn_toggle_token, "setRevealed"):
            self.btn_toggle_token.setRevealed(False)

    def edit_token(self):
        """Разрешает редактирование API ключа"""
        self.token_input.setReadOnly(False)
        self.token_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 35, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 6px;
            }
        """)
        self.token_input.setFocus()
        self.btn_edit_token.hide()
        self.btn_save_token.show()
        self.log("Режим редактирования API ключа", "info")

    def toggle_token_visibility(self):
        """Переключает видимость API ключа"""
        if self.token_input.echoMode() == QLineEdit.Password:
            self.token_input.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_token.setRevealed(True)
        else:
            self.token_input.setEchoMode(QLineEdit.Password)
            self.btn_toggle_token.setRevealed(False)

    def _on_mode_changed(self, is_omniroute):
        """Обработчик переключателя режимов в шапке (Omniroute ↔ FreeModel)"""
        self.toggle_custom_token_fields(is_custom=not is_omniroute)

    def _on_language_toggled(self, code):
        """Клик по LanguageToggle — обновляем глобальный LANG."""
        if LANG is not None:
            LANG.set_lang(code)

    def _on_language_changed(self, code):
        """Сигнал от LANG: обновляем тексты главного окна на лету, без
        пересоздания окна. Спрятанные / самонарисованные виджеты
        (подсказка-стрелка «клик», бейдж, бар статуса, шиммер заголовка,
        консоль) форсируем через .update()."""
        try:
            self.settings["app_language"] = code
        except Exception:
            pass
        try:
            if hasattr(self, "language_toggle"):
                self.language_toggle.set_lang(code, animate=True)
        except Exception:
            pass
        try:
            self._retranslate_ui()
        except Exception:
            pass
        # Очищаем консоль и перепечатываем стартовый баннер уже на новом языке —
        # старые записи в консоли остаются на исходном языке, что выглядит криво.
        try:
            if hasattr(self, "console"):
                self.console.clear()
                self._console_msg_count = 0
            if hasattr(self, "_print_console_banner"):
                self._print_console_banner()
        except Exception:
            pass
        # Форсируем перерисовку самонарисованных виджетов
        for attr in ("freemodel_click_hint", "freemodel_brand",
                     "status_indicator", "claude_install_indicator",
                     "title", "mode_toggle", "language_toggle"):
            try:
                w = getattr(self, attr, None)
                if w is not None and hasattr(w, "update"):
                    w.update()
            except Exception:
                pass

    def _retranslate_ui(self):
        """Перерисовывает все локализуемые тексты главного окна по текущему
        значению LANG.lang. Лучше всего использовать существующие
        state-sync методы (update_status, _update_install_button_state),
        которые сами читают tr() — это гарантирует, что выбранный язык
        применится и к статическим лейблам, и к динамическому состоянию."""
        try:
            # Static labels created один раз в _build_ui — нужно вручную
            if hasattr(self, "btn_uninstall_claude"):
                self.btn_uninstall_claude.setText(tr("Удалить Claude Code"))
            if hasattr(self, "btn_install_statusline"):
                self.btn_install_statusline.setText(tr("Status line"))
            if hasattr(self, "btn_fix_claude"):
                self.btn_fix_claude.setText(tr("Fix Claude"))
            if hasattr(self, "btn_stop_omniroute"):
                self.btn_stop_omniroute.setText(tr("Остановить Omniroute"))
            if hasattr(self, "btn_start_omniroute"):
                self.btn_start_omniroute.setText(tr("Запустить Omniroute"))
            if hasattr(self, "btn_claude"):
                self.btn_claude.setText(tr("Запустить Claude Code"))
            if hasattr(self, "btn_add_model"):
                self.btn_add_model.setText(tr("Добавить модель"))
            if hasattr(self, "btn_remove_model"):
                self.btn_remove_model.setText(tr("Удалить модель"))
            if hasattr(self, "btn_save_token"):
                self.btn_save_token.setText(tr("Сохранить"))
            if hasattr(self, "btn_edit_token"):
                self.btn_edit_token.setText(tr("Изменить"))
            if hasattr(self, "fm_btn_manage"):
                self.fm_btn_manage.setText(tr("Управление"))
            if hasattr(self, "fm_btn_save_key"):
                self.fm_btn_save_key.setText(tr("Сохранить"))
            if hasattr(self, "fm_btn_edit_key"):
                self.fm_btn_edit_key.setText(tr("Изменить"))
            if hasattr(self, "btn_configure_custom"):
                self.btn_configure_custom.setText(tr("Настроить"))
            if hasattr(self, "token_label"):
                self.token_label.setText(tr("API ключ:"))
            if hasattr(self, "dir_input"):
                self.dir_input.setPlaceholderText(tr("Не выбрана (будет запрошена)"))
            # Дочерние QLabel-ы по тексту через _tr_widgets (если был трекинг)
            self._retranslate_generic()
            # Прогоняем sync-методы, которые сами уже используют tr() —
            # они закроют динамические лейблы (status_label, claude_install_status_label,
            # btn_install_claude) с учётом ТЕКУЩЕГО реального состояния, а не дефолта.
            if hasattr(self, "_update_install_button_state"):
                try:
                    self._update_install_button_state()
                except Exception:
                    pass
            if hasattr(self, "_last_status"):
                try:
                    # update_status сам перетянет тексты «Подключен / Не запущен»
                    self.update_status(bool(self._last_status))
                except Exception:
                    pass
        except Exception:
            pass

    def _retranslate_generic(self):
        """Generic-проход: проходимся по сохранённому списку (widget, ru_key)
        и переустанавливаем текст через tr(). Список заполняется при сборке
        UI методом self._track_tr(widget, ru_key)."""
        for widget, ru_key, kind in getattr(self, "_tr_widgets", []):
            try:
                if widget is None:
                    continue
                txt = tr(ru_key)
                if kind == "text":
                    widget.setText(txt)
                elif kind == "title":
                    widget.setWindowTitle(txt)
                elif kind == "placeholder":
                    widget.setPlaceholderText(txt)
                elif kind == "tooltip":
                    widget.setToolTip(txt)
            except Exception:
                pass

    def _track_tr(self, widget, ru_key, kind="text"):
        """Регистрируем виджет для авто-перевода при смене язык  ."""
        if not hasattr(self, "_tr_widgets"):
            self._tr_widgets = []
        self._tr_widgets.append((widget, ru_key, kind))
        try:
            txt = tr(ru_key)
            if kind == "text":
                widget.setText(txt)
            elif kind == "title":
                widget.setWindowTitle(txt)
            elif kind == "placeholder":
                widget.setPlaceholderText(txt)
            elif kind == "tooltip":
                widget.setToolTip(txt)
        except Exception:
            pass

    def _fm_url_changed(self, new_url):
        """Сохраняет выбранный Base URL"""
        if new_url:
            prev = self.settings.get("custom_base_url", "")
            self.settings["custom_base_url"] = new_url
            save_settings(self.settings)
            if prev != new_url:
                self.log(f"Base URL {new_url} сохранён", "success")
            self._refresh_freemodel_brand_visibility()

    def _is_freemodel_endpoint(self, url):
        """True, если выбранный Base URL принадлежит сервису freemodel.dev."""
        if not url:
            return False
        return "freemodel.dev" in str(url).lower()

    def _refresh_freemodel_brand_visibility(self):
        """Показывает бейдж freemodel.dev только когда выбран соответствующий эндпоинт.

        В режиме Omniroute (Anthropic / прокси не от freemodel) или при выборе
        кастомного URL бейдж скрывается, чтобы не вводить в заблуждение —
        статус сервиса freemodel.dev не имеет отношения к чужому эндпоинту."""
        try:
            use_custom = self.settings.get("use_custom_token", False)
            url = self.settings.get("custom_base_url", "")
            visible = bool(use_custom) and self._is_freemodel_endpoint(url)
            if hasattr(self, "freemodel_brand"):
                self.freemodel_brand.setVisible(visible)
            if hasattr(self, "freemodel_click_hint"):
                self.freemodel_click_hint.setVisible(visible)
        except Exception:
            pass

    def _fm_model_changed(self, new_model):
        """Сохраняет выбранную модель FreeModel"""
        # Fable 5 заблокирована — её нельзя ни выбрать, ни сохранить
        if new_model == "Fable 5":
            return
        if new_model:
            self.settings["custom_model"] = new_model
            save_settings(self.settings)
        if hasattr(self, "fm_model_combo"):
            # Обновить цвет отображаемого текста и рамки под выбранную модель
            if hasattr(self, "_fm_model_colors") and new_model in self._fm_model_colors:
                self.fm_model_combo.setTextColor(self._fm_model_colors[new_model])
                self.fm_model_combo.setAccentColor(self._fm_model_colors[new_model])

    def _fm_show_fable5_blocked(self, _model_name):
        """Показывает окно блокировки Fable 5 при попытке выбора."""
        dlg = Fable5WarningDialog(self)
        dlg.exec()

    def _on_effort_changed(self, effort):
        """Сохраняет выбранный reasoning effort, пишет в ~/.claude/settings.json и обновляет цвет рамки"""
        self.settings["reasoning_effort"] = effort
        save_settings(self.settings)
        # Сразу прописываем в настройки самого Claude Code (поле effortLevel)
        self._write_claude_effort_setting(effort)
        self.log(f"Reasoning effort изменён на: {effort}", "info")

        if hasattr(self, "fm_effort_combo") and hasattr(self, "_fm_effort_colors"):
            if effort in self._fm_effort_colors:
                self.fm_effort_combo.setTextColor(self._fm_effort_colors[effort])
                self.fm_effort_combo.setAccentColor(self._fm_effort_colors[effort])

    def _fm_toggle_key(self):
        """Показать/скрыть API ключ"""
        if self.fm_key_input.echoMode() == QLineEdit.Password:
            self.fm_key_input.setEchoMode(QLineEdit.Normal)
            self.fm_btn_toggle_key.setRevealed(True)
        else:
            self.fm_key_input.setEchoMode(QLineEdit.Password)
            self.fm_btn_toggle_key.setRevealed(False)

    def _fm_save_key(self):
        """Сохраняет API ключ FreeModel и показывает инструкцию"""
        api_key = self.fm_key_input.text().strip()
        if not api_key:
            self.log("API ключ не может быть пустым", "warning")
            return
        self.settings["custom_api_key"] = api_key
        self.settings["custom_base_url"] = self.fm_url_combo.currentText()
        self.settings["custom_model"] = self.fm_model_combo.currentText()
        save_settings(self.settings)
        self.log("API ключ обновлён", "success")
        # Блокируем редактирование, переключаем кнопки
        self.fm_key_input.setReadOnly(True)
        self.fm_key_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(20, 20, 25, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.fm_btn_save_key.hide()
        self.fm_btn_edit_key.show()

        # После сохранения автоматически прячем значение
        self.fm_key_input.setEchoMode(QLineEdit.Password)
        if hasattr(self, "fm_btn_toggle_key") and hasattr(self.fm_btn_toggle_key, "setRevealed"):
            self.fm_btn_toggle_key.setRevealed(False)

    def _fm_edit_key(self):
        """Разрешает редактирование API ключа FreeModel"""
        self.fm_key_input.setReadOnly(False)
        self.fm_key_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 35, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.fm_key_input.setFocus()
        self.fm_btn_edit_key.hide()
        self.fm_btn_save_key.show()
        self.log("Режим редактирования API ключа", "info")

    def _fm_manage_urls(self):
        """Открывает окно управления Base URL"""
        urls = self.settings.get("custom_base_urls", [])
        current = self.fm_url_combo.currentText()
        dialog = BaseUrlManagerDialog(urls, current, self)
        if dialog.exec() == QDialog.Accepted:
            new_urls, new_current = dialog.get_result()
            self.settings["custom_base_urls"] = list(new_urls)
            self.settings["custom_base_url"] = new_current
            save_settings(self.settings)
            self.fm_url_combo.blockSignals(True)
            self.fm_url_combo.clear()
            self.fm_url_combo.addItems(new_urls)
            if new_current in new_urls:
                self.fm_url_combo.setCurrentText(new_current)
            self.fm_url_combo.blockSignals(False)
            # Сигналы комбо были заблокированы, поэтому _fm_url_changed не вызвался —
            # вручную обновляем видимость бейджа freemodel.dev (если удалили текущий
            # URL и фолбэкнулись на freemodel, бейдж должен вернуться).
            self._refresh_freemodel_brand_visibility()

    def _animate_opacity(self, effect, target, duration=280):
        """Плавно анимирует opacity у QGraphicsOpacityEffect"""
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(effect.opacity())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        anim.start()
        # Сохраняем ссылку чтобы анимация не была собрана GC
        if not hasattr(self, "_opacity_anims"):
            self._opacity_anims = []
        self._opacity_anims.append(anim)
        anim.finished.connect(lambda a=anim: self._opacity_anims.remove(a) if a in self._opacity_anims else None)

    def _animate_window_height(self, target_height):
        """Плавно изменяет высоту окна через resize()"""
        if hasattr(self, "_resize_anim") and self._resize_anim is not None:
            self._resize_anim.stop()
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)

        from PySide6.QtCore import QVariantAnimation
        anim = QVariantAnimation(self)
        anim.setDuration(280)
        anim.setStartValue(self.height())
        anim.setEndValue(target_height)
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        anim.valueChanged.connect(lambda v: self.resize(self.width(), int(v)))
        anim.start()
        self._resize_anim = anim

    def toggle_custom_token_fields(self, is_custom=None):
        """Скрывает/показывает секции для соответствующего режима"""
        if is_custom is None:
            is_custom = self.use_custom_token_checkbox.isChecked()

        self.settings["use_custom_token"] = is_custom
        save_settings(self.settings)

        # Синхронизируем оба переключателя
        if hasattr(self, "mode_toggle"):
            self.mode_toggle.setOmniroute(not is_custom)
        if self.use_custom_token_checkbox.isChecked() != is_custom:
            self.use_custom_token_checkbox.setChecked(is_custom)

        # Залочим текущую высоту, чтобы Qt не растянул окно при показе скрытых виджетов
        _was_initialized = getattr(self, "_height_initialized", False) and self.isVisible()
        if _was_initialized:
            _cur_h = self.height()
            self.setMinimumHeight(_cur_h)
            self.setMaximumHeight(_cur_h)

        # Полностью скрываем/показываем секции
        if hasattr(self, "omniroute_frame"):
            self.omniroute_frame.setVisible(not is_custom)
        if hasattr(self, "model_section_widget"):
            self.model_section_widget.setVisible(not is_custom)
        if hasattr(self, "token_section_widget"):
            self.token_section_widget.setVisible(not is_custom)
        if hasattr(self, "freemodel_section_widget"):
            self.freemodel_section_widget.setVisible(is_custom)

        # Видимость бейджа freemodel.dev пересчитывается по реально выбранному
        # URL и режиму (use_custom_token).
        self._refresh_freemodel_brand_visibility()

        self.btn_configure_custom.setEnabled(is_custom)

        # Кнопка запуска Claude доступна:
        # - В BaseURL режиме — если сохранён API ключ
        # - В Omniroute режиме — если Omniroute отвечает (last == True)
        if hasattr(self, "btn_claude"):
            if is_custom:
                has_key = bool(self.settings.get("custom_api_key", ""))
                self.btn_claude.setEnabled(has_key)
            else:
                last = getattr(self, "_last_status", None)
                self.btn_claude.setEnabled(bool(last))

        # Подгоняем высоту окна
        target_h = 750 if is_custom else 880
        if hasattr(self, "_height_initialized") and self._height_initialized and self.isVisible():
            self._animate_window_height(target_h)
        else:
            # Первая установка — мгновенно
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.resize(self.width(), target_h)
            self._height_initialized = True

        if not is_custom and hasattr(self, "status_timer"):
            self.check_status_async()

    def open_custom_token_dialog(self):
        """Открывает диалог настройки кастомного токена"""
        dialog = CustomTokenDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            # Настройки уже сохранены в диалоге
            save_settings(self.settings)
            self.log("Кастомные настройки сохранены", "success")


        # Обновляем статус кнопки Claude (теперь доступна без Omniroute)
        self.update_omniroute_status()

    MODEL_ID_MAP = {
        "Opus 4.8": "claude-opus-4-8",
        "Opus 4.8 (default)": "claude-opus-4-8",
        "Fable 5": "claude-fable-5",
        "Sonnet 4.6": "claude-sonnet-4-6",
        "Sonnet 4": "claude-sonnet-4",
        "Opus 4.7": "claude-opus-4-7",
        "Opus 4.6": "claude-opus-4-6",
    }

    # Модели, для которых НЕ передавать --model (только env), чтобы /model показывал Default
    NO_CLI_FLAG_MODELS = set()  # Пустой — все модели форсятся через --model

    def _resolve_model_id(self, model_choice):
        """Возвращает реальный ID модели для CLI/env или None для дефолта."""
        return self.MODEL_ID_MAP.get(model_choice)

    def _write_claude_model_setting(self, model_choice):
        """Записывает выбранную модель в ~/.claude/settings.json"""
        try:
            claude_settings_path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
            claude_settings = {}
            if os.path.exists(claude_settings_path):
                with open(claude_settings_path, 'r', encoding='utf-8') as f:
                    claude_settings = json.load(f)

            model_id = self._resolve_model_id(model_choice)
            if model_id is None:
                claude_settings.pop("model", None)
            else:
                claude_settings["model"] = model_id

            with open(claude_settings_path, 'w', encoding='utf-8') as f:
                json.dump(claude_settings, f, indent=2)
        except Exception as e:
            self.log(f"Не удалось записать модель в настройки Claude: {e}", "warning")

    def _fix_claude_install_method(self):
        """Если в ~/.claude.json стоит installMethod=native (остаток install.ps1),
        меняем на global. Иначе Claude Code при запуске ругается
        'claude command at ~/.local/bin/claude.exe missing or broken'."""
        try:
            path = os.path.join(os.path.expanduser("~"), ".claude.json")
            if not os.path.exists(path):
                return
            with open(path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    return
            if data.get("installMethod") == "native":
                data["installMethod"] = "global"
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                try:
                    self.log("installMethod в ~/.claude.json: native → global", "info")
                except Exception:
                    pass
        except Exception:
            pass

    def _write_claude_effort_setting(self, effort):
        """Записывает reasoning effort в ~/.claude/settings.json (поле effortLevel)"""
        if effort not in ("low", "medium", "high", "xhigh", "max"):
            return
        try:
            claude_dir = os.path.join(os.path.expanduser("~"), ".claude")
            os.makedirs(claude_dir, exist_ok=True)
            claude_settings_path = os.path.join(claude_dir, "settings.json")
            claude_settings = {}
            if os.path.exists(claude_settings_path):
                with open(claude_settings_path, 'r', encoding='utf-8') as f:
                    try:
                        claude_settings = json.load(f)
                    except json.JSONDecodeError:
                        claude_settings = {}
            claude_settings["effortLevel"] = effort
            with open(claude_settings_path, 'w', encoding='utf-8') as f:
                json.dump(claude_settings, f, indent=2)
        except Exception as e:
            self.log(f"Не удалось записать effort в настройки Claude: {e}", "warning")

    def launch_claude(self):
        """Запускает Claude Code с выбранной моделью"""
        # Жёсткая проверка: установленная версия не должна быть выше REQUIRED_CLAUDE_VERSION
        local = self._get_installed_claude_version() or getattr(self, "_claude_local_version", "")
        if local:
            try:
                cmp = compare_versions(local, REQUIRED_CLAUDE_VERSION)
            except Exception:
                cmp = 0
            if cmp > 0:
                self._show_version_block_dialog(local)
                return

        model = self.model_combo.currentText()

        # Рабочая директория
        working_dir = self.settings.get("working_directory", "")

        if not working_dir:
            # Если директория не установлена - запрашиваем
            working_dir = QFileDialog.getExistingDirectory(
                self,
                "Выберите рабочую директорию для Claude Code",
                os.path.expanduser("~"),
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )

            if not working_dir:
                self.log("Запуск отменен - директория не выбрана", "warning")
                return

        # Сохраняем выбранную модель
        self.settings["selected_model"] = model
        save_settings(self.settings)

        # Проверяем используется ли кастомный токен
        use_custom = self.settings.get("use_custom_token", False)

        if use_custom:
            self.log(f"Запуск Claude Code с кастомным токеном...", "info")
        else:
            self.log(f"Запуск Claude Code ({model})...", "info")

        # Устанавливаем переменные окружения и запускаем
        env = os.environ.copy()

        # Reasoning effort — пишем во все три места (CLI флаг, env var, settings.json),
        # потому что у settings.json есть баг с потерей "max" и схема режет верхние уровни.
        # --effort на CLI перебивает всё и работает даже при багах конфига.
        effort = self.settings.get("reasoning_effort", "high")
        if effort not in ("low", "medium", "high", "xhigh", "max"):
            effort = "high"
        env["CLAUDE_CODE_EFFORT_LEVEL"] = effort
        self._write_claude_effort_setting(effort)
        effort_flag = f" --effort {effort}"

        if use_custom:
            # Кастомные настройки (BaseURL)
            custom_api_key = self.settings.get("custom_api_key", "")

            if not custom_api_key:
                self.log("Кастомный API ключ не установлен", "error")
                return

            custom_model = self.settings.get("custom_model", "")
            custom_base_url = self.settings.get("custom_base_url", "https://cc.freemodel.dev")

            env["ANTHROPIC_API_KEY"] = custom_api_key
            env["ANTHROPIC_BASE_URL"] = custom_base_url
            env.pop("ANTHROPIC_MODEL", None)
            env.pop("ANTHROPIC_SMALL_FAST_MODEL", None)
            env["ANTHROPIC_AUTH_TOKEN"] = ""
            env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

            # Записываем модель в ~/.claude/settings.json для BaseURL
            self._write_claude_model_setting(custom_model)

            # Форсируем модель через --model (только для BaseURL)
            model_id = self._resolve_model_id(custom_model)
            cli_cmd = "claude"
            if model_id and model_id not in self.NO_CLI_FLAG_MODELS:
                cli_cmd += f" --model {model_id}"
            cli_cmd += effort_flag

            self.log(f"Используется кастомный токен для {custom_base_url} (effort={effort})", "info")
        else:
            # Обычные настройки через Omniroute
            env["ANTHROPIC_BASE_URL"] = "http://localhost:20128/v1"
            env["ANTHROPIC_AUTH_TOKEN"] = self.settings.get("auth_token", "")
            env["ANTHROPIC_API_KEY"] = ""
            env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
            # Передаём ID модели напрямую (kr/claude-sonnet-4.5 и т.д.)
            env["ANTHROPIC_MODEL"] = model
            env["ANTHROPIC_SMALL_FAST_MODEL"] = model

            # Форсируем модель через --model + effort, чтобы старые чаты не переключались
            cli_cmd = f"claude --model {model}{effort_flag}"

        # Снимаем блок PowerShell ExecutionPolicy для этой сессии — если у пользователя
        # стоит Restricted, claude.ps1 без этого не запустится. Scope Process действует
        # только внутри этого powershell-процесса, ничего глобально не меняем.
        ps_prefix = "Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force; "

        try:
            subprocess.Popen(
                ["powershell", "-NoExit", "-Command", f"{ps_prefix}cd '{working_dir}'; {cli_cmd}"],
                env=env
            )
            if use_custom:
                model_id = self._resolve_model_id(self.settings.get("custom_model", ""))
                if model_id and model_id not in self.NO_CLI_FLAG_MODELS:
                    self.log(f"Claude Code запущен (--model {model_id})", "success")
                else:
                    self.log(f"Claude Code запущен ({model_id or 'default'})", "success")
            else:
                self.log(f"Claude Code запущен ({model})", "success")
        except Exception as e:
            self.log(f"Ошибка запуска: {e}", "error")

    def _statusline_bash_command(self):
        """Возвращает строку для поля statusLine.command в settings.json.
        Принципиально та же конвенция, что и в стандартном клиенте Claude Code:
        /c/Users/<user>/.claude/statusline-command.sh"""
        target = os.path.join(os.path.expanduser("~"), ".claude", "statusline-command.sh")
        # C:\Users\danii\.claude\statusline-command.sh -> /c/Users/danii/.claude/statusline-command.sh
        target = target.replace("\\", "/")
        if len(target) >= 2 and target[1] == ":":
            target = "/" + target[0].lower() + target[2:]
        return target

    def _read_existing_statusline(self):
        """Читает текущий блок statusLine из ~/.claude/settings.json. Возвращает
        (есть_ли, представление_команды_для_показа)."""
        try:
            path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
            if not os.path.exists(path):
                return False, ""
            with open(path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    return False, ""
            sl = data.get("statusLine")
            if not isinstance(sl, dict):
                return False, ""
            cmd = sl.get("command") or ""
            if not cmd:
                return False, ""
            # Сравниваем с тем, что мы бы поставили — если уже наше,
            # э  о всё равно «уже есть» (предупреждаем о замене).
            return True, cmd
        except Exception:
            return False, ""

    def _install_status_line(self):
        """Совместимость со старыми вызовами: показывает единый диалог."""
        self._on_statusline_button_clicked()

    def _perform_status_line_install(self):
        """Записывает встроенный sh-скрипт в ~/.claude/ и прописывает блок statusLine.
        Показывает только окно прогресса (без подтверждения)."""
        # Запускаем окно прогресса + фоновый поток
        progress = StatusLineProgressDialog(parent=self)

        def worker():
            try:
                claude_dir = os.path.join(os.path.expanduser("~"), ".claude")
                os.makedirs(claude_dir, exist_ok=True)
                dst = os.path.join(claude_dir, "statusline-command.sh")
                settings_path = os.path.join(claude_dir, "settings.json")

                progress.progress_signal.emit(8)
                time.sleep(0.15)

                # 1) Пишем sh-скрипт из встроенной константы. ВАЖНО: только LF,
                #    Git-Bash в Windows падает на шебанге с CRLF.
                progress.progress_signal.emit(25)
                script_bytes = STATUSLINE_SCRIPT.replace("\r\n", "\n").encode("utf-8")
                with open(dst, 'wb') as fdst:
                    fdst.write(script_bytes)
                time.sleep(0.2)
                progress.progress_signal.emit(55)

                # 2) Обновляем settings.json
                settings = {}
                if os.path.exists(settings_path):
                    try:
                        with open(settings_path, 'r', encoding='utf-8') as f:
                            settings = json.load(f)
                            if not isinstance(settings, dict):
                                settings = {}
                    except json.JSONDecodeError:
                        settings = {}

                settings["statusLine"] = {
                    "type": "command",
                    "command": self._statusline_bash_command(),
                }
                progress.progress_signal.emit(80)

                with open(settings_path, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2, ensure_ascii=False)

                time.sleep(0.2)
                progress.progress_signal.emit(100)
                progress.finished_signal.emit(True, "")
                try:
                    self.log("Status line установлен в ~/.claude/settings.json", "success")
                except Exception:
                    pass
            except Exception as e:
                progress.finished_signal.emit(False, str(e))
                try:
                    self.log(f"Ошибка установки status line: {e}", "error")
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()
        progress.exec()

    def _is_status_line_installed(self):
        """True, если в ~/.claude/settings.json прописан непустой statusLine.command."""
        has, _ = self._read_existing_statusline()
        return has

    def _update_statusline_button_state(self):
        """Заглушка — кнопка теперь всегда называется «Status line»,
        окно после клика выбирается динамически. Оставлено для совместимости
        с местами, где этот метод раньше вызывался."""
        return

    def _on_statusline_button_clicked(self):
        """Открывает единое окно «Внимание» с тремя кнопками
        (Отмена · Удалить · Установить/Переустановить).
        Для переустановки и удаления — мини-подтверждение «вы уверены?»."""
        has_existing, existing_cmd = self._read_existing_statusline()
        dlg = StatusLineInstallDialog(
            has_existing=has_existing,
            existing_command=existing_cmd,
            parent=self,
        )
        result = dlg.exec()

        if result == QDialog.Accepted:
            # Переустановка существующего — спрашиваем подтверждение.
            # Свежая установка — без второго окна, текст уже был наверху.
            if has_existing:
                if not self._confirm_statusline_action(
                    title=tr("Переустановить status line?"),
                    message=tr(
                        "Вы действит  льно хотите переустановить status line? "
                        "Ваш текущий блок statusLine в ~/.claude/settings.json "
                        "и файл ~/.claude/statusline-command.sh будут полностью "
                        "перезаписаны нашей версией. Откатить это нельзя."
                    ),
                    detail=existing_cmd or None,
                    confirm_text=tr("Да, переустановить"),
                    icon="↻",
                    icon_color=(245, 180, 60),
                ):
                    self.log("Переустановка status line отменена", "info")
                    return
            self._perform_status_line_install()

        elif result == StatusLineInstallDialog.ACTION_REMOVE:
            if not self._confirm_statusline_action(
                title=tr("Удалить status line?"),
                message=tr(
                    "Вы действительно хотите удалить status line? "
                    "Блок statusLine уйдёт из ~/.claude/settings.json, "
                    "а файл ~/.claude/statusline-command.sh — будет стёрт. "
                    "Остальные настройки Claude Code останутся как есть."
                ),
                detail=existing_cmd or None,
                confirm_text=tr("Да, удалить"),
                icon="×",
                icon_color=(235, 90, 90),
            ):
                self.log("Удаление status line отменено", "info")
                return
            self._perform_status_line_remove()

        else:
            self.log("Д  йствие со status line отменено", "info")

    def _confirm_statusline_action(self, title, message, detail, confirm_text, icon, icon_color):
        """Маленькое окно подтверждения «вы действительно хотите…»."""
        dlg = ConfirmActionDialog(
            title=title,
            message=message,
            detail=detail,
            confirm_text=confirm_text,
            icon=icon,
            icon_color=icon_color,
            parent=self,
        )
        return dlg.exec() == QDialog.Accepted

    def _uninstall_status_line(self):
        """Совместимость со старыми вызовами."""
        self._perform_status_line_remove()

    def _perform_status_line_remove(self):
        """Удаляет блок statusLine из ~/.claude/settings.json и сам sh-скрипт.
        Без подтверждения — оно уже было в общем окне."""
        progress = StatusLineProgressDialog(parent=self)
        progress.title_lbl.setText(tr("Удаление status line"))
        progress.status_lbl.setText(tr("Подготовка…"))

        def worker():
            try:
                claude_dir = os.path.join(os.path.expanduser("~"), ".claude")
                settings_path = os.path.join(claude_dir, "settings.json")
                sh_path = os.path.join(claude_dir, "statusline-command.sh")

                progress.progress_signal.emit(10)
                time.sleep(0.12)

                # 1) Выпиливаем statusLine из settings.json
                if os.path.exists(settings_path):
                    try:
                        with open(settings_path, 'r', encoding='utf-8') as f:
                            settings = json.load(f)
                        if not isinstance(settings, dict):
                            settings = {}
                    except json.JSONDecodeError:
                        settings = {}
                    if "statusLine" in settings:
                        del settings["statusLine"]
                        with open(settings_path, 'w', encoding='utf-8') as f:
                            json.dump(settings, f, indent=2, ensure_ascii=False)
                progress.progress_signal.emit(60)
                time.sleep(0.15)

                # 2) Удаляем sh-скрипт
                if os.path.exists(sh_path):
                    try:
                        os.remove(sh_path)
                    except Exception:
                        pass
                progress.progress_signal.emit(100)
                progress.finished_signal.emit(True, "")
                try:
                    self.log("Status line удалён из ~/.claude/settings.json", "success")
                except Exception:
                    pass
            except Exception as e:
                progress.finished_signal.emit(False, str(e))
                try:
                    self.log(f"Ошибка удаления status line: {e}", "error")
                except Exception:
                    pass

        # Подменяем тексты success/failed под удаление
        orig_show_success = progress._show_success_state
        def _show_success_uninstall():
            orig_show_success()
            progress.title_lbl.setText(tr("Status line удалён ✓"))
            progress.status_lbl.setText(tr(
                "Блок statusLine удалён из ~/.claude/settings.json,\n"
                "файл ~/.claude/statusline-command.sh стёрт."
            ))
        progress._show_success_state = _show_success_uninstall

        threading.Thread(target=worker, daemon=True).start()
        progress.exec()

    # ----- Fix Claude (~/.claude.json → .bak) -----

    def _ensure_auto_updates_false_in_claude_json(self):
        """Молча проверяет, что в ~/.claude.json стоит autoUpdates=false.
        Если нет — дописывает. Все остальные ключи (numStartups,
        installMethod, oauthAccount, projects, …) остаются нетронутыми.

        Важно: реально автообновление выключает env.DISABLE_UPDATES=1
        в ~/.claude/settings.json (см. _ensure_disable_updates_in_settings).
        Этот флаг — подстраховка/совместимость: если CLI всё-таки где-то
        смотрит autoUpdates в .claude.json, нам ничего не стоит его поставить.
        Запускается из фонового потока при старте."""
        try:
            path = os.path.join(os.path.expanduser("~"), ".claude.json")

            # Лок на read→modify→write, чтобы не конфликтовать с
            # _perform_claude_json_fix (он тоже трогает ~/.claude.json).
            with self._claude_files_lock:
                data = {}
                existed = os.path.exists(path)
                if existed:
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if not isinstance(data, dict):
                            # Не словарь — НЕ трогаем, чтобы ничего не сломать.
                            try:
                                self.log(
                                    "Авто-фикс autoUpdates: ~/.claude.json не является JSON-объектом, "
                                    "пропускаем",
                                    "warning",
                                )
                            except Exception:
                                pass
                            return
                    except json.JSONDecodeError:
                        # Битый JSON — НЕ перезаписываем (это работа Fix Claude).
                        try:
                            self.log(
                                "Авто-фикс autoUpdates: ~/.claude.json повреждён, "
                                "пропускаем (используй кнопку Fix Claude)",
                                "warning",
                            )
                        except Exception:
                            pass
                        return

                # Уже стоит правильное значение → ничего не пишем.
                if data.get("autoUpdates") is False:
                    return

                data["autoUpdates"] = False

                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

            try:
                action = "обновлён" if existed else "создан"
                self.log(
                    f"Авто-фикс autoUpdates=false {action} в ~/.claude.json",
                    "success",
                )
            except Exception:
                pass
        except Exception as e:
            try:
                self.log(f"Авто-фикс autoUpdates не удался: {e}", "warning")
            except Exception:
                pass

    def _ensure_disable_updates_in_settings(self):
        """Молча проверяет, что в ~/.claude/settings.json есть env.DISABLE_UPDATES=1.
        Если нет — дописывает. Все остальные ключи (statusLine, model, theme, …)
        остаются нетронутыми. Запускается из фонового потока при старте.

        Зачем: это единственное место, где автообновление Claude Code реально
        выключается (см. логику Fix Claude). Без него CLI рано или поздно уедет
        с зафиксированной версии на свежую, где Anthropic блокирует сторонние
        Base URL — и FreeModel / Omniroute / прокси перестанут работать.
        Делаем это автоматически при старте, чтобы пользователю не приходилось
        каждый раз нажимать Fix Claude вручную."""
        try:
            claude_dir = os.path.join(os.path.expanduser("~"), ".claude")
            settings_path = os.path.join(claude_dir, "settings.json")

            # Лок на всю критическую секцию read→modify→write, чтобы не
            # конфликтовать с _perform_claude_json_fix (он тоже пишет сюда).
            with self._claude_files_lock:
                settings = {}
                if os.path.exists(settings_path):
                    try:
                        with open(settings_path, 'r', encoding='utf-8') as f:
                            settings = json.load(f)
                        if not isinstance(settings, dict):
                            settings = {}
                    except json.JSONDecodeError:
                        # Битый JSON — НЕ трогаем, чтобы не затереть пользовательские
                        # настройки. Этот случай разруливает уже сам Fix Claude.
                        try:
                            self.log(
                                "Авто-фикс DISABLE_UPDATES: ~/.claude/settings.json повреждён, "
                                "пропускаем (используй кнопку Fix Claude)",
                                "warning",
                            )
                        except Exception:
                            pass
                        return

                env_block = settings.get("env")
                if not isinstance(env_block, dict):
                    env_block = {}

                # Уже стоит правильное значение → ничего не пишем, не дёргаем диск.
                if env_block.get("DISABLE_UPDATES") == "1":
                    return

                os.makedirs(claude_dir, exist_ok=True)
                env_block["DISABLE_UPDATES"] = "1"
                settings["env"] = env_block

                with open(settings_path, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2, ensure_ascii=False)

            try:
                self.log(
                    "Авто-фикс DISABLE_UPDATES=1 добавлен в ~/.claude/settings.json "
                    "(автообновление Claude Code выключено)",
                    "success",
                )
            except Exception:
                pass
        except Exception as e:
            # Любой сбой — это не критично, пользователь всё ещё может
            # руками нажать Fix Claude. Не падаем, не показываем модалок.
            try:
                self.log(f"Авто-фикс DISABLE_UPDATES не удался: {e}", "warning")
            except Exception:
                pass

    def _claude_json_path(self):
        """Путь к проблемному файлу — ~/.claude.json (это НЕ ~/.claude/settings.json)."""
        return os.path.join(os.path.expanduser("~"), ".claude.json")

    def _claude_json_backup_target(self):
        """Подбираем .bak-имя так, чтобы не затереть уже существующий бэкап.
        Сначала .bak, затем .bak.2, .bak.3 и т.д."""
        base = self._claude_json_path() + ".bak"
        if not os.path.exists(base):
            return base
        i = 2
        while True:
            candidate = f"{base}.{i}"
            if not os.path.exists(candidate):
                return candidate
            i += 1

    def _on_fix_claude_button_clicked(self):
        """Показывает красное окно «Внимание» с предложением переименовать
        ~/.claude.json в .bak. При успехе запускает прогресс-диалог."""
        json_path = self._claude_json_path()
        exists = os.path.exists(json_path)
        backup_target = self._claude_json_backup_target() if exists else (json_path + ".bak")

        dlg = ClaudeJsonFixDialog(
            json_path=json_path,
            json_exists=exists,
            backup_target=backup_target,
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            try:
                self.log("Fix Claude отменён", "info")
            except Exception:
                pass
            return

        # Передаём заранее посчитанный backup_target, чтобы пользователь увидел
        # в success-сообщении ровно тот путь, что был показан в окне-предупреждении.
        # Worker всё равно проверит, что путь свободен, и если нет — подберёт новый.
        self._perform_claude_json_fix(preferred_backup=backup_target if exists else None)

    def _perform_claude_json_fix(self, preferred_backup=None):
        """Переименовывает ~/.claude.json → ~/.claude.json.bak (с числовым суффиксом,
        если такой бэкап уже есть). Показывает прогресс-диалог.
        Если передан `preferred_backup` — пытается использовать именно его,
        иначе подбирает новое имя сам."""
        progress = StatusLineProgressDialog(parent=self)
        progress.title_lbl.setText("Fix Claude")
        progress.status_lbl.setText("Подготовка…")

        # Подменяем success-текст под наш сценарий
        orig_show_success = progress._show_success_state
        # state, чтобы worker сохранил путь бэкапа для success-сообщения
        result_state = {"backup": None}

        def _show_success_fix():
            orig_show_success()
            progress.title_lbl.setText("Claude исправлен ✓")
            backup = result_state.get("backup") or "~/.claude.json.bak"
            backup_short = ClaudeJsonFixDialog._short(backup)
            # Честно показываем, какие из подопераций прошли —
            # если settings.json не записался, пользователь должен это знать.
            settings_ok = result_state.get("settings_ok", True)
            if settings_ok:
                tail = (
                    "~/.claude/settings.json пересоздан: оставлен только "
                    "env.DISABLE_UPDATES=1. Зависшие ключи (apiKeyHelper и т.п.), "
                    "которые ломали авторизацию, удалены. Модель, эффорт и токен "
                    "подхватятся из настроек приложения автоматически."
                )
            else:
                tail = (
                    "Не удалось пересоздать settings.json — смотри лог. "
                    "Автообновление и зависшие ключи могут остаться."
                )
            # Rich text: красным выделяем ключевое предупреждение про
            # необходимость ручного перезапуска. QLabel автоматически
            # рендерит HTML, никаких setTextFormat не нужно.
            html = (
                f"Старый файл сохранён как {backup_short}.<br>"
                f"{tail}<br><br>"
                "<span style='color:#E55A5A; font-weight:600;'>"
                "Необходимо вручную перезапустить приложение, "
                "чтобы изменения вступили в силу."
                "</span>"
            )
            progress.status_lbl.setText(html)
            # Меняем «Готово» на «Понятно». Стандартный clicked
            # (закрытие диалога через accept) трогать не нужно — он
            # настроен в __init__ и просто закроет окно.
            try:
                progress.btn_ok.setText("Понятно")
            except Exception:
                pass
        progress._show_success_state = _show_success_fix

        def worker():
            try:
                src = self._claude_json_path()
                progress.progress_signal.emit(10)
                time.sleep(0.12)

                # Лок на всю транзакцию: переименование + засев нового .claude.json
                # + мерж DISABLE_UPDATES в settings.json. Если параллельно работает
                # стартовый страж (_ensure_*) — он подождёт, и мы не потеряем
                # ничьих изменений.
                with self._claude_files_lock:
                    if not os.path.exists(src):
                        # Файла нет — фиксить нечего, но это не ошибка
                        progress.progress_signal.emit(100)
                        progress.finished_signal.emit(True, "")
                        try:
                            self.log("Fix Claude: файл ~/.claude.json не найден — ничего не делаем", "info")
                        except Exception:
                            pass
                        return

                    # Подбираем имя бэкапа. Если есть preferred_backup из диалога
                    # и он всё ещё свободен — берём его (так пользователь увидит
                    # в success тот же путь, что был обещан в окне). Иначе
                    # подбираем заново — закрываем TOCTOU.
                    if preferred_backup and not os.path.exists(preferred_backup):
                        dst = preferred_backup
                    else:
                        dst = self._claude_json_backup_target()
                    result_state["backup"] = dst
                    progress.progress_signal.emit(45)
                    time.sleep(0.18)

                    # Используем os.rename, чтобы при гонке (если кто-то создал dst
                    # прямо сейчас) словить ошибку, а не молча затереть бэкап.
                    os.rename(src, dst)
                    progress.progress_signal.emit(55)
                    time.sleep(0.1)

                    # Создаём свежий ~/.claude.json со всем, что обычно туда
                    # дописывает стартовый страж (_ensure_auto_updates_false_in_claude_json).
                    # Раньше autoUpdates тут не было — добавлялся только при следующем
                    # запуске приложения, и пользователь видел его «появление» как побочный
                    # эффект перезапуска. Пишем сразу: пусть всё нужное окажется на месте
                    # без всяких ожиданий и перезагрузок.
                    # Замечание про autoUpdates: ключ не задокументирован
                    # (issues #11263, #13213 в anthropics/claude-code) и реально
                    # автообновление выключается ниже через DISABLE_UPDATES=1
                    # в settings.json. autoUpdates тут — подстраховка/совместимость:
                    # есл   какая-то ветка кода CLI всё-таки его уважает —
                    # нам ничего не стоит её закрыть.
                    stub = {
                        "installMethod": "global",
                        "autoUpdates": False,
                    }
                    stub_ok = True
                    try:
                        with open(src, 'w', encoding='utf-8') as f:
                            json.dump(stub, f, indent=2, ensure_ascii=False)
                    except Exception as seed_err:
                        # Не критично: даже если запись стаба сорвётся,
                        # основной фикс (перенос в .bak) уже состоялся.
                        stub_ok = False
                        try:
                            self.log(
                                f"Fix Claude: не удалось засеять новый ~/.claude.json: {seed_err}",
                                "warning",
                            )
                        except Exception:
                            pass

                    progress.progress_signal.emit(80)
                    time.sleep(0.1)

                    # Пересоздаём ~/.claude/settings.json с нуля — НЕ мерж.
                    # Раньше мы аккуратно мержили только env.DISABLE_UPDATES в
                    # существующий файл, чтобы не потерять пользовательские
                    # ключи (model, effortLevel, statusLine, apiKeyHelper, …).
                    # На практике именно эти «зависшие» ключи (типа apiKeyHelper
                    # от старой установки) и ломают авторизацию — Claude видит
                    # одновременно apiKeyHelper и ANTHROPIC_API_KEY, ругается
                    # «auth may not work as expected» и виснет на Retrying.
                    # Поэтому Fix теперь работает как чистый сброс: всё, что
                    # пользователь настраивает через наше приложение (модель,
                    # эффорт, токены), хранится в настройках самого приложения
                    # и перезаписывается в settings.json при следующем
                    # взаимодействии — так что ничего «потерять» нельзя.
                    # А вот зависшие чужие ключи уходят, и авторизация снова
                    # становится однозначной.
                    #
                    # Замечание про DISABLE_UPDATES: это официально
                    # задокументированный механизм (code.claude.com/docs/en/setup):
                    # CLI читает env-блок при старте и пробрасывает переменные
                    # себе в окружение. DISABLE_UPDATES жёстче DISABLE_AUTOUPDATER —
                    # он блокирует и фоновую самообновлялку, и ручной `claude update`;
                    # нам именно это и нужно, так как версии после 2.1.180 ломают
                    # FreeModel / Omniroute / прокси (Anthropic блокирует сторонние
                    # Base URL). settings.json CLI не перезаписывает при запуске,
                    # поэтому флаг прилипает надёжно.
                    settings_ok = True
                    try:
                        claude_dir = os.path.join(os.path.expanduser("~"), ".claude")
                        os.makedirs(claude_dir, exist_ok=True)
                        settings_path = os.path.join(claude_dir, "settings.json")

                        fresh_settings = {
                            "env": {
                                "DISABLE_UPDATES": "1",
                            },
                        }

                        with open(settings_path, 'w', encoding='utf-8') as f:
                            json.dump(fresh_settings, f, indent=2, ensure_ascii=False)
                    except Exception as seed_err:
                        # Тоже не критично — основной фикс уже состоялся.
                        settings_ok = False
                        try:
                            self.log(
                                f"Fix Claude: не удалось пересоздать settings.json: {seed_err}",
                                "warning",
                            )
                        except Exception:
                            pass

                    # Запоминаем для success-сообщения, какие из подопераций прошли.
                    result_state["stub_ok"] = stub_ok
                    result_state["settings_ok"] = settings_ok

                progress.progress_signal.emit(100)
                progress.finished_signal.emit(True, "")
                try:
                    self.log(f"Fix Claude: ~/.claude.json → {dst}", "success")
                except Exception:
                    pass
            except Exception as e:
                progress.finished_signal.emit(False, str(e))
                try:
                    self.log(f"Ошибка Fix Claude: {e}", "error")
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()
        progress.exec()

    def _install_claude_code(self):
        """Устанавливает/переустанавливает Claude Code v{REQUIRED_CLAUDE_VERSION} через npm в PowerShell"""
        installed = self._is_claude_installed()
        local = getattr(self, "_claude_local_version", "")
        required = REQUIRED_CLAUDE_VERSION

        # Определяем сценарий: install / downgrade / reinstall
        needs_change = True
        is_update = False
        is_downgrade = False
        if installed and local:
            try:
                cmp = compare_versions(local, required)
            except Exception:
                cmp = 0
            if cmp == 0:
                needs_change = False
            elif cmp > 0:
                is_downgrade = True
            else:
                is_update = True

        if not needs_change:
            self.log(f"Claude Code v{required} уже установлен", "info")
            return

        if is_downgrade:
            title = tr("Откат Claude Code до") + f" v{required}"
            message = (
                tr("У тебя установлена") + f" v{local}. v{required} — " +
                tr("последняя стабильная версия, "
                   "на которой приложение проверено целиком. Более новые версии могут работать "
                   "нестабильно или вовсе не запускаться, а начиная с v2.1.181 Anthropic "
                   "заблокировала сторонние Base URL и API ключи — все запросы уходят только "
                   "в официальный сервис Anthropic, и FreeModel / Omniroute / прокси не работают.\n\n"
                   "npm переустановит пакет на нужную версию. Настройки в %USERPROFILE%\\.claude "
                   "не пострадают.")
            )
            confirm_text = tr("Откатить")
            icon = "↓"
            icon_color = (235, 150, 90)
        elif is_update:
            title = tr("Установка Claude Code") + f" v{required}"
            message = (
                tr("У тебя установлена") + f" v{local}. " +
                tr("Будет установлена фиксированная") + f" v{required} — " +
                tr("последняя стабильная версия, с которой это приложение работает гарантированно. "
                   "Более новые версии могут работать нестабильно или совсем не запускаться.")
            )
            confirm_text = tr("Установить")
            icon = "↑"
            icon_color = (245, 180, 60)
        else:
            title = tr("Установка Claude Code") + f" v{required}"
            message = (
                tr("Будет установлена фиксированная версия") + f" v{required} " +
                tr("через npm — "
                   "последняя стабильная, на которой проверено это приложение. "
                   "Более новые версии могут работать нестабильно или вовсе не запускаться, "
                   "а версии с 2.1.181 Anthropic блокирует сторонние Base URL и API ключи.\n\n"
                   "Откроется окно PowerShell, где пойдёт установка.")
            )
            confirm_text = tr("Установить")
            icon = "↓"
            icon_color = (120, 200, 130)

        dlg = ConfirmActionDialog(
            title=title,
            message=message,
            detail=f"npm install -g @anthropic-ai/claude-code@{required}",
            confirm_text=confirm_text,
            icon=icon,
            icon_color=icon_color,
            parent=self
        )
        if dlg.exec() != QDialog.Accepted:
            self.log("Операция отменена", "info")
            return

        if not self._is_npm_installed():
            self._show_npm_missing_dialog()
            return

        action_word = "переустановку" if installed else "установку"
        self.log(f"Запускаю {action_word} Claude Code v{required} через npm...", "info")

        progress_dlg = ClaudeInstallProgressDialog(
            is_update=installed,
            old_version=local,
            new_version=required,
            parent=self,
        )
        self._claude_install_dlg = progress_dlg

        try:
            popen = subprocess.Popen([
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                # 1) Прибить все запущенные claude.exe — иначе файл залочен и npm падает с EBUSY
                "Write-Host 'Останавливаю запущенные процессы claude...' -ForegroundColor Cyan; "
                "Get-Process claude -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; "
                "Start-Sleep -Milliseconds 600; "
                # 2) Снести старую установку через install.ps1 (живёт в ~/.local/bin и ~/.claude/local) —
                #    иначе её битый shim перехватывает команду 'claude' в PATH
                "Write-Host 'Удаляю старую установку Claude Code (install.ps1)...' -ForegroundColor Cyan; "
                "$localBin = Join-Path $env:USERPROFILE '.local\\bin'; "
                "if (Test-Path $localBin) { "
                "  Get-ChildItem $localBin -Filter 'claude*' -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue; "
                "} "
                "$claudeLocal = Join-Path $env:USERPROFILE '.claude\\local'; "
                "if (Test-Path $claudeLocal) { "
                "  Remove-Item -Recurse -Force $claudeLocal -ErrorAction SilentlyContinue; "
                "} "
                # 3) Установка через npm
                f"Write-Host 'Установка Claude Code v{required} через npm...' -ForegroundColor Cyan; "
                f"npm install -g @anthropic-ai/claude-code@{required}; "
                "Write-Host '`nГотово. Проверь команду: claude --version' -ForegroundColor Green; "
                "Write-Host '`nНажмите любую клавишу, чтобы закрыть PowerShell...' -ForegroundColor Cyan; "
                "$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')"
            ])
        except Exception as e:
            self.log(f"Не удалось запустить установку: {e}", "error")
            progress_dlg.mark_failed(f"Не удалось запустить PowerShell:\n{e}")
            progress_dlg.exec()
            return

        # Контекст для коллбэка
        self._claude_install_ctx = {
            "is_update": is_update,
            "old_local": local,
            "progress_dlg": progress_dlg,
            "popen": popen,
        }

        # Подключаем сигнал ОДИН раз (UniqueConnection чтобы не плодить дубли)
        try:
            self.claude_install_finished.disconnect(self._on_claude_install_done_safe)
        except Exception:
            pass
        self.claude_install_finished.connect(
            self._on_claude_install_done_safe, Qt.QueuedConnection
        )

        # Фоновая нить: ждёт PowerShell, читает версию там же (никаких subprocess.run в main!),
        # затем эмитит сигнал с готовым контекстом
        def _wait_and_emit():
            try:
                popen.wait()
            except Exception:
                pass
            try:
                rc = popen.returncode
            except Exception:
                rc = None
            # Версию читаем здесь, в фоне — не блокируем UI
            new_local = ""
            try:
                # дать инсталлятору пару секунд "отпустить" файл
                time.sleep(0.5)
                new_local = self._get_installed_claude_version()
            except Exception:
                new_local = ""
            try:
                installed_now = self._is_claude_installed()
            except Exception:
                installed_now = False
            ctx = {
                "is_update": is_update,
                "old_local": local,
                "new_local": new_local,
                "installed_now": installed_now,
                "returncode": rc,
            }
            try:
                self.claude_install_finished.emit(ctx)
            except Exception:
                pass

        threading.Thread(target=_wait_and_emit, daemon=True).start()

        # Показываем окно (модально, но процесс PowerShell идёт параллельно)
        progress_dlg.exec()

    def _on_claude_install_done_safe(self, ctx):
        """Вызывается на main thread через сигнал. Все subprocess-вызовы уже сделаны в фоне."""
        if not isinstance(ctx, dict):
            return

        is_update = ctx.get("is_update", False)
        old_local = ctx.get("old_local", "") or ""
        new_local = ctx.get("new_local", "") or ""
        installed_now = bool(ctx.get("installed_now", False))
        returncode = ctx.get("returncode")

        progress_dlg = None
        try:
            saved_ctx = getattr(self, "_claude_install_ctx", None) or {}
            progress_dlg = saved_ctx.get("progress_dlg")
        except Exception:
            progress_dlg = None

        # Проверка валидности диалога
        dlg_alive = False
        if progress_dlg is not None:
            try:
                from shiboken6 import isValid
                dlg_alive = isValid(progress_dlg)
            except Exception:
                dlg_alive = True  # если проверить не можем — пробуем

        if new_local:
            self._claude_local_version = new_local

        # После npm-установки чиним installMethod, иначе Claude всё ещё думает
        # что он "native" и ищет ~/.local/bin/claude.exe
        try:
            self._fix_claude_install_method()
        except Exception:
            pass

        if dlg_alive:
            try:
                if is_update:
                    version_changed = bool(new_local) and bool(old_local) and new_local != old_local
                    if version_changed:
                        progress_dlg.mark_finished(actual_version=new_local)
                    else:
                        progress_dlg.mark_cancelled()
                else:
                    if installed_now and new_local:
                        progress_dlg.mark_finished(actual_version=new_local)
                    else:
                        progress_dlg.mark_cancelled()
            except Exception:
                pass

        try:
            self._update_install_button_state()
        except Exception:
            pass

        try:
            threading.Thread(target=self._check_claude_version, daemon=True).start()
        except Exception:
            pass

    def _show_version_block_dialog(self, current_version):
        """Показывает окно блокировки запуска: установленная версия Claude Code слишком новая."""
        required = REQUIRED_CLAUDE_VERSION
        message = (
            tr("У тебя установлена Claude Code") + f" v{current_version}, " +
            tr("а приложение работает только с") + f" v{required}.\n\n"
            f"v{required} — " +
            tr("последняя стабильная версия, на которой это приложение проверено целиком. "
               "Более новые версии могут работать нестабильно или вовсе не запускаться.\n\n"
               "Кроме того, начиная с v2.1.181 Anthropic заблокировала использование сторонних "
               "Base URL и API ключей — запросы уходят только в официальный сервис Anthropic, "
               "поэтому через FreeModel / Omniroute / любые прокси такая версия CLI работать не будет.\n\n") +
            tr("Нажми «Откатить» — npm переустановит CLI на") + f" v{required}, " +
            tr("и запуск снова заработает.")
        )
        dlg = ConfirmActionDialog(
            title=tr("Запуск заблокирован"),
            message=message,
            detail=f"npm install -g @anthropic-ai/claude-code@{required}",
            confirm_text=tr("Откатить до") + f" v{required}",
            icon="!",
            icon_color=(235, 90, 90),
            parent=self
        )
        self.log(
            f"Запуск заблокирован: установлена v{current_version}, требуется v{required}",
            "warning"
        )
        if dlg.exec() == QDialog.Accepted:
            self._install_claude_code()

    def _is_npm_installed(self):
        """True если в системе есть npm (нужен для установки Claude Code).
        На Windows npm — это npm.cmd, поэтому ищем через PATHEXT вручную и
        также пробуем shell=True как фолбэк."""
        # 1) Прямой поиск исполняемого файла через PATH + PATHEXT
        try:
            import shutil
            if shutil.which("npm"):
                return True
            for name in ("npm.cmd", "npm.exe", "npm.bat", "npm"):
                if shutil.which(name):
                    return True
        except Exception:
            pass

        # 2) Фолбэк: запуск через shell (на Windows .cmd резолвится только так)
        try:
            result = subprocess.run(
                "npm --version",
                shell=True,
                capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            return result.returncode == 0
        except Exception:
            return False

    def _is_winget_available(self):
        """True если в системе есть winget (встроен в Windows 10 1809+ и Windows 11)."""
        try:
            import shutil
            if shutil.which("winget"):
                return True
        except Exception:
            pass
        try:
            r = subprocess.run(
                "winget --version",
                shell=True, capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            return r.returncode == 0
        except Exception:
            return False

    def _show_npm_missing_dialog(self):
        """Сообщает пользователю что нужен Node.js / npm. Если в системе есть
        winget — предлагает поставить Node.js LTS прямо в PowerShell. Иначе —
        fallback на открытие официальной страницы скачивания."""
        download_url = "https://nodejs.org/en/download"
        has_winget = self._is_winget_available()

        if has_winget:
            message = tr(
                "В системе не найден npm — он входит в состав Node.js. "
                "Без npm Claude Code установить нельзя.\n\n"
                "Нажми «Установить Node.js» — откроется окно PowerShell, "
                "в котором winget автоматически скачает и поставит Node.js LTS "
                "с официального источника (OpenJS.NodeJS.LTS).\n\n"
                "После окончания установки закрой и заново открой это приложение, "
                "чтобы оно увидело npm в обновлённом PATH."
            )
            detail = "winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements"
            confirm_text = tr("Установить Node.js")
        else:
            message = tr(
                "В системе не найден npm — он входит в состав Node.js. "
                "Без npm Claude Code установить нельзя.\n\n"
                "На твоей системе нет winget, поэтому установить автоматически не получится. "
                "Нажми «Скачать Node.js» — откроется официальная страница "
                "nodejs.org/en/download. Скачай Windows Installer (.msi) LTS, "
                "поставь его и перезапусти это приложение."
            )
            detail = download_url
            confirm_text = tr("Скачать Node.js")

        dlg = ConfirmActionDialog(
            title=tr("Нужен Node.js (npm)"),
            message=message,
            detail=detail,
            confirm_text=confirm_text,
            icon="!",
            icon_color=(235, 180, 110),
            parent=self
        )
        if dlg.exec() != QDialog.Accepted:
            return

        if has_winget:
            self._install_nodejs_via_winget()
        else:
            try:
                import webbrowser
                webbrowser.open(download_url)
                self.log(f"Открыта страница скачивания Node.js: {download_url}", "info")
            except Exception as e:
                self.log(f"Не удалось открыть браузер: {e}", "warning")

    def _install_nodejs_via_winget(self):
        """Запускает PowerShell с winget install OpenJS.NodeJS.LTS — пользователь
        видит весь процесс. После завершения окно ждёт нажатия клавиши."""
        self.log("Запускаю установку Node.js LTS через winget...", "info")
        try:
            subprocess.Popen([
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                "Write-Host 'Устанавливаю Node.js LTS через winget...' -ForegroundColor Cyan; "
                "Write-Host 'Источник: OpenJS.NodeJS.LTS (winget по умолчанию берёт официальный пакет с nodejs.org)' -ForegroundColor DarkGray; "
                "winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements; "
                "if ($LASTEXITCODE -eq 0) { "
                "  Write-Host '`nNode.js установлен. Перезапусти Claude Code Manager, чтобы он подхватил npm в PATH.' -ForegroundColor Green; "
                "} else { "
                "  Write-Host '`nУстановка завершилась с ошибкой. Код выхода:' $LASTEXITCODE -ForegroundColor Yellow; "
                "  Write-Host 'Можно поставить вручную с https://nodejs.org/en/download' -ForegroundColor Yellow; "
                "} "
                "Write-Host '`nНажмите любую клавишу, чтобы закрыть PowerShell...' -ForegroundColor Cyan; "
                "$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')"
            ])
        except Exception as e:
            self.log(f"Не удалось запустить установку Node.js: {e}", "error")

    def _detect_claude_install_dirs(self):
        """Возвращает список существующих папок где может лежать claude"""
        candidates = [
            os.path.join(os.environ.get("USERPROFILE", ""), ".local", "bin"),
            os.path.join(os.environ.get("APPDATA", ""), "npm"),
        ]
        return [d for d in candidates if os.path.isdir(d)]

    def _is_claude_installed(self):
        """True если есть claude в %USERPROFILE%\\.local\\bin или %APPDATA%\\npm"""
        for d in self._detect_claude_install_dirs():
            for name in ("claude.exe", "claude.cmd", "claude.bat", "claude"):
                if os.path.isfile(os.path.join(d, name)):
                    return True
        return False

    def _update_install_button_state(self):
        """Обновляет кнопки и индикатор по состоянию (нет / нужная версия / другая версия)"""
        installed = self._is_claude_installed()
        local = getattr(self, "_claude_local_version", "")
        required = REQUIRED_CLAUDE_VERSION

        version_match = False
        version_higher = False
        version_unknown = installed and not local  # бинарь есть, но версию ещё не успели прочитать
        if installed and local:
            try:
                cmp = compare_versions(local, required)
            except Exception:
                cmp = 0
            version_match = (cmp == 0)
            version_higher = (cmp > 0)

        if hasattr(self, "btn_install_claude"):
            if not installed:
                self.btn_install_claude.setEnabled(True)
                self.btn_install_claude.setText(tr("Установить Claude Code") + f" v{required}")
                self.btn_install_claude.set_hover_color(80, 200, 110)
            elif version_unknown:
                # Не знаем версию — не показываем «установлен», ждём перепроверки
                self.btn_install_claude.setEnabled(False)
                self.btn_install_claude.setText(tr("Проверка версии…"))
            elif version_match:
                self.btn_install_claude.setEnabled(False)
                self.btn_install_claude.setText(f"Claude Code v{required} " + tr("установлен"))
            elif version_higher:
                self.btn_install_claude.setEnabled(True)
                self.btn_install_claude.setText(tr("Откатить до") + f" v{required}")
                self.btn_install_claude.set_hover_color(235, 150, 90)
            else:
                self.btn_install_claude.setEnabled(True)
                self.btn_install_claude.setText(tr("Установить") + f" v{required}")
                self.btn_install_claude.set_hover_color(245, 180, 60)

        if hasattr(self, "btn_uninstall_claude"):
            self.btn_uninstall_claude.setEnabled(installed)

        if hasattr(self, "claude_install_indicator"):
            if not installed:
                self.claude_install_indicator.set_state("off")
            elif version_unknown:
                # Нейтральное «проверяю» — не зелёный, не красный
                self.claude_install_indicator.set_state("warn")
            elif version_match:
                self.claude_install_indicator.set_state("on")
            else:
                self.claude_install_indicator.set_state("warn")

        if hasattr(self, "claude_install_status_label"):
            if not installed:
                self.claude_install_status_label.setText(tr("Не установлен"))
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(255, 50, 50); background: transparent; border: none;"
                )
            elif version_unknown:
                self.claude_install_status_label.setText(tr("Проверяю версию…"))
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(180, 180, 190); background: transparent; border: none;"
                )
            elif version_match:
                self.claude_install_status_label.setText(tr("Установлен") + f" v{local}")
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(0, 255, 100); background: transparent; border: none;"
                )
            elif version_higher:
                self.claude_install_status_label.setText(
                    tr("Установлен") + f" v{local} — " + tr("нужна") + f" v{required} (" + tr("запуск заблокирован") + ")"
                )
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(235, 150, 90); background: transparent; border: none;"
                )
            else:
                self.claude_install_status_label.setText(
                    tr("Установлен") + f" v{local} → " + tr("нужна") + f" v{required}"
                )
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(245, 180, 60); background: transparent; border: none;"
                )

    def _format_date(self, iso_date):
        """Преобразует ISO-дату из npm в DD.MM.YYYY"""
        if not iso_date:
            return ""
        try:
            return f"{iso_date[8:10]}.{iso_date[5:7]}.{iso_date[0:4]}"
        except Exception:
            return iso_date

    def _get_installed_claude_version(self):
        """Возвращает строку версии установленного claude или пустую строку"""
        # Сначала ищем сам claude в наших стандартных папках
        claude_path = None
        for d in self._detect_claude_install_dirs():
            for name in ("claude.exe", "claude.cmd", "claude.bat", "claude"):
                p = os.path.join(d, name)
                if os.path.isfile(p):
                    claude_path = p
                    break
            if claude_path:
                break
        if not claude_path:
            return ""
        try:
            result = subprocess.run(
                [claude_path, "--version"],
                capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            output = (result.stdout or "") + (result.stderr or "")
            # Формат: "1.2.3 (Claude Code)"
            import re
            m = re.search(r"(\d+\.\d+\.\d+)", output)
            return m.group(1) if m else ""
        except Exception:
            return ""

    def _compute_claude_binary_signature(self):
        """Сигнатура установленного claude (путь + mtime + size). Меняется при
        любой внешней установке/обновлении/удалении — без вызова subprocess."""
        parts = []
        for d in self._detect_claude_install_dirs():
            for name in ("claude.exe", "claude.cmd", "claude.bat", "claude"):
                p = os.path.join(d, name)
                try:
                    st = os.stat(p)
                    parts.append((p, int(st.st_mtime), st.st_size))
                except (FileNotFoundError, OSError):
                    continue
        return tuple(parts)

    def _poll_claude_binary(self):
        """Тикает раз в N секунд: если бинарь claude поменялся снаружи приложения —
        моментально перечитываем версию и обновляем кнопки. Иначе только UI-апдейт."""
        try:
            sig = self._compute_claude_binary_signature()
        except Exception:
            sig = ()
        prev = getattr(self, "_claude_binary_signature", None)
        if sig != prev:
            self._claude_binary_signature = sig
            # КРИТИЧНО: бинарь сменился — кэш версии устарел. Чистим, чтобы UI не
            # показывал зелёный «v2.1.173 установлен» по старому значению, пока
            # фоновая перепроверка не отработает.
            self._claude_local_version = ""
            if not getattr(self, "_version_check_running", False):
                threading.Thread(target=self._check_claude_version, daemon=True).start()
        self._update_install_button_state()

    def _check_claude_version(self):
        """Фоновая проверка локальной версии Claude Code. Целевая версия всегда жёстко зафиксирована."""
        if getattr(self, "_version_check_running", False):
            return
        self._version_check_running = True
        try:
            local = self._get_installed_claude_version()
            try:
                self._claude_binary_signature = self._compute_claude_binary_signature()
            except Exception:
                pass
            try:
                self.claude_version_checked.emit(local, REQUIRED_CLAUDE_VERSION, "")
            except Exception:
                pass
        finally:
            self._version_check_running = False

    def _on_claude_version_checked(self, local, latest, latest_date):
        """Получили результат проверки версии из фонового потока"""
        self._claude_local_version = local
        self._claude_latest_version = latest
        self._claude_latest_date = latest_date
        self._update_install_button_state()
        # Если установлена версия НИЖЕ требуемой — предупреждаем (раз за сессию)
        try:
            self._maybe_warn_outdated_version()
        except Exception:
            pass

    def _maybe_warn_outdated_version(self):
        """Если установленная версия Claude Code меньше REQUIRED_CLAUDE_VERSION,
        показывает окно с рекомендацией обновиться. Срабатывает один раз за
        сессию (флаг _outdated_warning_shown)."""
        if getattr(self, "_outdated_warning_shown", False):
            return
        local = getattr(self, "_claude_local_version", "") or ""
        if not local:
            return
        required = REQUIRED_CLAUDE_VERSION
        try:
            cmp = compare_versions(local, required)
        except Exception:
            return
        if cmp >= 0:
            return  # либо ровно required, либо выше — там своя логика блокировки

        self._outdated_warning_shown = True
        self.log(
            f"Установлена устаревшая Claude Code v{local} — рекомендуется обновить до v{required}",
            "warning"
        )
        dlg = ConfirmActionDialog(
            title=tr("Устаревшая   ерсия Claude Code"),
            message=(
                tr("У тебя установле  а Claude Code") + f" v{local} — " +
                tr("это устаревшая версия.") + "\n\n" +
                tr("Проверенная и стабильная версия, на которой это приложение работает гарантированно, — ") +
                f"v{required}. " +
                tr("На более старых версиях возможны "
                   "несовместимости (изменения в формате settings.json, путях, флагах CLI), "
                   "из-за которых запуск через Omniroute / FreeModel может вести себя нестабильно.\n\n") +
                tr("Рекомендуем обновить до") + f" v{required} — " +
                tr("npm переустановит пакет, "
                   "настройки в %USERPROFILE%\\.claude не пострадают.")
            ),
            detail=f"npm install -g @anthropic-ai/claude-code@{required}",
            confirm_text=tr("Обновить до") + f" v{required}",
            icon="↑",
            icon_color=(245, 180, 60),
            parent=self
        )
        if dlg.exec() == QDialog.Accepted:
            self._install_claude_code()

    def _uninstall_claude_code(self):
        """Удаляет Claude Code через npm uninstall с подтверждением"""
        if not self._is_claude_installed():
            self.log("Claude Code не установлен", "info")
            return

        local = getattr(self, "_claude_local_version", "") or self._get_installed_claude_version()
        version_part = f" v{local}" if local else ""

        dlg = ConfirmActionDialog(
            title=tr("Удалить Claude Code"),
            message=(
                tr("Будет удалён глобальный npm-пакет Claude Code") + version_part + ". " +
                tr("Настройки в %USERPROFILE%\\.claude не пострадают — удалится только бинарь.")
            ),
            detail="npm uninstall -g @anthropic-ai/claude-code",
            confirm_text=tr("Удалить"),
            icon="×",
            icon_color=(235, 90, 90),
            parent=self
        )
        if dlg.exec() != QDialog.Accepted:
            self.log("Удаление отменено", "info")
            return

        if not self._is_npm_installed():
            self._show_npm_missing_dialog()
            return

        self.log("Запускаю удаление Claude Code через npm...", "info")
        try:
            subprocess.Popen([
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                # 1) Прибить все запущенные claude.exe / node, держащие бинарь — иначе npm падает с EBUSY
                "Write-Host 'Останавливаю запущенные процессы claude...' -ForegroundColor Cyan; "
                "Get-Process claude -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; "
                "Start-Sleep -Milliseconds 600; "
                # 2) Основная попытка удаления npm-версии
                "Write-Host '  даление Claude Code (npm)...' -ForegroundColor Cyan; "
                "npm uninstall -g @anthropic-ai/claude-code; "
                # 3) Если файл всё ещё залочен и остался — повторная попытка после паузы
                "$npmDir = Join-Path $env:APPDATA 'npm\\node_modules\\@anthropic-ai\\claude-code'; "
                "if (Test-Path $npmDir) { "
                "  Write-Host '`nПовторная попытка (файл был залочен)...' -ForegroundColor Yellow; "
                "  Get-Process claude -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; "
                "  Start-Sleep -Seconds 2; "
                "  npm uninstall -g @anthropic-ai/claude-code; "
                "} "
                "if (Test-Path $npmDir) { "
                "  Write-Host '`nNPM не смог удалить — удаляю папку напрямую...' -ForegroundColor Yellow; "
                "  Remove-Item -Recurse -Force $npmDir -ErrorAction SilentlyContinue; "
                "  Get-ChildItem (Join-Path $env:APPDATA 'npm') -Filter 'claude*' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue; "
                "} "
                # 4) Снести установку через install.ps1 (~/.local/bin + ~/.claude/local)
                "Write-Host '`nУдаление Claude Code (install.ps1)...' -ForegroundColor Cyan; "
                "$localBin = Join-Path $env:USERPROFILE '.local\\bin'; "
                "if (Test-Path $localBin) { "
                "  Get-ChildItem $localBin -Filter 'claude*' -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue; "
                "} "
                "$claudeLocal = Join-Path $env:USERPROFILE '.claude\\local'; "
                "if (Test-Path $claudeLocal) { "
                "  Remove-Item -Recurse -Force $claudeLocal -ErrorAction SilentlyContinue; "
                "} "
                # 5) Финальная проверка
                "$leftNpm = Test-Path $npmDir; "
                "$leftLocal = (Test-Path $claudeLocal) -or (Test-Path (Join-Path $localBin 'claude.exe')); "
                "if ($leftNpm -or $leftLocal) { "
                "  Write-Host '`nНе всё удалось удалить — закрой все окна Claude Code и попробуй снова.' -ForegroundColor Red; "
                "} else { "
                "  Write-Host '`nClaude Code полностью удалён.' -ForegroundColor Green; "
                "} "
                "Write-Host '`nНажмите любую клавишу, чтобы закрыть PowerShell...' -ForegroundColor Cyan; "
                "$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')"
            ])
        except Exception as e:
            self.log(f"Не удалось запустить удаление: {e}", "error")
            return

        # Через несколько секунд обновим состояние кнопок/индикаторов
        def _refresh_after_delay():
            try:
                time.sleep(2.0)
                self.claude_version_checked.emit(
                    self._get_installed_claude_version(),
                    REQUIRED_CLAUDE_VERSION,
                    ""
                )
            except Exception:
                pass

        threading.Thread(target=_refresh_after_delay, daemon=True).start()

    def add_model(self):
        """Добавляет новую модель"""
        dialog = AddModelDialog(self)
        if dialog.exec() == QDialog.Accepted:
            model_name = dialog.get_model_name()
            if model_name and model_name not in self.settings["models"]:
                self.settings["models"].append(model_name)
                # Обновляем модель данных
                self.model_list_model.update_models(self.settings["models"])
                save_settings(self.settings)
                self.log(f"Добавлена модель: {model_name}", "success")

    def remove_model(self):
        """Удаляет выбранную модель"""
        current_model = self.model_combo.currentText()

        # Запрещаем удаление базовой модели
        if current_model == "kr/claude-sonnet-4.5":
            self.log("Нельзя удалить базовую модель", "warning")
            return

        if len(self.settings["models"]) > 1:
            # Показываем кастомный диалог подтверждения
            dialog = ConfirmDeleteDialog(current_model, self)
            result = dialog.exec()

            if result == QDialog.Accepted:
                current_index = self.model_combo.currentIndex()
                self.settings["models"].remove(current_model)
                # Обновляем модель данных
                self.model_list_model.update_models(self.settings["models"])
                save_settings(self.settings)
                self.log(f"Удалена модель: {current_model}", "success")
        else:
            self.log("Нельзя удалить последнюю модель", "warning")

    def _check_for_updates(self):
        """Проверяет наличие обновлений в фоновом режиме"""
        try:
            time.sleep(2)  # Небольшая задержка перед проверкой
            update_info = check_app_update()

            if update_info:
                if update_info.get('update_available'):
                    self.update_info = update_info
                    # Отправляем сигнал в главный поток
                    self.update_available.emit(update_info)
        except Exception as e:
            pass

    def _open_freemodel_stats(self):
        """Открывает диалог статистики freemodel.dev. Если он уже открыт — поднимает наверх."""
        existing = getattr(self, "_freemodel_stats_dialog", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        dlg = FreemodelStatsDialog(self)
        # держим ссылку, чтобы не собрался GC и чтобы можно было фокусировать повторно
        self._freemodel_stats_dialog = dlg
        dlg.show()

    def _poll_freemodel_status(self):
        """Фоновый поллер https://fm.bluealitas.com/api/status.

        Считаем «эффективное» состояние с учётом и overall, и mode:
        если сайт сейчас в режиме `confirming` (после ошибок проверяет, что
        сервис стабилен) — отдаём 'confirming' вне зависимости от overall.
        Так индикатор у бейджа жёлтый, как на сайте.
        Запросы фиксированно каждые 2 секунды — и при успехе, и при ошибке."""
        url = "https://fm.bluealitas.com/api/status"
        ctx = ssl.create_default_context()
        time.sleep(1)
        while True:
            try:
                req = Request(url, headers={"User-Agent": f"ClaudeCodeManager/{APP_VERSION}"})
                with urlopen(req, timeout=8, context=ctx) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                overall = str(data.get("overall") or "unknown").lower()
                mode = str(data.get("mode") or "").lower()
                if mode == "confirming":
                    effective = "confirming"
                elif overall in ("ok", "warn", "bad", "down", "unknown"):
                    effective = overall
                else:
                    effective = "unknown"
                self.freemodel_status_signal.emit(effective)
            except Exception:
                self.freemodel_status_signal.emit("unknown")
            time.sleep(2)

    def _show_update_notification(self, update_info):
        """Авто-запуск скачивания обновления без подтверждения от пользователя."""
        try:
            # Показываем индикатор в углу
            self.update_indicator.setVisible(True)
            self.update_indicator.show()
            self.update_indicator.raise_()

            # Сразу стартуем скачивание — без UpdateAppDialog и без кнопки «Обновить»
            from PySide6.QtCore import QTimer
            QTimer.singleShot(600, self._start_update_download)
        except Exception:
            pass

    def _on_update_indicator_clicked(self):
        """Клик по индикатору — обновление уже идёт автоматически, ничего не делаем."""
        # Авто-обновление само открывает окно скачивания; повторный запуск не нужен.
        return

    def _start_update_download(self):
        """Запускает скачивание обновления (один раз)."""
        if not self.update_info or not self.update_info.get('download_url'):
            return
        # Защита от повторного запуска (auto-start + ручной клик в редком случае)
        if getattr(self, '_update_download_started', False):
            return
        self._update_download_started = True

        download_dialog = DownloadUpdateDialog(self.update_info, self)
        download_dialog.start_download()
        download_dialog.exec()

        # Если скачивание успешно, скрываем индикатор
        if download_dialog.download_success:
            self.update_indicator.setVisible(False)
        else:
            # Скачивание не прошло — разрешим повторную попытку при следующем чек-цикле
            self._update_download_started = False

# ============================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================================

def main():
    app = QApplication(sys.argv)
    # Глобальный менеджер языка — создаём ПОСЛЕ QApplication, но ДО окон,
    # чтобы виджеты при инициализации уже могли читать LANG.lang.
    global LANG
    LANG = LanguageManager()
    window = ClaudeManager()
    window.show()

    # Если приложение запущено БЕЗ прав администратора — показываем окно-предупреждение
    # один раз при старте. Окно модальное относительно главного, не блокирует процесс
    # и закрывается одной кнопкой «Понятно». Если IsUserAnAdmin() недоступна
    # (нестандартное окружение) — молча пропускаем, чтобы не пугать ложным алертом.
    try:
        import ctypes
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        is_admin = True

    if not is_admin:
        try:
            # Небольшая задержка через singleShot, чтобы главное окно успело
            # отрендериться — диалог красивее «всплывает» поверх готового UI,
            # а не поверх пустого холста на первом фрейме.
            from PySide6.QtCore import QTimer
            def _show_admin_warn():
                try:
                    AdminWarningDialog(window).exec()
                except Exception:
                    pass
            QTimer.singleShot(250, _show_admin_warn)
        except Exception:
            pass

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
