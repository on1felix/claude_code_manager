"""
=====================================================
 Claude Code Manager — PySide6 Edition
 Управление Omniroute и Claude Code
=====================================================
"""
import sys, subprocess, os, threading, time, json, socket, math
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QFrame,
                               QComboBox, QLineEdit, QDialog, QScrollArea, QTextEdit, QFileDialog)
from PySide6.QtCore import Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QBrush, QTextCursor, QIcon, QPixmap
from PySide6.QtCore import QPointF, QRectF

APP_VERSION = "1.0"
OMNIROUTE_PORT = 20128
SETTINGS_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "ClaudeManager")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

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
                return json.load(f)
    except:
        pass
    return {
        "models": [
            "kr/claude-sonnet-4.5",
            "cx/gpt-5.3-codex-xhigh",
            "gh/claude-opus-4.6"
        ],
        "selected_model": "kr/claude-sonnet-4.5",
        "omniroute_path": "C:\\Users\\danii\\AppData\\Roaming\\npm\\omniroute.cmd",
        "working_directory": "",
        "auth_token": ""
    }

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

# ============================================================
# ИНДИКАТОР СТАТУСА (ТОЧКА)
# ============================================================

class StatusIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)  # Увеличил размер виджета
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
        # Чуть медленнее
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
        # Плавный переход к тусклому оранжевому
        base_r, base_g, base_b = 60, 60, 65
        hover_r, hover_g, hover_b = 60, 140, 200  # Темнее голубой

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
# ДИАЛОГ ДОБАВЛЕНИЯ МОДЕЛИ
# ============================================================

class AddModelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить модель")
        self.setModal(True)
        self.setFixedSize(400, 150)

        layout = QVBoxLayout()

        label = QLabel("Введите название модели:")
        label.setFont(QFont("Segoe UI", 10))
        label.setStyleSheet("color: rgb(200, 200, 200);")
        layout.addWidget(label)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Например: kr/claude-sonnet-4.5")
        self.input.setFont(QFont("Segoe UI", 10))
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 35, 200);
                color: rgb(200, 200, 200);
                border: 1px solid rgb(60, 60, 65);
                border-radius: 4px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.input)

        btn_layout = QHBoxLayout()

        btn_ok = StyledButton("Добавить")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        btn_cancel = StyledButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.setStyleSheet("QDialog { background-color: rgb(20, 20, 25); }")

    def get_model_name(self):
        return self.input.text().strip()

# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================

class ClaudeManager(QMainWindow):
    status_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claude Code Manager")
        self.setFixedSize(700, 750)

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

        # Подключаем сигнал к слоту
        self.status_changed.connect(self.update_status)

        # Центральный виджет
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Заголовок с иконкой
        title_layout = QHBoxLayout()
        title_layout.setAlignment(Qt.AlignCenter)
        title_layout.setSpacing(10)

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
                    icon_label.setPixmap(icon_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                break

        title_layout.addWidget(icon_label)

        # Текст заголовка
        title = QLabel("CLAUDE CODE MANAGER")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: rgb(140, 140, 145);")
        title_layout.addWidget(title)

        main_layout.addLayout(title_layout)

        # Секция Omniroute
        omniroute_frame = QFrame()
        omniroute_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 30, 35, 200);
                border: 1px solid rgb(60, 60, 65);
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

        # Кнопка запуска Omniroute
        self.btn_omniroute = StyledButton("Запустить Omniroute")
        self.btn_omniroute.clicked.connect(self.toggle_omniroute)
        omniroute_layout.addWidget(self.btn_omniroute)

        main_layout.addWidget(omniroute_frame)

        # Секция Claude Code
        claude_frame = QFrame()
        claude_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 30, 35, 200);
                border: 1px solid rgb(60, 60, 65);
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
        self.model_combo.addItems(self.settings["models"])
        self.model_combo.setCurrentText(self.settings["selected_model"])
        self.model_combo.setMaxVisibleItems(4)  # Показывать только 4 модели, остальные через скролл
        model_layout.addWidget(self.model_combo, 1)

        claude_layout.addLayout(model_layout)

        # Кнопки управления моделями
        model_btn_layout = QHBoxLayout()

        btn_add_model = StyledButton("Добавить модель")
        btn_add_model.clicked.connect(self.add_model)
        model_btn_layout.addWidget(btn_add_model)

        btn_remove_model = StyledButton("Удалить модель")
        btn_remove_model.clicked.connect(self.remove_model)
        model_btn_layout.addWidget(btn_remove_model)

        claude_layout.addLayout(model_btn_layout)

        # Токен авторизации
        token_layout = QHBoxLayout()

        token_label = QLabel("Токен:")
        token_label.setFont(QFont("Segoe UI", 10))
        token_label.setStyleSheet("color: rgb(180, 180, 180);")
        token_layout.addWidget(token_label)

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
        token_layout.addWidget(self.token_input, 1)

        self.btn_toggle_token = StyledButton("Показать")
        self.btn_toggle_token.setMaximumWidth(100)
        self.btn_toggle_token.clicked.connect(self.toggle_token_visibility)
        token_layout.addWidget(self.btn_toggle_token)

        self.btn_save_token = StyledButton("Сохранить")
        self.btn_save_token.setMaximumWidth(100)
        self.btn_save_token.clicked.connect(self.save_token)
        # Если токен уже сохранен, скрываем кнопку сохранить
        if self.settings.get("auth_token", ""):
            self.btn_save_token.hide()
        token_layout.addWidget(self.btn_save_token)

        self.btn_edit_token = StyledButton("Изменить")
        self.btn_edit_token.setMaximumWidth(100)
        self.btn_edit_token.clicked.connect(self.edit_token)
        # Если токен не сохранен, скрываем кнопку изменить
        if not self.settings.get("auth_token", ""):
            self.btn_edit_token.hide()
        token_layout.addWidget(self.btn_edit_token)

        claude_layout.addLayout(token_layout)

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
        self.btn_claude = StyledButton("Запустить Claude Code")
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
            prefix = "✓"
        elif level == "error":
            color = "#ff3232"  # Красный
            prefix = "✗"
        elif level == "warning":
            color = "#ffaa00"  # Оранжевый
            prefix = "⚠"
        else:  # info
            color = "#b4b4b4"  # Серый
            prefix = "•"

        formatted_message = f'<span style="color: #888;">[{timestamp}]</span> <span style="color: {color};">{prefix} {message}</span>'
        self.console.append(formatted_message)
        # Прокручиваем вниз
        self.console.moveCursor(QTextCursor.End)

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

        if is_running:
            self.status_label.setText("Подключен")
            self.status_label.setStyleSheet("color: rgb(0, 255, 100);")
            self.btn_omniroute.setText("Остановить Omniroute")
            self.btn_claude.setEnabled(True)
        else:
            self.status_label.setText("Не запущен")
            self.status_label.setStyleSheet("color: rgb(255, 50, 50);")
            self.btn_omniroute.setText("Запустить Omniroute")
            self.btn_claude.setEnabled(False)

    def toggle_omniroute(self):
        """Запускает или останавливает Omniroute"""
        if check_omniroute_status():
            # Остановка
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
        else:
            # Запуск
            try:
                omniroute_path = self.settings.get("omniroute_path", "omniroute.cmd")
                self.log(f"Запуск Omniroute...", "info")

                # Запускаем в отдельном окне
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

    def _wait_for_omniroute(self):
        """Ожидает запуска Omniroute"""
        for i in range(30):
            if check_omniroute_status():
                QTimer.singleShot(0, lambda: self.log("Omniroute успешно подключен", "success"))
                return
            time.sleep(0.5)
        QTimer.singleShot(0, lambda: self.log("Таймаут ожидания подключения", "warning"))

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

        self.log(f"Запуск Claude Code ({model})...", "info")

        # Устанавливаем переменные окружения и запускаем
        env = os.environ.copy()
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
                self.model_combo.addItem(model_name)
                save_settings(self.settings)
                self.log(f"Добавлена модель: {model_name}", "success")

    def remove_model(self):
        """Удаляет выбранную модель"""
        current_model = self.model_combo.currentText()
        if len(self.settings["models"]) > 1:
            self.settings["models"].remove(current_model)
            self.model_combo.removeItem(self.model_combo.currentIndex())
            save_settings(self.settings)
            self.log(f"Удалена модель: {current_model}", "success")
        else:
            self.log("Нельзя удалить последнюю модель", "warning")

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
