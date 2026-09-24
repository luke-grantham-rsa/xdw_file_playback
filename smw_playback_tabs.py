### Rohde & Schwarz Automation for demonstration use.
### Title  : PyQt6 tabs that transfer generated xDW files to an SMW200A and play them with the
###           Extended Sequencer, either on a single baseband ('SMW Playback') or on individual
###           sequencers S1-S6 in Extended Sequencer Advanced mode ('Multi-Sequencer').
import os

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from smw_control import DEFAULT_REMOTE_DIR, TRIGGER_MODES, TRIGGER_SOURCES, SmwInstrument, files_for_basename

DEFAULT_SMW_ADDRESS = "192.168.1.11"
ARMED_TRIGGER_MODES = ('AAUT', 'ARET', 'SING')
STREAM_OUTPUTS = {'RF A': 'RFA', 'RF B': 'RFB', 'None': 'NONE'}


class InstrumentWorker(QThread):
    """Runs one instrument operation off the GUI thread so long uploads don't freeze the window."""
    log = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, operation):
        super().__init__()
        self.operation = operation

    def run(self):
        try:
            self.operation(self.log.emit)
        except Exception as exc:
            self.failed.emit(str(exc))


class InstrumentSession(QObject):
    """The SMW connection shared by all instrument tabs. Runs one operation at a time."""
    changed = pyqtSignal()    # connected/busy state changed
    connected = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.smw = None
        self.idn = ''
        self.worker = None

    @property
    def busy(self):
        return self.worker is not None

    def run(self, operation, log, parent, on_success=None):
        """Runs operation(log) on a worker thread; on_success is called on the GUI thread."""
        self.worker = InstrumentWorker(operation)
        self.worker.log.connect(log)
        failed = []

        def on_failed(message):
            failed.append(message)
            log(f"ERROR: {message}")
            QMessageBox.critical(parent, "Instrument Error", message)

        def finished():
            self.worker = None
            if on_success and not failed:
                on_success()
            self.changed.emit()

        self.worker.failed.connect(on_failed)
        self.worker.finished.connect(finished)
        self.changed.emit()
        self.worker.start()

    def connect_to(self, address, log, parent):
        smw = SmwInstrument(address)
        idn = []

        def connect(log):
            log(f"Connecting to {smw.host}...")
            idn.append(smw.connect())
            log(idn[0])
            missing = {'SMW-K503', 'SMW-K504'} - smw.options()
            if missing:
                log(f"WARNING: instrument is missing option(s) {', '.join(sorted(missing))} required for xDW playback")

        def on_connected():
            self.smw = smw
            self.idn = idn[0]
            self.connected.emit()

        self.run(connect, log, parent, on_success=on_connected)

    def disconnect(self):
        if self.smw:
            self.smw.close()
            self.smw = None
            self.idn = ''
            self.changed.emit()


class ConnectionBox(QGroupBox):
    """IP address + Connect/Disconnect for the shared session. Every instrument tab shows one."""

    def __init__(self, session, log):
        super().__init__("Instrument")
        self.session = session
        self.log = log
        layout = QFormLayout(self)
        address_row = QHBoxLayout()
        self.le_address = QLineEdit(DEFAULT_SMW_ADDRESS)
        self.b_connect = QPushButton("Connect")
        self.b_connect.clicked.connect(self.toggle_connection)
        address_row.addWidget(self.le_address)
        address_row.addWidget(self.b_connect)
        layout.addRow("IP address:", address_row)
        self.l_idn = QLabel("Not connected")
        self.l_idn.setStyleSheet("color: gray;")
        layout.addRow("Status:", self.l_idn)
        session.changed.connect(self.update_controls)
        self.update_controls()

    def toggle_connection(self):
        if self.session.smw:
            self.session.disconnect()
            self.log("Disconnected")
        else:
            self.session.connect_to(self.le_address.text().strip(), self.log, self)

    def update_controls(self):
        connected = self.session.smw is not None
        if connected:
            self.le_address.setText(self.session.smw.host)
        self.b_connect.setText("Disconnect" if connected else "Connect")
        self.b_connect.setEnabled(not self.session.busy)
        self.le_address.setEnabled(not connected and not self.session.busy)
        self.l_idn.setText(self.session.idn or "Not connected")


class InstrumentTab(QWidget):
    """Common layout for instrument tabs: connection box at the top, log at the bottom."""

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        self.vbox = QVBoxLayout(self)
        self.vbox.addWidget(ConnectionBox(session, self.append_log))
        self.action_buttons = []
        session.changed.connect(self.update_controls)

    def add_log(self):
        self.vbox.addWidget(QLabel("Log:"))
        self.vbox.addWidget(self.log_view, stretch=1)
        self.update_controls()

    @property
    def smw(self):
        return self.session.smw

    def append_log(self, message):
        self.log_view.appendPlainText(str(message))

    def run_operation(self, operation, on_success=None):
        self.session.run(operation, self.append_log, self, on_success)

    def update_controls(self):
        ready = self.session.smw is not None and not self.session.busy
        for b in self.action_buttons:
            b.setEnabled(ready)

    def transfer(self, files, remote_dir, log):
        """Transfers the files and returns the instrument path of the .ps_def (files[0])."""
        for path in files:
            log(f"Transferring {os.path.basename(path)} ({os.path.getsize(path):,} bytes) to {remote_dir}")
            self.smw.upload_file(path, remote_dir)
        return f"{remote_dir.rstrip('/')}/{os.path.basename(files[0])}"

    def browse_ps_def(self, line_edit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Definition File", line_edit.text(), "PDW Definition Files (*.ps_def);;All Files (*)"
        )
        if path:
            line_edit.setText(path)

    def selected_files(self, ps_def):
        if not os.path.isfile(ps_def):
            QMessageBox.warning(self, "Missing Definition File", "Please select a generated .ps_def file.")
            return None
        return files_for_basename(ps_def)


class SmwPlaybackTab(InstrumentTab):
    def __init__(self, session):
        super().__init__(session)
        layout = self.vbox

        files_box = QGroupBox("Files")
        files_layout = QFormLayout()
        ps_def_row = QHBoxLayout()
        self.le_ps_def = QLineEdit()
        self.le_ps_def.setPlaceholderText("Generated .ps_def file (filled in automatically after Generate)")
        self.le_ps_def.textChanged.connect(self.refresh_file_list)
        self.b_ps_def_browse = QPushButton("Browse...")
        self.b_ps_def_browse.clicked.connect(lambda: self.browse_ps_def(self.le_ps_def))
        ps_def_row.addWidget(self.le_ps_def)
        ps_def_row.addWidget(self.b_ps_def_browse)
        files_layout.addRow("Definition file:", ps_def_row)
        self.l_files = QLabel("-")
        files_layout.addRow("Files to transfer:", self.l_files)
        self.le_remote_dir = QLineEdit(DEFAULT_REMOTE_DIR)
        files_layout.addRow("Instrument folder:", self.le_remote_dir)
        files_box.setLayout(files_layout)
        layout.addWidget(files_box)

        playback_box = QGroupBox("Extended Sequencer Playback")
        playback_layout = QFormLayout()
        self.cb_trigger_mode = QComboBox()
        self.cb_trigger_mode.addItems(TRIGGER_MODES.keys())
        playback_layout.addRow("Trigger mode:", self.cb_trigger_mode)
        self.cb_trigger_source = QComboBox()
        self.cb_trigger_source.addItems(TRIGGER_SOURCES.keys())
        playback_layout.addRow("Trigger source:", self.cb_trigger_source)
        self.chk_preset = QCheckBox("Preset instrument before playback")
        self.chk_preset.setChecked(True)
        playback_layout.addRow(self.chk_preset)
        self.chk_rf_on = QCheckBox("Turn RF on")
        self.chk_rf_on.setChecked(True)
        playback_layout.addRow(self.chk_rf_on)
        playback_box.setLayout(playback_layout)
        layout.addWidget(playback_box)

        actions_row = QHBoxLayout()
        self.b_transfer_play = QPushButton("Transfer && Play")
        self.b_transfer_play.clicked.connect(lambda: self.start_playback(transfer=True))
        self.b_transfer = QPushButton("Transfer Only")
        self.b_transfer.clicked.connect(self.transfer_only)
        self.b_play = QPushButton("Play")
        self.b_play.clicked.connect(lambda: self.start_playback(transfer=False))
        self.b_trigger = QPushButton("Execute Trigger")
        self.b_trigger.clicked.connect(lambda: self.run_operation(lambda log: self.smw.execute_trigger()))
        self.b_stop = QPushButton("Stop")
        self.b_stop.clicked.connect(self.stop_playback)
        self.action_buttons = [self.b_transfer_play, self.b_transfer, self.b_play, self.b_trigger, self.b_stop]
        for b in self.action_buttons:
            actions_row.addWidget(b)
        layout.addLayout(actions_row)

        self.add_log()

    def set_ps_def(self, path):
        self.le_ps_def.setText(path)

    def refresh_file_list(self):
        files = files_for_basename(self.le_ps_def.text().strip())
        self.l_files.setText(", ".join(os.path.basename(f) for f in files) if files else "-")

    def transfer_only(self):
        files = self.selected_files(self.le_ps_def.text().strip())
        if files:
            remote_dir = self.le_remote_dir.text().strip()
            self.run_operation(lambda log: (self.transfer(files, remote_dir, log), log("Transfer complete")))

    def start_playback(self, transfer):
        files = self.selected_files(self.le_ps_def.text().strip())
        if not files:
            return
        trigger_mode = TRIGGER_MODES[self.cb_trigger_mode.currentText()]
        trigger_source = TRIGGER_SOURCES[self.cb_trigger_source.currentText()]
        preset = self.chk_preset.isChecked()
        rf_on = self.chk_rf_on.isChecked()
        remote_dir = self.le_remote_dir.text().strip()
        remote_ps_def = f"{remote_dir.rstrip('/')}/{os.path.basename(files[0])}"

        def play(log):
            ps_def = self.transfer(files, remote_dir, log) if transfer else remote_ps_def
            self.smw.play_file(ps_def, trigger_mode, trigger_source, preset=preset, rf_on=rf_on, log=log)
            if trigger_mode in ARMED_TRIGGER_MODES:
                log("Playback armed - press 'Execute Trigger' to start")
            else:
                log("Playback running")

        self.run_operation(play)

    def stop_playback(self):
        rf_off = self.chk_rf_on.isChecked()

        def stop(log):
            self.smw.stop()
            log("Extended Sequencer: OFF")
            if rf_off:
                self.smw.set_rf(False)
                log("RF: OFF")

        self.run_operation(stop)


class SequencerRow:
    """The widgets for one sequencer (S1-S6) in the Multi-Sequencer tab."""

    def __init__(self, index, num_streams):
        self.index = index
        self.l_name = QLabel(f"S{index}")
        self.l_file = QLabel("-")
        self.chk_enabled = QCheckBox()
        self.cb_stream = QComboBox()
        self.cb_stream.addItems([f"Stream {chr(65 + di)}" for di in range(num_streams)])
        self.sb_freq_offset = QDoubleSpinBox()
        self.sb_freq_offset.setRange(-250.0, 250.0)
        self.sb_freq_offset.setDecimals(6)
        self.sb_freq_offset.setSuffix(" MHz")
        self.sb_attenuation = QDoubleSpinBox()
        self.sb_attenuation.setRange(0.0, 100.0)
        self.sb_attenuation.setDecimals(2)
        self.sb_attenuation.setSuffix(" dB")
        self.sb_trigger_delay = QDoubleSpinBox()
        self.sb_trigger_delay.setRange(0.0, 688e6)
        self.sb_trigger_delay.setDecimals(4)
        self.sb_trigger_delay.setSuffix(" us")

    def widgets(self):
        return (self.l_name, self.l_file, self.chk_enabled, self.cb_stream,
                self.sb_freq_offset, self.sb_attenuation, self.sb_trigger_delay)

    def load(self, config):
        self.l_file.setText(os.path.basename(config['file']) if config['file'] else "-")
        self.l_file.setToolTip(config['file'])
        self.chk_enabled.setChecked(config['enabled'])
        if config['stream']:
            self.cb_stream.setCurrentIndex(config['stream'] - 1)
        self.sb_freq_offset.setValue(config['freq_offset'] / 1e6)
        self.sb_attenuation.setValue(config['attenuation'])
        self.sb_trigger_delay.setValue(config['trigger_delay'] * 1e6)

    def settings(self):
        return {
            'enabled': self.chk_enabled.isChecked(),
            'stream': self.cb_stream.currentIndex() + 1,
            'freq_offset': self.sb_freq_offset.value() * 1e6,
            'attenuation': self.sb_attenuation.value(),
            'trigger_delay': self.sb_trigger_delay.value() / 1e6,
        }


class MultiSequencerTab(InstrumentTab):
    """Loads a scenario onto each sequencer in Extended Sequencer Advanced mode, then plays them together."""
    COLUMNS = ("Sequencer", "Loaded file", "On", "Stream", "Freq offset", "Attenuation", "Trigger delay")

    def __init__(self, session):
        super().__init__(session)
        layout = self.vbox
        self.rows = []
        self.stream_output_boxes = []

        mode_row = QHBoxLayout()
        self.l_mode = QLabel("System mode: -")
        self.b_advanced_mode = QPushButton("Switch to Extended Sequencer Advanced Mode")
        self.b_advanced_mode.clicked.connect(self.enable_advanced_mode)
        self.b_advanced_mode.setVisible(False)
        self.b_refresh = QPushButton("Refresh from Instrument")
        self.b_refresh.clicked.connect(self.refresh)
        mode_row.addWidget(self.l_mode, stretch=1)
        mode_row.addWidget(self.b_advanced_mode)
        mode_row.addWidget(self.b_refresh)
        layout.addLayout(mode_row)

        load_box = QGroupBox("Load Files onto a Sequencer")
        load_layout = QFormLayout()
        ps_def_row = QHBoxLayout()
        self.le_ps_def = QLineEdit()
        self.le_ps_def.setPlaceholderText("Generated .ps_def file (filled in automatically after Generate)")
        self.b_ps_def_browse = QPushButton("Browse...")
        self.b_ps_def_browse.clicked.connect(lambda: self.browse_ps_def(self.le_ps_def))
        ps_def_row.addWidget(self.le_ps_def)
        ps_def_row.addWidget(self.b_ps_def_browse)
        load_layout.addRow("Definition file:", ps_def_row)
        self.le_remote_dir = QLineEdit(DEFAULT_REMOTE_DIR)
        load_layout.addRow("Instrument folder:", self.le_remote_dir)
        target_row = QHBoxLayout()
        self.cb_target = QComboBox()
        self.b_load = QPushButton("Transfer && Load")
        self.b_load.clicked.connect(self.load_onto_sequencer)
        target_row.addWidget(self.cb_target, stretch=1)
        target_row.addWidget(self.b_load)
        load_layout.addRow("Sequencer:", target_row)
        load_box.setLayout(load_layout)
        layout.addWidget(load_box)

        self.sequencer_box = QGroupBox("Sequencers")
        self.sequencer_grid = QGridLayout(self.sequencer_box)
        self.l_no_sequencers = QLabel("Connect to the instrument to see its sequencers.")
        self.l_no_sequencers.setStyleSheet("color: gray;")
        self.sequencer_grid.addWidget(self.l_no_sequencers, 0, 0)
        layout.addWidget(self.sequencer_box)

        playback_box = QGroupBox("Playback")
        playback_layout = QFormLayout()
        playback_layout.addRow("Trigger mode:", QLabel("Armed Auto (the only mode for Playback from File in advanced mode)"))
        self.cb_trigger_source = QComboBox()
        self.cb_trigger_source.addItems(TRIGGER_SOURCES.keys())
        self.cb_trigger_source.currentTextChanged.connect(
            lambda text: self.chk_start.setEnabled(TRIGGER_SOURCES[text] == 'INT'))
        playback_layout.addRow("Trigger source:", self.cb_trigger_source)
        self.chk_start = QCheckBox("Start immediately (execute trigger after arming)")
        self.chk_start.setChecked(True)
        playback_layout.addRow(self.chk_start)
        self.chk_rf_on = QCheckBox("Turn RF on for the outputs in use")
        self.chk_rf_on.setChecked(True)
        playback_layout.addRow(self.chk_rf_on)
        playback_box.setLayout(playback_layout)
        layout.addWidget(playback_box)

        actions_row = QHBoxLayout()
        self.b_play = QPushButton("Play All")
        self.b_play.clicked.connect(self.play_all)
        self.b_trigger = QPushButton("Execute Trigger")
        self.b_trigger.clicked.connect(lambda: self.run_operation(lambda log: self.smw.execute_trigger()))
        self.b_stop = QPushButton("Stop")
        self.b_stop.clicked.connect(self.stop_playback)
        for b in (self.b_play, self.b_trigger, self.b_stop):
            actions_row.addWidget(b)
        layout.addLayout(actions_row)

        self.action_buttons = [self.b_advanced_mode, self.b_refresh, self.b_load, self.b_play, self.b_trigger, self.b_stop]
        session.connected.connect(self.refresh)
        self.add_log()

    def set_ps_def(self, path):
        self.le_ps_def.setText(path)

    def update_controls(self):
        super().update_controls()
        has_sequencers = bool(self.rows)
        ready = self.session.smw is not None and not self.session.busy
        for b in (self.b_load, self.b_play, self.b_trigger, self.b_stop):
            b.setEnabled(ready and has_sequencers)

    def refresh(self):
        result = {}

        def read(log):
            result['advanced'] = self.smw.is_advanced_mode()
            if result['advanced']:
                result['num_streams'] = self.smw.stream_count()
                result['config'] = self.smw.read_advanced_config()
                log(f"Found {len(result['config']['sequencers'])} sequencer(s), {result['num_streams']} stream(s)")
            else:
                log("Instrument is not in Extended Sequencer Advanced mode")

        self.run_operation(read, on_success=lambda: self.show_config(result))

    def show_config(self, result):
        advanced = result['advanced']
        self.l_mode.setText("System mode: Extended Sequencer Advanced" if advanced
                            else "System mode: not Extended Sequencer Advanced")
        self.b_advanced_mode.setVisible(not advanced)
        if advanced:
            self.build_rows(result['num_streams'], result['config'])
        else:
            self.build_rows(0, None)

    def build_rows(self, num_streams, config):
        while self.sequencer_grid.count():
            widget = self.sequencer_grid.takeAt(0).widget()
            if widget and widget is not self.l_no_sequencers:
                widget.deleteLater()
        self.rows = []
        self.stream_output_boxes = []
        self.stream_max_sequencers = config['stream_max_sequencers'] if config else []
        self.cb_target.clear()
        self.l_no_sequencers.setVisible(not config)
        if not config:
            self.l_no_sequencers.setText("Switch the instrument to Extended Sequencer Advanced mode to use sequencers.")
            self.sequencer_grid.addWidget(self.l_no_sequencers, 0, 0)
            self.update_controls()
            return

        for col, title in enumerate(self.COLUMNS):
            self.sequencer_grid.addWidget(QLabel(f"<b>{title}</b>"), 0, col)
        for i, seq_config in enumerate(config['sequencers'], start=1):
            row = SequencerRow(i, num_streams)
            row.load(seq_config)
            for col, widget in enumerate(row.widgets()):
                self.sequencer_grid.addWidget(widget, i, col)
            self.rows.append(row)
            self.cb_target.addItem(f"S{i}")

        outputs_row = QHBoxLayout()
        for di, output in enumerate(config['stream_outputs']):
            box = QComboBox()
            box.addItems(STREAM_OUTPUTS.keys())
            box.setCurrentText(next(k for k, v in STREAM_OUTPUTS.items() if v == output))
            outputs_row.addWidget(QLabel(f"Stream {chr(65 + di)} output:"))
            outputs_row.addWidget(box)
            self.stream_output_boxes.append(box)
        outputs_row.addStretch(1)
        outputs = QWidget()
        outputs.setLayout(outputs_row)
        self.sequencer_grid.addWidget(outputs, len(self.rows) + 1, 0, 1, len(self.COLUMNS))
        self.update_controls()

    def enable_advanced_mode(self):
        answer = QMessageBox.question(
            self, "Switch System Mode",
            "Switching to Extended Sequencer Advanced mode disables the fading simulator, AWGN, BB input and "
            "all baseband digital standards on the instrument. Continue?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        def switch(log):
            log("Switching to Extended Sequencer Advanced mode (this can take a while)...")
            self.smw.enable_advanced_mode()
            log("Extended Sequencer Advanced mode: ON")

        self.run_operation(switch, on_success=self.refresh)

    def load_onto_sequencer(self):
        files = self.selected_files(self.le_ps_def.text().strip())
        if not files:
            return
        row = self.rows[self.cb_target.currentIndex()]
        remote_dir = self.le_remote_dir.text().strip()

        def load(log):
            ps_def = self.transfer(files, remote_dir, log)
            log("Fading/Baseband Config mode: Extended Sequencer Advanced")
            log(f"Loading {os.path.basename(ps_def)} onto S{row.index}")
            self.smw.load_sequencer_file(row.index, ps_def)

        def loaded():
            row.l_file.setText(os.path.basename(files[0]))
            row.l_file.setToolTip(f"{remote_dir.rstrip('/')}/{os.path.basename(files[0])}")
            row.chk_enabled.setChecked(True)
            self.append_log(f"S{row.index} ready")

        self.run_operation(load, on_success=loaded)

    def play_all(self):
        empty = [f"S{row.index}" for row in self.rows if row.chk_enabled.isChecked() and row.l_file.text() == "-"]
        if empty:
            QMessageBox.warning(self, "No File Loaded", f"No file is loaded on {', '.join(empty)}. "
                                "Load a file or turn the sequencer off.")
            return
        if not any(row.chk_enabled.isChecked() for row in self.rows):
            QMessageBox.warning(self, "No Sequencers On", "Turn on at least one sequencer.")
            return
        sequencers = [row.settings() for row in self.rows]
        for di, max_count in enumerate(self.stream_max_sequencers, start=1):
            assigned = [f"S{st}" for st, seq in enumerate(sequencers, start=1) if seq['stream'] == di]
            if len(assigned) > max_count:
                QMessageBox.warning(self, "Too Many Sequencers on Stream",
                                    f"Stream {chr(64 + di)} can hold at most {max_count} sequencer(s) on this "
                                    f"instrument, but {', '.join(assigned)} are assigned to it.")
                return
        stream_outputs = [STREAM_OUTPUTS[box.currentText()] for box in self.stream_output_boxes]
        trigger_source = TRIGGER_SOURCES[self.cb_trigger_source.currentText()]
        start = trigger_source == 'INT' and self.chk_start.isChecked()
        rf_on = self.chk_rf_on.isChecked()

        def play(log):
            self.smw.play_sequencers(sequencers, stream_outputs, trigger_source, start=start, rf_on=rf_on, log=log)
            if start:
                log("Playback running")
            elif trigger_source == 'INT':
                log("Playback armed - press 'Execute Trigger' to start")
            else:
                log(f"Playback armed - waiting for trigger on {trigger_source}")

        self.run_operation(play)

    def stop_playback(self):
        used_streams = {row.cb_stream.currentIndex() for row in self.rows}
        rf_paths = sorted({STREAM_OUTPUTS[box.currentText()] for di, box in enumerate(self.stream_output_boxes)
                           if di in used_streams} - {'NONE'})
        rf_off = self.chk_rf_on.isChecked()

        def stop(log):
            self.smw.stop()
            log("Extended Sequencer: OFF")
            if rf_off:
                for path in rf_paths:
                    self.smw.set_rf(False, 1 if path == 'RFA' else 2)
                    log(f"RF {path[-1]}: OFF")

        self.run_operation(stop)
