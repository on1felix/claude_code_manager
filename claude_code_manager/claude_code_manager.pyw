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
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QBrush, QTextCursor, QIcon, QPixmap, QLinearGradient, QPainterPath, QFontMetrics
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtSvg import QSvgRenderer

APP_VERSION = "5.4"  # Для обновлений
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
        "custom_endpoint": ""
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
        self._state = "off"  # "off" (red), "on" (green), "warn" (yellow)
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
        """state: 'on' (зелёный), 'off' (красный), 'warn' (жёлтый)"""
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

        # Цвет точки и свечения по состоянию
        if self._state == "on":
            glow = (0, 255, 100, int(60 * pulse))
            brightness = int(180 + 75 * pulse)
            core = (0, brightness, int(brightness * 0.4))
        elif self._state == "warn":
            # жёлто-оранжевый
            glow = (255, 170, 30, int(70 * pulse))
            brightness = int(180 + 75 * pulse)
            core = (brightness, int(brightness * 0.62), int(brightness * 0.10))
        else:
            glow = (255, 50, 50, int(50 * pulse))
            brightness = int(180 + 75 * pulse)
            core = (brightness, 50, 50)

        glow_radius = 5.0 + 2.5 * pulse
        painter.setBrush(QColor(*glow))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, glow_radius, glow_radius)

        painter.setBrush(QColor(*core))
        painter.drawEllipse(center, 4.5, 4.5)

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
            # Зеленое свечение с плавной пульсацией (уменьшил радиус)
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
        title = QLabel("Добавить модель")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #CCCCCC; background: transparent; border: none;")
        layout.addWidget(title)

        label = QLabel("Введите название модели:")
        label.setFont(QFont("Segoe UI", 11))
        label.setStyleSheet("color: rgb(180, 180, 180); background: transparent; border: none;")
        layout.addWidget(label)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Например: kr/claude-sonnet-4.5")
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

        btn_cancel = RedButton("Отмена")
        btn_cancel.setMinimumHeight(40)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = GreenButton("Добавить")
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
        top_banner = QLabel("Fable 5 временно недоступна")
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
        title_label = QLabel("Модель заблокирована\nправительством США")
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
        desc_label = QLabel(
            "По официальному заявлению правительства США, доступ\n"
            "к модели Fable 5 временно приостановлен на территории\n"
            "всех юрисдикций.\n\n"
            "Согласно решению, Fable 5 признана настолько мощной,\n"
            "что — по словам представителей правительства — способна\n"
            "взломать защищённые системы Пентагона. На этом основании\n"
            "модель отнесена к технологиям двойного назначения\n"
            "и временно изъята из публичного оборота.\n\n"
            "Доступ будет восстановлен после завершения проверки\n"
            "и установки регулирующих ограничений Anthropic."
        )
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
        source_label = QLabel("Источник: официальное заявление правительства США")
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
        btn_ok = GlowDialogButton("Понятно",
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
        top_banner = QLabel("Запуск без прав администратора")
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
        title_label = QLabel("Рекомендуется запустить\nот имени администратора")
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
        desc_label = QLabel(
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
        )
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
        hint_label = QLabel(
            "Совет:  закройте приложение и запустите от имени администратора"
        )
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
        btn_ok = GlowDialogButton("Понятно",
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
    def __init__(self, title, message, detail=None, confirm_text="Продолжить",
                 icon="⚙", icon_color=(100, 150, 255), parent=None):
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

        self.cancel_btn = RedButton("Отмена")
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

        # Рисуем темный текст только на области прогресса (clipping)
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

        title = QLabel("Управление Base URL")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #CCCCCC; background: transparent; border: none;")
        title_row.addWidget(title, 1)

        self.btn_close = _CloseButton(parent=container)
        self.btn_close.clicked.connect(self.accept)
        title_row.addWidget(self.btn_close)
        layout.addLayout(title_row)

        info = QLabel("Добавьте или удалите URL из списка")
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
        self.btn_remove_url = RedButton("Удалить выбранный URL")
        self.btn_remove_url.setMinimumHeight(32)
        self.btn_remove_url.clicked.connect(self.remove_url)
        layout.addWidget(self.btn_remove_url)

        # Разделитель — добавление нового
        add_label = QLabel("Добавить новый URL:")
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

        self.btn_add_url = GreenButton("Добавить")
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
            self.btn_remove_url.setText("Базовый URL нельзя удалить")
        else:
            self.btn_remove_url.setText("Удалить выбранный URL")

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
        title = QLabel("Настройки кастомного токена")
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

        self.btn_manage_urls = StyledButton("Управление")
        self.btn_manage_urls.setMaximumWidth(120)
        self.btn_manage_urls.setMinimumHeight(0)
        self.btn_manage_urls.setFixedHeight(36)
        self.btn_manage_urls.setFont(QFont("Segoe UI", 9))
        self.btn_manage_urls.clicked.connect(self.open_url_manager)
        url_layout.addWidget(self.btn_manage_urls)

        layout.addLayout(url_layout)

        # API ключ
        key_label = QLabel("API ключ:")
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

        self.btn_toggle_key = StyledButton("Показать")
        self.btn_toggle_key.setMaximumWidth(100)
        self.btn_toggle_key.clicked.connect(self.toggle_key_visibility)
        key_layout.addWidget(self.btn_toggle_key)

        layout.addLayout(key_layout)

        # Модель
        model_label = QLabel("Модель:")
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

        btn_cancel = RedButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = GreenButton("Сохранить")
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
            self.btn_toggle_key.setText("Скрыть")
        else:
            self.key_input.setEchoMode(QLineEdit.Password)
            self.btn_toggle_key.setText("Показать")

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
        title = QLabel("Доступно обновление!")
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

        self.cancel_btn = RedButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject_animated)

        self.update_btn = GreenButton("Обновить")
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
            self.title_lbl.setText("Claude Code обновлён ✓")
            if ver:
                self.sub_lbl.setText(f"Версия v{ver}")
            else:
                self.sub_lbl.setText("")
            self.status_lbl.setText(
                "Обновление завершено успешно.\n"
                "Перезапустите Claude Code для применения изменений."
            )
        else:
            ver = actual_version or self._new_version
            self.title_lbl.setText("Claude Code установлен ✓")
            if ver:
                self.sub_lbl.setText(f"Версия v{ver}")
            else:
                self.sub_lbl.setText("")
            self.status_lbl.setText(
                "Установка завершена успешно.\n"
                "Если команда claude не найдена — открой новое окно консоли\n"
                "(npm обычно сам прописывает её в PATH)."
            )
        self.btn_ok.show()

    def mark_cancelled(self):
        if self._finished:
            return
        self._finished = True
        self.spinner.stop()
        self.spinner.hide()
        self.title_lbl.setText(
            "Обновление отменено" if self._is_update else "Установка отменена"
        )
        self.title_lbl.setStyleSheet(
            "color: rgba(200, 180, 80, 0.9); background: transparent; border: none;"
        )
        self.sub_lbl.setText("")
        self.status_lbl.setText(
            "Окно PowerShell было закрыто до завершения.\n"
            "Можете попробовать снова в любой момент."
        )
        self.btn_ok.show()

    def mark_failed(self, message=""):
        if self._finished:
            return
        self._finished = True
        self.spinner.stop()
        self.spinner.hide()
        self.title_lbl.setText(
            "Обновление не завершено" if self._is_update else "Установка не завершена"
        )
        self.title_lbl.setStyleSheet(
            "color: rgb(235, 110, 110); background: transparent; border: none;"
        )
        self.sub_lbl.setText("")
        self.status_lbl.setText(
            message or "Окно PowerShell было закрыто до завершения операции.\n"
                      "Попробуйте ещё раз."
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

        caption = QLabel("Пример отображения в Claude Code")
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
        legend = QLabel("модель  ·  контекст  ·  session ID  ·  git-репозиторий")
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
        title_label = QLabel("Внимание")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet(
            f"color: rgb({r}, {g}, {b}); background: transparent; border: none;"
        )
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Единый текст с пометкой текущего состояния
        if has_existing:
            state_line = (
                '<span style="color:#F5C850;"><b>● Сейчас status line установлен.</b></span><br>'
                "Можно <b>переустановить</b> его (наш скрипт перезапишет твой) "
                "или <b>удалить</b> — тогда блок <code>statusLine</code> уйдёт "
                "из <code>~/.claude/settings.json</code>, а файл "
                "<code>~/.claude/statusline-command.sh</code> будет стёрт.<br><br>"
            )
        else:
            state_line = (
                '<span style="color:rgba(200,200,205,0.7);">● Сейчас status line не настроен.</span><br>'
                "Менеджер скопирует <code>statusline-command.sh</code> в "
                "<code>~/.claude/</code> и пропишет блок <code>statusLine</code> "
                "в <code>~/.claude/settings.json</code>.<br>"
                "Кнопка <b>«Удалить»</b> сейчас неактивна — удалять пока нечего.<br><br>"
            )

        message = (
            state_line +
            "Status line — это строка внизу окна Claude Code, в которой видно "
            "текущую модель, заполненность контекста, ID сессии и git-репозиторий "
            "рабочей папки. Ниже — как именно он будет выглядеть."
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
            existing_label = QLabel(f"Текущая команда:\n{existing_command}")
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

        self.cancel_btn = StyledButton("Отмена")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.remove_btn = StyledButton("Удалить")
        self.remove_btn.setMinimumHeight(40)
        self.remove_btn.set_hover_color(235, 90, 90)
        self.remove_btn.setEnabled(has_existing)
        self.remove_btn.clicked.connect(lambda: self.done(self.ACTION_REMOVE))
        btn_layout.addWidget(self.remove_btn)

        self.confirm_btn = GreenButton("Переустановить" if has_existing else "Установить")
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

        self.title_lbl = QLabel("Установка status line")
        self.title_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.title_lbl.setStyleSheet(
            f"color: rgb({r}, {g}, {b}); background: transparent; border: none;"
        )
        self.title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_lbl)

        self.progress_bar = AnimatedProgressBar("#78C882")
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Подготовка…")
        self.status_lbl.setFont(QFont("Segoe UI", 10))
        self.status_lbl.setStyleSheet(
            "color: rgba(210, 210, 215, 0.9); background: transparent; border: none;"
        )
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        self.btn_ok = GreenButton("Готово")
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
        self.title_lbl.setText("Status line установлен ✓")
        self.status_lbl.setText(
            "Скрипт скопирован в ~/.claude/statusline-command.sh,\n"
            "блок statusLine прописан в ~/.claude/settings.json.\n"
            "Запусти Claude Code — строка появится внизу окна."
        )
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
        self.title_lbl.setText("Не удалось установить")
        self.title_lbl.setStyleSheet(
            f"color: rgb({r}, {g}, {b}); background: transparent; border: none;"
        )
        self.status_lbl.setText(message or "Неизвестная ошибка")
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
        title_label = QLabel("Внимание")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet(
            f"color: rgb({r}, {g}, {b}); background: transparent; border: none;"
        )
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Текст с описанием проблемы и тем, что произойдёт
        if json_exists:
            state_line = (
                f'<span style="color:#EB5A5A;"><b>● Найден файл ~/.claude.json.</b></span><br>'
                "У многих пользователей старые/несовместимые настройки из этого файла "
                "ломают первый запуск Claude Code: <b>ошибки API</b>, "
                "<b>Claude вообще не отвечает</b>, странные сбои авторизации. "
                "Особенно если ты раньше пользовался Claude Code через другие способы.<br><br>"
            )
        else:
            state_line = (
                '<span style="color:rgba(200,200,205,0.7);">● Файл ~/.claude.json не найден.</span><br>'
                "Исправлять нечего — этот фикс нужен только когда Claude Code "
                "не отвечает или возвращает ошибки API при первом запуске "
                "именно из-за старого <code>~/.claude.json</code>.<br><br>"
            )

        message = (
            state_line +
            "<b>Что сделает кнопка «Исправить»:</b><br>"
            f"• переименует <code>{self._short(json_path)}</code> "
            f"→ <code>{self._short(backup_target)}</code><br>"
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
            "обновится с зафиксированной v" + REQUIRED_CLAUDE_VERSION +
            " до более новой версии, где FreeModel / Omniroute / прокси "
            "уже не работают."
        )

        message_label = QLabel(message)
        message_label.setFont(QFont("Segoe UI", 10))
        message_label.setStyleSheet("color: #B5B5B5; background: transparent; border: none;")
        message_label.setAlignment(Qt.AlignLeft)
        message_label.setWordWrap(True)
        message_label.setTextFormat(Qt.RichText)
        layout.addWidget(message_label)

        # Подсказка «когда нажимать»
        hint_label = QLabel(
            "Нажимай, только если у тебя реально проблемы: "
            "Claude Code не отвечает, выдаёт ошибки API, или ведёт себя странно "
            "после смены способа авторизации."
        )
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

        self.cancel_btn = StyledButton("Отмена")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.set_hover_color(235, 90, 90)  # красный hover — согласуется с акцентом окна
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.confirm_btn = GreenButton("Исправить")
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
        cl.setContentsMargins(30, 25, 30, 25)
        cl.setSpacing(15)

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

        # Кнопки
        self.cancel_btn = RedButton("Отмена")
        self.cancel_btn.clicked.connect(self._cancel_download)

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
        cl.addWidget(self.cancel_btn)
        cl.addWidget(self.success_buttons_widget)

        self.container.setLayout(cl)
        main_layout.addWidget(self.container)
        self.setLayout(main_layout)
        self.setFixedSize(380, 340)

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
            downloads = os.path.join(os.path.expanduser("~"), "Downloads")
            new_exe_path = os.path.join(downloads, f"ClaudeCodeManager_v{self.update_info['latest']}.exe")
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

            self.message_label.setText("Выберите действие:")
            self.message_label.show()

            self.cancel_btn.hide()
            self.success_buttons_widget.show()
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

    def _cancel_download(self):
        self._cancelled = True
        self.reject()

    def _open_folder(self):
        """Просто открывает папку с новой версией"""
        subprocess.Popen(f'explorer /select,"{self.downloaded_path}"')
        self.accept()

    def _delete_old_and_open(self):
        """Удаляет старую версию, закрывает приложение и открывает папку с новой"""
        current_exe = sys.executable
        is_compiled = current_exe.lower().endswith('.exe') and 'python' not in current_exe.lower()

        if is_compiled and os.path.exists(current_exe):
            # Создаем batch скрипт во временной папке
            temp_dir = os.path.join(os.getenv('TEMP'), 'claude_update')
            os.makedirs(temp_dir, exist_ok=True)
            batch_path = os.path.join(temp_dir, "update_claude_code_manager.bat")

            try:
                with open(batch_path, 'w') as f:
                    f.write('@echo off\n')
                    f.write('timeout /t 2 /nobreak >nul\n')
                    f.write(f'del /f /q "{current_exe}"\n')
                    f.write(f'start "" explorer /select,"{self.downloaded_path}"\n')
                    f.write(f'del /f /q "{batch_path}"\n')

                # Запускаем batch и закрываем приложение
                subprocess.Popen(batch_path, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                QApplication.quit()
            except Exception as e:
                self.message_label.setText(f"Ошибка: {e}")
        else:
            # Если не скомпилировано, просто открываем папку
            subprocess.Popen(f'explorer /select,"{self.downloaded_path}"')
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

        self.btn_install_claude = StyledButton(f"Установить Claude Code v{REQUIRED_CLAUDE_VERSION}")
        self.btn_install_claude.setFixedHeight(34)
        self.btn_install_claude.clicked.connect(self._install_claude_code)
        install_row.addWidget(self.btn_install_claude)

        self.btn_uninstall_claude = StyledButton("Удалить Claude Code")
        self.btn_uninstall_claude.setFixedHeight(34)
        self.btn_uninstall_claude.set_hover_color(235, 90, 90)  # красный hover
        self.btn_uninstall_claude.clicked.connect(self._uninstall_claude_code)
        install_row.addWidget(self.btn_uninstall_claude)

        self.btn_install_statusline = StyledButton("Status line")
        self.btn_install_statusline.setFixedHeight(34)
        self.btn_install_statusline.set_hover_color(120, 180, 230)  # нейтральный голубоватый hover
        self.btn_install_statusline.clicked.connect(self._on_statusline_button_clicked)
        install_row.addWidget(self.btn_install_statusline)

        # Fix Claude — переименовывает проблемный ~/.claude.json в .bak.
        # Нужен пользователям, у которых Claude Code не отвечает / выдаёт ошибки API
        # после миграции с других способов запуска.
        self.btn_fix_claude = StyledButton("Fix Claude")
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

        self.status_label = QLabel("Не запущен")
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet("color: rgb(150, 150, 150);")
        header_layout.addWidget(self.status_label)
        header_layout.addStretch()

        omniroute_layout.addLayout(header_layout)

        # Кнопки управления Omniroute
        omniroute_btn_layout = QHBoxLayout()

        self.btn_start_omniroute = GreenButton("Запустить Omniroute")
        self.btn_start_omniroute.clicked.connect(self.start_omniroute)
        self._btn_start_omniroute_dim = QGraphicsOpacityEffect()
        self._btn_start_omniroute_dim.setOpacity(1.0)
        self.btn_start_omniroute.setGraphicsEffect(self._btn_start_omniroute_dim)
        omniroute_btn_layout.addWidget(self.btn_start_omniroute)

        self.btn_stop_omniroute = RedButton("Остановить Omniroute")
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

        self.claude_install_status_label = QLabel("Не установлен")
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
        model_label = QLabel("Модель:")
        model_label.setFont(QFont("Segoe UI", 10))
        model_label.setStyleSheet(
            "color: rgb(180, 180, 180); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 6px; padding: 4px 8px;"
        )
        model_layout.addWidget(model_label)

        self.model_combo = PickerComboBox()
        self.model_list_model = ModelListModel(self.settings["models"])
        self.model_combo.setModel(self.model_list_model)
        self.model_combo.setCurrentText(self.settings["selected_model"])
        self.model_combo.setMaxVisibleItems(4)
        self.model_combo.set_picker(title="Выбор модели Omniroute")
        model_layout.addWidget(self.model_combo, 1)

        model_section_layout.addLayout(model_layout)

        # Кнопки управления моделями
        model_btn_layout = QHBoxLayout()

        self.btn_add_model = GreenButton("Добавить модель")
        self.btn_add_model.clicked.connect(self.add_model)
        model_btn_layout.addWidget(self.btn_add_model)

        self.btn_remove_model = RedButton("Удалить модель")
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

        self.token_label = QLabel("API ключ:")
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

        self.btn_toggle_token = StyledButton("Показать")
        self.btn_toggle_token.setMaximumWidth(100)
        self.btn_toggle_token.clicked.connect(self.toggle_token_visibility)
        self.token_layout.addWidget(self.btn_toggle_token)

        self.btn_save_token = StyledButton("Сохранить")
        self.btn_save_token.setMaximumWidth(100)
        self.btn_save_token.clicked.connect(self.save_token)
        # Если токен уже сохранен, скрываем кнопку сохранить
        if self.settings.get("auth_token", ""):
            self.btn_save_token.hide()
        self.token_layout.addWidget(self.btn_save_token)

        self.btn_edit_token = StyledButton("Изменить")
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
        self.fm_url_combo.set_picker(title="Выбор Base URL")
        self.fm_url_combo.currentTextChanged.connect(self._fm_url_changed)
        url_row.addWidget(self.fm_url_combo, 1)

        self.fm_btn_manage = StyledButton("Управление")
        self.fm_btn_manage.setMinimumHeight(0)
        self.fm_btn_manage.setFixedHeight(36)
        self.fm_btn_manage.setFixedWidth(130)
        self.fm_btn_manage.clicked.connect(self._fm_manage_urls)
        url_row.addWidget(self.fm_btn_manage)
        freemodel_layout.addLayout(url_row)

        # API key: label + input + show/save
        key_row = QHBoxLayout()
        key_lbl = QLabel("API ключ:")
        key_lbl.setFont(QFont("Segoe UI", 10))
        key_lbl.setStyleSheet(
            "color: rgb(180, 180, 180); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 6px; padding: 4px 8px;"
        )
        key_lbl.setFixedWidth(90)
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

        self.fm_btn_toggle_key = StyledButton("Показать")
        self.fm_btn_toggle_key.setMinimumHeight(0)
        self.fm_btn_toggle_key.setFixedHeight(36)
        self.fm_btn_toggle_key.setFixedWidth(90)
        self.fm_btn_toggle_key.clicked.connect(self._fm_toggle_key)
        key_row.addWidget(self.fm_btn_toggle_key)

        self.fm_btn_save_key = StyledButton("Сохранить")
        self.fm_btn_save_key.setMinimumHeight(0)
        self.fm_btn_save_key.setFixedHeight(36)
        self.fm_btn_save_key.setFixedWidth(110)
        self.fm_btn_save_key.clicked.connect(self._fm_save_key)
        if _has_fm_key:
            self.fm_btn_save_key.hide()
        key_row.addWidget(self.fm_btn_save_key)

        self.fm_btn_edit_key = StyledButton("Изменить")
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
        model_lbl = QLabel("Модель:")
        model_lbl.setFont(QFont("Segoe UI", 10))
        model_lbl.setStyleSheet(
            "color: rgb(180, 180, 180); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 6px; padding: 4px 8px;"
        )
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
            title="Выбор модели",
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
        self.btn_configure_custom = StyledButton("Настроить")
        self.btn_configure_custom.hide()
        self._btn_configure_custom_dim = QGraphicsOpacityEffect()
        self._btn_configure_custom_dim.setOpacity(1.0)

        claude_layout.addWidget(self.freemodel_section_widget)

        # Применяем начальное состояние видимости секций
        self.toggle_custom_token_fields()

        # Выбор рабочей директории
        dir_layout = QHBoxLayout()

        dir_label = QLabel("Директория:")
        dir_label.setFont(QFont("Segoe UI", 10))
        dir_label.setStyleSheet(
            "color: rgb(180, 180, 180); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 6px; padding: 4px 8px;"
        )
        dir_layout.addWidget(dir_label)

        self.dir_input = QLineEdit()
        self.dir_input.setReadOnly(True)
        self.dir_input.setPlaceholderText("Не выбрана (будет запрошена)")
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

        btn_browse = StyledButton("Обзор")
        btn_browse.setMaximumWidth(80)
        btn_browse.clicked.connect(self.browse_directory)
        dir_layout.addWidget(btn_browse)

        btn_clear = StyledButton("Очистить")
        btn_clear.setMaximumWidth(80)
        btn_clear.clicked.connect(self.clear_directory)
        dir_layout.addWidget(btn_clear)

        claude_layout.addLayout(dir_layout)

        # Кнопка запуска Claude Code
        self.btn_claude = GreenButton("Запустить Claude Code")
        self.btn_claude.clicked.connect(self.launch_claude)
        self.btn_claude.setEnabled(False)
        claude_layout.addWidget(self.btn_claude)

        main_layout.addWidget(claude_frame)

        # Консоль
        console_frame = QFrame()
        console_frame.setObjectName("console_frame")
        console_frame.setStyleSheet("""
            QFrame#console_frame {
                background-color: rgba(25, 25, 30, 220);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 8px;
            }
        """)
        console_layout = QVBoxLayout(console_frame)
        console_layout.setContentsMargins(12, 8, 12, 12)
        console_layout.setSpacing(6)

        console_label = QLabel("Консоль")
        console_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        console_label.setStyleSheet(
            "color: rgb(220, 220, 220); background-color: rgba(30, 30, 35, 200); "
            "border: 2px solid rgb(60, 60, 65); border-radius: 8px; padding: 4px 10px;"
        )
        console_layout.addWidget(console_label)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 10))
        self.console.setMaximumHeight(160)
        self.console.setMinimumHeight(160)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: rgba(15, 15, 20, 250);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(50, 50, 55);
                border-radius: 6px;
                padding: 10px;
                line-height: 1.4;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 0px;
            }
            QScrollBar::handle:vertical {
                background: transparent;
            }
            QScrollBar::handle:vertical:hover {
                background: transparent;
            }
        """)
        console_layout.addWidget(self.console)

        console_frame.setMaximumHeight(210)
        main_layout.addWidget(console_frame)

        main_layout.addStretch(1)

        # Футер
        footer = QLabel(
            f"© 2026 Claude Code Manager v{APP_VERSION}   ·   "
            f"by {AUTHOR_NAME}   ·   Discord: {AUTHOR_DISCORD}"
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
        self.log("Приложение запущено", "info")
        self.log(f"Порт Omniroute: {OMNIROUTE_PORT}", "info")
        self.log(f"Автор: {AUTHOR_NAME}  ·  Discord: {AUTHOR_DISCORD}", "info")
        self.log(f"GitHub: {AUTHOR_GITHUB}", "info")
        self.log("─" * 50, "info")
        self.log("Для работы с Base URL (freemodel и др.):", "warning")
        self.log("Если впервые — запустите Claude Code и введите /logout.", "warning")
        self.log("Это нужно сделать только один раз. Даже если вы", "warning")
        self.log("поменяете API ключ — повторно вводить /logout не нужно.", "warning")
        self.log("Приложение автоматически подставит ключ и Base URL.", "warning")
        self.log("─" * 50, "info")
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

    def log(self, message, level="info"):
        """Добавляет сообщение в консоль с цветовым форматированием"""
        timestamp = time.strftime("%H:%M:%S")

        # Определяем цвет в зависимости от уровня
        if level == "success":
            color = "#00ff64"  # Зеленый
            prefix = "●"  # Цветная точка
        elif level == "error":
            color = "#ff3232"  # Красный
            prefix = "●"  # Цветная точка
        elif level == "warning":
            color = "#ffaa00"  # Оранжевый
            prefix = "●"  # Цветная точка
        else:  # info
            color = "#b4b4b4"  # Серый
            prefix = "●"  # Цветная точка

        formatted_message = f'<span style="color: #888;">[{timestamp}]</span> <span style="color: {color};">{prefix} {message}</span>'
        self.console.append(formatted_message)
        # Прокручиваем вниз
        self.console.moveCursor(QTextCursor.End)

    def _animate_shimmer(self):
        """Анимирует шиммер слева направо"""
        # Двигаем волну слева направо
        self._shimmer_offset += 0.015  # Средняя скорость

        # Когда волна прошла весь текст, ждем 2 секунды и начинаем снова
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
            self.status_label.setText("Подключен")
            self.status_label.setStyleSheet("color: rgb(0, 255, 100);")
            self.btn_start_omniroute.setEnabled(False)
            self.btn_stop_omniroute.setEnabled(True)
            self.btn_claude.setEnabled(True)
        else:
            self.status_label.setText("Не запущен")
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
            self.btn_toggle_token.setText("Скрыть")
        else:
            self.token_input.setEchoMode(QLineEdit.Password)
            self.btn_toggle_token.setText("Показать")

    def _on_mode_changed(self, is_omniroute):
        """Обработчик переключателя режимов в шапке (Omniroute ↔ FreeModel)"""
        self.toggle_custom_token_fields(is_custom=not is_omniroute)

    def _fm_url_changed(self, new_url):
        """Сохраняет выбранный Base URL"""
        if new_url:
            prev = self.settings.get("custom_base_url", "")
            self.settings["custom_base_url"] = new_url
            save_settings(self.settings)
            if prev != new_url:
                self.log(f"Base URL {new_url} сохранён", "success")

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
            self.fm_btn_toggle_key.setText("Скрыть")
        else:
            self.fm_key_input.setEchoMode(QLineEdit.Password)
            self.fm_btn_toggle_key.setText("Показать")

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
        target_h = 825 if is_custom else 905
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

        try:
            subprocess.Popen(
                ["powershell", "-NoExit", "-Command", f"cd '{working_dir}'; {cli_cmd}"],
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
            # это всё равно «уже есть» (предупреждаем о замене).
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
                    title="Переустановить status line?",
                    message=(
                        "Вы действительно хотите переустановить status line? "
                        "Ваш текущий блок statusLine в ~/.claude/settings.json "
                        "и файл ~/.claude/statusline-command.sh будут полностью "
                        "перезаписаны нашей версией. Откатить это нельзя."
                    ),
                    detail=existing_cmd or None,
                    confirm_text="Да, переустановить",
                    icon="↻",
                    icon_color=(245, 180, 60),
                ):
                    self.log("Переустановка status line отменена", "info")
                    return
            self._perform_status_line_install()

        elif result == StatusLineInstallDialog.ACTION_REMOVE:
            if not self._confirm_statusline_action(
                title="Удалить status line?",
                message=(
                    "Вы действительно хотите удалить status line? "
                    "Блок statusLine уйдёт из ~/.claude/settings.json, "
                    "а файл ~/.claude/statusline-command.sh — будет стёрт. "
                    "Остальные настройки Claude Code останутся как есть."
                ),
                detail=existing_cmd or None,
                confirm_text="Да, удалить",
                icon="×",
                icon_color=(235, 90, 90),
            ):
                self.log("Удаление status line отменено", "info")
                return
            self._perform_status_line_remove()

        else:
            self.log("Действие со status line отменено", "info")

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
        progress.title_lbl.setText("Удаление status line")
        progress.status_lbl.setText("Подготовка…")

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
            progress.title_lbl.setText("Status line удалён ✓")
            progress.status_lbl.setText(
                "Блок statusLine удалён из ~/.claude/settings.json,\n"
                "файл ~/.claude/statusline-command.sh стёрт."
            )
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
                    # если какая-то ветка кода CLI всё-таки его уважает —
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
            title = f"Откат Claude Code до v{required}"
            message = (
                f"У тебя установлена v{local}. v{required} — последняя стабильная версия, "
                f"на которой приложение проверено целиком. Более новые версии могут работать "
                f"нестабильно или вовсе не запускаться, а начиная с v2.1.181 Anthropic "
                f"заблокировала сторонние Base URL и API ключи — все запросы уходят только "
                f"в официальный сервис Anthropic, и FreeModel / Omniroute / прокси не работают.\n\n"
                "npm переустановит пакет на нужную версию. Настройки в %USERPROFILE%\\.claude "
                "не пострадают."
            )
            confirm_text = "Откатить"
            icon = "↓"
            icon_color = (235, 150, 90)
        elif is_update:
            title = f"Установка Claude Code v{required}"
            message = (
                f"У тебя установлена v{local}. Будет установлена фиксированная v{required} — "
                "последняя стабильная версия, с которой это приложение работает гарантированно. "
                "Более новые версии могут работать нестабильно или совсем не запускаться."
            )
            confirm_text = "Установить"
            icon = "↑"
            icon_color = (245, 180, 60)
        else:
            title = f"Установка Claude Code v{required}"
            message = (
                f"Будет установлена фиксированная версия v{required} через npm — "
                "последняя стабильная, на которой проверено это приложение. "
                "Более новые версии могут работать нестабильно или вовсе не запускаться, "
                "а версии с 2.1.181 Anthropic блокирует сторонние Base URL и API ключи.\n\n"
                "Откроется окно PowerShell, где пойдёт установка."
            )
            confirm_text = "Установить"
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
            f"У тебя установлена Claude Code v{current_version}, "
            f"а приложение работает только с v{required}.\n\n"
            f"v{required} — последняя стабильная версия, на которой это приложение проверено целиком. "
            "Более новые версии могут работать нестабильно или вовсе не запускаться.\n\n"
            "Кроме того, начиная с v2.1.181 Anthropic заблокировала использование сторонних "
            "Base URL и API ключей — запросы уходят только в официальный сервис Anthropic, "
            "поэтому через FreeModel / Omniroute / любые прокси такая версия CLI работать не будет.\n\n"
            f"Нажми «Откатить» — npm переустановит CLI на v{required}, и запуск снова заработает."
        )
        dlg = ConfirmActionDialog(
            title="Запуск заблокирован",
            message=message,
            detail=f"npm install -g @anthropic-ai/claude-code@{required}",
            confirm_text=f"Откатить до v{required}",
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
            message = (
                "В системе не найден npm — он входит в состав Node.js. "
                "Без npm Claude Code установить нельзя.\n\n"
                "Нажми «Установить Node.js» — откроется окно PowerShell, "
                "в котором winget автоматически скачает и поставит Node.js LTS "
                "с официального источника (OpenJS.NodeJS.LTS).\n\n"
                "После окончания установки закрой и заново открой это приложение, "
                "чтобы оно увидело npm в обновлённом PATH."
            )
            detail = "winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements"
            confirm_text = "Установить Node.js"
        else:
            message = (
                "В системе не найден npm — он входит в состав Node.js. "
                "Без npm Claude Code установить нельзя.\n\n"
                "На твоей системе нет winget, поэтому установить автоматически не получится. "
                "Нажми «Скачать Node.js» — откроется официальная страница "
                "nodejs.org/en/download. Скачай Windows Installer (.msi) LTS, "
                "поставь его и перезапусти это приложение."
            )
            detail = download_url
            confirm_text = "Скачать Node.js"

        dlg = ConfirmActionDialog(
            title="Нужен Node.js (npm)",
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
                self.btn_install_claude.setText(f"Установить Claude Code v{required}")
                self.btn_install_claude.set_hover_color(80, 200, 110)
            elif version_unknown:
                # Не знаем версию — не показываем «установлен», ждём перепроверки
                self.btn_install_claude.setEnabled(False)
                self.btn_install_claude.setText("Проверка версии…")
            elif version_match:
                self.btn_install_claude.setEnabled(False)
                self.btn_install_claude.setText(f"Claude Code v{required} установлен")
            elif version_higher:
                self.btn_install_claude.setEnabled(True)
                self.btn_install_claude.setText(f"Откатить до v{required}")
                self.btn_install_claude.set_hover_color(235, 150, 90)
            else:
                self.btn_install_claude.setEnabled(True)
                self.btn_install_claude.setText(f"Установить v{required}")
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
                self.claude_install_status_label.setText("Не установлен")
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(220, 120, 120); background: transparent; border: none;"
                )
            elif version_unknown:
                self.claude_install_status_label.setText("Проверяю версию…")
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(180, 180, 190); background: transparent; border: none;"
                )
            elif version_match:
                self.claude_install_status_label.setText(f"Установлен v{local}")
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(120, 220, 140); background: transparent; border: none;"
                )
            elif version_higher:
                self.claude_install_status_label.setText(
                    f"Установлен v{local} — нужна v{required} (запуск заблокирован)"
                )
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(235, 150, 90); background: transparent; border: none;"
                )
            else:
                self.claude_install_status_label.setText(
                    f"Установлен v{local} → нужна v{required}"
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
            title="Устаревшая версия Claude Code",
            message=(
                f"У тебя установлена Claude Code v{local} — это устаревшая версия.\n\n"
                f"Проверенная и стабильная версия, на которой это приложение работает "
                f"гарантированно, — v{required}. На более старых версиях возможны "
                "несовместимости (изменения в формате settings.json, путях, флагах CLI), "
                "из-за которых запуск через Omniroute / FreeModel может вести себя нестабильно.\n\n"
                f"Рекомендуем обновить до v{required} — npm переустановит пакет, "
                "настройки в %USERPROFILE%\\.claude не пострадают."
            ),
            detail=f"npm install -g @anthropic-ai/claude-code@{required}",
            confirm_text=f"Обновить до v{required}",
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
            title="Удалить Claude Code",
            message=(
                f"Будет удалён глобальный npm-пакет Claude Code{version_part}. "
                "Настройки в %USERPROFILE%\\.claude не пострадают — удалится только бинарь."
            ),
            detail="npm uninstall -g @anthropic-ai/claude-code",
            confirm_text="Удалить",
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
                "Write-Host 'Удаление Claude Code (npm)...' -ForegroundColor Cyan; "
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

    def _show_update_notification(self, update_info):
        """Показывает индикатор и диалог обновления (вызывается в главном потоке)"""
        try:
            # Показываем индикатор
            self.update_indicator.setVisible(True)
            self.update_indicator.show()
            self.update_indicator.raise_()

            # Автоматически показываем диалог
            dialog = UpdateAppDialog(update_info, self)
            result = dialog.exec()

            if result == QDialog.Accepted and dialog.confirmed:
                self._start_update_download()
        except Exception as e:
            pass

    def _on_update_indicator_clicked(self):
        """Обработчик клика по индикатору обновления"""
        if not self.update_info:
            return

        # Показываем диалог обновления
        dialog = UpdateAppDialog(self.update_info, self)
        if dialog.exec() == QDialog.Accepted and dialog.confirmed:
            # Пользователь подтвердил обновление
            self._start_update_download()

    def _start_update_download(self):
        """Запускает скачивание обновления"""
        if not self.update_info or not self.update_info.get('download_url'):
            return

        download_dialog = DownloadUpdateDialog(self.update_info, self)
        download_dialog.start_download()
        download_dialog.exec()

        # Если скачивание успешно, скрываем индикатор
        if download_dialog.download_success:
            self.update_indicator.setVisible(False)

# ============================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================================

def main():
    app = QApplication(sys.argv)
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
