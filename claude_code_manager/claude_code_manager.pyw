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
import sys, subprocess, os, threading, time, json, socket, math, ssl, random, shutil, re
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QFrame,
                               QComboBox, QLineEdit, QDialog, QScrollArea, QTextEdit, QFileDialog, QStyledItemDelegate, QMessageBox, QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QProgressBar, QCheckBox, QSizePolicy)
from PySide6.QtCore import Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, QAbstractListModel, QModelIndex, Property, QObject, QThread, QSize, QEvent
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QBrush, QTextCursor, QIcon, QPixmap, QLinearGradient, QRadialGradient, QPainterPath, QFontMetrics
from PySide6.QtCore import QPointF, QRectF, QUrl
from PySide6.QtSvg import QSvgRenderer

APP_VERSION = "5.7.2"  # Для обновлений
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
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
        except Exception as e:
            # Файл существует, но не распарсился (битый JSON и т.п.).
            # Делаем бэкап, чтобы save_settings НЕ затёр пользовательские данные дефолтами.
            try:
                backup_path = SETTINGS_FILE + ".corrupt.bak"
                # Не перезаписываем предыдущий бэкап, если он уже есть
                if not os.path.exists(backup_path):
                    shutil.copy2(SETTINGS_FILE, backup_path)
                else:
                    # Складываем нумерованные бэкапы, чтобы ничего не терялось
                    i = 2
                    while os.path.exists(f"{backup_path}.{i}"):
                        i += 1
                    shutil.copy2(SETTINGS_FILE, f"{backup_path}.{i}")
            except:
                pass
            # Возвращаем None-подобный сигнал через исключение наверх было бы правильнее,
            # но чтобы не ломать вызывающий код — возвращаем дефолт. Бэкап уже сделан.
            print(f"[load_settings] Ошибка чтения {SETTINGS_FILE}: {e}. Бэкап сохранён рядом.")
            return _default_settings()
        else:
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
            loaded.setdefault("auto_update_enabled", True)
            migrate_api_keys(loaded)
            return loaded
    return _default_settings()

def _default_settings():
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
        "app_language": "ru",
        "auto_update_enabled": True,
        "use_1m_context": False,
        "api_keys": [],
        "selected_key_id": ""
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
    settings.setdefault("auto_update_enabled", True)
    return settings

def save_settings(settings):
    ensure_settings_dir()
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except:
        pass


# ============================================================
# УПРАВЛЕНИЕ API-КЛЮЧАМИ (пул именованных ключей)
# ============================================================
# Модель: settings["api_keys"] = [
#   {
#     "id", "name", "value",
#     "enabled": bool,               # True = ключ активен (зелёный)
#     "activated_at": epoch-seconds, # когда включили (для истории)
#     "limit_type": "" | "5h" | "7d",# тип лимита (только когда enabled=False)
#     "resets_at":  0 | epoch-seconds, # когда лимит закончится и ключ автовключится
#   }
# ]
# Цвет рамки карточки:
#   green  — enabled=True (ключ активен)
#   yellow — enabled=False, limit_type='5h' (короткий 5-часовой лимит)
#   red    — enabled=False, limit_type='7d' (длинный 7-дневный лимит)
# При достижении resets_at ключ автоматически включается (enabled=True),
# limit_type/resets_at очищаются. При запуске Claude берётся первый ЗЕЛЁНЫЙ
# ключ; его значение зеркалируется в settings["custom_api_key"] для
# обратной совместимости со старым кодом.

KEY_LIMIT_5H_SECONDS = 5 * 3600
KEY_LIMIT_7D_SECONDS = 7 * 24 * 3600

def _new_key_id():
    return f"k{int(time.time() * 1000)}{random.randint(1000, 9999)}"

def key_expired(key):
    """True, если у выключенного ключа истёк таймер лимита и его пора автовключить."""
    if key.get("enabled", False):
        return False
    resets_at = key.get("resets_at", 0) or 0
    return bool(resets_at) and time.time() >= resets_at

def reset_key_limit(key):
    """Сбросить лимит и вернуть ключ в активное состояние.
    Возвращает True, если что-то реально поменяли."""
    changed = False
    if not key.get("enabled", False):
        key["enabled"] = True
        key["activated_at"] = time.time()
        changed = True
    if key.get("limit_type"):
        key["limit_type"] = ""
        changed = True
    if key.get("resets_at"):
        key["resets_at"] = 0
        changed = True
    return changed

def key_color_state(key):
    """green / red / yellow — визуальное состояние ключа.
    - enabled=True                     → green (активен).
    - enabled=False, limit_type='5h'   → yellow (5-часовой лимит).
    - enabled=False, limit_type='7d'   → red (7-дневный лимит).
    - enabled=False без корректного типа → red (fallback, старые записи).
    Если resets_at уже наступил, считаем ключ включённым (green) — авто-сброс.
    """
    if key.get("enabled", False):
        return "green"
    # Если таймер лимита уже истёк — визуально ключ уже активен.
    # (Реальное обновление enabled/limit_type делает refresh_state в UI-потоке
    #  или reset_key_limit при загрузке.)
    if key_expired(key):
        return "green"
    lt = key.get("limit_type", "")
    if lt == "5h":
        return "yellow"
    return "red"  # '7d' или неизвестный → красный

def first_active_key(settings):
    """Активный ключ, который реально пойдёт в ANTHROPIC_API_KEY.
    Приоритет: явно выбранный пользователем (selected_key_id), если он зелёный;
    иначе — первый зелёный по порядку."""
    keys = settings.get("api_keys", [])
    sel_id = settings.get("selected_key_id") or ""
    if sel_id:
        for k in keys:
            if k.get("id") == sel_id and key_color_state(k) == "green":
                return k
    for k in keys:
        if key_color_state(k) == "green":
            return k
    return None

def sync_custom_api_key(settings):
    """Зеркалирует значение активного ключа в custom_api_key
    (обратная совместимость: код запуска читает именно custom_api_key).
    Заодно чистит устаревший selected_key_id, если такого ключа больше нет."""
    keys = settings.get("api_keys", [])
    ids = {k.get("id") for k in keys}
    if settings.get("selected_key_id") and settings["selected_key_id"] not in ids:
        settings["selected_key_id"] = ""
    k = first_active_key(settings)
    settings["custom_api_key"] = k.get("value", "") if k else ""
    # Если явного выбора нет, но есть зелёный кандидат — зафиксируем его как выбранный,
    # чтобы UI сразу подсветил активную карточку.
    if k and not settings.get("selected_key_id"):
        settings["selected_key_id"] = k.get("id", "")
    return settings

def migrate_api_keys(settings):
    """Приводит settings["api_keys"] к нормальному виду; при отсутствии списка
    переносит старый одиночный custom_api_key как «Ключ 1»."""
    keys = settings.get("api_keys")
    if not isinstance(keys, list):
        keys = []
    if not keys:
        legacy = (settings.get("custom_api_key") or "").strip()
        if legacy:
            keys = [{
                "id": _new_key_id(),
                "name": "Ключ 1",
                "value": legacy,
                "enabled": True,
                "activated_at": time.time(),
            }]
    norm = []
    for k in keys:
        if not isinstance(k, dict):
            continue
        val = (k.get("value") or "").strip()
        if not val:
            continue
        enabled = bool(k.get("enabled", True))
        # limit_type: только для выключенных ключей; допустимые значения '5h'|'7d'.
        limit_type = k.get("limit_type", "") if not enabled else ""
        if limit_type not in ("5h", "7d"):
            limit_type = "" if enabled else limit_type  # старые записи без типа → пусто
        resets_at = k.get("resets_at", 0) or 0
        try:
            resets_at = float(resets_at)
        except (TypeError, ValueError):
            resets_at = 0
        # Автосброс: если таймер лимита уже истёк, включаем ключ прямо в миграции —
        # чтобы фактическое состояние соответствовало визуальному после долгой паузы.
        if not enabled and resets_at and time.time() >= resets_at:
            enabled = True
            limit_type = ""
            resets_at = 0
        norm.append({
            "id": k.get("id") or _new_key_id(),
            "name": (k.get("name") or "Ключ").strip() or "Ключ",
            "value": val,
            "enabled": enabled,
            "activated_at": k.get("activated_at", 0) or 0,
            "limit_type": limit_type if not enabled else "",
            "resets_at": resets_at if not enabled else 0,
        })
    settings["api_keys"] = norm
    sync_custom_api_key(settings)
    return settings


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
    "Поддержка новых версий Claude Code": "Support for new Claude Code versions",
    "Авто-обновление": "Auto-update",
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
    "Управление API ключами": "Manage API keys",
    "Зелёный — активен. Жёлтый — 5-часовой лимит. Красный — 7-дневный лимит.": "Green — active. Yellow — 5-hour limit. Red — 7-day limit.",
    "Ключей пока нет — добавьте первый ниже": "No keys yet — add the first one below",
    "Добавить новый ключ:": "Add new key:",
    "Название": "Name",
    "Удалить этот API ключ?": "Delete this API key?",
    "Ключ и его настройки будут удалены безвозвратно.": "The key and its settings will be permanently removed.",
    "Да, удалить": "Yes, delete",
    "Ключ": "Key",
    "активен": "active",
    "подтвердите": "confirm",
    "выключен": "disabled",
    # ── Ultracode-совместимость: варнинг при downgrade
    "не поддерживает ultracode — effort понижен до max":
        "does not support ultracode — effort lowered to max",
    "не поддерживает ultracode — понижаю до max":
        "does not support ultracode — lowering to max",
    # ── ModelDialog: подписи моделей (короткие описания)
    "быстрый и дешёвый — для простых задач": "fast and cheap — for simple tasks",
    "новый Sonnet — быстрее и умнее 4.6": "new Sonnet — faster and smarter than 4.6",
    "мощный Opus — уверенно решает большинство задач": "powerful Opus — handles most tasks confidently",
    "усиленный Opus 4.7 — сложные многошаговые задачи": "amplified Opus 4.7 — complex multi-step tasks",
    "флагманский Opus 4.8 — максимум качества": "flagship Opus 4.8 — maximum quality",
    "экспериментальная Fable 5 — необычные вопросы": "experimental Fable 5 — unusual questions",
    # ── EffortDialog: заголовок и подписи уровней
    "Reasoning Effort": "Reasoning Effort",
    "минимум размышлений — быстро и дёшево": "minimal reasoning — fast and cheap",
    "сбалансированный режим по умолчанию": "balanced default mode",
    "усиленное рассуждение для сложных задач": "amplified reasoning for hard problems",
    "экстремальный уровень — редкие тяжёлые случаи": "extreme reasoning — rare heavy cases",
    "максимум размышлений — потолок обычного режима": "maximum reasoning — ceiling of normal mode",
    "максимум мощности + многоагентная оркестрация": "maximum power + multi-agent orchestration",
    "Reasoning effort изменён на": "Reasoning effort changed to",
    # ── диалог выбора типа лимита при выключении ключа
    "Выберите тип лимита": "Choose limit type",
    "На какой срок отключить ключ?": "For how long to disable the key?",
    "5-часовой лимит": "5-hour limit",
    "7-дневный лимит": "7-day limit",
    "макс. 5 часов": "max 5 hours",
    "макс. 7 дней": "max 7 days",
    # ── диалог ввода длительности
    "Через сколько сбросится лимит?": "When should the limit reset?",
    "Часы": "Hours",
    "Минуты": "Minutes",
    "Дни": "Days",
    "Подтвердить": "Confirm",
    "Максимум 5 часов": "Maximum 5 hours",
    "Максимум 7 дней": "Maximum 7 days",
    "Укажите время больше нуля": "Set a value greater than zero",
    # ── обратный отсчёт на карточке ключа
    "Сброс через": "Resets in",
    "готов к сбросу": "ready to reset",
    "д": "d",
    "ч": "h",
    "м": "m",
    "с": "s",
    "Ключи не добавлены — откройте «Управление»": "No keys added — open “Manage”",
    "Нет активного API ключа — включите ключ в окне «Управление»": "No active API key — enable one in the “Manage” window",
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
    "Ошибка": "Error",
    "МБ": "MB",
    "Удаление status line": "Removing status line",
    "Status line удалён ✓": "Status line removed ✓",
    "Claude исправлен ✓": "Claude fixed ✓",
    "Claude Code обновлён ✓": "Claude Code updated ✓",
    "Claude Code установлен ✓": "Claude Code installed ✓",
    # ── баннеры
    "Запуск без прав администратора": "Running without administrator rights",
    "Рекомендуется запустить\nот имени администратора": "Recommended to run\nas administrator",
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
    # ── диалог прогресса install/update/uninstall
    "Идёт установка…\nНе закрывайте окно PowerShell.":
        "Installing…\nDo not close the PowerShell window.",
    "Идёт обновление…\nНе закрывайте окно PowerShell.":
        "Updating…\nDo not close the PowerShell window.",
    "Идёт удаление…\nНе закрывайте окно PowerShell.":
        "Uninstalling…\nDo not close the PowerShell window.",
    "Claude Code установлен ✓": "Claude Code installed ✓",
    "Claude Code обновлён ✓": "Claude Code updated ✓",
    "Claude Code удалён ✓": "Claude Code uninstalled ✓",
    "Удаление Claude Code": "Uninstall Claude Code",
    "Удаление отменено": "Uninstall cancelled",
    "Удаление не завершено": "Uninstall not completed",
    "Удаление завершено успешно.": "Uninstall completed successfully.",
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
    "Fable 5 — Модель высшего класса": "Fable 5 — Top-tier model",
    "Один запрос при уровне /effort High может потребовать "
    "до 15% вашего дневного лимита токенов.\n\n"
    "Fable 5 на среднем уровне /effort (Medium) превосходит "
    "Opus 4.8 на максимальных настройках (xHigh / Max) — разрыв "
    "составляет около 5% в пользу Fable 5.\n\n"
    "По общей мощности Fable 5 превосходит Opus 4.8 примерно "
    "в 2 раза — но и стоит соответственно.\n\n"
    "Используйте эту модель только тогда, когда другие уже не "
    "справляются — она стоит каждого токена, но расходует их "
    "значительно быстрее.":
        "A single request at /effort High can burn up to 15% of "
        "your daily token limit.\n\n"
        "Fable 5 at /effort Medium beats Opus 4.8 at its maximum "
        "settings (xHigh / Max) — the gap is about 5% in Fable 5's "
        "favor.\n\n"
        "Overall Fable 5 is roughly 2× more powerful than Opus 4.8 — "
        "and priced accordingly.\n\n"
        "Use this model only when others no longer keep up — it's "
        "worth every token, but it spends them much faster.",
    "Выпущена Anthropic · 09 июня 2026": "Released by Anthropic · June 09, 2026",
    "Продолжить": "Continue",
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

    # ── status label
    "Установлена": "Installed",
    "Доступно обновление": "Update available",
    "Обновить Claude Code": "Update Claude Code",
    "Откатить Claude Code": "Rollback Claude Code",

    # ── Add to PATH button + dialog
    "Добавить в PATH": "Add to PATH",
    "Добавлено в PATH": "Added to PATH",
    "Уже в PATH": "Already in PATH",
    "Не удалось добавить в PATH": "Could not add to PATH",
    "Claude Code не найден": "Claude Code not found",
    "Не нашёл папку с установленной Claude Code. "
    "Сначала установи Claude Code кнопкой выше, потом жми «Добавить в PATH».":
        "The Claude Code install folder wasn't found. "
        "Install Claude Code with the button above first, then click «Add to PATH».",
    "Папка с Claude Code уже прописана в пользовательской PATH.":
        "The Claude Code folder is already in your user PATH.",
    "Добавит папку с Claude Code в пользовательскую PATH, чтобы "
    "команду «claude» можно было запускать из любой консоли. "
    "После этого перезапусти терминал.":
        "Adds the Claude Code folder to your user PATH so the «claude» "
        "command works from any console. Restart the terminal after this.",
    "Папка с Claude Code добавлена в пользовательскую PATH. "
    "Открой новую консоль и проверь: claude --version.":
        "The Claude Code folder was added to your user PATH. "
        "Open a new console and check: claude --version.",
    "Что-то пошло не так при записи в реестр:":
        "Something went wrong while writing to the registry:",
    "Понятно": "Got it",
    "Ок": "OK",
    "Добавить": "Add",

    # ── Safe-mode install / rollback / block-launch dialogs
    "проверенная стабильная версия, на которой приложение работает всегда. "
    "Установщик поставит именно её. Настройки в %USERPROFILE%\\.claude не пострадают.":
        "the proven stable version the app always works on. "
        "The installer will pin exactly this version. Settings in %USERPROFILE%\\.claude are untouched.",
    "проверенная стабильная версия, на которой приложение работает всегда.":
        "the proven stable version the app always works on.",
    "проверенная стабильная версия, на которой приложение работает всегда.\n\n"
    "Откроется окно PowerShell, где пойдёт установка.":
        "the proven stable version the app always works on.\n\n"
        "A PowerShell window will open and the install will start.",
    "а приложение сейчас в безопасном режиме и работает только с":
        "and the app is in safe mode and only runs on",
    "проверенная стабильная версия, на которой приложение работает всегда.\n\n"
    "Нажми «Откатить» — установщик поставит проверенную версию, и запуск снова заработает.\n\n"
    "Если откатывать версию не хочется — включи «Авто-обновление» на панели над кнопками. "
    "В этом режиме приложение перестаёт следить за версией и запускает любую установленную.":
        "the proven stable version the app always works on.\n\n"
        "Click «Roll back» — the installer will put back the proven version and launch will work again.\n\n"
        "If you don't want to roll back — turn on «Auto-update» on the panel above the buttons. "
        "In that mode the app stops watching the version and launches whatever is installed.",
    "установщик поставит нужную версию, настройки в %USERPROFILE%\\.claude не пострадают.":
        "the installer will put the required version; settings in %USERPROFILE%\\.claude aren't affected.",

    # ── Auto-update toggle confirm dialog
    "Включится официальный установщик "
    "(npm install -g @anthropic-ai/claude-code). Claude Code будет "
    "обновляться сам до последней версии.\n\n"
    "Сейчас всё работает и на последней версии. Если что-то "
    "вдруг перестанет работать — просто выключи этот переключатель, "
    "и приложение вернёт проверенную версию, на которой всё "
    "гарантированно работает.":
        "The official installer will kick in "
        "(npm install -g @anthropic-ai/claude-code). Claude Code will "
        "keep itself updated to the latest version.\n\n"
        "Right now everything works on the latest version too. If something "
        "suddenly breaks — just turn this switch off and the app will bring back "
        "the proven version everything is guaranteed to work on.",
    "Включить": "Enable",

    # ── Install Claude Code (official variant title/text)
    "Скачает и поставит последнюю версию Claude Code через npm "
    "(@anthropic-ai/claude-code).\n\n"
    "Настройки в %USERPROFILE%\\.claude не пострадают.\n\n"
    "Откроется окно PowerShell, где пойдёт установка.":
        "Downloads and installs the latest Claude Code via npm "
        "(@anthropic-ai/claude-code).\n\n"
        "Settings in %USERPROFILE%\\.claude are not affected.\n\n"
        "A PowerShell window will open and the install will start.",
    "Обновление Claude Code": "Update Claude Code",
    "последняя": "latest",

    # ── Safe-mode switch (turning auto-update OFF)
    "Переход в безопасный режим": "Switching to safe mode",
    "Приложение перестанет обновлять Claude Code и зафиксируется "
    f"на проверенной версии v{REQUIRED_CLAUDE_VERSION} — именно на ней "
    "гарантированно работают FreeModel / Omniroute / любые сторонние "
    "Base URL и API-ключи.\n\n"
    "Встроенный автообновлятор Claude Code будет выключен "
    "(DISABLE_UPDATES=1, autoUpdates=false), чтобы CLI сам не "
    "подтянул новую версию за спиной. Если сейчас установлена "
    "версия новее — запуск будет заблокирован, пока не откатишь "
    "её кнопкой «Откатить Claude Code».\n\n"
    "Включай этот режим только если сам этого хочешь или если "
    "на новой версии реально появились проблемы.":
        "The app will stop updating Claude Code and will pin to the proven "
        f"version v{REQUIRED_CLAUDE_VERSION} — the one that reliably works "
        "with FreeModel / Omniroute / any third-party Base URLs and API keys.\n\n"
        "Claude Code's built-in auto-updater will be turned off "
        "(DISABLE_UPDATES=1, autoUpdates=false), so the CLI can't quietly "
        "pull in a newer version behind your back. If you currently have a "
        "newer version installed, launch will be blocked until you roll it "
        "back with the «Roll back Claude Code» button.\n\n"
        "Turn this on only if you actually want to, or if the newer version "
        "has caused real problems for you.",
    "Перейти в безопасный режим": "Switch to safe mode",
    "Поддержка новых версий: включение отменено": "Support for new versions: enabling cancelled",
    "Поддержка новых версий Claude Code включена": "Support for new Claude Code versions enabled",
    "Безопасный режим: переход отменён": "Safe mode: switch cancelled",
    "Поддержка новых версий Claude Code выключена — вернулись к безопасному режиму":
        "Support for new Claude Code versions disabled — back to safe mode",

    # ── 1M-context toggle
    "1M-контекст включён": "1M context enabled",
    "1M-контекст выключен": "1M context disabled",
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

def check_claude_code_latest_version():
    """Запрашивает реально опубликованную последнюю версию Claude Code CLI
    (npm registry). Возвращает пустую строку при любой ошибке сети."""
    try:
        req = Request(
            "https://registry.npmjs.org/@anthropic-ai/claude-code/latest",
            headers={'User-Agent': 'ClaudeManager-Updater'}
        )
        with urlopen(req, timeout=8, context=_ssl_context) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return data.get('version', '') or ''
    except:
        return ''

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
# БЕЙДЖ freemodel.dev — просто надпись
# ============================================================

class FreemodelBrand(QWidget):
    """Логотип «freemodel.dev» в левом верхнем углу главного окна.
    «freemodel» — зелёный (#34d399), «.dev» — мягкий белый (#d1d5db).
    Индикатор статуса и клик убраны — окно статистики больше не работает."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

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
            # Зелёное свечение с плавной пульсацией (уменьшил радиус)
            glow_radius = 5.0 + 2.5 * pulse
            glow_alpha = int(70 * pulse)
            painter.setBrush(QColor(52, 211, 153, glow_alpha))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center, glow_radius, glow_radius)

            # Основная точка с плавной пульсацией яркости
            t = 0.85 + 0.15 * pulse
            painter.setBrush(QColor(int(52 * t), int(211 * t), int(153 * t)))
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
        hover_r, hover_g, hover_b = 52, 211, 153  # новый FreeModel зелёный

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


class EffortPickerComboBox(PickerComboBox):
    """PickerComboBox с подменённым popup: вместо PickerDialog со списком
    карточек открывается компактный EffortDialog с ползунком.
    Текст текущего значения рисуется вручную — центр, жирный, ВЕРХНИЙ регистр
    (как метки в EffortSlider), чтобы состояние комбо визуально совпадало с
    активной ячейкой ползунка."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Явно храним QColor текста — чтобы не парсить его каждый paintEvent.
        # Обновляется через setTextColor().
        self._text_qcolor = QColor(200, 200, 200)
        # Комбо на главной странице — display-only. Effort меняется теперь
        # внутри ModelDialog через встроенный EffortSlider, поэтому клик по
        # самому комбо ничего не открывает: убираем указатель, отключаем
        # клавиатурный фокус.
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def setTextColor(self, color):
        # Синхронизируем свой QColor и позволяем базе применить CSS
        # (нужно только для цвета placeholder-текста стрелки drop-down).
        try:
            if isinstance(color, QColor):
                self._text_qcolor = QColor(color)
            elif isinstance(color, tuple) and len(color) >= 3:
                self._text_qcolor = QColor(int(color[0]), int(color[1]), int(color[2]))
            elif isinstance(color, str):
                m = re.search(r"(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color)
                if m:
                    self._text_qcolor = QColor(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            pass
        super().setTextColor(color)

    def paintEvent(self, event):
        # Сначала рисуем стандартный «фон + рамка» через стиль, но БЕЗ текста
        # (currentText = "") — потом рисуем свой центрированный жирный UPPERCASE.
        from PySide6.QtWidgets import QStyleOptionComboBox, QStylePainter, QStyle
        painter = QStylePainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        opt.currentText = ""
        opt.currentIcon = QIcon()
        painter.drawComplexControl(QStyle.CC_ComboBox, opt)

        # Наш текст: жирный, UPPERCASE, по центру
        text = (self.currentText() or "").upper()
        if not text:
            return
        f = QFont(self.font())
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QPen(self._text_qcolor))
        # Оставляем небольшой отступ справа под треугольник drop-down,
        # чтобы длинное "ULTRACODE" не наезжало на стрелку.
        rect = self.rect().adjusted(6, 0, -14, 0)
        painter.drawText(rect, Qt.AlignCenter, text)

    def showPopup(self):
        # Отдельного popup больше нет: effort меняется через EffortSlider
        # внутри ModelDialog. Оставляем метод как no-op, чтобы стандартный
        # QComboBox-механизм не пытался открыть системный список.
        return

    def mousePressEvent(self, event):
        # Клик по комбо ничего не делает — комбо теперь display-only.
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def keyPressEvent(self, event):
        # Space/Enter на native QComboBox открывают popup — нам это не нужно.
        event.accept()

    def enterEvent(self, event):
        # Комбо display-only — hover-подсветка рамки не нужна. Явно держим
        # _is_hovered=False, чтобы StyledComboBox._animate_hover не оживил
        # рамку до яркого цвета акцента.
        self._is_hovered = False
        # super() базового QWidget всё равно нужен для системных сигналов
        # (курсор и т.п.), но НЕ StyledComboBox.enterEvent, который взводит флаг.
        QComboBox.enterEvent(self, event)

    def leaveEvent(self, event):
        self._is_hovered = False
        QComboBox.leaveEvent(self, event)


class ModelPickerComboBox(PickerComboBox):
    """PickerComboBox для FreeModel-модели: при клике открывает ModelDialog
    вместо стандартного списка карточек. Текст в комбо просто жирный —
    без принудительного UPPERCASE (модели уже читаются в 'Opus 4.8' виде,
    ломать capitalisation не нужно)."""

    # Отдельный сигнал: model + effort. Родитель (ClaudeCodeManager) слушает
    # его и вызывает и _fm_model_changed, и _on_effort_changed. Стандартный
    # currentTextChanged на комбо продолжает работать для модели.
    modelEffortPicked = Signal(str, str)

    def showPopup(self):
        if self._picker_dlg is not None:
            return
        cur = self.currentText()
        if cur not in MODEL_ORDER:
            cur = "Opus 4.8"
        # Пробрасываем текущий effort из settings в ModelDialog
        current_effort = "high"
        try:
            parent_win = self.window()
            if parent_win is not None and hasattr(parent_win, "settings"):
                eff = parent_win.settings.get("reasoning_effort", "high")
                if eff in EFFORT_LEVELS:
                    current_effort = eff
        except Exception:
            pass
        dlg = ModelDialog(current_model=cur, parent=self.window(), current_effort=current_effort)
        dlg.applied.connect(self._on_model_effort_picked)
        dlg.destroyed.connect(self._on_picker_destroyed)
        self._picker_dlg = dlg

        def _show_and_position():
            dlg.show()
            dlg.adjustSize()
            dw, dh = dlg.width(), dlg.height()
            parent_win = self.window()
            try:
                if parent_win is not None:
                    pg = parent_win.frameGeometry()
                    center = pg.center()
                    dlg.move(center.x() - dw // 2, center.y() - dh // 2)
            except Exception:
                pass

        QTimer.singleShot(0, _show_and_position)

    def _on_model_effort_picked(self, model, effort):
        # Сначала выставляем сам текст комбо (currentTextChanged триггерит
        # _fm_model_changed → _on_effort_changed через downgrade-логику), а
        # потом отдельно пробрасываем effort, чтобы владелец приложения
        # сохранил его и обновил EffortPickerComboBox.
        if model and model != self.currentText():
            self.setCurrentText(model)
        try:
            self.modelEffortPicked.emit(model, effort)
        except Exception:
            pass


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
    """Предупреждение о модели Fable 5 — модель высшего класса."""
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
                border: 2px solid rgba(235, 90, 90, 0.6);
                border-radius: 18px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(12)

        # Иконка — огонь
        icon_label = QLabel("🔥")
        icon_label.setFont(QFont("Segoe UI Emoji", 38))
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Главный заголовок
        title_label = QLabel(tr("Fable 5 — Модель высшего класса"))
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: rgb(235, 110, 110);
                background: transparent;
                border: none;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: rgba(235, 90, 90, 0.3); background: rgba(235, 90, 90, 0.3); border: none; max-height: 1px;")
        layout.addWidget(sep)

        # Основное описание
        desc_label = QLabel(tr(
            "Один запрос при уровне /effort High может потребовать "
            "до 15% вашего дневного лимита токенов.\n\n"
            "Fable 5 на среднем уровне /effort (Medium) превосходит "
            "Opus 4.8 на максимальных настройках (xHigh / Max) — разрыв "
            "составляет около 5% в пользу Fable 5.\n\n"
            "По общей мощности Fable 5 превосходит Opus 4.8 примерно "
            "в 2 раза — но и стоит соответственно.\n\n"
            "Используйте эту модель только тогда, когда другие уже не "
            "справляются — она стоит каждого токена, но расходует их "
            "значительно быстрее."
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

        # Плашка с датой релиза
        release_label = QLabel(tr("Выпущена Anthropic · 09 июня 2026"))
        release_label.setFont(QFont("Segoe UI", 9))
        release_label.setStyleSheet("""
            QLabel {
                color: rgba(235, 110, 110, 0.85);
                background: rgba(235, 90, 90, 0.1);
                border: 1px solid rgba(235, 90, 90, 0.28);
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        release_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(release_label)

        layout.addSpacing(4)

        # Кнопки
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_cancel = GlowDialogButton(tr("Отмена"),
                                      base_rgb=(90, 90, 90),
                                      hover_rgb=(120, 120, 120))
        btn_cancel.clicked.connect(self.reject)
        btn_ok = GlowDialogButton(tr("Продолжить"),
                                  base_rgb=(235, 90, 90),
                                  hover_rgb=(235, 110, 110))
        btn_ok.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addSpacing(12)
        btn_row.addWidget(btn_ok)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedWidth(480)

        # Анимация появления
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
            text = f"{self._progress}%  •  {self._downloaded_mb:.1f} / {self._total_mb:.1f} {tr('МБ')}"
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
        self.setCursor(Qt.PointingHandCursor)
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
    EN активен → подсветка зелёная (#34d399, унифицированный зелёный цвет).
    RU активен → подсветка холодная голубоватая (#6aa9ff).
    Плавная анимация цвета пилюли и яркости лейблов между состояниями.
    """
    toggled = Signal(str)  # 'ru' | 'en'

    # Цвета берутся из унифицированной палитры приложения (#34d399) и подбираются
    # к нему по контрасту для RU.
    _EN_COL = (52, 211, 153)   # новый зелёный
    _RU_COL = (106, 169, 255)  # #6aa9ff

    def __init__(self, lang="ru", parent=None):
        super().__init__(parent)
        self.setFixedSize(78, 22)
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


class ContextToggle(QWidget):
    """Компактный переключатель размера контекста 200K / 1M.

    Полная стилистическая копия LanguageToggle: слегка скруглённый прямоугольник
    (radius ~6), плавная анимация цвета пилюли и яркости лейблов, hover-подсветка
    неактивной стороны в цвет соответствующей опции.

    200K активен → холодная голубоватая (#6aa9ff, как RU в LanguageToggle).
    1M активен → зелёная (#34d399, как EN — унифицированный зелёный).
    """
    toggled = Signal(bool)  # True = 1M, False = 200K

    _200K_COL = (106, 169, 255)  # #6aa9ff (как RU)
    _1M_COL = (52, 211, 153)     # новый зелёный (как EN)

    def __init__(self, one_m=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(78, 22)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self._one_m = bool(one_m)
        self._progress = 1.0 if self._one_m else 0.0
        self._target = self._progress

        self._hover_200 = 0.0
        self._hover_1m = 0.0
        self._hover_200_target = 0.0
        self._hover_1m_target = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def isOneM(self):
        return self._one_m

    def setOneM(self, val, animate=True):
        val = bool(val)
        if val == self._one_m:
            return
        self._one_m = val
        self._target = 1.0 if val else 0.0
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
        for name in ("_hover_200", "_hover_1m"):
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
        is_right = event.pos().x() >= self.width() / 2
        new_val = is_right
        if new_val != self._one_m:
            self._one_m = new_val
            self._target = 1.0 if new_val else 0.0
            self.toggled.emit(new_val)
            self.update()

    def mouseMoveEvent(self, event):
        is_right = event.pos().x() >= self.width() / 2
        if is_right:
            self._hover_1m_target = 0.0 if self._one_m else 1.0
            self._hover_200_target = 0.0
        else:
            self._hover_200_target = 0.0 if not self._one_m else 1.0
            self._hover_1m_target = 0.0
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_200_target = 0.0
        self._hover_1m_target = 0.0
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self._progress
        w, h = self.width(), self.height()

        track_r = 6.0
        pill_r = 5.0

        p.setBrush(QColor(28, 28, 33))
        p.setPen(QPen(QColor(60, 60, 65), 1.4))
        p.drawRoundedRect(QRectF(0.7, 0.7, w - 1.4, h - 1.4), track_r, track_r)

        r0, g0, b0 = self._200K_COL
        r1, g1, b1 = self._1M_COL
        r = int(r0 + (r1 - r0) * t)
        g = int(g0 + (g1 - g0) * t)
        b = int(b0 + (b1 - b0) * t)

        pad = 2.5
        pill_w = w / 2 - pad
        pill_x = pad / 2 + (w / 2) * t

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

        grad = QLinearGradient(QPointF(0, pad), QPointF(0, h - pad))
        grad.setColorAt(0.0, QColor(min(255, r + 18), min(255, g + 18), min(255, b + 18), 240))
        grad.setColorAt(1.0, QColor(max(0, r - 10), max(0, g - 10), max(0, b - 10), 240))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(pill_x, pad, pill_w, h - pad * 2), pill_r, pill_r)

        p.setFont(QFont("Segoe UI", 9, QFont.Bold))

        left_active = 1.0 - t
        if left_active > 0.5:
            left_pen = QColor(20, 22, 28)
        else:
            shade = int(130 + 25 * (1 - t))
            base = QColor(shade, shade, shade + 5)
            hr, hg, hb = self._200K_COL
            hover = self._hover_200
            left_pen = QColor(
                int(base.red()   + (hr - base.red())   * hover),
                int(base.green() + (hg - base.green()) * hover),
                int(base.blue()  + (hb - base.blue())  * hover),
            )
        p.setPen(left_pen)
        p.drawText(QRectF(0, 0, w / 2, h), Qt.AlignCenter, "200K")

        if t > 0.5:
            right_pen = QColor(15, 28, 22)
        else:
            shade = int(130 + 25 * t)
            base = QColor(shade, shade + 5, shade)
            hr, hg, hb = self._1M_COL
            hover = self._hover_1m
            right_pen = QColor(
                int(base.red()   + (hr - base.red())   * hover),
                int(base.green() + (hg - base.green()) * hover),
                int(base.blue()  + (hb - base.blue())  * hover),
            )
        p.setPen(right_pen)
        p.drawText(QRectF(w / 2, 0, w / 2, h), Qt.AlignCenter, "1M")

        p.end()


class _CtxSeparator(QWidget):
    """Тонкая сероватая вертикальная полоска — визуальный разделитель между
    текстом выбранной модели и 1M-тумблером. Служит также «hover-щитом»:
    когда курсор над ней, рамка combobox'а модели не подсвечивается."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(6, 22)
        # Курсор — стрелка (не рука), полоска не кликабельная
        self.setCursor(Qt.ArrowCursor)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(120, 120, 130), 1.2))
        x = self.width() / 2.0
        p.drawLine(QPointF(x, 3.0), QPointF(x, self.height() - 3.0))
        p.end()


class _CtxShield(QWidget):
    """Прозрачный «щит» на всю правую полосу combobox'а — от палочки-разделителя
    до правого края. Ничего не рисует, но:
      • перехватывает клики (чтобы под ним не открывался picker модели);
      • при Enter/Leave (через eventFilter в главном окне) гасит подсветку
        рамки combobox'а, чтобы она не «загоралась» при наведении в этой
        полосе — в том числе в зазорах вокруг самого тумблера."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.ArrowCursor)
        # Прозрачный: не рисуем фон/содержимое

    def mousePressEvent(self, ev):
        ev.accept()

    def mouseReleaseEvent(self, ev):
        ev.accept()

    def mouseDoubleClickEvent(self, ev):
        ev.accept()


# ============================================================
# EFFORT SLIDER — широкий ползунок выбора reasoning-effort
# ============================================================
# Идеология: расширенная копия LanguageToggle с 5 позициями.
# Ползунок плавно скользит между ячейками, цвет пилюли плавно лерпится
# между цветами уровней. Ultracode подсвечивается фиолетовым свечением.

EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max", "ultracode"]

EFFORT_COLORS = {
    "low":       (120, 220, 130),  # зелёный
    "medium":    (180, 210, 130),  # оливково-зелёный
    "high":      (235, 180, 110),  # оранжевый
    "xhigh":     (235, 120, 100),  # красновато-оранжевый
    "max":       (220, 70, 85),    # насыщенно-красный — потолок «чистого» reasoning
    "ultracode": (170, 110, 255),  # фиолетовый — max + оркестрация
}

EFFORT_LABELS = {
    "low":       "LOW",
    "medium":    "MEDIUM",
    "high":      "HIGH",
    "xhigh":     "XHIGH",
    "max":       "MAX",
    "ultracode": "ULTRACODE",
}


class EffortSlider(QWidget):
    """Широкий 5-позиционный ползунок выбора reasoning-effort.
    Пилюля плавно скользит между позициями, цвет плавно интерполируется
    между цветами соседних уровней. Клик по любой ячейке = переход на неё."""

    changed = Signal(str)  # эмит с новым уровнем

    def __init__(self, level="high", parent=None, disabled_levels=None):
        super().__init__(parent)
        self.setFixedSize(468, 34)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        if level not in EFFORT_LEVELS:
            level = "high"
        self._level = level
        # progress ∈ [0 .. len-1] — реальная непрерывная позиция пилюли
        self._target = float(EFFORT_LEVELS.index(level))
        self._progress = self._target
        # hover: подсветка неактивной ячейки при наведении (по индексу)
        self._hover_idx = -1
        self._hover_alpha = {i: 0.0 for i in range(len(EFFORT_LEVELS))}
        self._hover_target = {i: 0.0 for i in range(len(EFFORT_LEVELS))}
        # Заблокированные уровни (например, ultracode при 4.6-tier модели) —
        # клик по такой ячейке не переключает выбор, текст рисуется тусклым.
        self._disabled = set(disabled_levels or ())
        # пульс фиолетового свечения для ultracode
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_level(self, level, animate=True):
        if level not in EFFORT_LEVELS:
            return
        if level in self._disabled:
            return
        if level == self._level:
            return
        self._level = level
        self._target = float(EFFORT_LEVELS.index(level))
        if not animate:
            self._progress = self._target
        self.update()

    def set_disabled_levels(self, disabled_levels):
        """Обновляет набор запрещённых уровней на лету. Если сам текущий
        уровень попал в запрет — сдвигаем ползунок на ближайший разрешённый
        слева, чтобы Ultracode плавно поехал на MAX при выборе 4.6-модели."""
        new_disabled = set(disabled_levels or ())
        if new_disabled == self._disabled:
            return
        self._disabled = new_disabled
        if self._level in self._disabled:
            i = EFFORT_LEVELS.index(self._level)
            fallback = None
            for j in range(i - 1, -1, -1):
                candidate = EFFORT_LEVELS[j]
                if candidate not in self._disabled:
                    fallback = candidate
                    break
            if fallback is None:
                for j in range(i + 1, len(EFFORT_LEVELS)):
                    candidate = EFFORT_LEVELS[j]
                    if candidate not in self._disabled:
                        fallback = candidate
                        break
            if fallback is not None:
                self._level = fallback
                self._target = float(EFFORT_LEVELS.index(fallback))
                self.changed.emit(fallback)
        self.update()

    def level(self):
        return self._level

    def _cell_width(self):
        return self.width() / len(EFFORT_LEVELS)

    def _idx_from_x(self, x):
        cw = self._cell_width()
        idx = int(x // cw)
        return max(0, min(len(EFFORT_LEVELS) - 1, idx))

    def _lerp_color(self, prog):
        """Плавная интерполяция цвета пилюли на основе непрерывной позиции."""
        n = len(EFFORT_LEVELS)
        prog = max(0.0, min(n - 1, prog))
        i = int(prog)
        f = prog - i
        if i >= n - 1:
            return EFFORT_COLORS[EFFORT_LEVELS[-1]]
        c0 = EFFORT_COLORS[EFFORT_LEVELS[i]]
        c1 = EFFORT_COLORS[EFFORT_LEVELS[i + 1]]
        return (
            int(c0[0] + (c1[0] - c0[0]) * f),
            int(c0[1] + (c1[1] - c0[1]) * f),
            int(c0[2] + (c1[2] - c0[2]) * f),
        )

    def _tick(self):
        changed = False
        d = self._target - self._progress
        if abs(d) > 0.004:
            self._progress += d * 0.18
            changed = True
        elif self._progress != self._target:
            self._progress = self._target
            changed = True
        for i in range(len(EFFORT_LEVELS)):
            cur = self._hover_alpha[i]
            tgt = self._hover_target[i]
            d = tgt - cur
            if abs(d) > 0.003:
                self._hover_alpha[i] = cur + d * 0.09
                changed = True
            elif cur != tgt:
                self._hover_alpha[i] = tgt
                changed = True
        # пульс фиолетового ultracode — вечная синусоида
        self._pulse = (self._pulse + 0.045) % (math.pi * 2)
        if self._level == "ultracode" or abs(self._progress - (len(EFFORT_LEVELS) - 1)) < 0.5:
            changed = True
        if changed:
            self.update()

    def mousePressEvent(self, event):
        idx = self._idx_from_x(event.pos().x())
        new_level = EFFORT_LEVELS[idx]
        if new_level in self._disabled:
            return
        if new_level != self._level:
            self._level = new_level
            self._target = float(idx)
            self.changed.emit(new_level)
            self.update()

    def mouseMoveEvent(self, event):
        idx = self._idx_from_x(event.pos().x())
        # Подсвечиваем ТОЛЬКО ячейку под курсором, если она не текущая
        # и не заблокирована.
        cur_idx = EFFORT_LEVELS.index(self._level)
        for i in range(len(EFFORT_LEVELS)):
            disabled_here = EFFORT_LEVELS[i] in self._disabled
            self._hover_target[i] = (1.0 if (i == idx and i != cur_idx and not disabled_here) else 0.0)
        self._hover_idx = idx
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        for i in range(len(EFFORT_LEVELS)):
            self._hover_target[i] = 0.0
        self._hover_idx = -1
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n = len(EFFORT_LEVELS)
        cw = w / n

        track_r = 8.0
        pill_r = 6.5

        # Трек
        p.setBrush(QColor(28, 28, 33))
        p.setPen(QPen(QColor(60, 60, 65), 1.4))
        p.drawRoundedRect(QRectF(0.7, 0.7, w - 1.4, h - 1.4), track_r, track_r)

        # Тонкие разделители между ячейками
        p.setPen(QPen(QColor(52, 52, 58), 1.0))
        for i in range(1, n):
            x = i * cw
            p.drawLine(QPointF(x, 4), QPointF(x, h - 4))

        # Позиция и цвет пилюли
        r, g, b = self._lerp_color(self._progress)
        pad = 3.0
        pill_w = cw - pad * 1.4
        pill_x = self._progress * cw + (cw - pill_w) / 2.0

        # Мягкое свечение по периметру пилюли (внутри клипа трека).
        # Для ultracode свечение усилено пульсом.
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1.4, 1.4, w - 2.8, h - 2.8), track_r - 1, track_r - 1)
        p.save()
        p.setClipPath(clip)
        is_ultra = self._level == "ultracode" or (self._progress > n - 1.5)
        pulse_amp = (0.5 + 0.5 * math.sin(self._pulse)) if is_ultra else 0.0
        glow_boost = 1.0 + 0.8 * pulse_amp
        for i in range(1, 4):
            base_alpha = 48 * (1 - (i - 1) / 3.2) * glow_boost
            alpha = int(max(0, min(200, base_alpha)))
            p.setPen(QPen(QColor(r, g, b, alpha), 1))
            p.setBrush(Qt.NoBrush)
            ex = i * 1.4
            p.drawRoundedRect(
                QRectF(pill_x - ex, pad - ex, pill_w + ex * 2, h - pad * 2 + ex * 2),
                pill_r + ex, pill_r + ex
            )
        p.restore()

        # Сама пилюля — вертикальный градиент
        grad = QLinearGradient(QPointF(0, pad), QPointF(0, h - pad))
        grad.setColorAt(0.0, QColor(min(255, r + 18), min(255, g + 18), min(255, b + 18), 240))
        grad.setColorAt(1.0, QColor(max(0, r - 10), max(0, g - 10), max(0, b - 10), 240))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(pill_x, pad, pill_w, h - pad * 2), pill_r, pill_r)

        # Тексты уровней
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        for i, lvl in enumerate(EFFORT_LEVELS):
            cx = i * cw
            rect = QRectF(cx, 0, cw, h)
            is_disabled = lvl in self._disabled
            # Активная ячейка (на которую смотрит пилюля) — тёмный текст на цветном фоне
            dist = abs(self._progress - i)
            if dist < 0.5:
                # Насколько «под пилюлей» — от 1.0 в центре до 0 на границе
                cover = 1.0 - dist * 2.0
                # тёмный текст на цветном фоне для контраста
                dark = QColor(20, 22, 28)
                # неактивная база — серый
                shade = int(140 + 20 * (1.0 - dist))
                pale = QColor(shade, shade, shade + 4)
                pen = QColor(
                    int(pale.red()   + (dark.red()   - pale.red())   * cover),
                    int(pale.green() + (dark.green() - pale.green()) * cover),
                    int(pale.blue()  + (dark.blue()  - pale.blue())  * cover),
                )
            else:
                # Неактивная — серый с плавной hover-подсветкой в цвет уровня
                lc = EFFORT_COLORS[lvl]
                shade = 145
                base = QColor(shade, shade, shade + 4)
                hover = self._hover_alpha.get(i, 0.0)
                pen = QColor(
                    int(base.red()   + (lc[0] - base.red())   * hover),
                    int(base.green() + (lc[1] - base.green()) * hover),
                    int(base.blue()  + (lc[2] - base.blue())  * hover),
                )
            # Заблокированные ячейки — заметно тусклее (перекрашиваем поверх)
            if is_disabled:
                pen = QColor(80, 80, 86)
            p.setPen(pen)
            p.drawText(rect, Qt.AlignCenter, EFFORT_LABELS[lvl])

        p.end()


class EffortDialog(QDialog):
    """Широкое окно выбора reasoning-effort. Ползунок EffortSlider,
    крупный текст текущего уровня, короткое описание. Никаких кнопок:
    закрытие крестиком (или Esc) — применение уровня, который стоит
    в ползунке в этот момент."""

    applied = Signal(str)  # эмит с финальным уровнем при закрытии

    LEVEL_DESCRIPTIONS = {
        "low":       "минимум размышлений — быстро и дёшево",
        "medium":    "сбалансированный режим по умолчанию",
        "high":      "усиленное рассуждение для сложных задач",
        "xhigh":     "экстремальный уровень — редкие тяжёлые случаи",
        "max":       "максимум размышлений — потолок обычного режима",
        "ultracode": "максимум мощности + многоагентная оркестрация",
    }
    LEVEL_DESCRIPTIONS_EN = {
        "low":       "minimal reasoning — fast and cheap",
        "medium":    "balanced default mode",
        "high":      "amplified reasoning for hard problems",
        "xhigh":     "extreme reasoning — rare heavy cases",
        "max":       "maximum reasoning — ceiling of normal mode",
        "ultracode": "maximum power + multi-agent orchestration",
    }

    def __init__(self, current_level="high", parent=None, current_model=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Обязательно: без WA_DeleteOnClose сигнал destroyed не эмитится и
        # EffortPickerComboBox._picker_dlg остаётся non-None → повторный клик
        # по комбо ничего не делает до перезапуска приложения.
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setModal(True)
        # Если текущая модель — Opus 4.6 или Sonnet 4.6, ultracode отключен
        # (эти модели не поддерживают многоагентную оркестрацию).
        self._disabled_levels = set()
        if current_model in MODELS_WITHOUT_ULTRACODE:
            self._disabled_levels.add("ultracode")
        if current_level not in EFFORT_LEVELS:
            current_level = "high"
        # Если выбранный уровень заблокирован для этой модели — стартуем с max
        if current_level in self._disabled_levels:
            current_level = "max"
        self._level = current_level
        self._initial_level = current_level

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        container = DottedFrame()
        container.setObjectName("effortDialogContainer")
        container.setStyleSheet("""
            QFrame#effortDialogContainer {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 16px;
            }
        """)
        outer.addWidget(container)

        shadow = QGraphicsDropShadowEffect(container)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 6)
        container.setGraphicsEffect(shadow)

        inner = QVBoxLayout(container)
        inner.setContentsMargins(18, 12, 18, 16)
        inner.setSpacing(10)

        # Заголовок + крестик
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        title = QLabel(tr("Reasoning Effort"))
        title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title.setStyleSheet("color: rgb(200, 200, 210); background: transparent; border: none;")
        head.addWidget(title)
        head.addStretch()
        self.close_btn = _CloseButton(parent=container)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.clicked.connect(self.close)
        head.addWidget(self.close_btn)
        inner.addLayout(head)

        # Ползунок
        row = QHBoxLayout()
        row.addStretch()
        self.slider = EffortSlider(level=current_level, disabled_levels=self._disabled_levels)
        self.slider.changed.connect(self._on_slider_changed)
        row.addWidget(self.slider)
        row.addStretch()
        inner.addLayout(row)

        # Описание уровня — цвет = цвет уровня
        self.desc_lbl = QLabel(self._desc_text(current_level))
        self.desc_lbl.setFont(QFont("Segoe UI", 9))
        self.desc_lbl.setAlignment(Qt.AlignCenter)
        self._apply_desc_color(current_level)
        self.desc_lbl.setWordWrap(True)
        inner.addWidget(self.desc_lbl)

        self.setFixedWidth(560)
        self.adjustSize()

        # Плавное появление
        self.setWindowOpacity(0.0)
        self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in.setDuration(220)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self._closing = False

    def _desc_text(self, level):
        # LANG хранит текущий язык в атрибуте .lang (не .get()) — раньше здесь
        # был неверный LANG.get(), который валился в except и всегда отдавал RU.
        try:
            if LANG is not None and LANG.lang == "en":
                return self.LEVEL_DESCRIPTIONS_EN.get(level, "")
        except Exception:
            pass
        return self.LEVEL_DESCRIPTIONS.get(level, "")

    def _apply_desc_color(self, level):
        r, g, b = EFFORT_COLORS.get(level, (200, 200, 200))
        self.desc_lbl.setStyleSheet(
            f"color: rgb({r},{g},{b}); background: transparent; border: none;"
        )

    def _on_slider_changed(self, level):
        self._level = level
        self.desc_lbl.setText(self._desc_text(level))
        self._apply_desc_color(level)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_in.start()

    def closeEvent(self, event):
        if self._closing:
            super().closeEvent(event)
            return
        self._closing = True
        event.ignore()
        # Применяем выбор ТОЛЬКО если он изменился — чтобы Esc/крестик без
        # перемещения ползунка не гнал лишний save.
        if self._level != self._initial_level:
            try:
                self.applied.emit(self._level)
            except Exception:
                pass
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(200)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(self.close)
        fade.start()
        self._fade_out = fade

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        # Стрелки влево/вправо для клавиатурной навигации, пропуская
        # заблокированные уровни (ultracode при 4.6-tier модели).
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            step = -1 if event.key() == Qt.Key_Left else 1
            i = EFFORT_LEVELS.index(self._level) + step
            while 0 <= i < len(EFFORT_LEVELS):
                candidate = EFFORT_LEVELS[i]
                if candidate not in self._disabled_levels:
                    self._on_slider_changed(candidate)
                    self.slider.set_level(candidate)
                    return
                i += step
            return
        super().keyPressEvent(event)


# ============================================================
# MODEL SLIDER — такой же ползунок, но для выбора модели
# ============================================================
# Порядок фиксированный: от «дешёвых» Sonnet до «Fable 5» — совпадает с
# цветовой градацией зелёный → красный. Ползунок 1-в-1 копирует EffortSlider,
# только позиций 6 и вместо пульсирующего свечения — фиолетовое подсвечение
# на Fable 5 (флагманский платный уровень).

MODEL_ORDER = ["Sonnet 4.6", "Sonnet 5", "Opus 4.6", "Opus 4.7", "Opus 4.8", "Fable 5"]

MODEL_COLORS_MAP = {
    "Sonnet 4.6": (130, 220, 130),   # насыщенно-зелёный
    "Sonnet 5":   (180, 235, 150),   # светло-зелёный (чуть желтее 4.6)
    "Opus 4.6":   (230, 220, 130),
    "Opus 4.7":   (235, 180, 110),
    "Opus 4.8":   (235, 150, 130),
    "Fable 5":    (235,  90,  90),
}

MODEL_LABELS_SHORT = {
    "Sonnet 4.6": "Sonnet 4.6",
    "Sonnet 5":   "Sonnet 5",
    "Opus 4.6":   "Opus 4.6",
    "Opus 4.7":   "Opus 4.7",
    "Opus 4.8":   "Opus 4.8",
    "Fable 5":    "Fable 5",
}

# Модели, у которых нет поддержки ultracode (устаревшие 4.6-tier).
# Если пользователь выбирает Opus 4.6 или Sonnet 4.6 — ultracode принудительно
# понижается до max. И наоборот: в EffortDialog при этих моделях ячейка
# ULTRACODE помечается disabled.
MODELS_WITHOUT_ULTRACODE = {"Sonnet 4.6", "Opus 4.6"}


class ModelSlider(QWidget):
    """6-позиционный ползунок выбора модели. Копия EffortSlider,
    подстроенная под MODEL_ORDER/MODEL_COLORS_MAP."""

    changed = Signal(str)  # эмит с новым именем модели

    def __init__(self, model="Opus 4.8", parent=None):
        super().__init__(parent)
        self.setFixedSize(468, 34)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        if model not in MODEL_ORDER:
            model = "Opus 4.8"
        self._model = model
        self._target = float(MODEL_ORDER.index(model))
        self._progress = self._target
        self._hover_idx = -1
        self._hover_alpha = {i: 0.0 for i in range(len(MODEL_ORDER))}
        self._hover_target = {i: 0.0 for i in range(len(MODEL_ORDER))}
        # Пульс для Fable 5 — красноватое свечение, как ultracode у effort
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_model(self, model, animate=True):
        if model not in MODEL_ORDER:
            return
        if model == self._model:
            return
        self._model = model
        self._target = float(MODEL_ORDER.index(model))
        if not animate:
            self._progress = self._target
        self.update()

    def model(self):
        return self._model

    def _cell_width(self):
        return self.width() / len(MODEL_ORDER)

    def _idx_from_x(self, x):
        cw = self._cell_width()
        idx = int(x // cw)
        return max(0, min(len(MODEL_ORDER) - 1, idx))

    def _lerp_color(self, prog):
        n = len(MODEL_ORDER)
        prog = max(0.0, min(n - 1, prog))
        i = int(prog)
        f = prog - i
        if i >= n - 1:
            return MODEL_COLORS_MAP[MODEL_ORDER[-1]]
        c0 = MODEL_COLORS_MAP[MODEL_ORDER[i]]
        c1 = MODEL_COLORS_MAP[MODEL_ORDER[i + 1]]
        return (
            int(c0[0] + (c1[0] - c0[0]) * f),
            int(c0[1] + (c1[1] - c0[1]) * f),
            int(c0[2] + (c1[2] - c0[2]) * f),
        )

    def _tick(self):
        changed = False
        d = self._target - self._progress
        if abs(d) > 0.004:
            self._progress += d * 0.18
            changed = True
        elif self._progress != self._target:
            self._progress = self._target
            changed = True
        for i in range(len(MODEL_ORDER)):
            cur = self._hover_alpha[i]
            tgt = self._hover_target[i]
            d = tgt - cur
            if abs(d) > 0.003:
                self._hover_alpha[i] = cur + d * 0.09
                changed = True
            elif cur != tgt:
                self._hover_alpha[i] = tgt
                changed = True
        self._pulse = (self._pulse + 0.045) % (math.pi * 2)
        if self._model == "Fable 5" or abs(self._progress - (len(MODEL_ORDER) - 1)) < 0.5:
            changed = True
        if changed:
            self.update()

    def mousePressEvent(self, event):
        idx = self._idx_from_x(event.pos().x())
        new_model = MODEL_ORDER[idx]
        if new_model != self._model:
            self._model = new_model
            self._target = float(idx)
            self.changed.emit(new_model)
            self.update()

    def mouseMoveEvent(self, event):
        idx = self._idx_from_x(event.pos().x())
        cur_idx = MODEL_ORDER.index(self._model)
        for i in range(len(MODEL_ORDER)):
            self._hover_target[i] = (1.0 if (i == idx and i != cur_idx) else 0.0)
        self._hover_idx = idx
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        for i in range(len(MODEL_ORDER)):
            self._hover_target[i] = 0.0
        self._hover_idx = -1
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n = len(MODEL_ORDER)
        cw = w / n

        track_r = 8.0
        pill_r = 6.5

        p.setBrush(QColor(28, 28, 33))
        p.setPen(QPen(QColor(60, 60, 65), 1.4))
        p.drawRoundedRect(QRectF(0.7, 0.7, w - 1.4, h - 1.4), track_r, track_r)

        p.setPen(QPen(QColor(52, 52, 58), 1.0))
        for i in range(1, n):
            x = i * cw
            p.drawLine(QPointF(x, 4), QPointF(x, h - 4))

        r, g, b = self._lerp_color(self._progress)
        pad = 3.0
        pill_w = cw - pad * 1.4
        pill_x = self._progress * cw + (cw - pill_w) / 2.0

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1.4, 1.4, w - 2.8, h - 2.8), track_r - 1, track_r - 1)
        p.save()
        p.setClipPath(clip)
        is_fable = self._model == "Fable 5" or (self._progress > n - 1.5)
        pulse_amp = (0.5 + 0.5 * math.sin(self._pulse)) if is_fable else 0.0
        glow_boost = 1.0 + 0.8 * pulse_amp
        for i in range(1, 4):
            base_alpha = 48 * (1 - (i - 1) / 3.2) * glow_boost
            alpha = int(max(0, min(200, base_alpha)))
            p.setPen(QPen(QColor(r, g, b, alpha), 1))
            p.setBrush(Qt.NoBrush)
            ex = i * 1.4
            p.drawRoundedRect(
                QRectF(pill_x - ex, pad - ex, pill_w + ex * 2, h - pad * 2 + ex * 2),
                pill_r + ex, pill_r + ex
            )
        p.restore()

        grad = QLinearGradient(QPointF(0, pad), QPointF(0, h - pad))
        grad.setColorAt(0.0, QColor(min(255, r + 18), min(255, g + 18), min(255, b + 18), 240))
        grad.setColorAt(1.0, QColor(max(0, r - 10), max(0, g - 10), max(0, b - 10), 240))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(pill_x, pad, pill_w, h - pad * 2), pill_r, pill_r)

        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        for i, name in enumerate(MODEL_ORDER):
            cx = i * cw
            rect = QRectF(cx, 0, cw, h)
            dist = abs(self._progress - i)
            if dist < 0.5:
                cover = 1.0 - dist * 2.0
                dark = QColor(20, 22, 28)
                shade = int(140 + 20 * (1.0 - dist))
                pale = QColor(shade, shade, shade + 4)
                pen = QColor(
                    int(pale.red()   + (dark.red()   - pale.red())   * cover),
                    int(pale.green() + (dark.green() - pale.green()) * cover),
                    int(pale.blue()  + (dark.blue()  - pale.blue())  * cover),
                )
            else:
                lc = MODEL_COLORS_MAP[name]
                shade = 145
                base = QColor(shade, shade, shade + 4)
                hover = self._hover_alpha.get(i, 0.0)
                pen = QColor(
                    int(base.red()   + (lc[0] - base.red())   * hover),
                    int(base.green() + (lc[1] - base.green()) * hover),
                    int(base.blue()  + (lc[2] - base.blue())  * hover),
                )
            p.setPen(pen)
            p.drawText(rect, Qt.AlignCenter, MODEL_LABELS_SHORT[name])

        p.end()


class ModelDialog(QDialog):
    """Компактное окно выбора модели FreeModel в стиле EffortDialog.
    Ползунок ModelSlider + короткое описание модели (цветное) под ним.
    Никаких кнопок — крестик/Esc применяет выбор."""

    # Эмитим и модель, и effort — теперь ModelDialog управляет обоими.
    applied = Signal(str, str)

    LEVEL_DESCRIPTIONS = {
        "Sonnet 4.6": "быстрый и дешёвый — для простых задач",
        "Sonnet 5":   "новый Sonnet — быстрее и умнее 4.6",
        "Opus 4.6":   "мощный Opus — уверенно решает большинство задач",
        "Opus 4.7":   "усиленный Opus 4.7 — сложные многошаговые задачи",
        "Opus 4.8":   "флагманский Opus 4.8 — максимум качества",
        "Fable 5":    "экспериментальная Fable 5 — необычные вопросы",
    }
    LEVEL_DESCRIPTIONS_EN = {
        "Sonnet 4.6": "fast and cheap — for simple tasks",
        "Sonnet 5":   "new Sonnet — faster and smarter than 4.6",
        "Opus 4.6":   "powerful Opus — handles most tasks confidently",
        "Opus 4.7":   "amplified Opus 4.7 — complex multi-step tasks",
        "Opus 4.8":   "flagship Opus 4.8 — maximum quality",
        "Fable 5":    "experimental Fable 5 — unusual questions",
    }

    def __init__(self, current_model="Opus 4.8", parent=None, current_effort="high"):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Обязательно: аналогично EffortDialog — иначе повторное открытие
        # блокируется, потому что destroyed не эмитится.
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setModal(True)
        if current_model not in MODEL_ORDER:
            current_model = "Opus 4.8"
        if current_effort not in EFFORT_LEVELS:
            current_effort = "high"
        # Начальные disabled для effort — сразу учитывают текущую модель.
        initial_disabled = set()
        if current_model in MODELS_WITHOUT_ULTRACODE:
            initial_disabled.add("ultracode")
        # Если стартовый effort несовместим с моделью — тихо чиним до max,
        # чтобы диалог открылся в консистентном состоянии.
        if current_effort in initial_disabled:
            current_effort = "max"
        self._model = current_model
        self._initial_model = current_model
        self._effort = current_effort
        self._initial_effort = current_effort

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        container = DottedFrame()
        container.setObjectName("modelDialogContainer")
        container.setStyleSheet("""
            QFrame#modelDialogContainer {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 16px;
            }
        """)
        outer.addWidget(container)

        shadow = QGraphicsDropShadowEffect(container)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 6)
        container.setGraphicsEffect(shadow)

        inner = QVBoxLayout(container)
        inner.setContentsMargins(18, 12, 18, 16)
        inner.setSpacing(10)

        # Заголовок + крестик. Слева — фиксированный отступ шириной с крестик,
        # плюс stretch, и такой же stretch справа — так заголовок оказывается
        # ровно по центру, а крестик остаётся в правом углу.
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addSpacing(24)
        head.addStretch()
        title = QLabel(tr("Выбор модели"))
        title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title.setStyleSheet("color: rgb(200, 200, 210); background: transparent; border: none;")
        title.setAlignment(Qt.AlignCenter)
        head.addWidget(title)
        head.addStretch()
        self.close_btn = _CloseButton(parent=container)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.clicked.connect(self.close)
        head.addWidget(self.close_btn)
        inner.addLayout(head)

        # Ползунок модели
        row = QHBoxLayout()
        row.addStretch()
        self.slider = ModelSlider(model=current_model)
        self.slider.changed.connect(self._on_slider_changed)
        row.addWidget(self.slider)
        row.addStretch()
        inner.addLayout(row)

        # Описание модели — цвет = цвет модели
        self.desc_lbl = QLabel(self._desc_text(current_model))
        self.desc_lbl.setFont(QFont("Segoe UI", 9))
        self.desc_lbl.setAlignment(Qt.AlignCenter)
        self._apply_desc_color(current_model)
        self.desc_lbl.setWordWrap(True)
        inner.addWidget(self.desc_lbl)

        # Разделитель "Reasoning Effort" под описанием модели
        sep_lbl = QLabel(tr("Reasoning Effort"))
        sep_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        sep_lbl.setAlignment(Qt.AlignCenter)
        sep_lbl.setStyleSheet("color: rgb(180, 180, 190); background: transparent; border: none; margin-top: 6px;")
        inner.addWidget(sep_lbl)

        # Второй ползунок — effort. Тот же самый EffortSlider, что и в
        # старом EffortDialog. disabled_levels берётся из модели.
        eff_row = QHBoxLayout()
        eff_row.addStretch()
        self.effort_slider = EffortSlider(level=current_effort, disabled_levels=initial_disabled)
        self.effort_slider.changed.connect(self._on_effort_slider_changed)
        eff_row.addWidget(self.effort_slider)
        eff_row.addStretch()
        inner.addLayout(eff_row)

        # Описание effort'а — цвет = цвет уровня
        self.effort_desc_lbl = QLabel(self._effort_desc_text(current_effort))
        self.effort_desc_lbl.setFont(QFont("Segoe UI", 9))
        self.effort_desc_lbl.setAlignment(Qt.AlignCenter)
        self._apply_effort_desc_color(current_effort)
        self.effort_desc_lbl.setWordWrap(True)
        inner.addWidget(self.effort_desc_lbl)

        self.setFixedWidth(560)
        self.adjustSize()

        self.setWindowOpacity(0.0)
        self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in.setDuration(220)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self._closing = False

    def _desc_text(self, model):
        try:
            if LANG is not None and LANG.lang == "en":
                return self.LEVEL_DESCRIPTIONS_EN.get(model, "")
        except Exception:
            pass
        return self.LEVEL_DESCRIPTIONS.get(model, "")

    def _apply_desc_color(self, model):
        r, g, b = MODEL_COLORS_MAP.get(model, (200, 200, 200))
        self.desc_lbl.setStyleSheet(
            f"color: rgb({r},{g},{b}); background: transparent; border: none;"
        )

    def _effort_desc_text(self, level):
        try:
            if LANG is not None and LANG.lang == "en":
                return EffortDialog.LEVEL_DESCRIPTIONS_EN.get(level, "")
        except Exception:
            pass
        return EffortDialog.LEVEL_DESCRIPTIONS.get(level, "")

    def _apply_effort_desc_color(self, level):
        r, g, b = EFFORT_COLORS.get(level, (200, 200, 200))
        self.effort_desc_lbl.setStyleSheet(
            f"color: rgb({r},{g},{b}); background: transparent; border: none;"
        )

    def _on_slider_changed(self, model):
        self._model = model
        self.desc_lbl.setText(self._desc_text(model))
        self._apply_desc_color(model)
        # Синхронизируем disabled-набор ползунка effort — при 4.6-модели
        # ultracode запрещён. set_disabled_levels сам сдвинет ползунок с
        # ultracode на max, если тот выбран (плавная анимация).
        new_disabled = set()
        if model in MODELS_WITHOUT_ULTRACODE:
            new_disabled.add("ultracode")
        self.effort_slider.set_disabled_levels(new_disabled)

    def _on_effort_slider_changed(self, level):
        self._effort = level
        self.effort_desc_lbl.setText(self._effort_desc_text(level))
        self._apply_effort_desc_color(level)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_in.start()

    def closeEvent(self, event):
        if self._closing:
            super().closeEvent(event)
            return
        self._closing = True
        event.ignore()
        # applied эмитим ВСЕГДА, если что-то изменилось — модель или effort.
        if self._model != self._initial_model or self._effort != self._initial_effort:
            try:
                self.applied.emit(self._model, self._effort)
            except Exception:
                pass
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(200)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(self.close)
        fade.start()
        self._fade_out = fade

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        if event.key() == Qt.Key_Left:
            i = MODEL_ORDER.index(self._model)
            if i > 0:
                new_m = MODEL_ORDER[i - 1]
                self._on_slider_changed(new_m)
                self.slider.set_model(new_m)
            return
        if event.key() == Qt.Key_Right:
            i = MODEL_ORDER.index(self._model)
            if i < len(MODEL_ORDER) - 1:
                new_m = MODEL_ORDER[i + 1]
                self._on_slider_changed(new_m)
                self.slider.set_model(new_m)
            return
        super().keyPressEvent(event)


# ============================================================
# УПРАВЛЕНИЕ API-КЛЮЧАМИ — виджеты
# ============================================================

class KeyToggle(QWidget):
    """Переключатель состояния ключа OFF / ON — карбоновая копия LanguageToggle.

    OFF (слева) = красный (ключ выключен), ON (справа) = зелёный (активен).
    Клик эмитит toggled(bool) ТОЛЬКО если состояние реально меняется —
    т.е. клик по стороне, на которой ползунок уже стоит, ничего не делает
    (без «моргания»). Подтвердить «пожелтевший» ключ можно, кликнув по ON."""
    toggled = Signal(bool)  # True = ON/enabled

    _OFF_COL = (224, 90, 90)   # красный
    _ON_COL = (52, 211, 153)   # новый зелёный

    def __init__(self, on=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(78, 22)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self._on = bool(on)
        self._progress = 1.0 if self._on else 0.0
        self._target = self._progress
        self._hover_off = 0.0
        self._hover_on = 0.0
        self._hover_off_target = 0.0
        self._hover_on_target = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_on(self, on, animate=True):
        on = bool(on)
        self._on = on
        self._target = 1.0 if on else 0.0
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
        for name in ("_hover_off", "_hover_on"):
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
        new_on = event.pos().x() >= self.width() / 2
        if new_on == self._on:
            # Клик по стороне, на которой ползунок уже стоит — игнорируем,
            # чтобы не было «моргания» и лишних toggled-событий.
            return
        self._on = new_on
        self._target = 1.0 if new_on else 0.0
        self.toggled.emit(new_on)
        self.update()

    def mouseMoveEvent(self, event):
        is_right = event.pos().x() >= self.width() / 2
        if is_right:
            self._hover_on_target = 0.0 if self._on else 1.0
            self._hover_off_target = 0.0
        else:
            self._hover_off_target = 0.0 if not self._on else 1.0
            self._hover_on_target = 0.0
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_off_target = 0.0
        self._hover_on_target = 0.0
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self._progress
        w, h = self.width(), self.height()
        track_r = 6.0
        pill_r = 5.0

        p.setBrush(QColor(28, 28, 33))
        p.setPen(QPen(QColor(60, 60, 65), 1.4))
        p.drawRoundedRect(QRectF(0.7, 0.7, w - 1.4, h - 1.4), track_r, track_r)

        r0, g0, b0 = self._OFF_COL
        r1, g1, b1 = self._ON_COL
        r = int(r0 + (r1 - r0) * t)
        g = int(g0 + (g1 - g0) * t)
        b = int(b0 + (b1 - b0) * t)

        pad = 2.5
        pill_w = w / 2 - pad
        pill_x = pad / 2 + (w / 2) * t

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

        grad = QLinearGradient(QPointF(0, pad), QPointF(0, h - pad))
        grad.setColorAt(0.0, QColor(min(255, r + 18), min(255, g + 18), min(255, b + 18), 240))
        grad.setColorAt(1.0, QColor(max(0, r - 10), max(0, g - 10), max(0, b - 10), 240))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(pill_x, pad, pill_w, h - pad * 2), pill_r, pill_r)

        p.setFont(QFont("Segoe UI", 8, QFont.Bold))

        # OFF (левая) — яркая когда t=0
        if (1.0 - t) > 0.5:
            off_pen = QColor(30, 15, 15)
        else:
            shade = int(130 + 25 * (1 - t))
            base = QColor(shade + 5, shade, shade)
            hr, hg, hb = self._OFF_COL
            hov = self._hover_off
            off_pen = QColor(
                int(base.red()   + (hr - base.red())   * hov),
                int(base.green() + (hg - base.green()) * hov),
                int(base.blue()  + (hb - base.blue())  * hov),
            )
        p.setPen(off_pen)
        p.drawText(QRectF(0, 0, w / 2, h), Qt.AlignCenter, "OFF")

        # ON (правая) — яркая когда t=1
        if t > 0.5:
            on_pen = QColor(15, 28, 22)
        else:
            shade = int(130 + 25 * t)
            base = QColor(shade, shade + 5, shade)
            hr, hg, hb = self._ON_COL
            hov = self._hover_on
            on_pen = QColor(
                int(base.red()   + (hr - base.red())   * hov),
                int(base.green() + (hg - base.green()) * hov),
                int(base.blue()  + (hb - base.blue())  * hov),
            )
        p.setPen(on_pen)
        p.drawText(QRectF(w / 2, 0, w / 2, h), Qt.AlignCenter, "ON")
        p.end()


class KeyCard(QFrame):
    """Строка одного API-ключа: тумблер OFF/ON, имя, маскированное значение,
    статус, глаз, крестик удаления. Рамка плавно перекрашивается под состояние
    (зелёный/красный/жёлтый) и мягко «загорается» при смене."""
    toggled = Signal(str, bool)      # (key_id, on) — состояние изменилось
    delete_requested = Signal(str)   # key_id
    select_requested = Signal(str)   # key_id — клик по телу карточки
    changed = Signal(str)            # key_id — dict ключа мутирован (для мгновенного save_settings)

    _COLORS = {
        "green":  (52, 211, 153),
        "red":    (224, 90, 90),
        "yellow": (235, 200, 90),
    }

    def __init__(self, key, parent=None):
        super().__init__(parent)
        self.key = key
        self.setFixedHeight(58)
        self.setCursor(Qt.PointingHandCursor)
        state = key_color_state(key)
        col = self._COLORS[state]
        self._cur = list(col)
        self._target = list(col)
        self._glow = 0.0
        self._last_state = state
        self._revealed = False
        self._selected = False
        # Плавный «пульс» выбранной карточки — интерполируется 0..1 (усиливает рамку и лёгкое свечение)
        self._sel_progress = 0.0

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 12, 8)
        lay.setSpacing(10)

        # Ползунок в позиции ON только когда ключ действительно активен (зелёный).
        # Жёлтый и красный — оба означают OFF, ползунок слева.
        self.toggle = KeyToggle(on=(state == "green"))
        self.toggle.toggled.connect(self._on_toggle)
        lay.addWidget(self.toggle, 0, Qt.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(1)
        self.name_lbl = QLabel(key.get("name", "Ключ"))
        self.name_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.name_lbl.setStyleSheet("color: rgb(220,220,225); background: transparent; border: none;")
        # Игнорируем «естественную» ширину текста, чтобы длинное имя/ключ не
        # распирали строку и не выталкивали глаз/крестик за край карточки.
        self.name_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        info.addWidget(self.name_lbl)
        self.val_lbl = QLabel(self._mask(key.get("value", "")))
        self.val_lbl.setFont(QFont("Consolas", 9))
        self.val_lbl.setStyleSheet("color: rgb(140,140,148); background: transparent; border: none;")
        self.val_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        info.addWidget(self.val_lbl)
        lay.addLayout(info, 1)

        self.status_lbl = QLabel("")
        self.status_lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.status_lbl.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(self.status_lbl, 0, Qt.AlignVCenter)

        self.eye = EyeToggleButton()
        self.eye.setFixedSize(34, 30)
        self.eye.clicked.connect(self._toggle_reveal)
        lay.addWidget(self.eye, 0, Qt.AlignVCenter)

        self.del_btn = _CloseButton()
        self.del_btn.clicked.connect(lambda: self.delete_requested.emit(self.key.get("id", "")))
        lay.addWidget(self.del_btn, 0, Qt.AlignVCenter)

        self._update_status_text()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _mask(self, v):
        v = v or ""
        if len(v) <= 4:
            return "•" * len(v)
        return v[:6] + "•" * 8

    def _on_toggle(self, on):
        """Тумблер эмитит это ПОСЛЕ того, как переключил свой визуальный
        _on внутрь себя (проверив, что состояние действительно меняется).
        Наша задача — либо принять изменение (и мутировать key), либо
        откатить визуал тумблера (при отмене диалога)."""
        if on:
            # OFF → ON вручную. Сброс лимита, ключ активен.
            reset_key_limit(self.key)
            self._retarget()
            self._update_status_text()
            self.toggled.emit(self.key.get("id", ""), True)
            self.changed.emit(self.key.get("id", ""))
            return

        # ON → OFF: два диалога подряд.
        limit_type, seconds = self._prompt_limit()
        if limit_type is None:
            # Отмена на любом шаге — возвращаем тумблер визуально на ON.
            self.toggle.blockSignals(True)
            self.toggle.set_on(True, animate=True)
            self.toggle.blockSignals(False)
            return

        self.key["enabled"] = False
        self.key["limit_type"] = limit_type
        self.key["resets_at"] = time.time() + seconds
        self.key["disabled_at"] = time.time()  # для истории
        self._retarget()
        self._update_status_text()
        self.toggled.emit(self.key.get("id", ""), False)
        self.changed.emit(self.key.get("id", ""))

    def _prompt_limit(self):
        """Возвращает (limit_type, seconds) или (None, None) при отмене."""
        parent_win = self.window()
        type_dlg = KeyLimitTypeDialog(parent=parent_win)
        if type_dlg.exec() != QDialog.Accepted or not type_dlg.result_type:
            return (None, None)
        dur_dlg = KeyLimitDurationDialog(type_dlg.result_type, parent=parent_win)
        if dur_dlg.exec() != QDialog.Accepted or not dur_dlg.result_seconds:
            return (None, None)
        return (type_dlg.result_type, int(dur_dlg.result_seconds))

    def _retarget(self):
        state = key_color_state(self.key)
        self._last_state = state
        self._target = list(self._COLORS[state])
        self._glow = 1.0
        self.update()

    def refresh_state(self):
        """Вызывается по таймеру окна раз в секунду:
        • обновляет текст обратного отсчёта;
        • при истечении resets_at авто-включает ключ (эмитит toggled + changed);
        • перекрашивает рамку при смене цветового состояния."""
        auto_reactivated = False
        if key_expired(self.key):
            # Таймер лимита истёк — авто-сброс. reset_key_limit сам обновит поля.
            reset_key_limit(self.key)
            self.toggle.blockSignals(True)
            self.toggle.set_on(True, animate=True)
            self.toggle.blockSignals(False)
            auto_reactivated = True
        state = key_color_state(self.key)
        if state != self._last_state:
            self._retarget()
        self._update_status_text()
        if auto_reactivated:
            self.toggled.emit(self.key.get("id", ""), True)
            self.changed.emit(self.key.get("id", ""))

    def _toggle_reveal(self):
        self._revealed = not self._revealed
        self.eye.setRevealed(self._revealed)
        self._apply_value_text()

    def _apply_value_text(self):
        """Раскрытый ключ показываем целиком, но с многоточием в середине,
        чтобы уместить его в доступную ширину (видны начало и конец)."""
        full = self.key.get("value", "")
        if not self._revealed:
            self.val_lbl.setText(self._mask(full))
            return
        fm = QFontMetrics(self.val_lbl.font())
        avail = max(40, self.val_lbl.width())
        self.val_lbl.setText(fm.elidedText(full, Qt.ElideMiddle, avail))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Ширина изменилась — переэлидируем раскрытый ключ под новую ширину.
        if getattr(self, "_revealed", False):
            self._apply_value_text()

    def _update_status_text(self):
        state = key_color_state(self.key)
        if state == "green":
            txt = tr("активен")
        else:
            # Показываем обратный отсчёт до сброса.
            resets_at = self.key.get("resets_at", 0) or 0
            remain = int(max(0, resets_at - time.time())) if resets_at else 0
            if remain <= 0:
                txt = tr("готов к сбросу")
            else:
                txt = tr("Сброс через") + " " + self._format_remaining(remain)
        r, g, b = self._COLORS[state]
        self.status_lbl.setText(txt)
        self.status_lbl.setStyleSheet(f"color: rgb({r},{g},{b}); background: transparent; border: none;")

    @staticmethod
    def _format_remaining(seconds):
        """Красивый обратный отсчёт: 6д 12ч 05м, 3ч 12м 05с, 12м 05с, 05с."""
        seconds = max(0, int(seconds))
        d, r = divmod(seconds, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        parts = []
        if d > 0:
            parts.append(f"{d}{tr('д')}")
            parts.append(f"{h}{tr('ч')}")
            parts.append(f"{m:02d}{tr('м')}")
        elif h > 0:
            parts.append(f"{h}{tr('ч')}")
            parts.append(f"{m:02d}{tr('м')}")
            parts.append(f"{s:02d}{tr('с')}")
        elif m > 0:
            parts.append(f"{m}{tr('м')}")
            parts.append(f"{s:02d}{tr('с')}")
        else:
            parts.append(f"{s}{tr('с')}")
        return " ".join(parts)

    def set_selected(self, selected):
        selected = bool(selected)
        if selected == self._selected:
            return
        self._selected = selected
        # Обновляем целевое состояние пульса — сам анимируется в _tick
        self.update()

    def mousePressEvent(self, event):
        # Клик по «телу» карточки (не по toggle/eye/delete/status) — заявка на выбор.
        # Дочерние виджеты обрабатывают клик у себя и сюда событие не пробрасывают.
        if event.button() == Qt.LeftButton:
            self.select_requested.emit(self.key.get("id", ""))
        super().mousePressEvent(event)

    def _tick(self):
        changed = False
        for i in range(3):
            d = self._target[i] - self._cur[i]
            if abs(d) > 0.8:
                self._cur[i] += d * 0.12
                changed = True
            elif self._cur[i] != self._target[i]:
                self._cur[i] = self._target[i]
                changed = True
        if self._glow > 0.001:
            self._glow *= 0.94
            if self._glow < 0.02:
                self._glow = 0.0
            changed = True
        # Плавный ход к _selected (0..1)
        sel_target = 1.0 if self._selected else 0.0
        d = sel_target - self._sel_progress
        if abs(d) > 0.004:
            self._sel_progress += d * 0.15
            changed = True
        elif self._sel_progress != sel_target:
            self._sel_progress = sel_target
            changed = True
        if changed:
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r, g, b = int(self._cur[0]), int(self._cur[1]), int(self._cur[2])
        glow = self._glow
        sel = self._sel_progress
        rect = QRectF(1.5, 1.5, w - 3, h - 3)
        # тёмный фон
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(26, 26, 31, 235))
        p.drawRoundedRect(rect, 10, 10)
        # цветная подложка: усиливается при «загорании» + при выборе
        tint_a = int(20 + 34 * glow + 26 * sel)
        p.setBrush(QColor(r, g, b, min(255, tint_a)))
        p.drawRoundedRect(rect, 10, 10)
        # рамка — ярче и толще на пике glow и когда карточка выбрана
        boost = int(45 * glow + 35 * sel)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(
            QColor(min(255, r + boost), min(255, g + boost), min(255, b + boost)),
            2.0 + 1.4 * glow + 1.2 * sel
        ))
        p.drawRoundedRect(rect, 10, 10)
        # Индикатор выбора: маленькая цветная точка у левого верхнего угла
        if sel > 0.02:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(r, g, b, int(255 * sel)))
            dot_r = 3.2
            p.drawEllipse(QPointF(9.5, 8.5), dot_r, dot_r)
        p.end()


# ============================================================
# ДИАЛОГИ УСТАНОВКИ ЛИМИТА У КЛЮЧА
# ============================================================

class _LimitTypeCard(QPushButton):
    """Большая карточка-кнопка в диалоге выбора типа лимита.
    Стилизована под весь остальной UI: тёмный фон, цветная рамка,
    плавное свечение по наведению."""
    def __init__(self, title, subtitle, color_rgb, parent=None):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._col = color_rgb
        self._hover = 0.0
        self._hover_target = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(96)
        self.setMinimumWidth(180)
        self.setStyleSheet("QPushButton{background: transparent; border: none;}")
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def enterEvent(self, e):
        self._hover_target = 1.0
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover_target = 0.0
        super().leaveEvent(e)

    def _tick(self):
        d = self._hover_target - self._hover
        if abs(d) > 0.005:
            self._hover += d * 0.15
            self.update()
        elif self._hover != self._hover_target:
            self._hover = self._hover_target
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r, g, b = self._col
        rect = QRectF(1.5, 1.5, w - 3, h - 3)

        # фон
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(26, 26, 31, 235))
        p.drawRoundedRect(rect, 12, 12)
        # цветная подсветка
        tint = int(24 + 40 * self._hover)
        p.setBrush(QColor(r, g, b, tint))
        p.drawRoundedRect(rect, 12, 12)
        # рамка
        boost = int(30 * self._hover)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(min(255, r + boost), min(255, g + boost), min(255, b + boost)),
                     1.7 + 1.5 * self._hover))
        p.drawRoundedRect(rect, 12, 12)

        # заголовок
        p.setFont(QFont("Segoe UI", 12, QFont.Bold))
        p.setPen(QColor(230, 230, 235))
        p.drawText(QRectF(0, 20, w, 26), Qt.AlignCenter, self._title)
        # подзаголовок
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor(150, 150, 155))
        p.drawText(QRectF(0, 54, w, 22), Qt.AlignCenter, self._subtitle)
        p.end()


class KeyLimitTypeDialog(QDialog):
    """Первый шаг выключения ключа: пользователь выбирает тип лимита —
    5-часовой (жёлтый) или 7-дневный (красный). Отмена = не выключать ключ."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.result_type = None

        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 16px;
            }
        """)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(14)

        title = QLabel(tr("Выберите тип лимита"))
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #DDDDDD; background: transparent; border: none;")
        lay.addWidget(title)

        subtitle = QLabel(tr("На какой срок отключить ключ?"))
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #B5B5B5; background: transparent; border: none;")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self.btn_5h = _LimitTypeCard(tr("5-часовой лимит"), tr("макс. 5 часов"),
                                     (235, 200, 90))
        self.btn_5h.clicked.connect(lambda: self._pick("5h"))
        cards_row.addWidget(self.btn_5h)
        self.btn_7d = _LimitTypeCard(tr("7-дневный лимит"), tr("макс. 7 дней"),
                                     (224, 90, 90))
        self.btn_7d.clicked.connect(lambda: self._pick("7d"))
        cards_row.addWidget(self.btn_7d)
        lay.addLayout(cards_row)

        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        self.cancel_btn = RedButton(tr("Отмена"))
        self.cancel_btn.setMinimumHeight(38)
        self.cancel_btn.setMinimumWidth(140)
        self.cancel_btn.clicked.connect(self.reject)
        cancel_row.addWidget(self.cancel_btn)
        cancel_row.addStretch()
        lay.addLayout(cancel_row)

        main.addWidget(container)
        self.setLayout(main)
        self.setMinimumWidth(440)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(200)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def _pick(self, t):
        self.result_type = t
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def _fade_out_and(self, done):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(180)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(done)
        fade.start()
        self._fade = fade

    def accept(self):
        self._fade_out_and(lambda: super(KeyLimitTypeDialog, self).accept())

    def reject(self):
        self._fade_out_and(lambda: super(KeyLimitTypeDialog, self).reject())


class _NumberSpinner(QWidget):
    """Компактный вертикально-стилизованный числовой спиннер: слева
    квадратная кнопка «−», по центру крупное число, справа кнопка «+».
    Все клампы и валидация — внутри. По изменению эмитит valueChanged(int)."""
    valueChanged = Signal(int)

    def __init__(self, minimum=0, maximum=59, initial=0, parent=None):
        super().__init__(parent)
        self._min = minimum
        self._max = maximum
        self._value = max(minimum, min(maximum, initial))
        self.setFixedSize(120, 56)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.btn_dec = QPushButton("−")
        self.btn_dec.setFixedSize(30, 44)
        self.btn_dec.setCursor(Qt.PointingHandCursor)
        self.btn_dec.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.btn_dec.setStyleSheet(self._btn_css())
        self.btn_dec.clicked.connect(lambda: self.set_value(self._value - 1))
        lay.addWidget(self.btn_dec)

        self.num_lbl = QLabel(str(self._value))
        self.num_lbl.setAlignment(Qt.AlignCenter)
        self.num_lbl.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.num_lbl.setStyleSheet(
            "color: rgb(230, 230, 235); background: rgb(26, 26, 31);"
            "border: 1.5px solid rgb(70, 70, 80); border-radius: 8px;")
        self.num_lbl.setFixedSize(48, 44)
        lay.addWidget(self.num_lbl)

        self.btn_inc = QPushButton("+")
        self.btn_inc.setFixedSize(30, 44)
        self.btn_inc.setCursor(Qt.PointingHandCursor)
        self.btn_inc.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.btn_inc.setStyleSheet(self._btn_css())
        self.btn_inc.clicked.connect(lambda: self.set_value(self._value + 1))
        lay.addWidget(self.btn_inc)

    @staticmethod
    def _btn_css():
        return (
            "QPushButton{color: rgb(210,210,215); background: rgb(30,30,35);"
            "border: 1.5px solid rgb(70,70,80); border-radius: 8px;}"
            "QPushButton:hover{background: rgb(46,46,55); border-color: rgb(120,120,130);}"
            "QPushButton:pressed{background: rgb(22,22,26);}"
        )

    def value(self):
        return self._value

    def set_range(self, minimum, maximum):
        self._min, self._max = minimum, maximum
        self.set_value(self._value)

    def set_value(self, v):
        v = max(self._min, min(self._max, int(v)))
        if v == self._value:
            self.num_lbl.setText(str(v))
            return
        self._value = v
        self.num_lbl.setText(str(v))
        self.valueChanged.emit(v)


class KeyLimitDurationDialog(QDialog):
    """Второй шаг выключения: ввод точной длительности лимита.
    limit_type='5h' → часы (0-5) + минуты (0-59), суммарно ≤ 5 ч.
    limit_type='7d' → дни (0-7) + часы (0-23) + минуты (0-59), суммарно ≤ 7 дн.
    Возвращает result_seconds > 0 при подтверждении, иначе result_seconds=None."""
    def __init__(self, limit_type, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.limit_type = limit_type
        self.result_seconds = None

        if limit_type == "5h":
            self._max_seconds = KEY_LIMIT_5H_SECONDS
            title_txt = tr("5-часовой лимит")
            hint_txt = tr("Максимум 5 часов")
            color = (235, 200, 90)
        else:
            self._max_seconds = KEY_LIMIT_7D_SECONDS
            title_txt = tr("7-дневный лимит")
            hint_txt = tr("Максимум 7 дней")
            color = (224, 90, 90)

        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 16px;
            }
        """)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(12)

        title = QLabel(title_txt)
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color: rgb({color[0]},{color[1]},{color[2]}); background: transparent; border: none;")
        lay.addWidget(title)

        subtitle = QLabel(tr("Через сколько сбросится лимит?"))
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #B5B5B5; background: transparent; border: none;")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        # Спиннеры
        row = QHBoxLayout()
        row.setSpacing(14)
        row.setContentsMargins(0, 4, 0, 4)
        row.addStretch()

        def _column(caption, spinner):
            col = QVBoxLayout()
            col.setSpacing(4)
            col.setAlignment(Qt.AlignCenter)
            cap = QLabel(caption)
            cap.setFont(QFont("Segoe UI", 9))
            cap.setAlignment(Qt.AlignCenter)
            cap.setStyleSheet("color: rgb(150,150,155); background: transparent; border: none;")
            col.addWidget(cap)
            wrap = QHBoxLayout()
            wrap.addStretch()
            wrap.addWidget(spinner)
            wrap.addStretch()
            col.addLayout(wrap)
            return col

        if limit_type == "5h":
            self.sp_days = None
            self.sp_hours = _NumberSpinner(0, 5, 0)
            self.sp_minutes = _NumberSpinner(0, 59, 30)  # разумный дефолт
            row.addLayout(_column(tr("Часы"), self.sp_hours))
            row.addLayout(_column(tr("Минуты"), self.sp_minutes))
        else:
            self.sp_days = _NumberSpinner(0, 7, 1)
            self.sp_hours = _NumberSpinner(0, 23, 0)
            self.sp_minutes = _NumberSpinner(0, 59, 0)
            row.addLayout(_column(tr("Дни"), self.sp_days))
            row.addLayout(_column(tr("Часы"), self.sp_hours))
            row.addLayout(_column(tr("Минуты"), self.sp_minutes))
        row.addStretch()
        lay.addLayout(row)

        # обвязка клампа — при любом изменении пересчитать и, если сумма > max, обрезать
        self.sp_hours.valueChanged.connect(self._clamp_total)
        self.sp_minutes.valueChanged.connect(self._clamp_total)
        if self.sp_days is not None:
            self.sp_days.valueChanged.connect(self._clamp_total)

        hint = QLabel(hint_txt)
        hint.setFont(QFont("Segoe UI", 9))
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(
            f"color: rgba({color[0]}, {color[1]}, {color[2]}, 220);"
            f"background: rgba({color[0]}, {color[1]}, {color[2]}, 28);"
            f"border: 1px solid rgba({color[0]}, {color[1]}, {color[2]}, 90);"
            "border-radius: 6px; padding: 4px 12px;")
        lay.addWidget(hint)

        self.err_lbl = QLabel("")
        self.err_lbl.setFont(QFont("Segoe UI", 9))
        self.err_lbl.setAlignment(Qt.AlignCenter)
        self.err_lbl.setStyleSheet("color: rgb(224, 90, 90); background: transparent; border: none;")
        lay.addWidget(self.err_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.cancel_btn = RedButton(tr("Отмена"))
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)
        self.confirm_btn = GreenButton(tr("Подтвердить"))
        self.confirm_btn.setMinimumHeight(40)
        self.confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(self.confirm_btn)
        lay.addLayout(btn_row)

        main.addWidget(container)
        self.setLayout(main)
        self.setMinimumWidth(440)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(200)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def _total_seconds(self):
        d = self.sp_days.value() if self.sp_days is not None else 0
        h = self.sp_hours.value()
        m = self.sp_minutes.value()
        return d * 86400 + h * 3600 + m * 60

    def _clamp_total(self):
        total = self._total_seconds()
        if total <= self._max_seconds:
            self.err_lbl.setText("")
            return
        # Обрезаем «лишние» единицы: сначала минуты, потом часы, потом дни.
        for sp in (self.sp_minutes, self.sp_hours, self.sp_days):
            if sp is None:
                continue
            while sp.value() > 0 and self._total_seconds() > self._max_seconds:
                sp.blockSignals(True)
                sp.set_value(sp.value() - 1)
                sp.blockSignals(False)
        self.err_lbl.setText("")

    def _on_confirm(self):
        total = self._total_seconds()
        if total <= 0:
            self.err_lbl.setText(tr("Укажите время больше нуля"))
            return
        if total > self._max_seconds:
            # На всякий случай — clamp защитит, но подстрахуемся
            total = self._max_seconds
        self.result_seconds = total
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def _fade_out_and(self, done):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(180)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(done)
        fade.start()
        self._fade = fade

    def accept(self):
        self._fade_out_and(lambda: super(KeyLimitDurationDialog, self).accept())

    def reject(self):
        self._fade_out_and(lambda: super(KeyLimitDurationDialog, self).reject())


class ApiKeyManagerDialog(QDialog):
    """Широкое окно управления API-ключами: список карточек (до 6 видимых,
    дальше скролл), создание нового ключа с именем. Единственное место, где
    можно добавлять/выбирать/включать ключи."""
    CARD_H = 58
    GAP = 8
    MAX_VISIBLE = 4

    # Эмитим при любой мутации ключа (тумблер, авто-сброс таймера) — главное
    # окно ловит и сразу пишет settings.json, чтобы состояние переживало крэш.
    state_changed = Signal()

    def __init__(self, keys, selected_id="", parent=None):
        super().__init__(parent)
        # рабочая копия — на случай отмены мутации не заденут settings напрямую
        self.keys = [dict(k) for k in (keys or [])]
        self.selected_id = selected_id or ""
        # Если выбранного ключа больше нет в списке — сбрасываем выбор
        if self.selected_id and not any(k.get("id") == self.selected_id for k in self.keys):
            self.selected_id = ""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = DottedFrame()
        container.setObjectName("apiKeyManagerContainer")
        container.setStyleSheet("""
            QFrame#apiKeyManagerContainer {
                background-color: rgb(20, 20, 25);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 18, 28, 24)
        layout.setSpacing(12)

        # Заголовок + крестик
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        left_spacer = QWidget()
        left_spacer.setFixedSize(28, 28)
        left_spacer.setStyleSheet("background: transparent; border: none;")
        title_row.addWidget(left_spacer)
        title = QLabel(tr("Управление API ключами"))
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #CCCCCC; background: transparent; border: none;")
        title_row.addWidget(title, 1)
        self.btn_close = _CloseButton(parent=container)
        self.btn_close.clicked.connect(self.accept)
        title_row.addWidget(self.btn_close)
        layout.addLayout(title_row)

        info = QLabel(tr("Зелёный — активен. Жёлтый — 5-часовой лимит. Красный — 7-дневный лимит."))
        info.setFont(QFont("Segoe UI", 9))
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color: rgb(120, 120, 120); background: transparent; border: none;")
        layout.addWidget(info)

        # Скролл-область с карточками
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
            QScrollBar::handle:vertical { background: rgb(70,70,78); border-radius: 4px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: rgb(95,95,105); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        self.cards_host = QWidget()
        self.cards_host.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 6, 0)
        self.cards_layout.setSpacing(self.GAP)
        self.cards_layout.addStretch()
        self.scroll.setWidget(self.cards_host)
        layout.addWidget(self.scroll)

        # Пустой плейсхолдер
        self.empty_lbl = QLabel(tr("Ключей пока нет — добавьте первый ниже"))
        self.empty_lbl.setFont(QFont("Segoe UI", 9))
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.empty_lbl.setStyleSheet("color: rgb(110,110,116); background: transparent; border: none;")
        layout.addWidget(self.empty_lbl)

        # Секция добавления
        add_label = QLabel(tr("Добавить новый ключ:"))
        add_label.setFont(QFont("Segoe UI", 10))
        add_label.setStyleSheet("color: rgb(180, 180, 180); background: transparent; border: none;")
        layout.addWidget(add_label)

        _input_style = """
            QLineEdit {
                background-color: rgba(30, 30, 35, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 8px;
            }
        """
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr("Название"))
        self.name_input.setFont(QFont("Segoe UI", 9))
        self.name_input.setFixedWidth(150)
        self.name_input.setStyleSheet(_input_style)
        add_row.addWidget(self.name_input)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("fe_oa_xxxxx...")
        self.key_input.setFont(QFont("Segoe UI", 9))
        self.key_input.setStyleSheet(_input_style)
        self.key_input.returnPressed.connect(self.add_key)
        add_row.addWidget(self.key_input, 1)

        self.btn_add = GreenButton(tr("Добавить"))
        self.btn_add.setMinimumHeight(0)
        self.btn_add.setFixedHeight(38)
        self.btn_add.setMaximumWidth(120)
        self.btn_add.clicked.connect(self.add_key)
        add_row.addWidget(self.btn_add)
        layout.addLayout(add_row)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedWidth(620)

        self._rebuild_cards()

        # Живой пересчёт: обратный отсчёт до сброса лимита + авто-включение
        # ключа по истечении таймера. Тикаем раз в секунду, чтобы отсчёт
        # выглядел плавным.
        self._state_timer = QTimer(self)
        self._state_timer.timeout.connect(self._refresh_states)
        self._state_timer.start(1000)

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
        # Центрируем окно относительно родителя (или экрана) РОВНО при первом
        # показе — до этого позиция ещё «дефолтная», и Qt при переводе RU→EN
        # может выставить её не по центру. После центрирования выставляем
        # _positioned = True, чтобы дальнейшие _refit_window сохраняли позицию.
        if not getattr(self, "_positioned", False):
            self._center_on_parent()
            self._positioned = True

    def _reference_height(self):
        """Высота, которую окно занимало бы при MAX_VISIBLE карточках (полный
        скролл-потолок). Верх окна цепляется за эту высоту — тогда при 1-2
        ключах окно короче снизу, но верх остаётся на том же уровне и не
        подъезжает к переключателю Omniroute/BaseURL."""
        return (self.MAX_VISIBLE * self.CARD_H
                + (self.MAX_VISIBLE - 1) * self.GAP + 6  # scroll area
                + 200)  # шапка + плейсхолдер + строка добавления + отступы

    def _center_on_parent(self):
        try:
            self.adjustSize()
            self.setFixedWidth(620)
            dw = self.width()
            ref_h = self._reference_height()
            parent_win = self.parent().window() if self.parent() else None
            if parent_win is not None and parent_win.isVisible():
                pg = parent_win.frameGeometry()
                cx = pg.center().x()
                cy = pg.center().y()
            else:
                from PySide6.QtGui import QGuiApplication
                screen = QGuiApplication.primaryScreen().availableGeometry()
                cx = screen.center().x()
                cy = screen.center().y()
            # Верх диалога — как если бы он был максимальной высоты.
            top_y = cy - ref_h // 2
            self.move(cx - dw // 2, top_y)
        except Exception:
            pass

    def accept(self):
        fade = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        fade.setDuration(200)
        fade.setStartValue(self._opacity_effect.opacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: super(ApiKeyManagerDialog, self).accept())
        fade.start()
        self._fade_out = fade

    def reject(self):
        # Крестик закрытия = accept; reject ведёт себя так же (изменения сохраняются)
        self.accept()

    def _card_widgets(self):
        cards = []
        for i in range(self.cards_layout.count()):
            w = self.cards_layout.itemAt(i).widget()
            if isinstance(w, KeyCard):
                cards.append(w)
        return cards

    def _rebuild_cards(self):
        # удалить старые карточки
        for w in self._card_widgets():
            w.setParent(None)
            w.deleteLater()
        # вставить актуальные (перед финальным stretch)
        insert_at = 0
        for key in self.keys:
            card = KeyCard(key)
            card.toggled.connect(self._on_card_toggle)
            card.changed.connect(self._on_card_changed)
            card.delete_requested.connect(self._on_card_delete)
            card.select_requested.connect(self._on_card_select)
            card.set_selected(key.get("id") == self.selected_id)
            self.cards_layout.insertWidget(insert_at, card)
            insert_at += 1
        n = len(self.keys)
        self.empty_lbl.setVisible(n == 0)
        self.scroll.setVisible(n > 0)
        vis = max(1, min(self.MAX_VISIBLE, n))
        self.scroll.setFixedHeight(vis * self.CARD_H + (vis - 1) * self.GAP + 6)
        # После изменения количества карточек окно должно и расти, и
        # уменьшаться. По умолчанию QDialog запоминает наибольший вычисленный
        # sizeHint как минимум — сбрасываем ограничения и переподгоняем размер.
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        QTimer.singleShot(0, self._refit_window)

    def _refit_window(self):
        # Пересчёт высоты под текущий контент. Ширину держим = 620.
        # Позицию окна фиксируем по ЛЕВОМУ ВЕРХНЕМУ углу — иначе Qt при
        # уменьшении высоты «подтягивает» окно вверх, и оно скачет по экрану
        # каждый раз, когда пользователь удаляет ключ.
        top_left = self.pos()
        self.layout().activate()
        self.adjustSize()
        self.setFixedWidth(620)
        # Восстанавливаем позицию — если она уже была задана (после первого показа).
        if getattr(self, "_positioned", False):
            self.move(top_left)

    def _apply_selection_to_cards(self):
        for card in self._card_widgets():
            card.set_selected(card.key.get("id") == self.selected_id)

    def _on_card_select(self, key_id):
        # Выбираем только зелёные ключи (жёлтые/красные — сначала подтвердить/включить).
        key = next((k for k in self.keys if k.get("id") == key_id), None)
        if not key or key_color_state(key) != "green":
            return
        if self.selected_id == key_id:
            return
        self.selected_id = key_id
        self._apply_selection_to_cards()

    def _on_card_toggle(self, key_id, on):
        # мутация уже применена внутри KeyCard к тому же dict-объекту из self.keys.
        # Если карточку выключили — сбрасываем выбор; если это была первая активация
        # ключа и других зелёных нет — можем сразу назначить выбранным.
        if not on and self.selected_id == key_id:
            self.selected_id = ""
        elif on and not self.selected_id:
            key = next((k for k in self.keys if k.get("id") == key_id), None)
            if key and key_color_state(key) == "green":
                self.selected_id = key_id
        self._apply_selection_to_cards()

    def _on_card_changed(self, key_id):
        """Ключ мутирован (пользователь переключил тумблер или таймер лимита истёк).
        Прокидываем наверх — главное окно тут же вызовет save_settings, чтобы
        состояние переживало закрытие приложения даже без явного 'ОК'."""
        self.state_changed.emit()

    def _on_card_delete(self, key_id):
        key = next((k for k in self.keys if k.get("id") == key_id), None)
        if not key:
            return
        # Стилистически как окно подтверждения для status line: компактная
        # иконка «внимание» в цветной обводке (жёлтый), а не большой ⚠.
        confirm = ConfirmActionDialog(
            title=tr("Удалить этот API ключ?"),
            message=tr("Ключ и его настройки будут удалены безвозвратно."),
            detail=key.get("name", "Ключ"),
            confirm_text=tr("Да, удалить"),
            icon="!",
            icon_color=(245, 180, 60),
            parent=self,
        )
        if confirm.exec() != QDialog.Accepted:
            return
        self.keys = [k for k in self.keys if k.get("id") != key_id]
        if self.selected_id == key_id:
            self.selected_id = ""
        self._rebuild_cards()

    def add_key(self):
        val = self.key_input.text().strip()
        if not val:
            self.key_input.setFocus()
            return
        name = self.name_input.text().strip() or (tr("Ключ") + f" {len(self.keys) + 1}")
        new_id = _new_key_id()
        self.keys.append({
            "id": new_id,
            "name": name,
            "value": val,
            "enabled": True,
            "activated_at": time.time(),
        })
        # Первый заведённый ключ автоматически становится выбранным
        if not self.selected_id:
            self.selected_id = new_id
        self.name_input.clear()
        self.key_input.clear()
        self._rebuild_cards()
        # прокрутить вниз к новому ключу
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()))

    def _refresh_states(self):
        for card in self._card_widgets():
            card.refresh_state()

    def get_result(self):
        return [dict(k) for k in self.keys], self.selected_id


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
        models = ["Fable 5", "Opus 4.8", "Opus 4.7", "Opus 4.6", "Sonnet 5", "Sonnet 4.6", "Sonnet 4"]
        self.model_combo.addItems(models)
        # Цвета для каждой модели (от зелёного к красному)
        _sd_model_colors = {
            "Sonnet 4":     QColor(120, 220, 120),
            "Sonnet 4.6":   QColor(110, 240, 110),
            "Sonnet 5":     QColor(100, 230, 100),
            "Opus 4.6":     QColor(230, 220, 130),
            "Opus 4.7":     QColor(235, 180, 110),
            "Opus 4.8":     QColor(235, 150, 130),
            "Fable 5":   QColor(235, 90, 90),
        }
        for i in range(self.model_combo.count()):
            txt = self.model_combo.itemText(i)
            if txt in _sd_model_colors:
                self.model_combo.setItemData(i, _sd_model_colors[txt], Qt.ForegroundRole)
            pass
        # Маппинг старых сохранённых значений на новые метки
        model_remap = {
            "default (claude-opus-4-8)": "Opus 4.8",
            "Opus 4.8 (default)": "Opus 4.8",
            "claude-sonnet-5": "Sonnet 5",
            "claude-sonnet-4-6 (/model → 2)": "Sonnet 4.6",
            "claude-sonnet-4-6": "Sonnet 4.6",
            "claude-opus-4-7": "Opus 4.7",
            "claude-opus-4-6": "Opus 4.6",
            "claude-fable-5": "Fable 5",
        }
        saved_model = settings.get("custom_model", "Opus 4.8")
        saved_model = model_remap.get(saved_model, saved_model)
        if saved_model in models:
            self.model_combo.setCurrentText(saved_model)
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

    def save_settings(self):
        """Сохраняет настройки"""
        api_key = self.key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Ошибка", "API ключ не может быть пустым")
            return

        chosen_model = self.model_combo.currentText()

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

    def __init__(self, color=(52, 211, 153), size=72, parent=None):
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
    """Показывает прогресс установки/обновления/удаления, ждёт закрытия PowerShell."""

    def __init__(self, is_update=False, old_version="", new_version="",
                 is_uninstall=False, parent=None):
        super().__init__(parent)
        self._is_update = is_update
        self._is_uninstall = is_uninstall
        self._old_version = old_version
        self._new_version = new_version
        self._finished = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowModality(Qt.ApplicationModal)

        if is_uninstall:
            self._accent = (235, 90, 90)   # красный
            self._title_text = tr("Удаление Claude Code")
            # Не жёстко-русский action_word — берём готовый tr()-ключ
            self._status_running_text = tr("Идёт удаление…\nНе закрывайте окно PowerShell.")
        elif is_update:
            self._accent = (245, 180, 60)   # жёлто-оранжевый
            self._title_text = tr("Обновление Claude Code")
            self._status_running_text = tr("Идёт обновление…\nНе закрывайте окно PowerShell.")
        else:
            self._accent = (52, 211, 153)  # зелёный
            self._title_text = tr("Установка Claude Code")
            self._status_running_text = tr("Идёт установка…\nНе закрывайте окно PowerShell.")

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
            # Если new_version выглядит как номер версии (начинается с цифры), добавляем "v"
            new_fmt = f"v{new_version}" if new_version and new_version[0].isdigit() else new_version
            old_fmt = f"v{old_version}" if old_version and old_version[0].isdigit() else old_version
            sub_text = f"{old_fmt}  →  {new_fmt}"
        elif new_version:
            sub_text = f"v{new_version}" if new_version[0].isdigit() else new_version
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
        self.status_lbl = QLabel(self._status_running_text)
        self.status_lbl.setFont(QFont("Segoe UI", 10))
        self.status_lbl.setStyleSheet(
            "color: rgba(210, 210, 215, 0.9); background: transparent; border: none;"
        )
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        # Кнопка OK (скрыта до завершения)
        self.btn_ok = GlowDialogButton(tr("Понятно"),
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
        if self._is_uninstall:
            self.title_lbl.setText(tr("Claude Code удалён ✓"))
            self.sub_lbl.setText("")
            self.status_lbl.setText(tr(
                "Удаление завершено успешно."
            ))
        elif self._is_update:
            ver = actual_version or self._new_version
            self.title_lbl.setText(tr("Claude Code обновлён ✓"))
            if ver:
                ver_fmt = f"v{ver}" if ver[0].isdigit() else ver
                self.sub_lbl.setText(tr("Версия") + f" {ver_fmt}")
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
                ver_fmt = f"v{ver}" if ver[0].isdigit() else ver
                self.sub_lbl.setText(tr("Версия") + f" {ver_fmt}")
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
        if self._is_uninstall:
            title = tr("Удаление отменено")
        elif self._is_update:
            title = tr("Обновление отменено")
        else:
            title = tr("Установка отменена")
        self.title_lbl.setText(title)
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
        if self._is_uninstall:
            title = tr("Удаление не завершено")
        elif self._is_update:
            title = tr("Обновление не завершено")
        else:
            title = tr("Установка не завершена")
        self.title_lbl.setText(title)
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

        accent = (52, 211, 153)  # зелёный
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

        self.progress_bar = AnimatedProgressBar("#34d399")
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
        self.title_label = QLabel(tr("Скачивание обновления"))
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

        cl.addLayout(ic)
        cl.addWidget(self.title_label)
        cl.addWidget(self.version_label)
        cl.addWidget(self.progress_bar)
        cl.addWidget(self.message_label)

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
            self.title_label.setText(tr("Обновление скачано!"))
            self.icon_label.setText("✓")
            self.icon_label.setStyleSheet("""
                QLabel {
                    color: #34d399;
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
                    color: #34d399;
                    font-size: 16px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }
            """)

            # Финал полностью автоматический: старый .exe удаляется, новый запускается.
            self.message_label.setText(tr("Завершаем обновление…"))
            self.message_label.show()

            # Небольшая задержка, чтобы пользователь успел увидеть «Обновление скачано!»
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1200, self._delete_old_and_open)
        else:
            self.title_label.setText(tr("Ошибка скачивания"))
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
            self.message_label.setText(f"{tr('Ошибка')}: {message}")
            self.message_label.show()

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
    claude_uninstall_finished = Signal(object)  # context dict (по образцу install)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claude Code Manager")
        self.setFixedWidth(740)
        # Стартовая высота — зависит от сохранённого режима
        _is_fm = self.settings.get("use_custom_token", False) if False else False
        # Будет переустановлено в toggle_custom_token_fields()
        self.resize(740, 905)

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
        # На каждом старте принудительно открываем вкладку BaseURL
        # (независимо от того, какая была выбрана в прошлый раз).
        self.settings["use_custom_token"] = True
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

        # Стражи safe-режима (пин версии + запрет автообновления) запускаем
        # только если пользователь не включил официальные обновления —
        # иначе они тут же откатят DISABLE_UPDATES/autoUpdates обратно.
        if not self.settings.get("auto_update_enabled", False):
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

        self.btn_install_claude = StyledButton(tr("Установить Claude Code"))
        self.btn_install_claude.setFixedHeight(34)
        self.btn_install_claude.clicked.connect(self._install_claude_code)
        install_row.addWidget(self.btn_install_claude)

        self.btn_uninstall_claude = StyledButton(tr("Удалить Claude Code"))
        self.btn_uninstall_claude.setFixedHeight(34)
        self.btn_uninstall_claude.set_hover_color(235, 90, 90)  # красный hover
        self.btn_uninstall_claude.clicked.connect(self._uninstall_claude_code)
        install_row.addWidget(self.btn_uninstall_claude)

        # Добавить в PATH — прописывает папку с claude в PATH пользователя,
        # если она там ещё не значится. Актуально только для auto-update режима
        # (install.ps1 кладёт бинарь в ~/.local/bin — эта папка обычно не в PATH).
        # В безопасном режиме ставим через npm, %APPDATA%\npm уже в PATH.
        self.btn_add_to_path = StyledButton(tr("Добавить в PATH"))
        self.btn_add_to_path.setFixedHeight(34)
        self.btn_add_to_path.set_hover_color(120, 180, 230)
        self.btn_add_to_path.setEnabled(self.settings.get("auto_update_enabled", False))
        self.btn_add_to_path.clicked.connect(self._on_add_to_path_clicked)
        install_row.addWidget(self.btn_add_to_path)

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
        self.update_indicator.move(self.width() - 78 - 8 - 45 + 4, 10)  # к левому краю ползунка языка
        self.update_indicator.raise_()

        # Переключатель языка интерфейса EN / RU — абсолютная позиция в правом
        # верхнем углу, чуть левее индикатора обновлений. Цвет пилюли меняется
        # плавно: EN — зелёный (#34d399, унифицированный), RU — голубоватый.
        self.language_toggle = LanguageToggle(LANG.lang if LANG else "ru", self)
        self.language_toggle.move(self.width() - 78 - 8, 12)
        self.language_toggle.raise_()
        self.language_toggle.toggled.connect(self._on_language_toggled)
        if LANG is not None:
            LANG.language_changed.connect(self._on_language_changed)

        # Бейдж freemodel.dev — абсолютная позиция в левом верхнем углу.
        # Виден только когда выбран freemodel-эндпоинт (cc.freemodel.dev,
        # api-cc.freemodel.dev и другие поддомены). Просто надпись, без
        # индикатора статуса и клика — окно статистики больше не работает.
        self.freemodel_brand = FreemodelBrand(self)
        self.freemodel_brand.move(12, 22)
        self.freemodel_brand.raise_()
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

        # Тумблер: официальные авто-обновления Claude Code через install.ps1
        # вместо пина на REQUIRED_CLAUDE_VERSION. Живёт справа внутри chip.
        autoupdate_lbl = QLabel(tr("Авто-обновление"))
        autoupdate_lbl.setFont(QFont("Segoe UI", 9))
        autoupdate_lbl.setStyleSheet("color: rgb(180, 180, 180); background: transparent; border: none;")
        self._track_tr(autoupdate_lbl, "Авто-обновление")
        claude_header_inner.addWidget(autoupdate_lbl)
        self.autoupdate_toggle = ToggleSwitch(checked=self.settings.get("auto_update_enabled", False))
        self.autoupdate_toggle.toggled.connect(self._on_auto_update_toggled)
        claude_header_inner.addWidget(self.autoupdate_toggle)

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

        # Поле ключа теперь только ОТОБРАЖАЕТ активный (первый зелёный) ключ —
        # read-only. Добавление/выбор/включение ключей происходит исключительно
        # в окне «Управление».
        self.fm_key_input = QLineEdit()
        self.fm_key_input.setPlaceholderText(tr("Ключи не добавлены — откройте «Управление»"))
        self.fm_key_input.setText(self.settings.get("custom_api_key", ""))
        self.fm_key_input.setEchoMode(QLineEdit.Password)
        self.fm_key_input.setFont(QFont("Segoe UI", 9))
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
        key_row.addWidget(self.fm_key_input, 1)

        self.fm_btn_toggle_key = EyeToggleButton()
        self.fm_btn_toggle_key.clicked.connect(self._fm_toggle_key)
        key_row.addWidget(self.fm_btn_toggle_key)

        self.fm_btn_manage_keys = StyledButton(tr("Управление"))
        self.fm_btn_manage_keys.setMinimumHeight(0)
        self.fm_btn_manage_keys.setFixedHeight(36)
        self.fm_btn_manage_keys.setFixedWidth(130)
        self.fm_btn_manage_keys.clicked.connect(self._fm_manage_keys)
        key_row.addWidget(self.fm_btn_manage_keys)
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

        # Кастомный picker: клик по комбо открывает ModelDialog с ползунком
        # (стиль совпадает с EffortDialog). На главном окне сам комбобокс
        # остаётся визуально прежним, только шрифт делаем жирнее — по просьбе
        # пользователя, чтобы название модели читалось увереннее.
        self.fm_model_combo = ModelPickerComboBox()
        self.fm_model_combo.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.fm_model_combo.setMaxVisibleItems(len(MODEL_ORDER))
        fm_models = ["Fable 5", "Opus 4.8", "Opus 4.7", "Opus 4.6", "Sonnet 5", "Sonnet 4.6"]
        self.fm_model_combo.addItems(fm_models)
        # Цвета для каждой модели (от зелёного к красному — по «дороговизне»)
        model_colors = {
            "Sonnet 4":     QColor(120, 220, 120),  # зелёный
            "Sonnet 4.6":   QColor(130, 220, 130),  # насыщенно-зелёный
            "Sonnet 5":     QColor(180, 235, 150),  # светло-зелёный (чуть желтее 4.6)
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
        )
        saved_m = self.settings.get("custom_model", "Opus 4.8")
        remap = {
            "default (claude-opus-4-8)": "Opus 4.8",
            "Opus 4.8 (default)": "Opus 4.8",
            "claude-sonnet-5": "Sonnet 5",
            "claude-sonnet-4-6 (/model → 2)": "Sonnet 4.6",
            "claude-sonnet-4-6": "Sonnet 4.6",
            "claude-opus-4-7": "Opus 4.7",
            "claude-opus-4-6": "Opus 4.6",
            "claude-fable-5": "Fable 5",
        }
        saved_m = remap.get(saved_m, saved_m)
        if saved_m in fm_models:
            self.fm_model_combo.setCurrentText(saved_m)
        # Начальный цвет текста и рамки под выбранную модель
        if saved_m in model_colors:
            self.fm_model_combo.setTextColor(model_colors[saved_m])
            self.fm_model_combo.setAccentColor(model_colors[saved_m])
        # Запомнить исходную модель для отката при отмене предупреждения
        self._fm_prev_model = saved_m if saved_m in fm_models else "Opus 4.8"
        self.fm_model_combo.currentTextChanged.connect(self._fm_model_changed)
        # ModelDialog теперь эмитит и модель, и effort одним сигналом
        try:
            self.fm_model_combo.modelEffortPicked.connect(self._on_model_effort_picked)
        except Exception:
            pass
        model_row.addWidget(self.fm_model_combo, 1)

        # 1M-контекст: маленький toggle-оверлей внутри правой части комбобокса модели
        # (стилистика — карбоновая копия LanguageToggle). Активная сторона:
        # 200K (синий) → дефолт; 1M (зелёный) → id получает суффикс [1M].
        self.ctx_toggle = ContextToggle(
            one_m=self.settings.get("use_1m_context", False),
            parent=self.fm_model_combo
        )
        self.ctx_toggle.toggled.connect(self._on_1m_context_toggled)
        self.ctx_toggle.raise_()

        # Сероватая полоска-разделитель между текстом модели и тумблером —
        # + служит «щитом» hover'а: пока курсор над ней или над тумблером,
        # рамка combobox'а не подсвечивается.
        self.ctx_separator = _CtxSeparator(parent=self.fm_model_combo)

        # Прозрачный «щит» на всю правую полосу combobox'а — блокирует
        # клики по фону и Enter в зазорах вокруг тумблера, чтобы рамка
        # не подсвечивалась и picker не открывался.
        self.ctx_shield = _CtxShield(parent=self.fm_model_combo)
        self.ctx_shield.lower()  # под toggle/separator в стеке дочерних
        self.ctx_separator.raise_()
        self.ctx_toggle.raise_()

        self.fm_model_combo.installEventFilter(self)
        self.ctx_toggle.installEventFilter(self)
        self.ctx_separator.installEventFilter(self)
        self.ctx_shield.installEventFilter(self)
        QTimer.singleShot(0, self._reposition_ctx_toggle)

        # Effort — тот же кликабельный комбобокс что и раньше, но при клике
        # открывается компактный EffortDialog с ползунком (вместо PickerDialog
        # со списком карточек).
        self.fm_effort_combo = EffortPickerComboBox()
        self.fm_effort_combo.setFont(QFont("Segoe UI", 9, QFont.Bold))
        # Минимальная ширина под самое длинное значение "ULTRACODE"
        # (жирным + запас на стрелку drop-down), чтобы текст не резался.
        self.fm_effort_combo.setMinimumWidth(120)
        fm_efforts = list(EFFORT_LEVELS)  # low / medium / high / xhigh / max / ultracode
        self.fm_effort_combo.addItems(fm_efforts)
        saved_fm_effort = self.settings.get("reasoning_effort", "high")
        if saved_fm_effort in fm_efforts:
            self.fm_effort_combo.setCurrentText(saved_fm_effort)
        else:
            self.fm_effort_combo.setCurrentText("high")
        self.fm_effort_combo.setMaxVisibleItems(len(fm_efforts))
        fm_effort_colors = {k: QColor(*v) for k, v in EFFORT_COLORS.items()}
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

        # Именно addStretch(1), а не addSpacing(10). Пружина между консолью
        # и футером поглощает разницу высот при переключении Omniroute↔BaseURL:
        # когда секции сверху скрываются, освободившееся место уходит СЮДА, а
        # не размазывается между stretch-факторами верхних виджетов — иначе те
        # видимо «прыгают» на промежуточные позиции. В эталонной версии окна
        # именно так и сделано.
        main_layout.addStretch(1)

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
            color = "#34d399"  # FreeModel зелёный (52, 211, 153)
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
            self.status_label.setStyleSheet("color: rgb(52, 211, 153);")
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
        for attr in ("freemodel_brand",
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
            if hasattr(self, "btn_add_to_path"):
                self.btn_add_to_path.setText(tr("Добавить в PATH"))
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
            if hasattr(self, "fm_btn_manage_keys"):
                self.fm_btn_manage_keys.setText(tr("Управление"))
            # Плейсхолдер поля активного ключа на главном экране (виден, когда ключей нет)
            if hasattr(self, "fm_key_input"):
                self.fm_key_input.setPlaceholderText(tr("Ключи не добавлены — откройте «Управление»"))
            # Заголовки picker-диалогов (модель / Base URL): _pick_title кэшируется в
            # combobox'е, а не тянется через tr() при каждом открытии — переустанавливаем вручную.
            if hasattr(self, "fm_model_combo"):
                self.fm_model_combo._pick_title = tr("Выбор модели")
            if hasattr(self, "fm_url_combo"):
                self.fm_url_combo._pick_title = tr("Выбор Base URL")
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
        except Exception:
            pass

    def _fm_model_changed(self, new_model):
        """Сохраняет выбранную модель FreeModel"""
        # Показать предупреждение при выборе Fable 5
        if new_model == "Fable 5":
            dlg = Fable5WarningDialog(self)
            if dlg.exec() != QDialog.Accepted:
                # Пользователь отменил — откатить на ту модель, с которой переключались
                prev = getattr(self, "_fm_prev_model", "Opus 4.8")
                self.fm_model_combo.blockSignals(True)
                self.fm_model_combo.setCurrentText(prev)
                self.fm_model_combo.blockSignals(False)
                # Вернуть цвет предыдущей модели
                if hasattr(self, "_fm_model_colors") and prev in self._fm_model_colors:
                    self.fm_model_combo.setTextColor(self._fm_model_colors[prev])
                    self.fm_model_combo.setAccentColor(self._fm_model_colors[prev])
                return
        if new_model:
            self.settings["custom_model"] = new_model
            save_settings(self.settings)
            # Опус 4.6 и Sonnet 4.6 не поддерживают ultracode — если сейчас
            # выставлен ultracode, тихо понижаем до max и обновляем combo effort.
            if (new_model in MODELS_WITHOUT_ULTRACODE
                    and self.settings.get("reasoning_effort") == "ultracode"):
                self.settings["reasoning_effort"] = "max"
                save_settings(self.settings)
                self.log(
                    f"{new_model} {tr('не поддерживает ultracode — effort понижен до max')}",
                    "warning"
                )
                # Триггерим обновление combo effort, чтобы цвет/текст сменились
                if hasattr(self, "fm_effort_combo"):
                    self.fm_effort_combo.blockSignals(True)
                    self.fm_effort_combo.setCurrentText("max")
                    self.fm_effort_combo.blockSignals(False)
                    if hasattr(self, "_fm_effort_colors") and "max" in self._fm_effort_colors:
                        self.fm_effort_combo.setTextColor(self._fm_effort_colors["max"])
                        self.fm_effort_combo.setAccentColor(self._fm_effort_colors["max"])
                self._write_claude_effort_setting("max")
        if hasattr(self, "fm_model_combo"):
            # Обновить цвет отображаемого текста и рамки под выбранную модель
            if hasattr(self, "_fm_model_colors") and new_model in self._fm_model_colors:
                self.fm_model_combo.setTextColor(self._fm_model_colors[new_model])
                self.fm_model_combo.setAccentColor(self._fm_model_colors[new_model])
        # Обновить «предыдущую» модель для будущих откатов
        if new_model:
            self._fm_prev_model = new_model

    def _on_model_effort_picked(self, model, effort):
        """ModelDialog закрылся — применяем и модель, и effort. Модель уже
        применена через currentTextChanged → _fm_model_changed (та сама
        может понизить ultracode до max при 4.6-tier). Здесь применяем
        только effort, чтобы затронуть fm_effort_combo и ~/.claude/settings.json."""
        if effort not in EFFORT_LEVELS:
            return
        # Защитный downgrade: если модель не поддерживает ultracode, а слайдер
        # почему-то отдал ultracode — сбиваем на max. В нормальном сценарии
        # ModelDialog уже сам синхронизирует это при движении модели.
        if effort == "ultracode" and model in MODELS_WITHOUT_ULTRACODE:
            effort = "max"
        # Если текущее значение уже равно этому — ничего не делаем, чтобы не
        # спамить лог "Reasoning effort изменён на".
        if self.settings.get("reasoning_effort") == effort:
            return
        self._on_effort_changed(effort)

    def _on_effort_changed(self, effort):
        """Сохраняет выбранный reasoning effort, пишет в ~/.claude/settings.json
        и обновляет цвет рамки/текста кликабельного комбобокса."""
        if effort not in EFFORT_LEVELS:
            return
        self.settings["reasoning_effort"] = effort
        save_settings(self.settings)
        # Сразу прописываем в настройки самого Claude Code (поле effortLevel)
        self._write_claude_effort_setting(effort)
        self.log(f"{tr('Reasoning effort изменён на')}: {effort}", "info")

        if hasattr(self, "fm_effort_combo") and hasattr(self, "_fm_effort_colors"):
            if effort in self._fm_effort_colors:
                # setCurrentText нужен, чтобы сам combobox отображал новый уровень
                # (EffortDialog эмитит applied → сюда, но не трогает текст комбо).
                if self.fm_effort_combo.currentText() != effort:
                    self.fm_effort_combo.blockSignals(True)
                    self.fm_effort_combo.setCurrentText(effort)
                    self.fm_effort_combo.blockSignals(False)
                self.fm_effort_combo.setTextColor(self._fm_effort_colors[effort])
                self.fm_effort_combo.setAccentColor(self._fm_effort_colors[effort])

    def _on_1m_context_toggled(self, checked):
        """Переключает 1M-контекст. При включении модели с поддержкой получат
        суффикс [1M] в ID; ~/.claude/settings.json перезаписывается сразу,
        чтобы Claude Code подхватил новый id при следующем запуске."""
        self.settings["use_1m_context"] = checked
        save_settings(self.settings)
        try:
            current_model = self.fm_model_combo.currentText() if hasattr(self, "fm_model_combo") else self.settings.get("custom_model", "")
            if current_model:
                self._write_claude_model_setting(current_model)
        except Exception:
            pass
        self.log(
            tr("1M-контекст включён") if checked else tr("1M-контекст выключен"),
            "info"
        )

    def _reposition_ctx_toggle(self):
        """Прижимает 1M-тумблер к правому краю комбобокса модели, ставит
        разделитель слева от него и растягивает прозрачный «щит» на всю
        правую полосу combobox'а (от палочки до правого края, всю высоту)."""
        if not (hasattr(self, "ctx_toggle") and hasattr(self, "fm_model_combo")):
            return
        combo = self.fm_model_combo
        tw, th = self.ctx_toggle.width(), self.ctx_toggle.height()
        x = max(0, combo.width() - tw - 8)
        y = max(0, (combo.height() - th) // 2)
        self.ctx_toggle.move(x, y)
        sep = getattr(self, "ctx_separator", None)
        sep_x = x
        if sep is not None:
            sw, sh = sep.width(), sep.height()
            sy = max(0, (combo.height() - sh) // 2)
            sep_x = max(0, x - sw - 2)
            sep.move(sep_x, sy)
        shield = getattr(self, "ctx_shield", None)
        if shield is not None:
            # Щит: от левого края палочки до правого края combobox'а, на всю высоту
            shield.setGeometry(sep_x, 0, max(0, combo.width() - sep_x), combo.height())

    def _cursor_over_ctx_shield(self):
        """Курсор сейчас над «щитом» (тумблер / палочка / прозрачный щит)?"""
        combo = getattr(self, "fm_model_combo", None)
        if combo is None:
            return False
        from PySide6.QtGui import QCursor
        pos = combo.mapFromGlobal(QCursor.pos())
        for shield in (
            getattr(self, "ctx_toggle", None),
            getattr(self, "ctx_separator", None),
            getattr(self, "ctx_shield", None),
        ):
            if shield is not None and shield.geometry().contains(pos):
                return True
        return False

    def eventFilter(self, obj, event):
        combo = getattr(self, "fm_model_combo", None)
        if combo is not None:
            if obj is combo and event.type() == QEvent.Resize:
                self._reposition_ctx_toggle()
            elif obj in (
                getattr(self, "ctx_toggle", None),
                getattr(self, "ctx_separator", None),
                getattr(self, "ctx_shield", None),
            ):
                et = event.type()
                if et == QEvent.Enter:
                    # Курсор зашёл на щит — гасим hover-подсветку combobox'а.
                    combo._is_hovered = False
                elif et == QEvent.Leave:
                    # Курсор ушёл со щита. Если он остался внутри combobox'а
                    # (и не над другим щитом) — вернём подсветку.
                    from PySide6.QtGui import QCursor
                    pos = combo.mapFromGlobal(QCursor.pos())
                    if combo.rect().contains(pos) and not self._cursor_over_ctx_shield():
                        combo._is_hovered = True
        return super().eventFilter(obj, event)

    def _fm_toggle_key(self):
        """Показать/скрыть API ключ"""
        if self.fm_key_input.echoMode() == QLineEdit.Password:
            self.fm_key_input.setEchoMode(QLineEdit.Normal)
            self.fm_btn_toggle_key.setRevealed(True)
        else:
            self.fm_key_input.setEchoMode(QLineEdit.Password)
            self.fm_btn_toggle_key.setRevealed(False)

    def _fm_manage_keys(self):
        """Открывает окно управления API-ключами (единственное место, где
        можно добавлять/включать/выбирать ключи)."""
        dlg = ApiKeyManagerDialog(
            self.settings.get("api_keys", []),
            selected_id=self.settings.get("selected_key_id", ""),
            parent=self,
        )
        # Пока диалог открыт, любая мутация ключа (клик тумблера, авто-сброс
        # таймера лимита) должна тут же сохраняться на диск — чтобы состояние
        # переживало неожиданное закрытие приложения.
        dlg.state_changed.connect(lambda: self._persist_key_state(dlg))
        dlg.exec()
        keys, selected_id = dlg.get_result()
        self.settings["api_keys"] = keys
        self.settings["selected_key_id"] = selected_id
        sync_custom_api_key(self.settings)
        save_settings(self.settings)
        self._refresh_active_key_display()
        # Активный ключ мог смениться — обновим модель в ~/.claude/settings.json
        try:
            current_model = self.fm_model_combo.currentText() if hasattr(self, "fm_model_combo") else self.settings.get("custom_model", "")
            if current_model:
                self._write_claude_model_setting(current_model)
        except Exception:
            pass

    def _persist_key_state(self, dlg):
        """Слот сигнала ApiKeyManagerDialog.state_changed: подхватывает
        текущее состояние ключей из открытого диалога и пишет settings.json,
        не дожидаясь закрытия окна."""
        try:
            keys, selected_id = dlg.get_result()
            self.settings["api_keys"] = keys
            self.settings["selected_key_id"] = selected_id
            sync_custom_api_key(self.settings)
            save_settings(self.settings)
            self._refresh_active_key_display()
        except Exception as e:
            print(f"[_persist_key_state] Не удалось сохранить: {e}")

    def _refresh_active_key_display(self):
        """Обновляет read-only поле активного ключа под текущий custom_api_key."""
        val = self.settings.get("custom_api_key", "")
        if hasattr(self, "fm_key_input"):
            self.fm_key_input.setEchoMode(QLineEdit.Password)
            self.fm_key_input.setText(val)
        if hasattr(self, "fm_btn_toggle_key") and hasattr(self.fm_btn_toggle_key, "setRevealed"):
            self.fm_btn_toggle_key.setRevealed(False)

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
        "Sonnet 5": "claude-sonnet-5",
        "Sonnet 4.6": "claude-sonnet-4-6",
        "Sonnet 4": "claude-sonnet-4",
        "Opus 4.7": "claude-opus-4-7",
        "Opus 4.6": "claude-opus-4-6",
    }

    # Модели, поддерживающие расширенный 1M-контекст — им дописываем суффикс [1M],
    # если пользователь включил соответствующий тумблер.
    MODELS_WITH_1M_CONTEXT = {
        "Opus 4.8", "Opus 4.8 (default)",
        "Opus 4.7", "Opus 4.6",
        "Sonnet 5", "Sonnet 4.6",
        "Fable 5",
    }

    # Модели, для которых НЕ передавать --model (только env), чтобы /model показывал Default
    NO_CLI_FLAG_MODELS = set()  # Пустой — все модели форсятся через --model

    def _resolve_model_id(self, model_choice):
        """Возвращает реальный ID модели для CLI/env или None для дефолта."""
        base = self.MODEL_ID_MAP.get(model_choice)
        if base is None:
            return None
        if self.settings.get("use_1m_context", False) and model_choice in self.MODELS_WITH_1M_CONTEXT:
            return base + "[1M]"
        return base

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
        """Записывает reasoning effort в ~/.claude/settings.json.
        Claude Code CLI знает только low/medium/high/xhigh/max. Для ultracode
        УДАЛЯЕМ effortLevel из settings.json и ставим ultracode=true — иначе
        effortLevel=max перебьёт ultracode-режим в текущей сессии."""
        if effort == "ultracode":
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
                claude_settings.pop("effortLevel", None)
                claude_settings["ultracode"] = True
                with open(claude_settings_path, 'w', encoding='utf-8') as f:
                    json.dump(claude_settings, f, indent=2)
            except Exception as e:
                self.log(f"Не удалось записать effort в настройки Claude: {e}", "warning")
            return
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
            claude_settings.pop("ultracode", None)
            with open(claude_settings_path, 'w', encoding='utf-8') as f:
                json.dump(claude_settings, f, indent=2)
        except Exception as e:
            self.log(f"Не удалось записать effort в настройки Claude: {e}", "warning")

    def launch_claude(self):
        """Запускает Claude Code с выбранной моделью"""
        # Жёсткая проверка: установленная версия не должна быть выше REQUIRED_CLAUDE_VERSION.
        # Пропускаем её, если включены официальные обновления — там версия выше пина ожидаема.
        if not self.settings.get("auto_update_enabled", False):
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

        # Reasoning effort. Для обычных уровней (low..max) — CLI-флаг + env +
        # settings.json.effortLevel. Для ultracode — вообще НЕ трогаем ни
        # --effort, ни CLAUDE_CODE_EFFORT_LEVEL: Claude Code сам увидит его
        # варнингом ("CLAUDE_CODE_EFFORT_LEVEL=max overrides effort this
        # session — clear it and ultracode takes over"), и включит ultracode
        # только по флагу CLAUDE_CODE_ULTRACODE=1 + settings.json.ultracode=true.
        effort_ui = self.settings.get("reasoning_effort", "high")
        cur_model_for_ultra = self.settings.get("custom_model") if use_custom else model
        if effort_ui == "ultracode" and cur_model_for_ultra in MODELS_WITHOUT_ULTRACODE:
            self.log(
                f"{cur_model_for_ultra} {tr('не поддерживает ultracode — понижаю до max')}",
                "warning"
            )
            effort_ui = "max"
        if effort_ui == "ultracode":
            # Явно вычищаем любые прежние значения из окружения родителя,
            # иначе они перебьют ultracode на текущей сессии.
            env.pop("CLAUDE_CODE_EFFORT_LEVEL", None)
            env["CLAUDE_CODE_ULTRACODE"] = "1"
            effort_flag = ""
            effort = "ultracode"
        else:
            cli_effort = effort_ui if effort_ui in ("low", "medium", "high", "xhigh", "max") else "high"
            env["CLAUDE_CODE_EFFORT_LEVEL"] = cli_effort
            env.pop("CLAUDE_CODE_ULTRACODE", None)
            effort_flag = f" --effort {cli_effort}"
            effort = cli_effort
        self._write_claude_effort_setting(effort_ui)

        if use_custom:
            # Кастомные настройки (BaseURL). Пересчитываем активный ключ на
            # случай, если зелёный ключ «пожелтел» за время работы приложения.
            sync_custom_api_key(self.settings)
            custom_api_key = self.settings.get("custom_api_key", "")

            if not custom_api_key:
                self.log("Нет активного API ключа — включите ключ в окне «Управление»", "error")
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
            self.log(tr("Действие со status line отменено"), "info")

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

    def _on_auto_update_toggled(self, checked):
        """Переключает режим обновления Claude Code: пин + блокировки (OFF,
        безопасный режим по умолчанию) ↔ официальный npm-пакет без ограничений (ON)."""
        if checked:
            dlg = ConfirmActionDialog(
                title=tr("Поддержка новых версий Claude Code"),
                message=tr(
                    "Включится официальный установщик "
                    "(npm install -g @anthropic-ai/claude-code). Claude Code будет "
                    "обновляться сам до последней версии.\n\n"
                    "Сейчас всё работает и на последней версии. Если что-то "
                    "вдруг перестанет работать — просто выключи этот переключатель, "
                    "и приложение вернёт проверенную версию, на которой всё "
                    "гарантированно работает."
                ),
                detail="npm install -g @anthropic-ai/claude-code",
                confirm_text=tr("Включить"),
                icon="↑",
                icon_color=(52, 211, 153),
                parent=self
            )
            if dlg.exec() != QDialog.Accepted:
                self.autoupdate_toggle.setChecked(False)
                self.log(tr("Поддержка новых версий: включение отменено"), "info")
                return

            self.settings["auto_update_enabled"] = True
            save_settings(self.settings)
            self._remove_safe_update_pins()
            self.log(tr("Поддержка новых версий Claude Code включена"), "success")
        else:
            dlg = ConfirmActionDialog(
                title=tr("Переход в безопасный режим"),
                message=tr(
                    "Приложение перестанет обновлять Claude Code и зафиксируется "
                    f"на проверенной версии v{REQUIRED_CLAUDE_VERSION} — именно на ней "
                    "гарантированно работают FreeModel / Omniroute / любые сторонние "
                    "Base URL и API-ключи.\n\n"
                    "Встроенный автообновлятор Claude Code будет выключен "
                    "(DISABLE_UPDATES=1, autoUpdates=false), чтобы CLI сам не "
                    "подтянул новую версию за спиной. Если сейчас установлена "
                    "версия новее — запуск будет заблокирован, пока не откатишь "
                    "её кнопкой «Откатить Claude Code».\n\n"
                    "Включай этот режим только если сам этого хочешь или если "
                    "на новой версии реально появились проблемы."
                ),
                detail="",
                confirm_text=tr("Перейти в безопасный режим"),
                icon="🛡",
                icon_color=(235, 150, 90),
                parent=self
            )
            if dlg.exec() != QDialog.Accepted:
                self.autoupdate_toggle.setChecked(True)
                self.log(tr("Безопасный режим: переход отменён"), "info")
                return

            self.settings["auto_update_enabled"] = False
            save_settings(self.settings)
            self._ensure_disable_updates_in_settings()
            self._ensure_auto_updates_false_in_claude_json()
            self.log(tr("Поддержка новых версий Claude Code выключена — вернулись к безопасному режиму"), "info")

        # Свежий фон-запрос версии: в auto-update режиме тянем актуальный
        # latest из npm registry, в safe — снапаем на REQUIRED_CLAUDE_VERSION.
        # Без этого лейбл «Доступно обновление / Установлена» показывал бы
        # старое значение до перезапуска приложения.
        self._claude_latest_version = ""
        try:
            threading.Thread(target=self._check_claude_version, daemon=True).start()
        except Exception:
            pass

        try:
            self._update_install_button_state()
        except Exception:
            pass

    def _remove_safe_update_pins(self):
        """Снимает DISABLE_UPDATES/autoUpdates=false, поставленные safe-режимом,
        чтобы встроенный автообновлятор Claude Code реально заработал."""
        try:
            with self._claude_files_lock:
                settings_path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
                if os.path.exists(settings_path):
                    try:
                        with open(settings_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, dict) and isinstance(data.get("env"), dict):
                            if "DISABLE_UPDATES" in data["env"]:
                                del data["env"]["DISABLE_UPDATES"]
                                if not data["env"]:
                                    del data["env"]
                                with open(settings_path, 'w', encoding='utf-8') as f:
                                    json.dump(data, f, indent=2, ensure_ascii=False)
                    except (json.JSONDecodeError, OSError):
                        pass

                json_path = self._claude_json_path()
                if os.path.exists(json_path):
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, dict) and data.get("autoUpdates") is False:
                            del data["autoUpdates"]
                            with open(json_path, 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=2, ensure_ascii=False)
                    except (json.JSONDecodeError, OSError):
                        pass
        except Exception as e:
            try:
                self.log(f"Не удалось снять safe-pin автообновления: {e}", "warning")
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
                    stub = {"installMethod": "global"}
                    if not self.settings.get("auto_update_enabled", False):
                        stub["autoUpdates"] = False
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

                        if self.settings.get("auto_update_enabled", False):
                            fresh_settings = {}
                        else:
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
        if self.settings.get("auto_update_enabled", False):
            self._install_claude_code_official()
            return

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
                tr("проверенная стабильная версия, на которой приложение работает всегда. "
                   "npm переустановит пакет на нужную версию. Настройки в %USERPROFILE%\\.claude не пострадают.")
            )
            confirm_text = tr("Откатить")
            icon = "↓"
            icon_color = (235, 150, 90)
        elif is_update:
            title = tr("Установка Claude Code") + f" v{required}"
            message = (
                tr("У тебя установлена") + f" v{local}. " +
                tr("Будет установлена фиксированная") + f" v{required} — " +
                tr("проверенная стабильная версия, на которой приложение работает всегда.")
            )
            confirm_text = tr("Установить")
            icon = "↑"
            icon_color = (245, 180, 60)
        else:
            title = tr("Установка Claude Code") + f" v{required}"
            message = (
                tr("Будет установлена фиксированная версия") + f" v{required} — " +
                tr("проверенная стабильная версия, на которой приложение работает всегда.\n\n"
                   "Откроется окно PowerShell, где пойдёт установка.")
            )
            confirm_text = tr("Установить")
            icon = "↓"
            icon_color = (52, 211, 153)

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

    def _install_claude_code_official(self):
        """Ставит/обновляет Claude Code через npm-пакет @anthropic-ai/claude-code
        (последняя официальная версия). Используется в режиме поддержки новых
        версий — без пина на REQUIRED_CLAUDE_VERSION."""
        installed = self._is_claude_installed()
        local = getattr(self, "_claude_local_version", "")

        # Получаем последнюю доступную версию из npm registry
        latest_available = check_claude_code_latest_version() or tr("последняя")

        message = tr(
            "Скачает и поставит последнюю версию Claude Code через npm "
            "(@anthropic-ai/claude-code).\n\n"
            "Настройки в %USERPROFILE%\\.claude не пострадают.\n\n"
            "Откроется окно PowerShell, где пойдёт установка."
        )
        dlg = ConfirmActionDialog(
            title=tr("Обновление Claude Code") if installed else tr("Установка Claude Code"),
            message=message,
            detail="npm install -g @anthropic-ai/claude-code",
            confirm_text=tr("Обновить") if installed else tr("Установить"),
            icon="↑",
            icon_color=(52, 211, 153),
            parent=self
        )
        if dlg.exec() != QDialog.Accepted:
            self.log("Операция отменена", "info")
            return

        action_word = "обновление" if installed else "установку"
        self.log(f"Запускаю {action_word} Claude Code через npm (@anthropic-ai/claude-code)...", "info")

        progress_dlg = ClaudeInstallProgressDialog(
            is_update=installed,
            old_version=local,
            new_version=latest_available,
            parent=self,
        )
        self._claude_install_dlg = progress_dlg

        try:
            popen = subprocess.Popen([
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                # 1) Прибить все запущенные claude.exe — иначе файл залочен и npm падает
                "Write-Host 'Останавливаю запущенные процессы claude...' -ForegroundColor Cyan; "
                "Get-Process claude -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; "
                "Start-Sleep -Milliseconds 600; "
                # 2) Установка/обновление последней версии через npm
                "Write-Host 'Установка/обновление Claude Code через npm...' -ForegroundColor Cyan; "
                "npm install -g @anthropic-ai/claude-code@latest; "
                "Write-Host '`nГотово. Проверь команду: claude --version' -ForegroundColor Green; "
                "Write-Host '`nНажмите любую клавишу, чтобы закрыть PowerShell...' -ForegroundColor Cyan; "
                "$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')"
            ])
        except Exception as e:
            self.log(f"Не удалось запустить установку: {e}", "error")
            progress_dlg.mark_failed(f"Не удалось запустить PowerShell:\n{e}")
            progress_dlg.exec()
            return

        self._claude_install_ctx = {
            "is_update": installed,
            "old_local": local,
            "progress_dlg": progress_dlg,
            "popen": popen,
        }

        try:
            self.claude_install_finished.disconnect(self._on_claude_install_done_safe)
        except Exception:
            pass
        self.claude_install_finished.connect(
            self._on_claude_install_done_safe, Qt.QueuedConnection
        )

        def _wait_and_emit():
            try:
                popen.wait()
            except Exception:
                pass
            try:
                rc = popen.returncode
            except Exception:
                rc = None
            new_local = ""
            try:
                time.sleep(0.5)
                new_local = self._get_installed_claude_version()
            except Exception:
                new_local = ""
            try:
                installed_now = self._is_claude_installed()
            except Exception:
                installed_now = False
            ctx = {
                "is_update": installed,
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
            tr("а приложение сейчас в безопасном режиме и работает только с") + f" v{required}.\n\n"
            f"v{required} — " +
            tr("проверенная стабильная версия, на которой приложение работает всегда.\n\n"
               "Нажми «Откатить» — установщик поставит проверенную версию, и запуск снова заработает.\n\n"
               "Если откатывать версию не хочется — включи «Авто-обновление» на панели над кнопками. "
               "В этом режиме приложение перестаёт следить за версией и запускает любую установленную.")
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

    def _find_claude_bin_dir(self):
        """Возвращает первую папку из _detect_claude_install_dirs, где реально
        лежит claude.exe. Пустая строка, если ни в одной."""
        for d in self._detect_claude_install_dirs():
            for name in ("claude.exe", "claude.cmd", "claude.bat", "claude"):
                if os.path.isfile(os.path.join(d, name)):
                    return d
        return ""

    def _get_user_path_entries(self):
        """Читает пользовательскую переменную PATH из реестра и возвращает
        список её элементов (пустые отфильтрованы)."""
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ) as key:
                try:
                    val, _ = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    return []
        except Exception:
            return []
        return [p.strip() for p in str(val).split(";") if p.strip()]

    def _on_add_to_path_clicked(self):
        """Добавляет папку с claude в пользовательскую PATH-переменную,
        если её там ещё нет. Показывает результат модалкой."""
        target = self._find_claude_bin_dir()
        if not target:
            dlg = ConfirmActionDialog(
                title=tr("Claude Code не найден"),
                message=tr(
                    "Не нашёл папку с установленной Claude Code. "
                    "Сначала установи Claude Code кнопкой выше, потом жми «Добавить в PATH»."
                ),
                detail="",
                confirm_text=tr("Понятно"),
                icon="!",
                icon_color=(235, 150, 90),
                parent=self
            )
            dlg.cancel_btn.hide()
            dlg.exec()
            return

        entries = self._get_user_path_entries()
        norm_target = os.path.normcase(os.path.normpath(target))
        already_present = any(
            os.path.normcase(os.path.normpath(p)) == norm_target for p in entries
        )
        if already_present:
            dlg = ConfirmActionDialog(
                title=tr("Уже в PATH"),
                message=tr("Папка с Claude Code уже прописана в пользовательской PATH."),
                detail=target,
                confirm_text=tr("Ок"),
                icon="✓",
                icon_color=(52, 211, 153),
                parent=self
            )
            dlg.cancel_btn.hide()
            dlg.exec()
            return

        dlg = ConfirmActionDialog(
            title=tr("Добавить в PATH"),
            message=tr(
                "Добавит папку с Claude Code в пользовательскую PATH, чтобы "
                "команду «claude» можно было запускать из любой консоли. "
                "После этого перезапусти терминал."
            ),
            detail=target,
            confirm_text=tr("Добавить"),
            icon="↑",
            icon_color=(120, 180, 230),
            parent=self
        )
        if dlg.exec() != QDialog.Accepted:
            return

        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
                try:
                    val, val_type = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    val, val_type = "", winreg.REG_EXPAND_SZ
                current = str(val or "")
                new_val = (current + (";" if current and not current.endswith(";") else "") + target)
                winreg.SetValueEx(key, "Path", 0, val_type or winreg.REG_EXPAND_SZ, new_val)

            # Broadcast WM_SETTINGCHANGE — чтобы уже запущенные оболочки заметили изменение.
            try:
                import ctypes
                HWND_BROADCAST = 0xFFFF
                WM_SETTINGCHANGE = 0x1A
                SMTO_ABORTIFHUNG = 0x0002
                ctypes.windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST, WM_SETTINGCHANGE, 0,
                    ctypes.c_wchar_p("Environment"),
                    SMTO_ABORTIFHUNG, 5000, None
                )
            except Exception:
                pass

            self.log(f"Добавил в PATH: {target}", "success")
            done = ConfirmActionDialog(
                title=tr("Добавлено в PATH"),
                message=tr(
                    "Папка с Claude Code добавлена в пользовательскую PATH. "
                    "Открой новую консоль и проверь: claude --version."
                ),
                detail=target,
                confirm_text=tr("Ок"),
                icon="✓",
                icon_color=(52, 211, 153),
                parent=self
            )
            done.cancel_btn.hide()
            done.exec()
        except Exception as e:
            self.log(f"Не удалось добавить в PATH: {e}", "error")
            err = ConfirmActionDialog(
                title=tr("Не удалось добавить в PATH"),
                message=tr("Что-то пошло не так при записи в реестр:") + f"\n{e}",
                detail=target,
                confirm_text=tr("Ок"),
                icon="!",
                icon_color=(235, 90, 90),
                parent=self
            )
            err.cancel_btn.hide()
            err.exec()

    def _update_install_button_state(self):
        """Обновляет кнопки и индикатор по состоянию (нет / нужная версия / другая версия)"""
        installed = self._is_claude_installed()
        local = getattr(self, "_claude_local_version", "")

        auto_update = self.settings.get("auto_update_enabled", False)

        # «Добавить в PATH» полезно только в auto-update режиме, где install.ps1
        # кладёт бинарь в ~/.local/bin (эта папка обычно не в PATH). В безопасном
        # режиме ставим через npm — папка %APPDATA%\npm уже в PATH.
        if hasattr(self, "btn_add_to_path"):
            self.btn_add_to_path.setEnabled(bool(auto_update))

        if auto_update:
            latest = getattr(self, "_claude_latest_version", "") or ""
            update_available = False
            if installed and local and latest:
                try:
                    update_available = compare_versions(latest, local) > 0
                except Exception:
                    update_available = False

            if hasattr(self, "btn_install_claude"):
                if not installed:
                    self.btn_install_claude.setEnabled(True)
                    self.btn_install_claude.setText(tr("Установить Claude Code"))
                    self.btn_install_claude.set_hover_color(52, 211, 153)
                elif update_available:
                    self.btn_install_claude.setEnabled(True)
                    self.btn_install_claude.setText(tr("Обновить Claude Code"))
                    self.btn_install_claude.set_hover_color(245, 180, 60)
                else:
                    self.btn_install_claude.setEnabled(False)
                    self.btn_install_claude.setText(tr("Установить Claude Code"))

            if hasattr(self, "btn_uninstall_claude"):
                self.btn_uninstall_claude.setEnabled(installed)

            if hasattr(self, "claude_install_indicator"):
                if not installed:
                    self.claude_install_indicator.set_state("off")
                elif update_available:
                    self.claude_install_indicator.set_state("warn")
                else:
                    self.claude_install_indicator.set_state("on")

            if hasattr(self, "claude_install_status_label"):
                if not installed:
                    text = tr("Не установлен")
                    color = "rgb(255, 50, 50)"
                elif update_available:
                    text = tr("Доступно обновление") + (f" v{latest}" if latest else "")
                    color = "rgb(245, 180, 60)"
                else:
                    text = tr("Установлена") + (f" v{local}" if local else "")
                    color = "rgb(52, 211, 153)"  # новый зелёный
                self.claude_install_status_label.setText(text)
                self.claude_install_status_label.setStyleSheet(
                    f"color: {color}; background: transparent; border: none;"
                )
            return

        # ── Safe mode: пин на REQUIRED_CLAUDE_VERSION ──
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
                self.btn_install_claude.setText(tr("Установить Claude Code"))
                self.btn_install_claude.set_hover_color(52, 211, 153)
            elif version_unknown:
                self.btn_install_claude.setEnabled(False)
                self.btn_install_claude.setText(tr("Установить Claude Code"))
            elif version_match:
                self.btn_install_claude.setEnabled(False)
                self.btn_install_claude.setText(tr("Установить Claude Code"))
            elif version_higher:
                self.btn_install_claude.setEnabled(True)
                self.btn_install_claude.setText(tr("Откатить Claude Code"))
                self.btn_install_claude.set_hover_color(235, 150, 90)
            else:
                self.btn_install_claude.setEnabled(True)
                self.btn_install_claude.setText(tr("Обновить Claude Code"))
                self.btn_install_claude.set_hover_color(245, 180, 60)

        if hasattr(self, "btn_uninstall_claude"):
            self.btn_uninstall_claude.setEnabled(installed)

        if hasattr(self, "claude_install_indicator"):
            if not installed:
                self.claude_install_indicator.set_state("off")
            elif version_unknown:
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
                self.claude_install_status_label.setText(tr("Установлена") + f" v{local}")
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(52, 211, 153); background: transparent; border: none;"
                )
            elif version_higher:
                self.claude_install_status_label.setText(
                    tr("Установлена") + f" v{local} — " + tr("запуск заблокирован")
                )
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(235, 150, 90); background: transparent; border: none;"
                )
            else:
                self.claude_install_status_label.setText(
                    tr("Доступно обновление") + f" v{required}"
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
            if self.settings.get("auto_update_enabled", False):
                latest = check_claude_code_latest_version() or local
            else:
                latest = REQUIRED_CLAUDE_VERSION
            try:
                self.claude_version_checked.emit(local, latest, "")
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
        if self.settings.get("auto_update_enabled", False):
            return
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
            title=tr("Устаревшая версия Claude Code"),
            message=(
                tr("У тебя установлена Claude Code") + f" v{local} — " +
                tr("это устаревшая версия.") + "\n\n" +
                tr("Проверенная и стабильная версия, на которой это приложение работает гарантированно, — ") +
                f"v{required}. " +
                tr("Рекомендуем обновить до") + f" v{required} — " +
                tr("установщик поставит нужную версию, настройки в %USERPROFILE%\\.claude не пострадают.")
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

        # Красное окно прогресса — тот же класс, что для install/update.
        progress_dlg = ClaudeInstallProgressDialog(
            is_uninstall=True,
            old_version=local,
            parent=self,
        )

        try:
            popen = subprocess.Popen([
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                # 1) Прибить все запущенные claude.exe / node, держащие бинарь — иначе npm падает с EBUSY
                "Write-Host 'Останавливаю запущенные процессы claude...' -ForegroundColor Cyan; "
                "Get-Process claude -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; "
                "Start-Sleep -Milliseconds 600; "
                # 2) Основная попытка удаления npm-версии
                "Write-Host 'Удаление Claude Code (npm)...' -ForegroundColor Cyan;"
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
            progress_dlg.mark_failed(f"Не удалось запустить PowerShell:\n{e}")
            progress_dlg.exec()
            return

        # Контекст для слота (по образцу установки)
        self._claude_uninstall_ctx = {
            "old_local": local,
            "progress_dlg": progress_dlg,
            "popen": popen,
        }

        # Подключаем сигнал ОДИН раз через QueuedConnection — гарантированно
        # доставит вызов в GUI-нить, в отличие от QTimer.singleShot из потока.
        try:
            self.claude_uninstall_finished.disconnect(self._on_claude_uninstall_done_safe)
        except Exception:
            pass
        self.claude_uninstall_finished.connect(
            self._on_claude_uninstall_done_safe, Qt.QueuedConnection
        )

        # Фоновая нить: ждёт PowerShell, читает состояние — не трогает Qt.
        def _wait_and_emit():
            try:
                popen.wait()
            except Exception:
                pass
            try:
                rc = popen.returncode
            except Exception:
                rc = None
            try:
                # Дать инсталлятору отпустить файлы
                time.sleep(0.5)
                still_installed = self._is_claude_installed()
            except Exception:
                still_installed = True
            try:
                new_local = self._get_installed_claude_version()
            except Exception:
                new_local = ""
            ctx = {
                "old_local": local,
                "new_local": new_local,
                "still_installed": still_installed,
                "returncode": rc,
            }
            try:
                self.claude_uninstall_finished.emit(ctx)
            except Exception:
                pass

        threading.Thread(target=_wait_and_emit, daemon=True).start()

        # Показываем окно прогресса (модально)
        progress_dlg.exec()

    def _on_claude_uninstall_done_safe(self, ctx):
        """Вызывается на main thread через сигнал. Все subprocess-вызовы уже сделаны в фоне."""
        if not isinstance(ctx, dict):
            return

        new_local = ctx.get("new_local", "") or ""
        still_installed = bool(ctx.get("still_installed", True))

        progress_dlg = None
        try:
            saved_ctx = getattr(self, "_claude_uninstall_ctx", None) or {}
            progress_dlg = saved_ctx.get("progress_dlg")
        except Exception:
            progress_dlg = None

        dlg_alive = False
        if progress_dlg is not None:
            try:
                from shiboken6 import isValid
                dlg_alive = isValid(progress_dlg)
            except Exception:
                dlg_alive = True

        self._claude_local_version = new_local

        if dlg_alive:
            try:
                if not still_installed:
                    progress_dlg.mark_finished()
                else:
                    progress_dlg.mark_cancelled()
            except Exception:
                pass

        try:
            self.claude_version_checked.emit(new_local, REQUIRED_CLAUDE_VERSION, "")
        except Exception:
            pass
        try:
            self._update_install_button_state()
        except Exception:
            pass

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
