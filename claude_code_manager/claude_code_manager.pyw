"""
=====================================================
 Claude Code Manager — PySide6 Edition
 Управление Omniroute и Claude Code
=====================================================
"""
import sys, subprocess, os, threading, time, json, socket, math, ssl
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QFrame,
                               QComboBox, QLineEdit, QDialog, QScrollArea, QTextEdit, QFileDialog, QStyledItemDelegate, QMessageBox, QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QProgressBar, QCheckBox)
from PySide6.QtCore import Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, QAbstractListModel, QModelIndex, Property, QObject, QThread
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QBrush, QTextCursor, QIcon, QPixmap, QLinearGradient, QPainterPath
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtSvg import QSvgRenderer

APP_VERSION = "3.4.3"  # Для обновлений
OMNIROUTE_PORT = 20128
SETTINGS_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "ClaudeManager")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
GITHUB_API_URL = "https://api.github.com/repos/on1felix/claude_code_manager/releases/latest"

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
                    loaded["custom_base_urls"] = ["https://cc.freemodel.dev", "https://api.inferall.ai"]
                else:
                    for u in ["https://cc.freemodel.dev", "https://api.inferall.ai"]:
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
            "https://cc.freemodel.dev",
            "https://api.inferall.ai"
        ],
        "custom_model": "",
        "custom_endpoint": ""
    }

DEFAULT_BASE_URLS = ["https://cc.freemodel.dev", "https://api.inferall.ai"]

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

    def __init__(self, text, color=None, tooltip=None, is_current=False, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 10, QFont.Medium))
        self.setMinimumHeight(42)
        if tooltip:
            self.setToolTip(tooltip)

        # Цвет текста и целевой цвет рамки — под модель.
        # Если цвета нет (например, у URL) — рамка голубая по умолчанию.
        if color is not None:
            self._text_color_str = f"rgb({color.red()}, {color.green()}, {color.blue()})"
            self._hover_rgb = (color.red(), color.green(), color.blue())
        else:
            self._text_color_str = "rgb(220, 220, 220)"
            self._hover_rgb = (60, 140, 200)

        # Постоянный фон одинаков для всех карточек
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


class PickerDialog(QDialog):
    """Окно выбора со списком карточек (popup, не блокирующее)."""

    picked = Signal(str)

    def __init__(self, items, current, parent=None, item_colors=None,
                 item_tooltips=None, title="Выбор"):
        super().__init__(parent)
        # Dialog + WindowModal — блокирует родительское окно, не закрывается при клике вне
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowModality(Qt.ApplicationModal)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        self.container = QFrame()
        self.container.setObjectName("pickerContainer")
        self.container.setStyleSheet("""
            QFrame#pickerContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 18, 22, 0.95),
                    stop:1 rgba(16, 16, 20, 0.95));
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

        for item in items:
            card = PickerCard(
                item,
                color=colors.get(item),
                tooltip=tooltips.get(item),
                is_current=(item == current),
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

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_in.start()

    def _pick(self, value):
        self.picked.emit(value)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)


class PickerComboBox(StyledComboBox):
    """ComboBox, который при клике открывает PickerDialog вместо нативного списка."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pick_colors = {}
        self._pick_tooltips = {}
        self._pick_title = "Выбор"
        self._picker_dlg = None

    def set_picker(self, colors=None, tooltips=None, title=None):
        if colors is not None:
            self._pick_colors = colors
        if tooltips is not None:
            self._pick_tooltips = tooltips
        if title:
            self._pick_title = title

    def showPopup(self):
        # Если уже открыт — игнорируем повторный вызов
        if self._picker_dlg is not None:
            return
        items = [self.itemText(i) for i in range(self.count())]
        if not items:
            return
        dlg = PickerDialog(
            items,
            current=self.currentText(),
            parent=self.window(),
            item_colors=self._pick_colors,
            item_tooltips=self._pick_tooltips,
            title=self._pick_title,
        )
        dlg.picked.connect(self._on_picked)
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

        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 18, 22, 0.98),
                    stop:1 rgba(16, 16, 20, 0.98));
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
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        """Плавное закрытие при принятии"""
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(200)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.finished.connect(lambda: super(AddModelDialog, self).accept())
        fade.start()
        self._fade = fade

    def reject(self):
        """Плавное закрытие при отмене"""
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(200)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
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

        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 18, 22, 0.98),
                    stop:1 rgba(16, 16, 20, 0.98));
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
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        """Плавное закрытие при принятии"""
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(200)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.finished.connect(lambda: super(ConfirmDeleteDialog, self).accept())
        fade.start()
        self._fade = fade

    def reject(self):
        """Плавное закрытие при отмене"""
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(200)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.finished.connect(lambda: super(ConfirmDeleteDialog, self).reject())
        fade.start()
        self._fade = fade

# ============================================================
# ПРЕДУПРЕЖДЕНИЕ О МОДЕЛИ FABLE 5
# ============================================================

class Fable5WarningDialog(QDialog):
    """Предупреждение при выборе модели Fable 5."""
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
                    stop:0 rgba(22, 14, 14, 0.98),
                    stop:1 rgba(18, 12, 12, 0.98));
                border: 2px solid rgba(235, 90, 90, 0.55);
                border-radius: 18px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        # Иконка
        icon_label = QLabel("🔥")
        icon_label.setFont(QFont("Segoe UI Emoji", 34))
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Заголовок
        title_label = QLabel("Fable 5 — Модель высшего класса")
        title_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
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
        sep.setStyleSheet("color: rgba(235, 90, 90, 0.25); background: rgba(235, 90, 90, 0.25); border: none; max-height: 1px;")
        layout.addWidget(sep)

        # Описание
        desc_label = QLabel(
            "Один запрос при уровне /effort High может потребовать\n"
            "до 15% вашего дневного лимита токенов.\n\n"
            "Fable 5 на среднем уровне /effort (Medium) превосходит\n"
            "Opus 4.8 на максимальных настройках (xHigh / Max) — разрыв\n"
            "составляет около 5% в пользу Fable 5.\n\n"
            "По общей мощности Fable 5 превосходит Opus 4.8\n"
            "примерно в 2 раза — но и стоит соответственно.\n\n"
            "Используйте эту модель только тогда, когда другие\n"
            "уже не справляются — она стоит каждого токена,\n"
            "но расходует их значительно быстрее."
        )
        desc_label.setFont(QFont("Segoe UI", 10))
        desc_label.setStyleSheet("""
            QLabel {
                color: rgba(210, 200, 200, 0.9);
                background: transparent;
                border: none;
            }
        """)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Плашка с датой релиза
        date_label = QLabel("Выпущена Anthropic · 09 июня 2026")
        date_label.setFont(QFont("Segoe UI", 9))
        date_label.setStyleSheet("""
            QLabel {
                color: rgba(235, 90, 90, 0.7);
                background: rgba(235, 90, 90, 0.08);
                border: 1px solid rgba(235, 90, 90, 0.2);
                border-radius: 6px;
                padding: 5px 10px;
            }
        """)
        date_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(date_label)

        layout.addSpacing(4)

        # Кнопка OK — не на всю ширину, по центру
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_ok = GlowDialogButton("Понятно",
                                  base_rgb=(235, 90, 90),
                                  hover_rgb=(235, 120, 120))
        btn_ok.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedWidth(420)

        # Анимация появления через windowOpacity (не конфликтует с дочерними виджетами)
        self.setWindowOpacity(0.0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(260)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(160)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.finished.connect(lambda: super(Fable5WarningDialog, self).accept())
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

        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 18, 22, 0.98),
                    stop:1 rgba(16, 16, 20, 0.98));
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

        btn_no = RedButton("Отмена")
        btn_no.setMinimumHeight(40)
        btn_no.clicked.connect(self.reject)
        btn_layout.addWidget(btn_no)

        btn_yes = GreenButton(confirm_text)
        btn_yes.setMinimumHeight(40)
        btn_yes.clicked.connect(self.accept)
        btn_layout.addWidget(btn_yes)

        layout.addLayout(btn_layout)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.adjustSize()
        self.setMinimumWidth(440)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(280)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

    def accept(self):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(180)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.finished.connect(lambda: super(ConfirmActionDialog, self).accept())
        fade.start()
        self._fade = fade

    def reject(self):
        fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade.setDuration(180)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
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
    DEFAULT_URLS = ("https://cc.freemodel.dev", "https://api.inferall.ai")

    def __init__(self, urls, current, parent=None):
        super().__init__(parent)
        self.urls = list(urls)
        self.current = current
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 18, 22, 0.98),
                    stop:1 rgba(16, 16, 20, 0.98));
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
        self._fade_anim.setDuration(200)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_anim.start()

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
        return list(self.urls), self.current

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

        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 18, 22, 0.98),
                    stop:1 rgba(16, 16, 20, 0.98));
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
        self.base_urls = list(settings.get("custom_base_urls", ["https://cc.freemodel.dev", "https://api.inferall.ai"]))
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
                self.model_combo.setItemData(i, _sd_model_colors[txt], Qt.ForegroundRole)
            pass
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
        if saved_model in models:
            self.model_combo.setCurrentText(saved_model)
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

    def save_settings(self):
        """Сохраняет настройки"""
        api_key = self.key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Ошибка", "API ключ не может быть пустым")
            return

        self.settings["custom_api_key"] = api_key
        self.settings["custom_base_url"] = self.url_combo.currentText()
        self.settings["custom_base_urls"] = list(self.base_urls)
        self.settings["custom_model"] = self.model_combo.currentText()
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

        self.container = QFrame()
        self.container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 18, 22, 0.98),
                    stop:1 rgba(16, 16, 20, 0.98));
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
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)

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
        fade.setDuration(200)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
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

        container = QFrame()
        container.setObjectName("installContainer")
        r, g, b = self._accent
        container.setStyleSheet(f"""
            QFrame#installContainer {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 18, 22, 0.98),
                    stop:1 rgba(16, 16, 20, 0.98));
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
        self._fade_in.setDuration(240)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_in.start()

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
                "Если команда claude не найдена — нажмите\n"
                "«Добавить в PATH» в главном окне."
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

class PathDoneDialog(QDialog):
    """Показывает результат операции добавления в PATH."""
    def __init__(self, added, skipped, error="", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowModality(Qt.ApplicationModal)

        success = not error and (added or skipped)
        accent = (100, 200, 130) if success else (235, 90, 90)
        r, g, b = accent
        icon = "✓" if success else "✕"

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName("pathDoneContainer")
        container.setStyleSheet(f"""
            QFrame#pathDoneContainer {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 18, 22, 0.98),
                    stop:1 rgba(16, 16, 20, 0.98));
                border: 2px solid rgba({r}, {g}, {b}, 0.55);
                border-radius: 18px;
            }}
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(12)

        # Иконка
        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI", 30, QFont.Bold))
        icon_lbl.setStyleSheet(
            f"color: rgb({r}, {g}, {b}); background: transparent; border: none;"
        )
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        # Заголовок
        title_lbl = QLabel("PATH обновлён" if success else "Ошибка обновления PATH")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_lbl.setStyleSheet(
            f"color: rgb({r}, {g}, {b}); background: transparent; border: none;"
        )
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(
            f"background: rgba({r}, {g}, {b}, 0.2); border: none; max-height: 1px;"
        )
        layout.addWidget(sep)

        if error:
            err_lbl = QLabel(f"Не удалось обновить PATH:\n{error}")
            err_lbl.setFont(QFont("Segoe UI", 9))
            err_lbl.setStyleSheet(
                "color: rgba(210,200,200,0.9); background: transparent; border: none;"
            )
            err_lbl.setAlignment(Qt.AlignCenter)
            err_lbl.setWordWrap(True)
            layout.addWidget(err_lbl)
        else:
            if added:
                added_lbl = QLabel("Добавлено в PATH:")
                added_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
                added_lbl.setStyleSheet(
                    "color: rgb(100,200,130); background: transparent; border: none;"
                )
                added_lbl.setAlignment(Qt.AlignCenter)
                layout.addWidget(added_lbl)
                for p in added:
                    pl = QLabel(p)
                    pl.setFont(QFont("Consolas", 8))
                    pl.setStyleSheet("""
                        QLabel {
                            color: rgba(200,220,200,0.85);
                            background: rgba(100,200,130,0.07);
                            border: 1px solid rgba(100,200,130,0.2);
                            border-radius: 4px;
                            padding: 4px 8px;
                        }
                    """)
                    pl.setAlignment(Qt.AlignCenter)
                    pl.setWordWrap(True)
                    layout.addWidget(pl)

            if skipped:
                skip_lbl = QLabel("Уже был в PATH:")
                skip_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
                skip_lbl.setStyleSheet(
                    "color: rgba(180,180,190,0.7); background: transparent; border: none;"
                )
                skip_lbl.setAlignment(Qt.AlignCenter)
                layout.addWidget(skip_lbl)
                for p in skipped:
                    pl = QLabel(p)
                    pl.setFont(QFont("Consolas", 8))
                    pl.setStyleSheet("""
                        QLabel {
                            color: rgba(180,180,190,0.65);
                            background: rgba(120,120,130,0.07);
                            border: 1px solid rgba(120,120,130,0.2);
                            border-radius: 4px;
                            padding: 4px 8px;
                        }
                    """)
                    pl.setAlignment(Qt.AlignCenter)
                    pl.setWordWrap(True)
                    layout.addWidget(pl)

            if success and added:
                hint_lbl = QLabel(
                    "Откройте новое окно консоли или IDE,\n"
                    "чтобы изменения вступили в силу."
                )
                hint_lbl.setFont(QFont("Segoe UI", 9))
                hint_lbl.setStyleSheet(
                    "color: rgba(180,180,190,0.7); background: transparent; border: none;"
                )
                hint_lbl.setAlignment(Qt.AlignCenter)
                layout.addWidget(hint_lbl)

        layout.addSpacing(4)

        # Кнопка
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = GlowDialogButton("Понятно", base_rgb=accent,
                                  hover_rgb=tuple(min(255, c + 30) for c in accent))
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedWidth(400)

        # Тень
        shadow = QGraphicsDropShadowEffect(container)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 160))
        container.setGraphicsEffect(shadow)

        # Анимация
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(240)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade.start()

    def accept(self):
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(160)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.finished.connect(lambda: super(PathDoneDialog, self).accept())
        fade.start()
        self._fade_out = fade


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

        self.container = QFrame()
        self.container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 18, 22, 0.96),
                    stop:1 rgba(16, 16, 20, 0.96));
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
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()

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

class ClaudeManager(QMainWindow):
    status_changed = Signal(bool)
    update_available = Signal(dict)  # Новый сигнал для обновлений
    path_add_finished = Signal(list, list, str)  # added, skipped, error
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

        # Центральный виджет
        central = QWidget()
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

        main_layout.addLayout(title_layout)

        # Переключатель режимов FreeModel ↔ Omniroute (под заголовком, по центру)
        mode_row = QHBoxLayout()
        mode_row.addStretch()
        self.mode_toggle = ModeToggle(omniroute_mode=not self.settings.get("use_custom_token", False))
        self.mode_toggle.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_toggle)
        mode_row.addStretch()
        main_layout.addLayout(mode_row)

        # Ряд кнопок установки Claude Code и добавления в PATH
        install_row = QHBoxLayout()
        install_row.addStretch()

        self.btn_install_claude = StyledButton("Установить Claude Code")
        self.btn_install_claude.setFixedHeight(34)
        self.btn_install_claude.clicked.connect(self._install_claude_code)
        install_row.addWidget(self.btn_install_claude)

        self.btn_add_to_path = StyledButton("Добавить в PATH")
        self.btn_add_to_path.setFixedHeight(34)
        self.btn_add_to_path.clicked.connect(self._add_npm_to_path)
        install_row.addWidget(self.btn_add_to_path)

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
        )
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
        if saved_m in fm_models:
            self.fm_model_combo.setCurrentText(saved_m)
        # Начальный цвет текста и рамки под выбранную модель
        if saved_m in model_colors:
            self.fm_model_combo.setTextColor(model_colors[saved_m])
            self.fm_model_combo.setAccentColor(model_colors[saved_m])
        self.fm_model_combo.currentTextChanged.connect(self._fm_model_changed)
        model_row.addWidget(self.fm_model_combo, 1)
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
        footer = QLabel("© 2026 Claude Code Manager v" + APP_VERSION)
        footer.setFont(QFont("Segoe UI", 8))
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: rgb(100, 100, 100);")
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

        # Периодическая проверка (на случай если поставили вручную)
        self._install_check_timer = QTimer(self)
        self._install_check_timer.timeout.connect(self._update_install_button_state)
        self._install_check_timer.start(5000)

        # Запуск фоновой проверки версии Claude (сразу + раз в час)
        threading.Thread(target=self._check_claude_version, daemon=True).start()
        self._claude_version_timer = QTimer(self)
        self._claude_version_timer.timeout.connect(
            lambda: threading.Thread(target=self._check_claude_version, daemon=True).start()
        )
        self._claude_version_timer.start(60 * 60 * 1000)  # 1 час

        # Первая проверка
        self.log("Приложение запущено", "info")
        self.log(f"Порт Omniroute: {OMNIROUTE_PORT}", "info")
        self.log("─" * 50, "info")
        self.log("Для работы с Base URL (freemodel / inferall и др.):", "warning")
        self.log("Если впервые — запустите Claude Code и введите /logout.", "warning")
        self.log("Это нужно сделать только один раз. Даже если вы", "warning")
        self.log("поменяете API ключ — повторно вводить /logout не нужно.", "warning")
        self.log("Приложение автоматически подставит ключ и Base URL.", "warning")
        self.log("─" * 50, "info")
        self.check_status_async()

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
        if new_model:
            self.settings["custom_model"] = new_model
            save_settings(self.settings)
        if hasattr(self, "fm_model_combo"):
            if new_model == "Fable 5":
                dlg = Fable5WarningDialog(self)
                dlg.exec()
            # Обновить цвет отображаемого текста и рамки под выбранную модель
            if hasattr(self, "_fm_model_colors") and new_model in self._fm_model_colors:
                self.fm_model_combo.setTextColor(self._fm_model_colors[new_model])
                self.fm_model_combo.setAccentColor(self._fm_model_colors[new_model])

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

    def launch_claude(self):
        """Запускает Claude Code с выбранной моделью"""
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

            self.log(f"Используется кастомный токен для {custom_base_url}", "info")
        else:
            # Обычные настройки через Omniroute
            env["ANTHROPIC_BASE_URL"] = "http://localhost:20128/v1"
            env["ANTHROPIC_AUTH_TOKEN"] = self.settings.get("auth_token", "")
            env["ANTHROPIC_API_KEY"] = ""
            env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
            # Передаём ID модели напрямую (kr/claude-sonnet-4.5 и т.д.)
            env["ANTHROPIC_MODEL"] = model
            env["ANTHROPIC_SMALL_FAST_MODEL"] = model

            # Форсируем модель через --model, чтобы старые чаты не переключались
            cli_cmd = f"claude --model {model}"

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

    def _install_claude_code(self):
        """Запускает официальный скрипт установки/обновления Claude Code от Anthropic в PowerShell"""
        installed = self._is_claude_installed()
        local = getattr(self, "_claude_local_version", "")
        latest = getattr(self, "_claude_latest_version", "")
        is_update = False
        if installed and local and latest:
            try:
                is_update = compare_versions(latest, local) > 0
            except Exception:
                is_update = False

        if is_update:
            dlg = ConfirmActionDialog(
                title=f"Обновление Claude Code до v{latest}",
                message=f"Будет запущен официальный скрипт от Anthropic для обновления "
                        f"с v{local} до v{latest}. Твои настройки в %USERPROFILE%\\.claude "
                        "не пострадают.",
                detail="irm https://claude.ai/install.ps1 | iex",
                confirm_text="Обновить",
                icon="↑",
                icon_color=(245, 180, 60),  # жёлто-оранжевый
                parent=self
            )
        else:
            dlg = ConfirmActionDialog(
                title="Установка Claude Code",
                message="Будет запущен официальный скрипт установки Claude Code от Anthropic. "
                        "Откроется окно PowerShell, где пойдёт установка.",
                detail="irm https://claude.ai/install.ps1 | iex",
                confirm_text="Установить",
                icon="↓",
                icon_color=(120, 200, 130),  # зелёный
                parent=self
            )
        if dlg.exec() != QDialog.Accepted:
            self.log("Операция отменена", "info")
            return

        action_word = "обновление" if is_update else "установку"
        self.log(f"Запускаю {action_word} Claude Code в окне PowerShell...", "info")

        # Открываем модальное окно прогресса
        progress_dlg = ClaudeInstallProgressDialog(
            is_update=is_update,
            old_version=local,
            new_version=latest,
            parent=self,
        )
        self._claude_install_dlg = progress_dlg

        try:
            popen = subprocess.Popen([
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                "Write-Host 'Установка Claude Code (официальный скрипт Anthropic)...' -ForegroundColor Cyan; "
                "try { irm https://claude.ai/install.ps1 | iex } catch { Write-Host $_ -ForegroundColor Red }; "
                "Write-Host '`nГотово. Проверь команду: claude --version' -ForegroundColor Green; "
                "Write-Host 'Если команда не найдена — нажми Добавить в PATH в приложении.' -ForegroundColor Yellow; "
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
        """Обновляет кнопку и индикатор по состоянию (установлен / не установлен / есть обновление)"""
        installed = self._is_claude_installed()
        local = getattr(self, "_claude_local_version", "")
        latest = getattr(self, "_claude_latest_version", "")
        latest_date = getattr(self, "_claude_latest_date", "")

        update_available = False
        if installed and local and latest:
            try:
                update_available = compare_versions(latest, local) > 0
            except Exception:
                update_available = False

        if hasattr(self, "btn_install_claude"):
            if not installed:
                self.btn_install_claude.setEnabled(True)
                self.btn_install_claude.setText("Установить Claude Code")
                self.btn_install_claude.set_hover_color(80, 200, 110)  # зелёный
            elif update_available:
                self.btn_install_claude.setEnabled(True)
                self.btn_install_claude.setText("Обновить Claude Code")
                self.btn_install_claude.set_hover_color(245, 180, 60)  # жёлто-оранжевый
            else:
                self.btn_install_claude.setEnabled(False)
                self.btn_install_claude.setText("Claude Code установлен")

        if hasattr(self, "claude_install_indicator"):
            if not installed:
                self.claude_install_indicator.set_state("off")
            elif update_available:
                self.claude_install_indicator.set_state("warn")
            else:
                self.claude_install_indicator.set_state("on")

        if hasattr(self, "claude_install_status_label"):
            if not installed:
                self.claude_install_status_label.setText("Не установлен")
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(220, 120, 120); background: transparent; border: none;"
                )
            elif update_available:
                self.claude_install_status_label.setText(
                    f"Доступно обновление: v{local} → v{latest}"
                )
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(245, 180, 60); background: transparent; border: none;"
                )
            else:
                version_part = f" v{local}" if local else ""
                self.claude_install_status_label.setText(f"Установлен{version_part}")
                self.claude_install_status_label.setStyleSheet(
                    "color: rgb(120, 220, 140); background: transparent; border: none;"
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

    def _check_claude_version(self):
        """Фоновая проверка локальной и актуальной версии Claude Code"""
        local = self._get_installed_claude_version()
        latest = ""
        latest_date = ""
        try:
            req = Request(
                "https://registry.npmjs.org/@anthropic-ai/claude-code",
                headers={"Accept": "application/vnd.npm.install-v1+json, application/json",
                         "User-Agent": "ClaudeCodeManager"}
            )
            ctx = ssl.create_default_context()
            with urlopen(req, timeout=8, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            latest = data.get("dist-tags", {}).get("latest", "") or ""
            if latest:
                latest_date = (data.get("time", {}) or {}).get(latest, "") or ""
        except Exception:
            pass
        try:
            self.claude_version_checked.emit(local, latest, latest_date)
        except Exception:
            pass

    def _on_claude_version_checked(self, local, latest, latest_date):
        """Получили результат проверки версии из фонового потока"""
        self._claude_local_version = local
        self._claude_latest_version = latest
        self._claude_latest_date = latest_date
        self._update_install_button_state()

    def _add_npm_to_path(self):
        """Добавляет существующие папки с claude в пользовательский PATH (полностью внутри приложения)"""
        existing = self._detect_claude_install_dirs()

        if not existing:
            self.log("Не найдены папки с claude. Сначала установите Claude Code.", "warning")
            return

        # Подтверждение
        paths_str = "\n".join(existing)
        dlg = ConfirmActionDialog(
            title="Добавить в PATH",
            message="Следующие пути будут добавлены в пользовательский PATH Windows, "
                    "чтобы команда claude была доступна из любого места.",
            detail=paths_str,
            confirm_text="Добавить",
            parent=self
        )
        if dlg.exec() != QDialog.Accepted:
            self.log("Добавление в PATH отменено", "info")
            return

        # Блокируем кнопку и запускаем спиннер
        self.btn_add_to_path.setEnabled(False)
        self._path_spinner_phase = 0
        self._path_spinner_timer = QTimer(self)
        self._path_spinner_timer.timeout.connect(self._tick_path_spinner)
        self._path_spinner_timer.start(80)

        # Подключаем сигнал завершения один раз
        if not getattr(self, "_path_signal_connected", False):
            self.path_add_finished.connect(self._finish_add_to_path)
            self._path_signal_connected = True

        # Запускаем работу в фоне чтобы UI не зависал
        threading.Thread(target=self._do_add_to_path, args=(existing,), daemon=True).start()

    def _tick_path_spinner(self):
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._path_spinner_phase = (self._path_spinner_phase + 1) % len(frames)
        self.btn_add_to_path.setText(f"{frames[self._path_spinner_phase]}  Обновление PATH...")

    def _do_add_to_path(self, paths_to_add):
        """Фоновая работа: правка реестра HKCU\\Environment\\Path + broadcast WM_SETTINGCHANGE"""
        added, skipped, error = [], [], ""
        try:
            import winreg, ctypes
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                                winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
                try:
                    current, vtype = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    current, vtype = "", winreg.REG_EXPAND_SZ

                existing_norm = {p.strip().rstrip("\\").lower()
                                 for p in current.split(";") if p.strip()}
                new_value = current
                for p in paths_to_add:
                    if p.strip().rstrip("\\").lower() in existing_norm:
                        skipped.append(p)
                        continue
                    if new_value and not new_value.endswith(";"):
                        new_value += ";"
                    new_value += p
                    added.append(p)
                    existing_norm.add(p.strip().rstrip("\\").lower())

                if added:
                    winreg.SetValueEx(key, "Path", 0, vtype, new_value)

            if added:
                try:
                    HWND_BROADCAST = 0xFFFF
                    WM_SETTINGCHANGE = 0x001A
                    SMTO_ABORTIFHUNG = 0x0002
                    result = ctypes.c_ulong()
                    ctypes.windll.user32.SendMessageTimeoutW(
                        HWND_BROADCAST, WM_SETTINGCHANGE, 0,
                        ctypes.c_wchar_p("Environment"),
                        SMTO_ABORTIFHUNG, 3000, ctypes.byref(result)
                    )
                except Exception:
                    # Не критично — PATH уже записан
                    pass
        except Exception as e:
            error = str(e) or repr(e) or "unknown error"

        # Возвращаемся в UI-поток через сигнал (потокобезопасно)
        try:
            self.path_add_finished.emit(added, skipped, error)
        except Exception:
            pass

    def _finish_add_to_path(self, added, skipped, error):
        if getattr(self, "_path_spinner_timer", None):
            self._path_spinner_timer.stop()
            self._path_spinner_timer = None
        self.btn_add_to_path.setText("Добавить в PATH")
        self.btn_add_to_path.setEnabled(True)

        # Лог в консоль
        if error:
            self.log(f"Не удалось обновить PATH: {error}", "error")
        else:
            for p in added:
                self.log(f"Добавлено в PATH: {p}", "success")
            for p in skipped:
                self.log(f"Уже было в PATH: {p}", "info")
            if added:
                self.log("PATH обновлён. Перезапусти открытые терминалы, чтобы изменения подхватились.", "warning")
            else:
                self.log("Нечего добавлять — все пути уже были в PATH", "info")

        # Модальное окно результата
        dlg = PathDoneDialog(added=added, skipped=skipped, error=error, parent=self)
        dlg.exec()

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
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
