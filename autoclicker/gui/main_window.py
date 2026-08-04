"""Main application window.

Ties together the click engine, the global hotkey backend and the persistence
services (settings / profiles / autostart / tray). All heavy work happens on
background threads; this window only updates labels and reacts to signals.

Hotkeys go through the :class:`HotkeyBackend` interface — the window never
knows which mechanism (evdev / IPC / X11 / Windows) is active.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ..core.click_engine import ClickEngine
from ..core.models import (
    CLICK_BUTTONS_NAMES,
    CLICK_TYPES,
    INTERVAL_UNITS,
    MODES,
    AppSettings,
    ClickSettings,
    Profile,
)
from ..input.hotkey_backends import create_backend
from ..services.autostart import AutostartManager
from ..services.hotkey_service import HotkeyService
from ..services.profile_service import ProfileService
from ..services.settings_service import SettingsService
from ..utils.logging_setup import log
from ..utils.timeutil import format_milliseconds
from .capture_dialog import CaptureDialog
from .components import Card, IconHelper, StatCard, ToggleSwitch
from .diagnostics import DiagnosticsDialog
from .settings_dialog import SettingsDialog
from .theme import GREEN, RED, AMBER


class MainWindow(QMainWindow):
    def __init__(self, app_settings: AppSettings) -> None:
        super().__init__()
        self.app_settings = app_settings
        self._current_backend_mode = app_settings.hotkey_backend

        # Services
        self.settings_service = SettingsService()
        self.profile_service = ProfileService()
        self.autostart = AutostartManager()

        # Engine + hotkey backend (interface, not a concrete implementation).
        self.engine = ClickEngine()
        self.backend = create_backend(app_settings.hotkey_backend)
        self.hotkey = HotkeyService(self.engine, self.backend, lambda: self.current_profile.settings)

        # State
        self.current_profile = self.profile_service.get(self.app_settings.last_profile) or Profile()
        self._run_start: float | None = None
        self._tray: "QSystemTrayIcon | None" = None

        self._build_ui()
        self._wire_engine()
        self._wire_backend()
        self._populate_from_settings(self.current_profile.settings)

        # Background threads
        self.backend.start()
        self.engine.start()
        self.hotkey.sync_hotkey()

        self._runtime_timer = QTimer(self)
        self._runtime_timer.setInterval(250)
        self._runtime_timer.timeout.connect(self._update_runtime)
        self._cps_timer = QTimer(self)
        self._cps_timer.setInterval(250)
        self._cps_timer.timeout.connect(self._update_cps)

        self._apply_app_settings()
        self._refresh_profiles()

    # =================================================================== UI
    def _build_ui(self) -> None:
        self.setWindowTitle("ZCode Auto Clicker")
        self.setWindowIcon(IconHelper.app_icon())
        self.resize(700, 800)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        # --- header ---
        header = QHBoxLayout()
        title = QLabel("ZCode Auto Clicker")
        title.setObjectName("big")
        self._status = QLabel("Stopped")
        self._status.setObjectName("statuspill")
        self._set_status_style(False)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._status)
        root.addLayout(header)

        # --- transport buttons ---
        transport = QHBoxLayout()
        self._start_btn = QPushButton("▶  Start")
        self._start_btn.setObjectName("primary")
        self._start_btn.clicked.connect(self.start_clicking)
        self._stop_btn = QPushButton("■  Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.clicked.connect(self.stop_clicking)
        self._stop_btn.setEnabled(False)
        transport.addWidget(self._start_btn)
        transport.addWidget(self._stop_btn)
        transport.addStretch(1)
        root.addLayout(transport)

        # --- stats ---
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self._count_stat = StatCard("Clicks", "0")
        self._runtime_stat = StatCard("Runtime", "0:00")
        self._cps_stat = StatCard("CPS", "0.0")
        self._interval_stat = StatCard("Interval", "100 ms")
        for w in (self._count_stat, self._runtime_stat, self._cps_stat, self._interval_stat):
            stats.addWidget(w)
        root.addLayout(stats)

        # --- hotkey status ---
        hk = QHBoxLayout()
        hk.setSpacing(10)
        self._hk_status = QLabel("…")
        self._hk_status.setObjectName("statuspill")
        self._hk_hint = QLabel("")
        self._hk_hint.setObjectName("subtitle")
        self._hk_hint.setWordWrap(True)
        hk.addWidget(self._hk_status)
        hk.addWidget(self._hk_hint, stretch=1)
        root.addLayout(hk)

        # --- click settings ---
        settings_card = Card(title="Click settings")
        form = QFormLayout()
        form.setSpacing(12)
        form.setContentsMargins(4, 4, 4, 4)

        self._interval_value = QDoubleSpinBox()
        self._interval_unit = QComboBox()
        self._interval_unit.addItems(INTERVAL_UNITS)
        interval_row = QHBoxLayout()
        interval_row.addWidget(self._interval_value)
        interval_row.addWidget(self._interval_unit)
        form.addRow("Interval", interval_row)

        self._button_box = QComboBox()
        self._button_box.addItems(CLICK_BUTTONS_NAMES)
        form.addRow("Mouse button", self._button_box)

        self._type_box = QComboBox()
        self._type_box.addItems(CLICK_TYPES)
        form.addRow("Click type", self._type_box)

        self._mode_box = QComboBox()
        self._mode_box.addItems(MODES)
        form.addRow("Mode", self._mode_box)

        self._hotkey_btn = QPushButton("F8")
        self._hotkey_btn.setObjectName("ghost")
        self._hotkey_btn.clicked.connect(self._change_hotkey)
        form.addRow("Hotkey", self._hotkey_btn)

        rand_row = QHBoxLayout()
        self._randomize_switch = ToggleSwitch()
        self._randomize_pct = QDoubleSpinBox()
        self._randomize_pct.setRange(0, 100)
        self._randomize_pct.setValue(10)
        self._randomize_pct.setSuffix(" %")
        self._randomize_pct.setDisabled(True)
        self._randomize_switch.toggled.connect(self._on_randomize_toggled)
        rand_row.addWidget(self._randomize_switch)
        rand_row.addWidget(self._randomize_pct)
        rand_row.addStretch(1)
        form.addRow("Randomize", rand_row)

        settings_card.card_layout().addLayout(form)
        root.addWidget(settings_card)

        # --- profiles ---
        profiles_card = Card(title="Profiles")
        p_layout = QVBoxLayout()
        p_layout.setSpacing(10)
        self._profile_combo = QComboBox()
        self._profile_combo.currentTextChanged.connect(self._on_profile_selected)
        p_layout.addWidget(self._profile_combo)

        p_buttons = QHBoxLayout()
        for text, slot in (
            ("New", self._new_profile),
            ("Save", self._save_profile),
            ("Delete", self._delete_profile),
            ("Export", self._export_profile),
            ("Import", self._import_profile),
        ):
            btn = QPushButton(text)
            btn.setObjectName("ghost")
            btn.clicked.connect(slot)  # type: ignore[arg-type]
            p_buttons.addWidget(btn)
        p_layout.addLayout(p_buttons)
        profiles_card.card_layout().addLayout(p_layout)
        root.addWidget(profiles_card)

        root.addStretch(1)

        self._build_menu()
        self.statusBar().showMessage("Ready")

        # React to any control change by pushing settings to the engine/backend.
        for widget in (
            self._interval_value,
            self._interval_unit,
            self._button_box,
            self._type_box,
            self._mode_box,
            self._randomize_switch,
            self._randomize_pct,
        ):
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(lambda *_: self._apply_settings())
            elif isinstance(widget, QDoubleSpinBox):
                widget.valueChanged.connect(lambda *_: self._apply_settings())
            else:
                widget.toggled.connect(lambda *_: self._apply_settings())  # type: ignore[attr-defined]

    def _build_menu(self) -> None:
        menubar = QMenuBar()
        self.setMenuBar(menubar)

        file_menu = QMenu("&File", self)
        act_settings = file_menu.addAction("App settings…")
        act_settings.triggered.connect(self._open_settings)
        file_menu.addSeparator()
        act_quit = file_menu.addAction("Quit")
        act_quit.triggered.connect(QApplication.instance().quit)
        menubar.addMenu(file_menu)

        profile_menu = QMenu("&Profile", self)
        for text, slot in (
            ("New…", self._new_profile),
            ("Save", self._save_profile),
            ("Delete", self._delete_profile),
            ("Export…", self._export_profile),
            ("Import…", self._import_profile),
        ):
            profile_menu.addAction(text, slot)  # type: ignore[arg-type]
        menubar.addMenu(profile_menu)

        tools_menu = QMenu("&Tools", self)
        act_diag = tools_menu.addAction("Diagnostics…")
        act_diag.triggered.connect(self._open_diagnostics)
        menubar.addMenu(tools_menu)

    # =============================================================== wiring
    def _wire_engine(self) -> None:
        self.engine.clicked.connect(self._on_clicked)
        self.engine.stateChanged.connect(self._on_state_changed)
        self.engine.error.connect(self._on_engine_error)
        self.engine.stopped.connect(lambda: log.info("engine stopped signal"))

    def _wire_backend(self) -> None:
        self.backend.status_changed.connect(self._update_backend_status)

    # =========================================================== settings
    def _populate_from_settings(self, s: ClickSettings) -> None:
        self._interval_value.setValue(s.interval_value)
        self._interval_unit.setCurrentText(s.interval_unit)
        self._button_box.setCurrentText(s.button)
        self._type_box.setCurrentText(s.click_type)
        self._mode_box.setCurrentText(s.mode)
        self._hotkey_btn.setText(s.hotkey_label)
        self._randomize_switch.setChecked(s.randomize)
        self._randomize_pct.setValue(s.randomize_pct)
        self._randomize_pct.setDisabled(not s.randomize)
        self._interval_stat.set_value(format_milliseconds(s.interval_ms()))

    def _collect_settings(self) -> ClickSettings:
        return ClickSettings(
            interval_value=self._interval_value.value(),
            interval_unit=self._interval_unit.currentText(),
            button=self._button_box.currentText(),
            click_type=self._type_box.currentText(),
            mode=self._mode_box.currentText(),
            hotkey_code=self.current_profile.settings.hotkey_code,
            hotkey_label=self.current_profile.settings.hotkey_label,
            randomize=self._randomize_switch.isChecked(),
            randomize_pct=self._randomize_pct.value(),
        )

    def _apply_settings(self) -> None:
        settings = self._collect_settings()
        self.current_profile.settings = settings
        self.engine.set_settings(settings)
        self.hotkey.sync_hotkey()
        self._interval_stat.set_value(format_milliseconds(settings.interval_ms()))
        if self.app_settings.autosave:
            self._autosave_profile()
            self._autosave_app()

    def _on_randomize_toggled(self, checked: bool) -> None:
        self._randomize_pct.setDisabled(not checked)
        self._apply_settings()

    # ============================================================ transport
    def start_clicking(self) -> None:
        if self.app_settings.run_in_background:
            self.engine.setPriority(Qt.ThreadPriority.LowPriority)
        self.engine.set_active(True)

    def stop_clicking(self) -> None:
        self.engine.set_active(False)

    def _on_state_changed(self, active: bool) -> None:
        self._set_status_style(active)
        self._status.setText("Running" if active else "Stopped")
        self._start_btn.setEnabled(not active)
        self._stop_btn.setEnabled(active)
        if active:
            self._run_start = time.time()
            self._runtime_timer.start()
            self._cps_timer.start()
        else:
            self._runtime_timer.stop()
            self._cps_timer.stop()
            self._run_start = None
            self._runtime_stat.set_value("0:00")
            self._cps_stat.set_value("0.0")

    def _on_clicked(self, total: int) -> None:
        self._count_stat.set_value(f"{total}")

    def _on_engine_error(self, msg: str) -> None:
        self.statusBar().showMessage(msg)
        QMessageBox.critical(self, "Input device error", msg)
        self._set_status_style(False)
        self._status.setText("Stopped")
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _update_runtime(self) -> None:
        if self._run_start is None:
            return
        elapsed = int(time.time() - self._run_start)
        self._runtime_stat.set_value(_format_hms(elapsed))

    def _update_cps(self) -> None:
        self._cps_stat.set_value(f"{self.engine.cps():.1f}")

    def _set_status_style(self, active: bool) -> None:
        self._pill(self._status, "Running" if active else "Stopped", GREEN if active else RED)

    def _pill(self, widget: QLabel, text: str, color: str) -> None:
        widget.setText(text)
        widget.setStyleSheet(
            f"background:{color}; color:#15151c; padding:4px 12px; "
            f"border-radius:10px; font-weight:600;"
        )

    # =============================================================== hotkey
    def _change_hotkey(self) -> None:
        dlg = CaptureDialog(self.backend, self.current_profile.settings.hotkey_code,
                            self.current_profile.settings.hotkey_label, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and self.backend.can_capture():
            self.current_profile.settings.hotkey_code = dlg.result_code
            self.current_profile.settings.hotkey_label = dlg.result_label
            self._hotkey_btn.setText(dlg.result_label)
            self._apply_settings()

    def _update_backend_status(self, active: bool) -> None:
        name = self.backend.name()
        if name == "ipc":
            self._pill(self._hk_status, "✔ IPC mode active", GREEN)
            self._hk_hint.setText(
                "Bind a compositor key:  autoclickerctl toggle   "
                "(niri: binds { \"F8\" { spawn \"autoclickerctl\" \"toggle\"; } })"
            )
        elif name == "dummy":
            self._pill(self._hk_status, "⚠ Hotkey unavailable", AMBER)
            self._hk_hint.setText("No usable hotkey backend for this session.")
        else:  # evdev / x11
            if active:
                self._pill(self._hk_status, "✔ Global hotkey active", GREEN)
                self._hk_hint.setText("")
            else:
                self._pill(self._hk_status, "⚠ Global hotkey unavailable", AMBER)
                self._hk_hint.setText(
                    "No read access to /dev/input — switch backend to IPC or join "
                    "the 'input' group."
                )

    # ============================================================== profiles
    def _refresh_profiles(self, select: str | None = None) -> None:
        names = self.profile_service.list_names()
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.addItems(names)
        if select:
            self._profile_combo.setCurrentText(select)
        elif self.current_profile.name in names:
            self._profile_combo.setCurrentText(self.current_profile.name)
        self._profile_combo.blockSignals(False)

    def _on_profile_selected(self, name: str) -> None:
        if not name:
            return
        profile = self.profile_service.get(name)
        if profile is None:
            return
        self.current_profile = profile
        self.app_settings.last_profile = name
        self._populate_from_settings(profile.settings)
        self.engine.set_settings(profile.settings)
        self.hotkey.sync_hotkey()
        if self.app_settings.autosave:
            self._autosave_app()

    def _new_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "New profile", "Profile name:")
        if not ok or not name.strip():
            return
        profile = Profile(name=name.strip(), settings=self._collect_settings())
        self.profile_service.save(profile)
        self.current_profile = profile
        self._refresh_profiles(select=profile.name)

    def _save_profile(self) -> None:
        self.current_profile.settings = self._collect_settings()
        self.profile_service.save(self.current_profile)
        self.statusBar().showMessage(f"Saved profile '{self.current_profile.name}'")
        self._refresh_profiles(select=self.current_profile.name)

    def _delete_profile(self) -> None:
        if self.current_profile.name == "Default":
            QMessageBox.information(self, "Cannot delete", "The Default profile cannot be deleted.")
            return
        self.profile_service.delete(self.current_profile.name)
        self.current_profile = self.profile_service.get("Default") or Profile()
        self._populate_from_settings(self.current_profile.settings)
        self._refresh_profiles(select=self.current_profile.name)

    def _export_profile(self) -> None:
        text = self.profile_service.export_json(self.current_profile)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export profile", f"{self.current_profile.name}.json", "JSON (*.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            QApplication.clipboard().setText(text)
            self.statusBar().showMessage("Profile exported (also copied to clipboard)")

    def _import_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import profile", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            profile = self.profile_service.import_json(text)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        self.profile_service.save(profile)
        self.current_profile = profile
        self._populate_from_settings(profile.settings)
        self._refresh_profiles(select=profile.name)

    # =========================================================== app settings
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.app_settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.app_settings = dlg.apply()
            self._apply_app_settings()
            if self.app_settings.autosave:
                self._autosave_app()

    def _open_diagnostics(self) -> None:
        DiagnosticsDialog(self.backend.name(), self).exec()

    def _apply_app_settings(self) -> None:
        if self.app_settings.start_with_system:
            self.autostart.enable(_autostart_command())
        else:
            self.autostart.disable()
        # Tray (needed for minimize-to-tray or close-to-tray).
        if (self.app_settings.minimize_to_tray or self.app_settings.close_to_tray) and self._tray_usable():
            self._ensure_tray()
        elif not (self.app_settings.minimize_to_tray or self.app_settings.close_to_tray):
            if self._tray is not None:
                self._tray.setVisible(False)
                self._tray = None
        # Hotkey backend switch if the user changed it.
        if self.app_settings.hotkey_backend != self._current_backend_mode:
            self._switch_backend(self.app_settings.hotkey_backend)

    def _switch_backend(self, mode: str) -> None:
        log.info("Switching hotkey backend: %s -> %s", self._current_backend_mode, mode)
        old = self.backend
        # Drop the old backend's status connection before swapping it out.
        try:
            old.status_changed.disconnect(self._update_backend_status)
        except (TypeError, RuntimeError):
            pass
        try:
            old.stop()
        except Exception as exc:  # pragma: no cover
            log.warning("backend stop failed: %s", exc)
        self.backend = create_backend(mode)
        self.backend.status_changed.connect(self._update_backend_status)
        self.hotkey.set_backend(self.backend)
        self.backend.start()
        self.hotkey.sync_hotkey()
        self._current_backend_mode = mode

    def _tray_usable(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def _ensure_tray(self) -> None:
        from ..services.tray import TrayIcon

        if self._tray is not None:
            return
        tray = TrayIcon(IconHelper.app_icon(), self)
        tray.show_action.triggered.connect(self._show_window)
        tray.start_action.triggered.connect(self.start_clicking)
        tray.stop_action.triggered.connect(self.stop_clicking)
        tray.quit_action.triggered.connect(QApplication.instance().quit)
        tray.setVisible(True)
        self._tray = tray

    # =============================================================== autosave
    def _autosave_profile(self) -> None:
        self.profile_service.save(self.current_profile)

    def _autosave_app(self) -> None:
        self.settings_service.save(self.app_settings)

    # ================================================================ window
    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def changeEvent(self, event) -> None:  # noqa: D401
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            if self.app_settings.minimize_to_tray and self._tray_usable():
                self.hide()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:  # noqa: D401
        if self.app_settings.close_to_tray and self._tray_usable() and self._tray is not None:
            self.hide()
            event.ignore()
            return
        self._shutdown()
        event.accept()

    def _shutdown(self) -> None:
        self.engine.stop_engine()
        self.backend.stop()


def _format_hms(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _autostart_command() -> str:
    import os
    import sys

    bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    launcher = os.path.join(bin_dir, "run.sh")
    if os.path.exists(launcher):
        return os.path.abspath(launcher)
    exe = sys.argv[0] if sys.argv and sys.argv[0].endswith(".py") else "autoclicker"
    return f"{exe} --start-minimized"
