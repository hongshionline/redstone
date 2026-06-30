# -*- coding: utf-8 -*-
"""红石联机的页面布局、背景和视觉交互。"""
from __future__ import annotations

from main import *


class JellyButton(QPushButton):
    """A layout-safe button with a small press bounce and a hover marquee border.

    Geometry is never changed, so buttons stay stable inside Qt layouts. The visual
    motion is drawn only inside the widget and does not use QGraphicsEffect.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._marquee_value = -1.0
        self._jelly_value = 0.0
        self._hovered = False
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover, True)

        self._marquee_animation = QPropertyAnimation(self, b"marqueeValue", self)
        self._marquee_animation.setStartValue(-1.0)
        self._marquee_animation.setEndValue(1.0)
        self._marquee_animation.setDuration(1250)
        self._marquee_animation.setLoopCount(-1)
        self._marquee_animation.setEasingCurve(QEasingCurve.Linear)

        self._jelly_animation = QPropertyAnimation(self, b"jellyValue", self)
        self._jelly_animation.setDuration(360)
        self._jelly_animation.setStartValue(0.0)
        self._jelly_animation.setKeyValueAt(0.30, 1.0)
        self._jelly_animation.setKeyValueAt(0.68, 0.45)
        self._jelly_animation.setEndValue(0.0)
        self._jelly_animation.setEasingCurve(QEasingCurve.OutCubic)

    def _get_marquee_value(self):
        return self._marquee_value

    def _set_marquee_value(self, value):
        self._marquee_value = float(value)
        self.update()

    marqueeValue = Property(float, _get_marquee_value, _set_marquee_value)

    def _get_jelly_value(self):
        return self._jelly_value

    def _set_jelly_value(self, value):
        self._jelly_value = max(0.0, min(1.0, float(value)))
        self.update()

    jellyValue = Property(float, _get_jelly_value, _set_jelly_value)

    def _is_dark_action(self):
        return self.objectName() in {"connBtn", "logBtn", "versionBtn"}

    def _play_jelly(self):
        self._jelly_animation.stop()
        self._jelly_animation.setStartValue(0.0)
        self._jelly_animation.start()

    def enterEvent(self, event):
        self._hovered = True
        if self.isEnabled():
            self._marquee_animation.start()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._marquee_animation.stop()
        self._marquee_value = -1.0
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self._play_jelly()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.width() < 8 or self.height() < 8:
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            rect = self.rect().adjusted(2, 2, -2, -2)
            radius = max(8.0, min(17.0, rect.height() / 2.0))
            dark = self._is_dark_action()
            outline = QColor(255, 255, 255, 170) if dark else QColor(17, 17, 17, 104)

            # Hover marquee: a gently moving dashed border, clipped to the rounded button.
            if self._hovered and self.isEnabled():
                pen = QPen(outline, 1.25)
                pen.setStyle(Qt.DashLine)
                pen.setDashPattern([2.2, 2.5])
                pen.setDashOffset(self._marquee_value * 15.0)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect, radius, radius)

                # Small travelling glint keeps the effect readable on high-DPI displays.
                x = rect.left() + (self._marquee_value + 1.0) * 0.5 * rect.width()
                glint = QColor(255, 255, 255, 42) if dark else QColor(17, 17, 17, 20)
                painter.setPen(QPen(glint, 2.0))
                start = max(rect.left() + radius, x - 18)
                end = min(rect.right() - radius, x + 18)
                if end > start:
                    painter.drawLine(int(start), int(rect.top() + 2), int(end), int(rect.top() + 2))

            # Press bounce: a soft inner ring and bubble that never affects layout geometry.
            if self._jelly_value > 0.001:
                pulse = self._jelly_value
                alpha = int((64 if dark else 42) * pulse)
                ring = QColor(255, 255, 255, alpha) if dark else QColor(17, 17, 17, alpha)
                painter.setPen(QPen(ring, 1.45 + pulse))
                painter.setBrush(Qt.NoBrush)
                inset = 2.5 + (1.0 - pulse) * 3.0
                painter.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), max(6.0, radius - inset), max(6.0, radius - inset))
                bubble_alpha = int((28 if dark else 18) * pulse)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(255, 255, 255, bubble_alpha) if dark else QColor(17, 17, 17, bubble_alpha))
                bubble = max(10.0, min(rect.width(), rect.height()) * (0.24 + 0.18 * pulse))
                center = rect.center()
                painter.drawEllipse(int(center.x() - bubble), int(center.y() - bubble), int(bubble * 2), int(bubble * 2))
        finally:
            painter.end()


class MotionCard(QFrame):
    """Subtle card entrance and hover sweep without opacity or shadow effects."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._entry_value = 0.0
        self._sweep_value = -1.0
        self._hovered = False
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover, True)

        self._entry_animation = QPropertyAnimation(self, b"entryValue", self)
        self._entry_animation.setDuration(420)
        self._entry_animation.setStartValue(0.0)
        self._entry_animation.setEndValue(1.0)
        self._entry_animation.setEasingCurve(QEasingCurve.OutCubic)

        self._sweep_animation = QPropertyAnimation(self, b"sweepValue", self)
        self._sweep_animation.setDuration(1450)
        self._sweep_animation.setStartValue(-0.15)
        self._sweep_animation.setEndValue(1.15)
        self._sweep_animation.setLoopCount(-1)
        self._sweep_animation.setEasingCurve(QEasingCurve.Linear)

    def _get_entry_value(self):
        return self._entry_value

    def _set_entry_value(self, value):
        self._entry_value = max(0.0, min(1.0, float(value)))
        self.update()

    entryValue = Property(float, _get_entry_value, _set_entry_value)

    def _get_sweep_value(self):
        return self._sweep_value

    def _set_sweep_value(self, value):
        self._sweep_value = float(value)
        self.update()

    sweepValue = Property(float, _get_sweep_value, _set_sweep_value)

    def play_entrance(self, delay=0):
        def start():
            if not self.isVisible():
                return
            self._entry_animation.stop()
            self._entry_animation.setStartValue(0.0)
            self._entry_animation.start()
        QTimer.singleShot(max(0, int(delay)), start)

    def showEvent(self, event):
        super().showEvent(event)
        self.play_entrance(35)

    def enterEvent(self, event):
        self._hovered = True
        self._sweep_animation.start()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._sweep_animation.stop()
        self._sweep_value = -0.15
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.width() < 10 or self.height() < 10:
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            rect = self.rect().adjusted(3, 3, -3, -3)
            radius = max(10.0, min(22.0, rect.height() / 2.0))

            # A short entrance line creates a clean, staged arrival on page switches.
            if self._entry_value > 0.001:
                half = rect.width() * (0.10 + 0.40 * self._entry_value)
                center_x = rect.center().x()
                left = max(rect.left() + radius, center_x - half)
                right = min(rect.right() - radius, center_x + half)
                alpha = int(58 * (1.0 - 0.35 * self._entry_value))
                painter.setPen(QPen(QColor(17, 17, 17, alpha), 1.35))
                painter.drawLine(int(left), int(rect.top() + 1), int(right), int(rect.top() + 1))

            # On hover, a small moving highlight passes along the top edge.
            if self._hovered:
                x = rect.left() + self._sweep_value * rect.width()
                left = max(rect.left() + radius, x - 26)
                right = min(rect.right() - radius, x + 26)
                if right > left:
                    painter.setPen(QPen(QColor(17, 17, 17, 82), 1.55))
                    painter.drawLine(int(left), int(rect.top() + 1), int(right), int(rect.top() + 1))
        finally:
            painter.end()


class BackgroundCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._smooth = False
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAutoFillBackground(False)

    def set_background_pixmap(self, pixmap, smooth=False):
        if pixmap is None or pixmap.isNull():
            return
        self._pixmap = pixmap
        self._smooth = bool(smooth)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor(255, 255, 255))
            if self._pixmap.isNull():
                return
            pw = self._pixmap.width()
            ph = self._pixmap.height()
            ww = max(1, self.width())
            wh = max(1, self.height())
            scale = max(ww / pw, wh / ph)
            tw = int(pw * scale)
            th = int(ph * scale)
            x = (ww - tw) // 2
            y = (wh - th) // 2
            painter.setRenderHint(QPainter.SmoothPixmapTransform, self._smooth)
            painter.drawPixmap(QRect(x, y, tw, th), self._pixmap)
        finally:
            painter.end()



class PanelMixin:

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("rootPanel")
        self._root_panel = central
        self.setCentralWidget(central)

        self._log_last_sig = None

        self._bg_label = BackgroundCanvas(central)
        self._bg_label.setObjectName("bgPhoto")
        self._bg_pixmap = QPixmap(resource_file("assets", "background.png"))
        self._bg_label.lower()
        self._render_background_pixmap()

        self._fx_blobs = []

        main_layout = QHBoxLayout(central)
        self._main_layout = main_layout
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(18)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(176)
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._sidebar = sidebar
        self._add_shadow(sidebar, blur=42, y=14, alpha=34, color=QColor(0, 0, 0, 72))

        sidebar_layout = QVBoxLayout(sidebar)
        self._sidebar_layout = sidebar_layout
        sidebar_layout.setContentsMargins(14, 18, 14, 18)
        sidebar_layout.setSpacing(10)

        self._nav_indicator = QFrame(sidebar)
        self._nav_indicator.setObjectName("navIndicator")
        self._nav_indicator.setFixedSize(0, 0)
        self._nav_indicator.hide()

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.btn_group.idClicked.connect(self._on_nav_clicked)
        self._nav_buttons = []
        icon_names = ["join", "log", "server", "version", "tutorial"]

        for i, text in enumerate(self.nav_items):
            btn = JellyButton(text)
            btn.setObjectName("navButton")
            btn.setFixedHeight(48)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            self._set_button_icon(btn, icon_names[i], 20)
            self.btn_group.addButton(btn, i)
            self._nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch(1)
        main_layout.addWidget(sidebar)

        content = QWidget()
        content.setObjectName("contentPanel")
        self._add_shadow(content, blur=54, y=18, alpha=42, color=QColor(0, 0, 0, 72))
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._content_panel = content

        content_layout = QVBoxLayout(content)
        self._content_layout = content_layout
        content_layout.setContentsMargins(28, 24, 28, 24)
        content_layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(18)
        self.title_label = QLabel()
        self.title_label.setObjectName("titleLabel")
        title_font = QFont("Microsoft YaHei", 21)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setFixedHeight(40)
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header_row.addWidget(self.title_label, 0)
        header_line = QFrame()
        header_line.setObjectName("headerLine")
        header_line.setFixedHeight(1)
        header_row.addWidget(header_line, 1, Qt.AlignVCenter)
        content_layout.addLayout(header_row, 0)

        self.stack = QStackedWidget()
        self.stack.setObjectName("mainStack")
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout.addWidget(self.stack, 1)

        for _ in range(len(self.nav_items)):
            self.stack.addWidget(QWidget())

        self._build_log_page()
        self._build_connect_page()
        self._build_server_page()
        self._build_version_page()
        self._build_tutorial_page()
        self._install_jelly_effects()

        main_layout.addWidget(content, 1)
        self._apply_responsive_layout()
        QTimer.singleShot(40, self._update_background_photo)
        QTimer.singleShot(80, self._apply_responsive_layout)


    # Video background is currently handled via static pixmap (_bg_pixmap).
    # Video decode infrastructure has been removed for simplicity.
    # To re-enable, implement _start_label_video_background with cv2.


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_background_photo()
        self._jelly_base_geometries.clear()
        self._apply_responsive_layout()
        self._move_nav_indicator(animate=False)
        if hasattr(self, "stack"):
            page = self.stack.currentWidget()
            if page is not None:
                page.updateGeometry()
                page.update()
            self.stack.updateGeometry()
            self.stack.update()
        self.update()


    def _apply_responsive_layout(self):
        if not hasattr(self, "_sidebar"):
            return
        w = max(1, self.width())
        h = max(1, self.height())
        compact = w < 1160
        very_compact = w < 1020

        outer = 14 if very_compact else 18 if compact else 20
        gap = 12 if very_compact else 15 if compact else 18
        if hasattr(self, "_main_layout"):
            self._main_layout.setContentsMargins(outer, outer, outer, outer)
            self._main_layout.setSpacing(gap)

        sidebar_w = 148 if very_compact else 162 if compact else 176
        button_h = 42 if very_compact else 45 if compact else 48
        self._sidebar.setFixedWidth(sidebar_w)
        self._sidebar.setMinimumHeight(max(310, h - outer * 2))
        self._sidebar.setMaximumHeight(16777215)
        for btn in getattr(self, "_nav_buttons", []):
            btn.setFixedHeight(button_h)
            btn.setIconSize(QSize(18 if very_compact else 20, 18 if very_compact else 20))

        if hasattr(self, "_content_layout"):
            left_right = 20 if very_compact else 24 if compact else 28
            top = 18 if very_compact else 22 if compact else 24
            bottom = 18 if very_compact else 22 if compact else 24
            self._content_layout.setContentsMargins(left_right, top, left_right, bottom)
            self._content_layout.setSpacing(10 if very_compact else 12 if compact else 14)

        if hasattr(self, "title_label"):
            font = self.title_label.font()
            font.setPointSize(17 if very_compact else 19 if compact else 21)
            font.setBold(True)
            self.title_label.setFont(font)
            self.title_label.setFixedHeight(34 if very_compact else 37 if compact else 40)
            self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.title_label.setGraphicsEffect(None)

        if hasattr(self, "_connect_info_frame"):
            self._connect_info_frame.setMinimumHeight(225 if very_compact else 240 if compact else 255)
            self._connect_info_frame.setMaximumHeight(292 if very_compact else 306 if compact else 320)
        if hasattr(self, "_connect_control_frame"):
            self._connect_control_frame.setMinimumWidth(0)
            self._connect_control_frame.setMaximumWidth(16777215)
            self._connect_control_frame.setMinimumHeight(84 if very_compact else 90 if compact else 96)
            self._connect_control_frame.setMaximumHeight(108 if very_compact else 116 if compact else 122)

        if hasattr(self, "_conn_port"):
            self._conn_port.setMinimumHeight(40 if very_compact else 43 if compact else 46)
            self._conn_port.setMaximumWidth(300 if very_compact else 330 if compact else 360)
        if hasattr(self, "_conn_btn"):
            self._conn_btn.setMinimumHeight(44 if very_compact else 47 if compact else 50)
            self._conn_btn.setMinimumWidth(160 if very_compact else 175 if compact else 190)


    def _add_shadow(self, widget, blur=30, y=8, alpha=55, color=None):
        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setOffset(0, y)
        effect.setColor(color or QColor(0, 0, 0, alpha))
        widget.setGraphicsEffect(effect)


    def _install_jelly_effects(self):
        # Layout-managed widgets must not be resized by press animations.
        # The stylesheet still provides hover and pressed feedback.
        pass


    def _asset_icon(self, name):
        path = resource_file("assets", "svg", f"{name}.svg")
        return QIcon(path) if os.path.exists(path) else QIcon()


    def _set_button_icon(self, button, name, size=18):
        icon = self._asset_icon(name)
        if not icon.isNull():
            button.setIcon(icon)
            button.setIconSize(QSize(size, size))


    def _update_background_photo(self):
        if not hasattr(self, "_bg_label"):
            return
        self._bg_label.setGeometry(0, 0, self.width(), self.height())
        self._bg_label.lower()
        self._render_background_pixmap()


    def _render_background_pixmap(self):
        if not hasattr(self, "_bg_label"):
            return
        pix = getattr(self, "_bg_pixmap", None)
        if pix is None or pix.isNull():
            return
        self._bg_label.set_background_pixmap(pix, smooth=True)


    def _layout_fx_blobs(self):
        if not hasattr(self, "_fx_blobs"):
            return
        w, h = self.width(), self.height()
        positions = [
            QRect(max(10, w - 380), -94, 340, 340),
            QRect(-98, max(130, h - 380), 270, 270),
            QRect(max(410, w - 570), max(340, h - 300), 210, 210),
            QRect(244, 46, 170, 170),
        ]
        for blob, rect in zip(self._fx_blobs, positions):
            if blob.geometry().isNull() or not self._fx_animations:
                blob.setGeometry(rect)
            blob.lower()


    def _move_nav_indicator(self, animate=True):
        if hasattr(self, "_nav_indicator"):
            self._nav_indicator.hide()
        return


    def _animate_current_page(self):
        # Avoid page opacity effects: they are expensive with scroll areas.
        # Cards animate their own thin top line using ordinary paint events instead.
        page = self.stack.currentWidget()
        if page is None:
            return
        page.setGraphicsEffect(None)
        cards = page.findChildren(MotionCard)
        for index, card in enumerate(cards):
            card.play_entrance(index * 70)
        page.updateGeometry()
        page.update()


    def _build_connect_page(self):
        page = self.stack.widget(0)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop)

        info_frame = MotionCard()
        info_frame.setObjectName("connectInfo")
        self._connect_info_frame = info_frame
        self._add_shadow(info_frame, blur=24, y=8, alpha=34, color=QColor(0, 0, 0, 54))
        info_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_frame.setMinimumHeight(250)
        info_frame.setMaximumHeight(320)

        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(24, 18, 24, 18)
        info_layout.setSpacing(10)

        section_title = QLabel("房间信息")
        section_title.setObjectName("sectionTitle")
        section_title.setFixedHeight(28)
        section_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        info_layout.addWidget(section_title)

        sep = QFrame()
        sep.setObjectName("connSep")
        sep.setFixedHeight(1)
        info_layout.addWidget(sep)

        grid_box = QVBoxLayout()
        grid_box.setContentsMargins(0, 4, 0, 0)
        grid_box.setSpacing(8)
        info_layout.addLayout(grid_box)

        def info_row(label, widget, action=None):
            row = QHBoxLayout()
            row.setSpacing(12)
            name_label = QLabel(label)
            name_label.setObjectName("fieldLabel")
            widget.setObjectName("fieldValue")
            widget.setMinimumWidth(120)
            widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(name_label, 0)
            row.addStretch(1)
            row.addWidget(widget, 0)
            if action is not None:
                row.addWidget(action, 0)
            grid_box.addLayout(row)

        self._conn_server = QLabel("--")
        self._conn_ip = QLabel("--")
        self._conn_latency = QLabel("未检测")
        self._conn_refresh_btn = JellyButton("刷新")
        self._conn_refresh_btn.setObjectName("smallActionBtn")
        self._set_button_icon(self._conn_refresh_btn, "refresh", 15)
        self._conn_addr = QLabel("--")
        self._conn_copy_btn = JellyButton("复制")
        self._conn_copy_btn.setObjectName("smallActionBtn")
        self._set_button_icon(self._conn_copy_btn, "copy", 15)
        self._conn_proto = QLabel("TCP")
        self._conn_uptime = QLabel("--")

        info_row("服务器:", self._conn_server)
        info_row("IP:", self._conn_ip)
        info_row("延迟:", self._conn_latency, self._conn_refresh_btn)
        self._conn_addr.setMinimumWidth(180)
        info_row("联机地址:", self._conn_addr, self._conn_copy_btn)
        info_row("协议:", self._conn_proto)
        info_row("已运行:", self._conn_uptime)
        info_layout.addStretch(1)

        control_frame = MotionCard()
        control_frame.setObjectName("connectControl")
        self._connect_control_frame = control_frame
        control_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        control_frame.setMinimumHeight(96)
        control_frame.setMaximumHeight(122)
        self._add_shadow(control_frame, blur=20, y=6, alpha=26, color=QColor(0, 0, 0, 42))

        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(24, 18, 24, 18)
        control_layout.setSpacing(14)

        port_name = QLabel("端口:")
        port_name.setObjectName("fieldLabel")
        control_layout.addWidget(port_name, 0, Qt.AlignVCenter)

        self._conn_port = QLineEdit()
        self._conn_port.setPlaceholderText("输入端口号")
        self._conn_port.setMinimumHeight(46)
        self._conn_port.setMaximumWidth(360)
        control_layout.addWidget(self._conn_port, 1, Qt.AlignVCenter)
        self._conn_detect_port_btn = JellyButton("识别")
        self._conn_detect_port_btn.setObjectName("smallActionBtn")
        self._conn_detect_port_btn.setMinimumHeight(42)
        self._conn_detect_port_btn.clicked.connect(lambda: self._auto_detect_minecraft_port(force=True))
        control_layout.addWidget(self._conn_detect_port_btn, 0, Qt.AlignVCenter)
        control_layout.addStretch(1)

        self._conn_btn = JellyButton("创建房间")
        self._conn_btn.setMinimumHeight(50)
        self._conn_btn.setMinimumWidth(190)
        self._conn_btn.setObjectName("connBtn")
        self._conn_btn.clicked.connect(self._toggle_room)
        control_layout.addWidget(self._conn_btn, 0, Qt.AlignVCenter)

        layout.addWidget(info_frame, 0)
        layout.addWidget(control_frame, 0)
        layout.addStretch(1)

        self._conn_refresh_btn.clicked.connect(self._ping_connect_server)
        self._conn_copy_btn.clicked.connect(self._copy_addr)

        self._conn_timer = QTimer(self)
        self._conn_timer.timeout.connect(self._update_uptime)
        self._frpc_monitor = QTimer(self)
        self._frpc_monitor.timeout.connect(self._check_frpc)
        self._quality_timer = QTimer(self)
        self._quality_timer.setInterval(10000)
        self._quality_timer.timeout.connect(self._connection_quality_tick)
        self._room_liveness_timer = QTimer(self)
        self._room_liveness_timer.setInterval(2000)
        self._room_liveness_timer.timeout.connect(self._room_liveness_tick)
        self._room_created = None
        self._room_data = None
        self._room_server_ip = None
        self._frpc_proc = None
        self._frpc_queue = None
        self._tunnel_id = None
        self._creating_room = False
        self._room_create_thread = None
        self._room_create_events = None
        self._room_create_cancel = None
        self._room_create_poll_timer = QTimer(self)
        self._room_create_poll_timer.setInterval(35)
        self._room_create_poll_timer.timeout.connect(self._poll_room_create_events)

        QTimer.singleShot(100, self._refresh_connect_info)
        QTimer.singleShot(200, self._check_existing_tunnel_async)
        QTimer.singleShot(320, self._start_server_probe_all)
        QTimer.singleShot(520, lambda: self._auto_detect_minecraft_port(force=False))


    def _build_log_page(self):
        page = self.stack.widget(1)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("logText")
        self.log_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.log_text, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn = JellyButton("用记事本打开")
        btn.setObjectName("logBtn")
        btn.setMinimumHeight(50)
        btn.setMinimumWidth(180)
        btn.clicked.connect(self._open_log)
        bottom.addWidget(btn)
        layout.addLayout(bottom)


    def _build_server_page(self):
        page = self.stack.widget(2)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        self._server_scroll = QScrollArea()
        self._server_scroll.setObjectName("serverScroll")
        self._server_scroll.setWidgetResizable(True)
        self._server_scroll.setFrameShape(QFrame.NoFrame)
        self._server_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container.setObjectName("serverScrollBody")
        self._server_layout = QVBoxLayout(container)
        self._server_layout.setContentsMargins(0, 0, 8, 0)
        self._server_layout.setSpacing(14)
        self._server_layout.setAlignment(Qt.AlignTop)
        self._server_scroll.setWidget(container)
        page_layout.addWidget(self._server_scroll)
        self._load_servers()


    def _build_version_page(self):
        page = self.stack.widget(3)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        version_card = MotionCard()
        version_card.setObjectName("versionCard")
        version_card.setMinimumHeight(260)
        self._add_shadow(version_card, blur=32, y=12, alpha=38, color=QColor(0, 0, 0, 50))
        card_layout = QVBoxLayout(version_card)
        card_layout.setContentsMargins(34, 32, 34, 32)
        card_layout.setSpacing(16)

        self._ver_cur_label = QLabel(f"V{VERSION}")
        self._ver_cur_label.setObjectName("versionCurrent")
        self._ver_cur_label.setFont(QFont("Microsoft YaHei", 32, QFont.Bold))
        self._ver_cur_label.setAlignment(Qt.AlignCenter)
        card_layout.addStretch(1)
        card_layout.addWidget(self._ver_cur_label)

        self._ver_latest_label = QLabel("最新版本: 检测中...")
        self._ver_latest_label.setObjectName("verLatestLabel")
        self._ver_latest_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._ver_latest_label)
        card_layout.addStretch(1)
        layout.addWidget(version_card, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn = JellyButton("前往官网下载最新版本客户端")
        btn.setMinimumHeight(52)
        btn.setMinimumWidth(260)
        btn.setObjectName("versionBtn")
        btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://shithub.site")))
        bottom.addWidget(btn)
        bottom.addStretch(1)
        layout.addLayout(bottom)


    def _build_tutorial_page(self):
        """Build a concise in-app guide without affecting tunnel or account logic."""
        page = self.stack.widget(4)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("tutorialScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("tutorialScrollBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        def add_card(number, title, lines, note=None):
            card = MotionCard()
            card.setObjectName("tutorialCard")
            self._add_shadow(card, blur=18, y=6, alpha=20, color=QColor(0, 0, 0, 40))
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(22, 18, 22, 18)
            card_layout.setSpacing(8)

            top = QHBoxLayout()
            badge = QLabel(str(number))
            badge.setObjectName("tutorialBadge")
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(28, 28)
            top.addWidget(badge, 0)
            heading = QLabel(title)
            heading.setObjectName("tutorialTitle")
            top.addWidget(heading, 1)
            top.addStretch(1)
            card_layout.addLayout(top)

            for line in lines:
                label = QLabel(line)
                label.setObjectName("tutorialText")
                label.setWordWrap(True)
                label.setTextFormat(Qt.PlainText)
                card_layout.addWidget(label)

            if note:
                note_label = QLabel(note)
                note_label.setObjectName("tutorialNote")
                note_label.setWordWrap(True)
                note_label.setTextFormat(Qt.PlainText)
                card_layout.addWidget(note_label)
            layout.addWidget(card)

        add_card(
            1,
            "开房间",
            [
                "1. 进入单人世界后，按 Esc，选择“对局域网开放”。",
                "2. 记下游戏显示的端口；回到联机页，点击“识别”，或直接填写该端口。",
                "3. 在“服务器”页选择节点，返回联机页后点击“创建房间”。",
                "4. 等待“联机地址”出现，点击“复制”，把完整地址发送给朋友。",
            ],
            "房主需要保持世界、局域网端口和红石联机程序持续运行。",
        )

        add_card(
            2,
            "进入房间",
            [
                "1. 向房主获取红石联机显示的完整“地址:端口”。",
                "2. 在 Minecraft 中进入“多人游戏” → “直接连接”，粘贴完整地址后连接。",
                "3. 游戏版本、加载器（Forge / Fabric / NeoForge）和所需 Mod 必须与房主匹配。",
                "4. 无法进入时，先确认房主没有退出世界，且联机地址没有重新创建。",
            ],
            "进入缓慢通常与房主网络、服务器线路、模组同步或世界区块加载有关。",
        )

        layout.addStretch(1)
        scroll.setWidget(body)
        page_layout.addWidget(scroll)


    def _apply_styles(self, bg):
        fg = "#0d0d0d"
        muted = "#636363"
        card = "rgba(255, 255, 255, 218)"
        card_solid = "rgba(255, 255, 255, 234)"
        card_soft = "rgba(247, 247, 247, 222)"
        line = "rgba(17, 17, 17, 120)"

        self.setStyleSheet(f"""
            QMainWindow {{
                background: #ffffff;
            }}
            QWidget#rootPanel {{
                background: transparent;
                color: {fg};
                font-family: "Microsoft YaHei", "Segoe UI";
                font-size: 10.5pt;
            }}
            QLabel#bgPhoto {{
                background: transparent;
                border: none;
            }}
            QWidget#sidebar {{
                background: rgba(255, 255, 255, 226);
                border-radius: 24px;
                border: 1px solid rgba(17, 17, 17, 150);
            }}
            QWidget#contentPanel {{
                background: rgba(255, 255, 255, 202);
                border-radius: 26px;
                border: 1px solid rgba(17, 17, 17, 150);
            }}
            QFrame#headerLine {{
                background: rgba(17, 17, 17, 58);
                border: none;
            }}
            QFrame#navIndicator {{
                background: transparent;
                border: none;
                max-width: 0px;
                max-height: 0px;
            }}
            QLabel {{
                color: {fg};
                background: transparent;
            }}
            QLabel#titleLabel {{
                color: {fg};
                font-size: 21pt;
                font-weight: 900;
                padding: 0px;
                margin: 0px;
            }}
            QLabel#sectionTitle, QLabel#serverName {{
                color: {fg};
                font-size: 11.5pt;
                font-weight: 900;
                padding: 0px;
                margin: 0px;
            }}
            QLabel#fieldLabel {{
                color: {muted};
                font-size: 10.5pt;
                font-weight: 700;
            }}
            QLabel#fieldValue {{
                color: {fg};
                font-size: 10.5pt;
                font-weight: 900;
            }}
            QPushButton {{
                border-radius: 14px;
                padding: 7px 14px;
                border: 1px solid transparent;
                background: transparent;
                color: {fg};
                text-align: center;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 235);
                border: 1px solid rgba(17, 17, 17, 170);
            }}
            QPushButton:pressed {{
                background: #eeeeee;
            }}
            QPushButton#navButton {{
                border-radius: 15px;
                padding: 7px 12px 7px 14px;
                text-align: left;
                font-size: 10.5pt;
                color: #4d4d4d;
                background: transparent;
                border: 1px solid transparent;
                icon-size: 20px;
                font-weight: 800;
            }}
            QPushButton#navButton:hover {{
                color: #111111;
                background: rgba(255, 255, 255, 220);
                border: 1px solid rgba(17, 17, 17, 135);
            }}
            QPushButton#navButton:checked {{
                color: #111111;
                background: rgba(255, 255, 255, 245);
                border: 1px solid #111111;
                font-weight: 900;
            }}
            QFrame#connectInfo, QFrame#connectControl, QFrame#serverCard, QFrame#versionCard, QFrame#tutorialCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {card_solid}, stop:1 {card_soft});
                border-radius: 22px;
                border: 1px solid rgba(17, 17, 17, 170);
            }}
            QFrame#connectControl {{
                background: rgba(255, 255, 255, 226);
            }}
            QFrame#serverCard {{
                background: rgba(255, 255, 255, 224);
                border: 1px solid rgba(17, 17, 17, 155);
            }}
            QFrame#serverCard:hover {{
                background: rgba(255, 255, 255, 244);
                border: 1px solid #111111;
            }}
            QFrame#connSep {{
                background-color: {line};
                border: none;
            }}
            QLineEdit {{
                background-color: rgba(255, 255, 255, 236);
                color: {fg};
                border: 1px solid rgba(17, 17, 17, 165);
                border-radius: 16px;
                padding: 9px 14px;
                selection-background-color: #111111;
                selection-color: #ffffff;
                font-weight: 700;
            }}
            QLineEdit:focus {{
                border: 2px solid #111111;
                background-color: #ffffff;
            }}
            QPlainTextEdit#logText {{
                background: rgba(255,255,255,226);
                color: {fg};
                border: 1px solid rgba(17, 17, 17, 165);
                border-radius: 22px;
                padding: 18px;
                font-size: 10pt;
                font-family: "Cascadia Mono", "Consolas", "Courier New";
                selection-background-color: #111111;
                selection-color: #ffffff;
            }}
            QPushButton#connBtn, QPushButton#logBtn, QPushButton#versionBtn {{
                background: #111111;
                color: #ffffff;
                border-radius: 17px;
                padding: 10px 18px;
                text-align: center;
                border: 1px solid #111111;
                font-weight: 900;
            }}
            QPushButton#connBtn:hover, QPushButton#logBtn:hover, QPushButton#versionBtn:hover {{
                background: #2a2a2a;
                border: 1px solid #2a2a2a;
            }}
            QPushButton#smallActionBtn {{
                background: rgba(255, 255, 255, 236);
                color: {fg};
                border: 1px solid rgba(17, 17, 17, 165);
                border-radius: 13px;
                padding: 6px 13px;
                min-width: 54px;
                font-weight: 900;
            }}
            QPushButton#smallActionBtn:hover {{
                background: #111111;
                color: #ffffff;
                border: 1px solid #111111;
            }}
            QLabel#statusLabel {{
                color: #111111;
                font-size: 9.5pt;
                font-weight: 900;
            }}
            QLabel#ipLabel {{
                color: {muted};
                font-size: 9.5pt;
                font-family: "Cascadia Mono", "Consolas", "Courier New";
                font-weight: 700;
            }}
            QLabel#latencyLabel {{
                color: {muted};
                font-size: 10pt;
                font-weight: 800;
            }}
            QPushButton#addServerBtn {{
                background-color: rgba(255, 255, 255, 208);
                border: 1px dashed rgba(17, 17, 17, 180);
                border-radius: 22px;
                padding: 18px;
                text-align: center;
                font-size: 10.5pt;
                color: {fg};
                font-weight: 900;
            }}
            QPushButton#addServerBtn:hover {{
                background: #111111;
                color: #ffffff;
                border: 1px dashed #111111;
            }}
            QLabel#verLatestLabel {{
                font-size: 11pt;
                color: {muted};
                font-weight: 800;
            }}
            QLabel#versionCurrent {{
                color: #111111;
                font-size: 32pt;
                font-weight: 900;
            }}
            QScrollArea#tutorialScroll, QWidget#tutorialScrollBody {{
                background: transparent;
                border: none;
            }}
            QFrame#tutorialCard {{
                background: rgba(255, 255, 255, 230);
                border: 1px solid rgba(17, 17, 17, 160);
                border-radius: 20px;
            }}
            QLabel#tutorialBadge {{
                background: #111111;
                color: #ffffff;
                border-radius: 14px;
                font-size: 10pt;
                font-weight: 900;
            }}
            QLabel#tutorialTitle {{
                color: #111111;
                font-size: 12pt;
                font-weight: 900;
            }}
            QLabel#tutorialText {{
                color: #383838;
                font-size: 10pt;
                font-weight: 700;
                line-height: 1.35;
            }}
            QLabel#tutorialNote {{
                background: rgba(17, 17, 17, 10);
                color: #555555;
                border: 1px solid rgba(17, 17, 17, 80);
                border-radius: 12px;
                padding: 8px 10px;
                font-size: 9.2pt;
                font-weight: 700;
            }}
            QScrollArea#serverScroll, QWidget#serverScrollBody {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 4px 2px 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: #111111;
                min-height: 28px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QMessageBox, QDialog {{
                background: #ffffff;
                color: {fg};
            }}
        """)

