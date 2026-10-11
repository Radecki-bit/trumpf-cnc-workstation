import sys
import math
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QPlainTextEdit, QLabel, QPushButton, QFileDialog,
    QGroupBox, QFormLayout, QLineEdit, QComboBox, QTabWidget,
    QGridLayout, QFrame, QStatusBar, QMessageBox
)


class PipelineSignals(QObject):
    log_agent1 = pyqtSignal(str)
    log_agent2 = pyqtSignal(str)
    append_code = pyqtSignal(str)
    telemetry = pyqtSignal(float, float, float, float, str)
    state_changed = pyqtSignal(str)


signals = PipelineSignals()


class CADViewWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(350)
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 50.0
        self.status_text = "READY"
        self.wireframe = [
            (0.0, 0.0), (60.0, 0.0), (80.0, 18.0), (80.0, 55.0),
            (58.0, 75.0), (24.0, 75.0), (0.0, 58.0), (0.0, 0.0)
        ]
        self.holes = [
            (22.0, 22.0), (58.0, 22.0), (22.0, 52.0), (58.0, 52.0)
        ]
        self.toolpath = [
            (10.0, 10.0), (25.0, 10.0), (25.0, 30.0), (55.0, 30.0),
            (55.0, 50.0), (65.0, 50.0), (65.0, 70.0), (45.0, 70.0),
            (32.0, 58.0), (20.0, 58.0), (12.0, 46.0), (13.0, 18.0)
        ]

    def set_tool_position(self, x, y, z, status_text):
        self.current_x = x
        self.current_y = y
        self.current_z = z
        self.status_text = status_text
        self.update()

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        bg = QColor(8, 16, 21)
        qp.fillRect(0, 0, w, h, bg)

        # Grid
        grid_color = QColor(28, 42, 46)
        pen = QPen(grid_color, 1)
        qp.setPen(pen)
        step = 24
        for x in range(0, w, step):
            qp.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            qp.drawLine(0, y, w, y)

        # World transform
        pad = 28
        min_dim = min(w, h) - pad * 2
        scale = min_dim / 110.0

        def to_screen(pt):
            x_mm, y_mm = pt
            sx = w / 2 + x_mm * scale - 55 * scale
            sy = h / 2 - y_mm * scale + 55 * scale
            return QPointF(sx, sy)

        outer = [to_screen(p) for p in self.wireframe]
        pen = QPen(QColor(0, 255, 102), 2)
        qp.setPen(pen)
        qp.drawPolyline(QPolygonF(outer))

        # Hole circles
        for cx, cy in self.holes:
            center = to_screen((cx, cy))
            r = 5.5 * scale
            qp.setPen(QPen(QColor(40, 120, 255), 1))
            qp.setBrush(QBrush(QColor(19, 39, 70), Qt.SolidPattern))
            qp.drawEllipse(center, r, r)

        # Toolpath preview
        path_points = [to_screen(p) for p in self.toolpath]
        qp.setPen(QPen(QColor(255, 180, 70), 2))
        qp.drawPolyline(QPolygonF(path_points))

        # Current tool position
        cx = w / 2 + self.current_x * scale - 55 * scale
        cy = h / 2 - self.current_y * scale + 55 * scale
        qp.setPen(QPen(QColor(255, 80, 80), 2))
        qp.setBrush(QBrush(QColor(255, 80, 80, 110)))
        qp.drawEllipse(QPointF(cx, cy), 7, 7)

        # Crosshair
        qp.setPen(QPen(QColor(0, 255, 153), 1, Qt.DashLine))
        qp.drawLine(0, cy, w, cy)
        qp.drawLine(cx, 0, cx, h)

        # Coordinates
        qp.setPen(QPen(QColor(180, 255, 210), 1))
        qp.setFont(QFont("Monospace", 10, QFont.Bold))
        qp.drawText(18, 24, f"X: {self.current_x:.3f} mm")
        qp.drawText(18, 42, f"Y: {self.current_y:.3f} mm")
        qp.drawText(18, 60, f"Z: {self.current_z:.3f} mm")
        qp.drawText(18, h - 18, self.status_text)


class Simulation3DWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(350)
        self.laser_x = 0.0
        self.laser_y = 0.0
        self.laser_z = 0.0
        self.progress = 0.0
        self.toolpath = [
            (-35, -35, 0), (-20, -25, 0), (-10, 40, 0), (20, 55, 0),
            (32, 22, 0), (38, -10, 0), (10, -30, 0), (-20, -40, 0)
        ]

    def set_state(self, x, y, z, progress):
        self.laser_x = x
        self.laser_y = y
        self.laser_z = z
        self.progress = progress
        self.update()

    def project_3d(self, x, y, z):
        cx = self.width() / 2
        cy = self.height() / 2
        px = cx + (x - z * 0.18) * 2.4
        py = cy + (y * 1.2 - z * 0.9)
        return px, py

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        qp.fillRect(0, 0, w, h, QColor(15, 17, 20))

        # Table / sheet
        table_points = [
            self.project_3d(-45, -45, 0),
            self.project_3d(45, -45, 0),
            self.project_3d(45, 45, 0),
            self.project_3d(-45, 45, 0),
        ]
        qp.setPen(QPen(QColor(120, 130, 150), 2))
        qp.setBrush(QBrush(QColor(32, 53, 60, 180)))
        qp.drawPolygon(QPolygonF([QPointF(*p) for p in table_points]))

        # Workpiece outline
        outline = [
            self.project_3d(-30, -30, 0),
            self.project_3d(30, -30, 0),
            self.project_3d(30, 30, 0),
            self.project_3d(-30, 30, 0),
        ]
        qp.setPen(QPen(QColor(0, 255, 140), 2))
        qp.setBrush(QBrush(QColor(22, 96, 72, 90)))
        qp.drawPolygon(QPolygonF([QPointF(*p) for p in outline]))

        # Toolpath in 3D simulation
        poly = []
        for x, y, z in self.toolpath:
            poly.append(QPointF(*self.project_3d(x, y, z)))
        qp.setPen(QPen(QColor(255, 175, 60), 3))
        qp.drawPolyline(QPolygonF(poly))

        # Laser head
        lx, ly = self.project_3d(self.laser_x, self.laser_y, self.laser_z)
        qp.setPen(QPen(QColor(110, 240, 255), 2))
        qp.setBrush(QBrush(QColor(40, 160, 210, 160)))
        qp.drawEllipse(QPointF(lx, ly), 10, 10)

        # Laser beam
        qp.setPen(QPen(QColor(120, 255, 180), 3))
        qp.drawLine(int(lx), int(ly), int(lx), int(ly - 70))

        # overlay labels
        qp.setPen(QPen(QColor(220, 240, 255), 1))
        qp.setFont(QFont("Monospace", 10, QFont.Bold))
        qp.drawText(15, 24, "MACHINE / 3D WORKCELL")
        qp.drawText(15, self.height() - 18, f"Progress: {self.progress:.1f}%")


class IndustrialControlCenter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smolinski|Labs - Trumpf Scan-to-NC Industrial Workstation")
        self.resize(1650, 950)
        self.setStyleSheet("""
            QWidget { background-color: #0c1116; color: #e7f4ff; }
            QMainWindow { background-color: #0c1116; }
            QGroupBox { background-color: #101820; border: 1px solid #2b3a40; border-radius: 6px; margin-top: 12px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #dff2ff; }
            QTabWidget::pane { border: 1px solid #2b3a40; background-color: #0f171d; }
            QTabBar::tab { background-color: #16232d; color: #bde7ff; border: 1px solid #2b3a40; padding: 8px 16px; }
            QTabBar::tab:selected { background-color: #203d59; color: #ffffff; }
            QPushButton { background-color: #1a2b33; border: 1px solid #335966; border-radius: 5px; color: white; font-weight: bold; padding: 10px; }
            QPushButton:hover { background-color: #214653; }
            QLineEdit, QComboBox, QPlainTextEdit { background-color: #0b1014; border: 1px solid #29414d; color: #dfefff; padding: 6px; }
            QLabel { color: #dfefff; }
            QStatusBar { background: #111a20; color: #dff6ff; }
        """)

        self.state = "IDLE"
        self.running = False
        self.paused = False
        self.sequence_index = 0
        self.machine_x = 0.0
        self.machine_y = 0.0
        self.machine_z = 50.0

        self.gcode_program = [
            "G21", "G90", "G17", "M03 S1200", "G00 X-12 Y-12 Z50", "G01 Z0 F2000",
            "G01 X0 Y0 F3000", "G01 X20 Y10 F2600", "G01 X35 Y15", "G01 X50 Y28",
            "G01 X62 Y40", "G01 X48 Y58", "G01 X28 Y64", "G01 X18 Y46",
            "G01 X10 Y20", "G01 X0 Y0", "G01 Z50 F2200", "M05", "M30"
        ]

        self.signals = signals
        self.signals.log_agent1.connect(self.append_agent1)
        self.signals.log_agent2.connect(self.append_agent2)
        self.signals.telemetry.connect(self.update_telemetry)
        self.signals.state_changed.connect(self.set_status_text)

        self._build_ui()
        self._connect_buttons()
        self._hook_timer()

        self.log_agent1("[LLaVA 13B] Rozpoczynanie analizy skanu CAD...")
        self.log_agent2("[DeepSeek-Coder-V2] Weryfikacja geometrii detalu i planu cięcia...")
        self.update_status_view()

    def _build_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        master_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(master_splitter)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        visual_splitter = QSplitter(Qt.Vertical)

        cad_group = QGroupBox("INTERAKTYWNY SZKIC CAD 2D & LIVE CROSSHAIR")
        cad_layout = QVBoxLayout(cad_group)
        self.cad_view = CADViewWidget()
        cad_layout.addWidget(self.cad_view)
        visual_splitter.addWidget(cad_group)

        cam_group = QGroupBox("SYMULACJA TRAJEKTORII 3D & DRZEWO PROCESOWE")
        cam_layout = QVBoxLayout(cam_group)
        self.cam_3d_view = Simulation3DWidget()
        cam_layout.addWidget(self.cam_3d_view)
        visual_splitter.addWidget(cam_group)

        visual_splitter.setSizes([450, 430])
        left_layout.addWidget(visual_splitter)
        master_splitter.addWidget(left_container)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("STATUS: READY / STATION ONLINE", 5000)

        self.control_tabs = QTabWidget()
        self.control_tabs.setStyleSheet("QTabBar::tab { height: 36px; width: 150px; font-weight: bold; }")

        # Tab 1: Machine
        tab_machine = QWidget()
        t_machine_layout = QVBoxLayout(tab_machine)

        coord_box = QGroupBox("POZYCJA / WSPÓŁRZĘDNE CNC")
        coord_layout = QGridLayout(coord_box)

        self.led_x = QLabel("X = 0.000")
        self.led_y = QLabel("Y = 0.000")
        self.led_z = QLabel("Z = 50.000")

        for lbl in [self.led_x, self.led_y, self.led_z]:
            lbl.setFont(QFont("Monospace", 14, QFont.Bold))
            lbl.setStyleSheet("color: #00ff66; background-color: #040b0f; padding: 8px; border: 1px solid #2d3c40;")
            lbl.setAlignment(Qt.AlignCenter)

        coord_layout.addWidget(QLabel("Oś X [mm]"), 0, 0)
        coord_layout.addWidget(self.led_x, 0, 1)
        coord_layout.addWidget(QLabel("Oś Y [mm]"), 1, 0)
        coord_layout.addWidget(self.led_y, 1, 1)
        coord_layout.addWidget(QLabel("Oś Z [mm]"), 2, 0)
        coord_layout.addWidget(self.led_z, 2, 1)
        t_machine_layout.addWidget(coord_box)

        btn_box = QGroupBox("PANEL OPERATORA & KONTROLA POTOKU")
        btn_layout = QGridLayout(btn_box)
        self.btn_home = QPushButton("HOME")
        self.btn_run = QPushButton("URUCHOM")
        self.btn_pause = QPushButton("PAUZA")
        self.btn_stop = QPushButton("STOP AWARYJNY")
        self.btn_reset = QPushButton("RESET ALARMU")

        self.btn_run.setStyleSheet("background-color: #1a5b30; color: white; font-weight: bold; padding: 10px;")
        self.btn_stop.setStyleSheet("background-color: #7a1d1d; color: white; font-weight: bold; padding: 10px;")
        self.btn_pause.setStyleSheet("background-color: #8a5b11; color: white; font-weight: bold; padding: 10px;")
        self.btn_home.setStyleSheet("background-color: #2c4964; color: white; font-weight: bold; padding: 10px;")
        self.btn_reset.setStyleSheet("background-color: #413b55; color: white; font-weight: bold; padding: 10px;")

        btn_layout.addWidget(self.btn_home, 0, 0)
        btn_layout.addWidget(self.btn_run, 0, 1)
        btn_layout.addWidget(self.btn_pause, 1, 0)
        btn_layout.addWidget(self.btn_stop, 1, 1)
        btn_layout.addWidget(self.btn_reset, 2, 0, 1, 2)
        t_machine_layout.addWidget(btn_box)

        agents_box = QGroupBox("DIAGNOSTYKA AGENTÓW / LOGI")
        agents_layout = QHBoxLayout(agents_box)
        self.txt_agent1 = QPlainTextEdit()
        self.txt_agent2 = QPlainTextEdit()
        self.txt_agent1.setReadOnly(True)
        self.txt_agent2.setReadOnly(True)
        self.txt_agent1.setStyleSheet("background-color: #0d141a; color: #84b7ff; font-family: monospace; font-size: 10pt;")
        self.txt_agent2.setStyleSheet("background-color: #0d141a; color: #ff9e9e; font-family: monospace; font-size: 10pt;")
        agents_layout.addWidget(self.txt_agent1)
        agents_layout.addWidget(self.txt_agent2)
        t_machine_layout.addWidget(agents_box)

        self.control_tabs.addTab(tab_machine, "Maszyna")

        # Tab 2: G-code editor
        tab_gcode = QWidget()
        t_gcode_layout = QVBoxLayout(tab_gcode)
        t_gcode_layout.addWidget(QLabel("Edytor programu NC / korekta operatora:"))
        self.gcode_editor = QPlainTextEdit()
        self.gcode_editor.setStyleSheet("background-color: #0b1115; color: #8cff83; font-family: monospace; font-size: 10.5pt;")
        self.gcode_editor.setPlainText("\n".join(self.gcode_program))
        t_gcode_layout.addWidget(self.gcode_editor)
        self.control_tabs.addTab(tab_gcode, "G-kod")

        # Tab 3: Controller settings
        tab_settings = QWidget()
        t_set_layout = QFormLayout(tab_settings)
        self.controller_name = QLineEdit("Trumpf TruControl / Sinumerik")
        self.max_feed = QLineEdit("12000")
        self.safe_z = QLineEdit("50.0")
        self.gas_pressure = QLineEdit("14.5")
        self.focus = QLineEdit("0.0")
        self.material = QComboBox()
        self.material.addItems(["Stal nierdzewna 1.5 mm", "Aluminium 2.0 mm", "Miedź 1.2 mm", "Blacha stalowa 3.0 mm"])
        t_set_layout.addRow("Kontroler CNC:", self.controller_name)
        t_set_layout.addRow("Maksym. posuw [mm/min]:", self.max_feed)
        t_set_layout.addRow("Bezpieczna oś Z [mm]:", self.safe_z)
        t_set_layout.addRow("Ciśnienie gazu [bar]:", self.gas_pressure)
        t_set_layout.addRow("Położenie ogniskowe [mm]:", self.focus)
        t_set_layout.addRow("Materiał:", self.material)
        self.control_tabs.addTab(tab_settings, "Ustawienia")

        # Tab 4: AI conversion options
        tab_conv = QWidget()
        t_conv_layout = QFormLayout(tab_conv)
        self.scan_file = QLineEdit("./projekty/input_scan.png")
        self.model_generator = QComboBox()
        self.model_generator.addItems(["llava:13b", "llava:34b", "sam:7b"])
        self.model_auditor = QComboBox()
        self.model_auditor.addItems(["deepseek-coder-v2", "qwen2.5-coder", "codellama:34b"])
        t_conv_layout.addRow("Plik wejściowy skanu:", self.scan_file)
        t_conv_layout.addRow("Model Generatora:", self.model_generator)
        t_conv_layout.addRow("Model Audytora:", self.model_auditor)
        self.control_tabs.addTab(tab_conv, "AI Konwersja")

        right_layout.addWidget(self.control_tabs)
        master_splitter.addWidget(right_container)
        master_splitter.setSizes([960, 690])

    def _connect_buttons(self):
        self.btn_run.clicked.connect(self.start_job)
        self.btn_pause.clicked.connect(self.pause_job)
        self.btn_stop.clicked.connect(self.stop_job)
        self.btn_home.clicked.connect(self.home_machine)
        self.btn_reset.clicked.connect(self.reset_alarm)

    def _hook_timer(self):
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._tick_machine)

    def append_agent1(self, text):
        self.txt_agent1.appendPlainText(text)

    def append_agent2(self, text):
        self.txt_agent2.appendPlainText(text)

    def set_status_text(self, text):
        self.status_bar.showMessage(f"STATUS: {text}")

    def log_agent1(self, text):
        self.signals.log_agent1.emit(text)

    def log_agent2(self, text):
        self.signals.log_agent2.emit(text)

    def update_telemetry(self, x, y, z, progress, message):
        self.led_x.setText(f"X = {x:.3f}")
        self.led_y.setText(f"Y = {y:.3f}")
        self.led_z.setText(f"Z = {z:.3f}")
        self.cad_view.set_tool_position(x, y, z, message)
        self.cam_3d_view.set_state(x, y, z, progress)
        self.status_bar.showMessage(f"STATUS: {message} | PROGRESS: {progress:.1f}%")

    def update_status_view(self):
        self.led_x.setText(f"X = {self.machine_x:.3f}")
        self.led_y.setText(f"Y = {self.machine_y:.3f}")
        self.led_z.setText(f"Z = {self.machine_z:.3f}")
        self.cad_view.set_tool_position(self.machine_x, self.machine_y, self.machine_z, "READY")
        self.cam_3d_view.set_state(self.machine_x, self.machine_y, self.machine_z, 0.0)

    def home_machine(self):
        self.state = "HOME"
        self.machine_x = 0.0
        self.machine_y = 0.0
        self.machine_z = 50.0
        self.sequence_index = 0
        self.running = False
        self.paused = False
        self.log_agent1("[HOME] Powrót do pozycji bazowej, kalibracja osi...")
        self.log_agent2("[HOME] Zdarzenie: zerowanie offsetu narzędzia i sprawdzenie czujników.")
        self.signals.telemetry.emit(self.machine_x, self.machine_y, self.machine_z, 0.0, "HOME / READY")
        self.signals.state_changed.emit("HOME")

    def reset_alarm(self):
        self.state = "READY"
        self.running = False
        self.paused = False
        self.log_agent1("[SYSTEM] Alarm wyzerowany - stan roboczy: READY")
        self.log_agent2("[SYSTEM] Weryfikacja zabezpieczeń i poprawność zera osi OK.")
        self.signals.state_changed.emit("READY")

    def pause_job(self):
        if not self.running:
            return
        self.paused = not self.paused
        if self.paused:
            self.state = "PAUSED"
            self.log_agent1("[OPERATOR] Praca wstrzymana - oczekiwanie na wznowienie.")
            self.signals.state_changed.emit("PAUSED")
        else:
            self.state = "RUNNING"
            self.log_agent1("[OPERATOR] Wznowienie procesu cięcia.")
            self.signals.state_changed.emit("RUNNING")

    def stop_job(self):
        self.running = False
        self.paused = False
        self.state = "STOPPED"
        self.sequence_index = 0
        self.log_agent1("[EMERGENCY STOP] Proces zatrzymany, przerywane wykonywanie programu.")
        self.log_agent2("[EMERGENCY STOP] Wykryto zatrzymanie awaryjne — zabezpieczenia aktywne.")
        self.signals.state_changed.emit("STOPPED")

    def start_job(self):
        self.gcode_program = self.gcode_editor.toPlainText().splitlines()
        if not self.gcode_program:
            self.log_agent2("[ERROR] Brak programu G-code do wykonania.")
            return

        self.running = True
        self.paused = False
        self.state = "RUNNING"
        self.sequence_index = 0
        self.log_agent1("[LASER] Rozpoczęcie procesu produkcyjnego.")
        self.log_agent2("[NESTED AI] Weryfikacja programu G-code i planu pokroju.")
        self.signals.state_changed.emit("RUNNING")
        self.timer.start()

    def _tick_machine(self):
        if not self.running or self.paused:
            return

        if self.sequence_index >= len(self.gcode_program):
            self.running = False
            self.state = "COMPLETE"
            self.log_agent1("[SYSTEM] Program zakończony poprawnie.")
            self.log_agent2("[AUDIT] Kontrola jakości: zbieżność profilu OK.")
            self.signals.state_changed.emit("COMPLETE")
            self.timer.stop()
            return

        cmd = self.gcode_program[self.sequence_index].strip()
        self.sequence_index += 1

        if not cmd:
            return

        if cmd.startswith("G00") or cmd.startswith("G01"):
            values = {"X": None, "Y": None, "Z": None, "F": None}
            for token in cmd.split():
                if len(token) >= 2 and token[0] in "XYZF":
                    try:
                        values[token[0]] = float(token[1:])
                    except ValueError:
                        pass

            if values["X"] is not None:
                self.machine_x = values["X"]
            if values["Y"] is not None:
                self.machine_y = values["Y"]
            if values["Z"] is not None:
                self.machine_z = values["Z"]

            status = f"CUT / {cmd[:10]}"
            progress = (self.sequence_index / len(self.gcode_program)) * 100.0
            self.log_agent2(f"[EXEC] {cmd} -> X:{self.machine_x:.3f} Y:{self.machine_y:.3f} Z:{self.machine_z:.3f}")
            self.signals.telemetry.emit(self.machine_x, self.machine_y, self.machine_z, progress, status)
            self.signals.state_changed.emit("RUNNING")

        elif cmd.startswith("M03"):
            self.log_agent1("[LASER] Rozpoczęcie wiązki / ustawienie mocy lasera.")
            self.signals.telemetry.emit(self.machine_x, self.machine_y, self.machine_z, (self.sequence_index / max(1, len(self.gcode_program))) * 100.0, "LASER ON")

        elif cmd.startswith("M05"):
            self.log_agent1("[LASER] Wyłączenie wiązki laserowej.")
            self.signals.telemetry.emit(self.machine_x, self.machine_y, self.machine_z, (self.sequence_index / max(1, len(self.gcode_program))) * 100.0, "LASER OFF")

        elif cmd.startswith("M30"):
            self.running = False
            self.state = "COMPLETE"
            self.log_agent1("[PROGRAM] Koniec programu. Wznowienie procesu po jakości.")
            self.signals.state_changed.emit("COMPLETE")
            self.timer.stop()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IndustrialControlCenter()
    window.show()
    sys.exit(app.exec_())
