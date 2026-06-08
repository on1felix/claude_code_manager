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
                               QComboBox, QLineEdit, QDialog, QScrollArea, QTextEdit, QFileDialog, QStyledItemDelegate, QMessageBox, QGraphicsOpacityEffect, QProgressBar, QCheckBox)
from PySide6.QtCore import Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, QAbstractListModel, QModelIndex, Property
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QBrush, QTextCursor, QIcon, QPixmap, QLinearGradient
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtSvg import QSvgRenderer

APP_VERSION = "2.8"  # Временно для теста обновлений
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
        self._pulse_time = 0.0
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._animate_pulse)
        self._pulse_timer.start(16)  # ~60 FPS
        self.setMouseTracking(True)

    def set_active(self, active):
        self._is_active = active
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

        # Плавная пульсация через синус (от 0.5 до 1.0)
        pulse = 0.75 + 0.25 * math.sin(self._pulse_time)

        if self._is_active:
            # Зеленое свечение с плавной пульсацией
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
        self._hover_timer = QTimer()
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.start(20)
        self._is_hovered = False
        self.setMouseTracking(True)

        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 45, 200);
                color: rgb(200, 200, 200);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton:pressed {
                background-color: rgba(30, 30, 35, 200);
            }
            QPushButton:disabled {
                background-color: rgba(30, 30, 35, 150);
                color: rgb(100, 100, 100);
                border: 2px solid rgb(40, 40, 45);
            }
        """)

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
        # Плавный переход к голубому
        base_r, base_g, base_b = 60, 60, 65
        hover_r, hover_g, hover_b = 60, 140, 200  # Голубой

        r = int(base_r + (hover_r - base_r) * self._hover_progress)
        g = int(base_g + (hover_g - base_g) * self._hover_progress)
        b = int(base_b + (hover_b - base_b) * self._hover_progress)

        bg_alpha = int(200 + 20 * self._hover_progress)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(40, 40, 45, {bg_alpha});
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

        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 45, 200);
                color: rgb(200, 200, 200);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton:pressed {
                background-color: rgba(30, 30, 35, 200);
            }
            QPushButton:disabled {
                background-color: rgba(30, 30, 35, 150);
                color: rgb(100, 100, 100);
                border: 2px solid rgb(40, 40, 45);
            }
        """)

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
        # Плавный переход к зеленому
        base_r, base_g, base_b = 60, 60, 65
        hover_r, hover_g, hover_b = 50, 180, 100  # Зеленый

        r = int(base_r + (hover_r - base_r) * self._hover_progress)
        g = int(base_g + (hover_g - base_g) * self._hover_progress)
        b = int(base_b + (hover_b - base_b) * self._hover_progress)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb(40, 40, 45);
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

        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 45, 200);
                color: rgb(200, 200, 200);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton:pressed {
                background-color: rgba(30, 30, 35, 200);
            }
            QPushButton:disabled {
                background-color: rgba(30, 30, 35, 150);
                color: rgb(100, 100, 100);
                border: 2px solid rgb(40, 40, 45);
            }
        """)

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
        # Плавный переход к голубому
        base_r, base_g, base_b = 60, 60, 65
        hover_r, hover_g, hover_b = 100, 180, 255  # Голубой

        r = int(base_r + (hover_r - base_r) * self._hover_progress)
        g = int(base_g + (hover_g - base_g) * self._hover_progress)
        b = int(base_b + (hover_b - base_b) * self._hover_progress)

        bg_alpha = int(200 + 20 * self._hover_progress)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(40, 40, 45, {bg_alpha});
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

        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 45, 200);
                color: rgb(200, 200, 200);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton:pressed {
                background-color: rgba(30, 30, 35, 200);
            }
            QPushButton:disabled {
                background-color: rgba(30, 30, 35, 150);
                color: rgb(100, 100, 100);
                border: 2px solid rgb(40, 40, 45);
            }
        """)

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
        # Плавный переход к красному
        base_r, base_g, base_b = 60, 60, 65
        hover_r, hover_g, hover_b = 200, 60, 60  # Красный

        r = int(base_r + (hover_r - base_r) * self._hover_progress)
        g = int(base_g + (hover_g - base_g) * self._hover_progress)
        b = int(base_b + (hover_b - base_b) * self._hover_progress)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb(40, 40, 45);
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
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        self.setStyleSheet("""
            QComboBox {
                background-color: rgba(40, 40, 45, 200);
                color: rgb(200, 200, 200);
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
        """)

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
        # Плавный переход к тусклому оранжевому
        base_r, base_g, base_b = 60, 60, 65
        hover_r, hover_g, hover_b = 60, 140, 200  # Темнее голубой

        r = int(base_r + (hover_r - base_r) * self._hover_progress)
        g = int(base_g + (hover_g - base_g) * self._hover_progress)
        b = int(base_b + (hover_b - base_b) * self._hover_progress)

        self.setStyleSheet(f"""
            QComboBox {{
                background-color: rgba(40, 40, 45, 200);
                color: rgb(200, 200, 200);
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
# ДИАЛОГ УПРАВЛЕНИЯ BASE URL
# ============================================================

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
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(12)

        title = QLabel("Управление Base URL")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #CCCCCC; background: transparent; border: none;")
        layout.addWidget(title)

        info = QLabel("Выберите URL или добавьте свой")
        info.setFont(QFont("Segoe UI", 9))
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color: rgb(120, 120, 120); background: transparent; border: none;")
        layout.addWidget(info)

        # Combo со списком URL
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

        # OK / Отмена
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_cancel = RedButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = GreenButton("Применить")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)

        main_layout.addWidget(container)
        self.setLayout(main_layout)
        self.setFixedWidth(440)

        self._update_remove_button()
        self.url_combo.currentTextChanged.connect(lambda _: self._update_remove_button())

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
        return list(self.urls), self.url_combo.currentText()

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
        model_label.setStyleSheet("color: rgb(180, 180, 180);")
        layout.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.setCursor(Qt.PointingHandCursor)
        self.model_combo.setFont(QFont("Segoe UI", 9))
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
        models = ["Opus 4.8 (default)", "Opus 4.7", "Opus 4.6", "Sonnet 4.6"]
        self.model_combo.addItems(models)
        # Маппинг старых сохранённых значений на новые метки
        model_remap = {
            "default (claude-opus-4-8)": "Opus 4.8 (default)",
            "claude-sonnet-4-6 (/model → 2)": "Sonnet 4.6",
            "claude-sonnet-4-6": "Sonnet 4.6",
            "claude-opus-4-7": "Opus 4.7",
            "claude-opus-4-6": "Opus 4.6",
        }
        saved_model = settings.get("custom_model", "Opus 4.8 (default)")
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

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claude Code Manager")
        self.setFixedSize(700, 800)  # Увеличил высоту с 750 до 800

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

        # Индикатор обновления (абсолютная позиция в правом верхнем углу)
        self.update_indicator = UpdateIndicator(self)
        self.update_indicator.clicked.connect(self._on_update_indicator_clicked)
        self.update_indicator.move(self.width() - 45, 10)  # 10px от верха, 45px от правого края
        self.update_indicator.raise_()

        # Секция Omniroute
        omniroute_frame = QFrame()
        omniroute_frame.setStyleSheet("""
            QFrame {
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
        omniroute_label.setStyleSheet("color: rgb(200, 200, 200);")
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

        main_layout.addWidget(omniroute_frame)

        # Секция Claude Code
        claude_frame = QFrame()
        claude_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 30, 35, 200);
                border: 2px solid rgb(60, 60, 65);
                border-radius: 8px;
            }
        """)
        claude_layout = QVBoxLayout(claude_frame)

        claude_label = QLabel("Claude Code")
        claude_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        claude_label.setStyleSheet("color: rgb(200, 200, 200);")
        claude_layout.addWidget(claude_label)

        # Выбор модели
        model_layout = QHBoxLayout()
        model_label = QLabel("Модель:")
        model_label.setFont(QFont("Segoe UI", 10))
        model_label.setStyleSheet("color: rgb(180, 180, 180);")
        model_layout.addWidget(model_label)

        self.model_combo = StyledComboBox()
        self.model_list_model = ModelListModel(self.settings["models"])
        self.model_combo.setModel(self.model_list_model)
        self.model_combo.setCurrentText(self.settings["selected_model"])
        self.model_combo.setMaxVisibleItems(4)
        model_layout.addWidget(self.model_combo, 1)

        claude_layout.addLayout(model_layout)

        # Кнопки управления моделями
        model_btn_layout = QHBoxLayout()

        self.btn_add_model = GreenButton("Добавить модель")
        self.btn_add_model.clicked.connect(self.add_model)
        model_btn_layout.addWidget(self.btn_add_model)

        self.btn_remove_model = RedButton("Удалить модель")
        self.btn_remove_model.clicked.connect(self.remove_model)
        model_btn_layout.addWidget(self.btn_remove_model)

        claude_layout.addLayout(model_btn_layout)

        # Opacity effects для модели (применяем к комбо и кнопкам)
        self._model_combo_dim = QGraphicsOpacityEffect(); self._model_combo_dim.setOpacity(1.0)
        self._btn_add_dim = QGraphicsOpacityEffect(); self._btn_add_dim.setOpacity(1.0)
        self._btn_remove_dim = QGraphicsOpacityEffect(); self._btn_remove_dim.setOpacity(1.0)
        self.model_combo.setGraphicsEffect(self._model_combo_dim)
        self.btn_add_model.setGraphicsEffect(self._btn_add_dim)
        self.btn_remove_model.setGraphicsEffect(self._btn_remove_dim)

        # Токен авторизации
        self.token_layout = QHBoxLayout()

        self.token_label = QLabel("Токен:")
        self.token_label.setFont(QFont("Segoe UI", 10))
        self.token_label.setStyleSheet("color: rgb(180, 180, 180);")
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

        claude_layout.addLayout(self.token_layout)

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

        # Переключатель кастомного токена
        token_type_layout = QHBoxLayout()

        token_type_label = QLabel("Токен FreeModel")
        token_type_label.setFont(QFont("Segoe UI", 10))
        token_type_label.setStyleSheet("color: rgb(180, 180, 180);")
        token_type_layout.addWidget(token_type_label)

        self.use_custom_token_checkbox = ToggleSwitch(checked=self.settings.get("use_custom_token", False))
        self.use_custom_token_checkbox.toggled.connect(self.toggle_custom_token_fields)
        token_type_layout.addWidget(self.use_custom_token_checkbox)

        # Кнопка настройки кастомного токена
        self.btn_configure_custom = StyledButton("Настроить")
        self.btn_configure_custom.setFont(QFont("Segoe UI", 8))
        self.btn_configure_custom.setMinimumHeight(0)
        self.btn_configure_custom.setFixedHeight(28)

        def _configure_update_style():
            p = self.btn_configure_custom._hover_progress
            r = int(60 + (60 - 60) * p)
            g = int(60 + (140 - 60) * p)
            b = int(65 + (200 - 65) * p)
            bg_alpha = int(200 + 20 * p)
            self.btn_configure_custom.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(40, 40, 45, {bg_alpha});
                    color: rgb(200, 200, 200);
                    border: 2px solid rgb({r}, {g}, {b});
                    border-radius: 6px;
                    padding: 2px 10px;
                }}
                QPushButton:pressed {{ background-color: rgba(30, 30, 35, 200); }}
                QPushButton:disabled {{ background-color: rgba(30, 30, 35, 150); color: rgb(100, 100, 100); border: 2px solid rgb(40, 40, 45); }}
            """)

        self.btn_configure_custom._update_style = _configure_update_style
        _configure_update_style()  # Применяем сразу при создании
        self.btn_configure_custom.clicked.connect(self.open_custom_token_dialog)
        token_type_layout.addWidget(self.btn_configure_custom)

        # Opacity effect для кнопки настройки — не скрываем, а делаем прозрачной
        self._btn_configure_custom_dim = QGraphicsOpacityEffect()
        self._btn_configure_custom_dim.setOpacity(1.0)
        self.btn_configure_custom.setGraphicsEffect(self._btn_configure_custom_dim)

        token_type_layout.addStretch()

        claude_layout.addLayout(token_type_layout)

        # Изначально скрываем кнопку настройки если не выбрано
        self.toggle_custom_token_fields()

        # Выбор рабочей директории
        dir_layout = QHBoxLayout()

        dir_label = QLabel("Директория:")
        dir_label.setFont(QFont("Segoe UI", 10))
        dir_label.setStyleSheet("color: rgb(180, 180, 180);")
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

        # Выбор папки проекта
        project_layout = QHBoxLayout()

        project_label = QLabel("Папка проекта:")
        project_label.setFont(QFont("Segoe UI", 10))
        project_label.setStyleSheet("color: rgb(180, 180, 180);")
        project_layout.addWidget(project_label)

        self.project_input = QLineEdit()
        self.project_input.setReadOnly(True)
        self.project_input.setPlaceholderText("Не выбрана (используется директория)")
        self.project_input.setText("")  # Всегда пустое по умолчанию
        self.project_input.setFont(QFont("Segoe UI", 9))
        self.project_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 35, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 6px;
            }
        """)
        project_layout.addWidget(self.project_input, 1)

        btn_browse_project = StyledButton("Обзор")
        btn_browse_project.setMaximumWidth(80)
        btn_browse_project.clicked.connect(self.browse_project)
        project_layout.addWidget(btn_browse_project)

        btn_clear_project = StyledButton("Очистить")
        btn_clear_project.setMaximumWidth(80)
        btn_clear_project.clicked.connect(self.clear_project)
        project_layout.addWidget(btn_clear_project)

        claude_layout.addLayout(project_layout)

        # Кнопка запуска Claude Code
        self.btn_claude = GreenButton("Запустить Claude Code")
        self.btn_claude.clicked.connect(self.launch_claude)
        self.btn_claude.setEnabled(False)
        claude_layout.addWidget(self.btn_claude)

        main_layout.addWidget(claude_frame)

        # Консоль
        console_frame = QFrame()
        console_frame.setStyleSheet("""
            QFrame {
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
        console_label.setStyleSheet("color: rgb(220, 220, 220);")
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

        main_layout.addWidget(console_frame)

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

        # Первая проверка
        self.log("Приложение запущено", "info")
        self.log(f"Порт Omniroute: {OMNIROUTE_PORT}", "info")
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

    def browse_project(self):
        """Открывает диалог выбора папки проекта"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку проекта",
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if directory:
            self.project_input.setText(directory)
            self.log(f"Установлена папка проекта: {directory}", "success")

    def clear_project(self):
        """Очищает папку проекта"""
        self.project_input.setText("")
        self.log("Папка проекта очищена", "info")

    def save_token(self):
        """Сохраняет токен в настройки"""
        token = self.token_input.text().strip()
        if not token:
            self.log("Токен не может быть пустым", "warning")
            return

        self.settings["auth_token"] = token
        save_settings(self.settings)
        self.log("Токен сохранен", "success")

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
        """Разрешает редактирование токена"""
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
        self.log("Режим редактирования токена", "info")

    def toggle_token_visibility(self):
        """Переключает видимость токена"""
        if self.token_input.echoMode() == QLineEdit.Password:
            self.token_input.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_token.setText("Скрыть")
        else:
            self.token_input.setEchoMode(QLineEdit.Password)
            self.btn_toggle_token.setText("Показать")

    def toggle_custom_token_fields(self, is_custom=None):
        """Затемняет секции при включении кастомного токена"""
        if is_custom is None:
            is_custom = self.use_custom_token_checkbox.isChecked()

        self.settings["use_custom_token"] = is_custom
        save_settings(self.settings)

        dim = 0.3 if is_custom else 1.0

        # Затемняем только кнопку запуска Omniroute
        self._btn_start_omniroute_dim.setOpacity(dim)
        self.btn_start_omniroute.setEnabled(not is_custom)

        # Затемняем модель
        self._model_combo_dim.setOpacity(dim)
        self._btn_add_dim.setOpacity(dim)
        self._btn_remove_dim.setOpacity(dim)
        self.model_combo.setEnabled(not is_custom)
        self.btn_add_model.setEnabled(not is_custom)
        self.btn_remove_model.setEnabled(not is_custom)

        # Затемняем токен
        self._token_label_dim.setOpacity(dim)
        self._token_input_dim.setOpacity(dim)
        self._btn_toggle_token_dim.setOpacity(dim)
        self._btn_save_token_dim.setOpacity(dim)
        self._btn_edit_token_dim.setOpacity(dim)
        self.token_input.setEnabled(not is_custom)
        self.btn_toggle_token.setEnabled(not is_custom)
        self.btn_save_token.setEnabled(not is_custom)
        self.btn_edit_token.setEnabled(not is_custom)

        # Кнопка настройки — только opacity, без setVisible (иначе меняется размер layout)
        self._btn_configure_custom_dim.setOpacity(1.0 if is_custom else 0.0)
        self.btn_configure_custom.setEnabled(is_custom)

        if not is_custom:
            self.check_status_async()

    def open_custom_token_dialog(self):
        """Открывает диалог настройки кастомного токена"""
        dialog = CustomTokenDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            # Настройки уже сохранены в диалоге
            save_settings(self.settings)
            self.log("Кастомные настройки сохранены", "success")

            # Выводим инструкцию по активации
            self.log("─" * 50, "info")
            self.log("Для активации кастомного токена вручную:", "warning")
            self.log("(активировать нужно только один раз)", "warning")
            self.log("1. Введите команду: /logout", "warning")
            self.log("2. Введите команду:", "warning")
            api_key = self.settings.get("custom_api_key", "")
            base_url = self.settings.get("custom_base_url", "https://cc.freemodel.dev")
            self.log(f'   $env:ANTHROPIC_BASE_URL="{base_url}"; $env:ANTHROPIC_API_KEY="{api_key}"; claude', "warning")
            self.log("─" * 50, "info")

        # Обновляем статус кнопки Claude (теперь доступна без Omniroute)
        self.update_omniroute_status()

    def _write_claude_model_setting(self, model_choice):
        """Записывает выбранную модель в ~/.claude/settings.json"""
        try:
            claude_settings_path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
            claude_settings = {}
            if os.path.exists(claude_settings_path):
                with open(claude_settings_path, 'r', encoding='utf-8') as f:
                    claude_settings = json.load(f)

            model_map = {
                "Opus 4.8 (default)": None,
                "Sonnet 4.6": "claude-sonnet-4-6",
                "Opus 4.7": "claude-opus-4-7",
                "Opus 4.6": "claude-opus-4-6",
            }
            model_id = model_map.get(model_choice)
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

        # Проверяем папку проекта (из поля ввода, не из настроек)
        project_folder = self.project_input.text().strip()

        # Если папка проекта не выбрана, используем директорию
        working_dir = self.settings.get("working_directory", "")

        if not project_folder and not working_dir:
            # Если ничего не установлено - запрашиваем
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
            # Кастомные настройки
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

            # Записываем модель в ~/.claude/settings.json чтобы она сохранялась
            custom_model = self.settings.get("custom_model", "default (claude-opus-4-8)")
            self._write_claude_model_setting(custom_model)

            self.log(f"Используется кастомный токен для {custom_base_url}", "info")
        else:
            # Обычные настройки через Omniroute
            env["ANTHROPIC_BASE_URL"] = "http://localhost:20128/v1"
            env["ANTHROPIC_AUTH_TOKEN"] = self.settings.get("auth_token", "")
            env["ANTHROPIC_API_KEY"] = ""
            env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
            env["ANTHROPIC_MODEL"] = model
            env["ANTHROPIC_SMALL_FAST_MODEL"] = model

        try:
            # Если выбрана папка проекта - запускаем из директории с аргументом
            if project_folder:
                self.log(f"Папка проекта: {project_folder}", "info")
                self.log(f"Память из: {working_dir if working_dir else 'домашняя папка'}", "info")

                # Запускаем из директории (для памяти), передаем папку проекта как аргумент
                launch_dir = working_dir if working_dir else os.path.expanduser("~")
                subprocess.Popen(
                    ["powershell", "-NoExit", "-Command", f"cd '{launch_dir}'; claude '{project_folder}'"],
                    env=env
                )
            else:
                # Запускаем просто в директории
                subprocess.Popen(
                    ["powershell", "-NoExit", "-Command", f"cd '{working_dir}'; claude"],
                    env=env
                )
            self.log("Claude Code запущен", "success")
        except Exception as e:
            self.log(f"Ошибка запуска: {e}", "error")

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
