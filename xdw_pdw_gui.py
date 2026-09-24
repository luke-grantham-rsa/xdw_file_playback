### Rohde & Schwarz Automation for demonstration use.
### Title  : PyQt6 GUI to load a PDW List .csv file, preview its contents, and generate the
###           xDW (.ps_def), Container Waveform (.wv), and Address Look-Up (.ps_adr) files.
###           Replaces the input()-driven command line flow in xdw_file_playback_v2_3.py.
###           The 'SMW Playback' tab transfers the generated files to an SMW200A and plays
###           them with the Extended Sequencer.
import csv
import os
import sys

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from smw_control import DEFAULT_REMOTE_DIR, TRIGGER_MODES, TRIGGER_SOURCES, SmwInstrument, files_for_basename
from xdw_file_playback import build_xdw_files

MAX_PREVIEW_ROWS = 500
DEFAULT_SMW_ADDRESS = "192.168.1.11"


def index_containing_substring(the_list, substring):
    """Method for finding substring in list. Used for column indexing."""
    for i, s in enumerate(the_list):
        if substring in s:
            return i
    return -1


class PdwCsvPreviewWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("R&S SMW200A xDW File Generation & Playback")
        self.resize(733, 600)

        self.has_arb_pdw = False

        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        central = QWidget()
        tabs.addTab(central, "Generate xDW Files")
        self.playback_tab = SmwPlaybackTab()
        tabs.addTab(self.playback_tab, "SMW Playback")
        layout = QVBoxLayout(central)

        file_row = QHBoxLayout()
        self.le_path = QLineEdit()
        self.le_path.setReadOnly(True)
        self.le_path.setPlaceholderText("No file selected")
        self.b_browse = QPushButton("Browse...")
        self.b_browse.clicked.connect(self.browse_file)
        file_row.addWidget(QLabel("PDW List .csv:"))
        file_row.addWidget(self.le_path)
        file_row.addWidget(self.b_browse)
        layout.addLayout(file_row)

        summary_box = QGroupBox("Preview Summary")
        summary_layout = QFormLayout()
        self.l_total_rows = QLabel("-")
        self.l_pdw_count = QLabel("-")
        self.l_tcdw_count = QLabel("-")
        self.l_arb_flag = QLabel("-")
        summary_layout.addRow("Total rows:", self.l_total_rows)
        summary_layout.addRow("Number of PDWs:", self.l_pdw_count)
        summary_layout.addRow("Number of TCDWs:", self.l_tcdw_count)
        summary_layout.addRow("Contains ARB PDW:", self.l_arb_flag)
        summary_box.setLayout(summary_layout)
        layout.addWidget(summary_box)

        layout.addWidget(QLabel("Data preview:"))
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setMinimumHeight(230)
        layout.addWidget(self.table, stretch=3)

        self.l_status = QLabel("")
        self.l_status.setStyleSheet("color: gray;")
        layout.addWidget(self.l_status)

        generate_box = QGroupBox("Generate xDW Files")
        generate_layout = QFormLayout()

        output_row = QHBoxLayout()
        self.le_output = QLineEdit()
        self.le_output.setPlaceholderText("Output file base name (no extension)")
        self.b_output_browse = QPushButton("Browse...")
        self.b_output_browse.clicked.connect(self.browse_output_basename)
        output_row.addWidget(self.le_output)
        output_row.addWidget(self.b_output_browse)
        generate_layout.addRow("Output base name:", output_row)

        self.le_comment = QLineEdit()
        self.le_comment.setPlaceholderText("Optional comment stored in the .ps_def file")
        generate_layout.addRow("Comment:", self.le_comment)

        generate_box.setLayout(generate_layout)
        layout.addWidget(generate_box)

        self.arb_waveform_paths = []
        self.required_arb_segments = 0

        self.arb_box = QGroupBox("ARB Waveform Segments")
        arb_box_layout = QVBoxLayout()

        self.l_arb_required = QLabel("No ARB PDWs in this file.")
        arb_box_layout.addWidget(self.l_arb_required)

        self.list_arb_waveforms = QListWidget()
        arb_box_layout.addWidget(self.list_arb_waveforms)

        arb_buttons_row = QHBoxLayout()
        self.b_arb_add = QPushButton("Add File(s)...")
        self.b_arb_add.clicked.connect(self.add_arb_waveforms)
        self.b_arb_remove = QPushButton("Remove Selected")
        self.b_arb_remove.clicked.connect(self.remove_selected_arb_waveform)
        self.b_arb_up = QPushButton("Move Up")
        self.b_arb_up.clicked.connect(self.move_arb_waveform_up)
        self.b_arb_down = QPushButton("Move Down")
        self.b_arb_down.clicked.connect(self.move_arb_waveform_down)
        arb_buttons_row.addWidget(self.b_arb_add)
        arb_buttons_row.addWidget(self.b_arb_remove)
        arb_buttons_row.addWidget(self.b_arb_up)
        arb_buttons_row.addWidget(self.b_arb_down)
        arb_box_layout.addLayout(arb_buttons_row)

        self.arb_box.setLayout(arb_box_layout)
        layout.addWidget(self.arb_box)

        self.b_generate = QPushButton("Generate xDW Files")
        self.b_generate.setEnabled(False)
        self.b_generate.clicked.connect(self.generate_files)
        layout.addWidget(self.b_generate)

        layout.addWidget(QLabel("Log:"))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        layout.addWidget(self.log_view, stretch=1)

        self.set_arb_controls_enabled(False)

    def set_arb_controls_enabled(self, enabled):
        self.arb_box.setEnabled(enabled)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select PDW List CSV", "", "CSV Files (*.csv);;All Files (*)"
        )
        if path:
            self.load_csv(path)

    def browse_output_basename(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Select Output Base Name", self.le_output.text(), "All Files (*)"
        )
        if path:
            base, _ext = os.path.splitext(path)
            self.le_output.setText(base)

    def refresh_arb_list(self):
        self.list_arb_waveforms.clear()
        for i, path in enumerate(self.arb_waveform_paths):
            self.list_arb_waveforms.addItem(f"{i}: {path}")

    def add_arb_waveforms(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select ARB Waveform File(s)", "", "Waveform Files (*.wv);;All Files (*)"
        )
        if paths:
            self.arb_waveform_paths.extend(paths)
            self.refresh_arb_list()

    def remove_selected_arb_waveform(self):
        row = self.list_arb_waveforms.currentRow()
        if row >= 0:
            del self.arb_waveform_paths[row]
            self.refresh_arb_list()

    def move_arb_waveform_up(self):
        row = self.list_arb_waveforms.currentRow()
        if row > 0:
            self.arb_waveform_paths[row - 1], self.arb_waveform_paths[row] = (
                self.arb_waveform_paths[row], self.arb_waveform_paths[row - 1]
            )
            self.refresh_arb_list()
            self.list_arb_waveforms.setCurrentRow(row - 1)

    def move_arb_waveform_down(self):
        row = self.list_arb_waveforms.currentRow()
        if 0 <= row < len(self.arb_waveform_paths) - 1:
            self.arb_waveform_paths[row + 1], self.arb_waveform_paths[row] = (
                self.arb_waveform_paths[row], self.arb_waveform_paths[row + 1]
            )
            self.refresh_arb_list()
            self.list_arb_waveforms.setCurrentRow(row + 1)

    def load_csv(self, path):
        try:
            with open(path, newline='') as csvfile:
                csvreader = csv.reader(csvfile, delimiter=',', quotechar='|')
                header = next(csvreader)
                rows = list(csvreader)
        except Exception as exc:
            QMessageBox.critical(self, "Error Reading File", f"Could not read {path}:\n{exc}")
            return

        type_idx = index_containing_substring(header, 'Type')
        if type_idx == -1:
            QMessageBox.warning(self, "Invalid CSV", "Could not find a 'Type' column in the selected file.")
            return

        mod_idx = index_containing_substring(header, 'Mod')
        pulse_width_idx = index_containing_substring(header, 'Pulse Width')

        pdw_count = sum(1 for row in rows if len(row) > type_idx and row[type_idx] == 'pdw')
        tcdw_count = sum(1 for row in rows if len(row) > type_idx and row[type_idx] == 'tcdw')
        arb_rows = [
            row for row in rows
            if len(row) > type_idx and row[type_idx] == 'pdw'
            and mod_idx != -1 and len(row) > mod_idx and row[mod_idx] == 'arb'
        ]
        has_arb = bool(arb_rows)

        max_segment_idx = -1
        if has_arb and pulse_width_idx != -1:
            for row in arb_rows:
                if len(row) > pulse_width_idx:
                    try:
                        max_segment_idx = max(max_segment_idx, int(float(row[pulse_width_idx])))
                    except ValueError:
                        pass

        self.le_path.setText(path)
        self.l_total_rows.setText(str(len(rows)))
        self.l_pdw_count.setText(str(pdw_count))
        self.l_tcdw_count.setText(str(tcdw_count))
        self.l_arb_flag.setText("Yes" if has_arb else "No")

        self.has_arb_pdw = has_arb
        self.required_arb_segments = max_segment_idx + 1
        self.set_arb_controls_enabled(has_arb)
        if has_arb:
            self.l_arb_required.setText(
                f"This file references waveform segment index up to {max_segment_idx} "
                f"(the 'Pulse Width' column selects a segment for 'arb' PDWs) "
                f"— add {self.required_arb_segments} file(s) below, in index order."
            )
        else:
            self.l_arb_required.setText("No ARB PDWs in this file.")

        if not self.le_output.text():
            self.le_output.setText(os.path.splitext(os.path.basename(path))[0])

        self.b_generate.setEnabled(True)
        self.populate_table(header, rows)

    def populate_table(self, header, rows):
        preview_rows = rows[:MAX_PREVIEW_ROWS]
        self.table.setColumnCount(len(header))
        self.table.setHorizontalHeaderLabels(header)
        self.table.setRowCount(len(preview_rows))
        for r, row in enumerate(preview_rows):
            for c in range(len(header)):
                value = row[c] if c < len(row) else ""
                self.table.setItem(r, c, QTableWidgetItem(value))

        if len(rows) > MAX_PREVIEW_ROWS:
            self.l_status.setText(f"Showing first {MAX_PREVIEW_ROWS} of {len(rows)} rows.")
        else:
            self.l_status.setText(f"Showing all {len(rows)} rows.")

    def generate_files(self):
        pdw_list_path = self.le_path.text()
        output_basename = self.le_output.text().strip()
        if not output_basename:
            QMessageBox.warning(self, "Missing Output Name", "Please provide an output base name.")
            return

        if self.has_arb_pdw:
            if len(self.arb_waveform_paths) < self.required_arb_segments:
                QMessageBox.warning(
                    self, "Missing ARB Waveforms",
                    f"This PDW list references waveform segment index up to {self.required_arb_segments - 1}, "
                    f"but only {len(self.arb_waveform_paths)} ARB waveform file(s) were added."
                )
                return
            missing = [p for p in self.arb_waveform_paths if not os.path.isfile(p)]
            if missing:
                QMessageBox.warning(self, "ARB Waveform Not Found", "Could not find:\n" + "\n".join(missing))
                return

        self.log_view.clear()
        self.b_generate.setEnabled(False)
        try:
            build_xdw_files(
                pdw_list_path,
                output_basename,
                comment=self.le_comment.text(),
                arb_waveform_files=self.arb_waveform_paths or ('pulse1.wv', 'pulse2.wv'),
                log=self.append_log,
            )
        except Exception as exc:
            self.append_log(f"ERROR: {exc}")
            QMessageBox.critical(self, "Generation Failed", f"Could not generate xDW files:\n{exc}")
        else:
            self.playback_tab.set_ps_def(os.path.abspath(f'{output_basename}.ps_def'))
            QMessageBox.information(
                self, "Success",
                f"Successfully generated files for '{output_basename}'.\n"
                f"Use the 'SMW Playback' tab to load them onto the instrument."
            )
        finally:
            self.b_generate.setEnabled(True)

    def append_log(self, message):
        self.log_view.appendPlainText(str(message))
        QApplication.processEvents()


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


class SmwPlaybackTab(QWidget):
    def __init__(self):
        super().__init__()
        self.smw = None
        self.worker = None

        layout = QVBoxLayout(self)

        connection_box = QGroupBox("Instrument")
        connection_layout = QFormLayout()
        address_row = QHBoxLayout()
        self.le_address = QLineEdit(DEFAULT_SMW_ADDRESS)
        self.b_connect = QPushButton("Connect")
        self.b_connect.clicked.connect(self.toggle_connection)
        address_row.addWidget(self.le_address)
        address_row.addWidget(self.b_connect)
        connection_layout.addRow("IP address:", address_row)
        self.l_idn = QLabel("Not connected")
        self.l_idn.setStyleSheet("color: gray;")
        connection_layout.addRow("Status:", self.l_idn)
        connection_box.setLayout(connection_layout)
        layout.addWidget(connection_box)

        files_box = QGroupBox("Files")
        files_layout = QFormLayout()
        ps_def_row = QHBoxLayout()
        self.le_ps_def = QLineEdit()
        self.le_ps_def.setPlaceholderText("Generated .ps_def file (filled in automatically after Generate)")
        self.le_ps_def.textChanged.connect(self.refresh_file_list)
        self.b_ps_def_browse = QPushButton("Browse...")
        self.b_ps_def_browse.clicked.connect(self.browse_ps_def)
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
        for b in (self.b_transfer_play, self.b_transfer, self.b_play, self.b_trigger, self.b_stop):
            actions_row.addWidget(b)
        layout.addLayout(actions_row)
        self.action_buttons = (self.b_transfer_play, self.b_transfer, self.b_play, self.b_trigger, self.b_stop)

        layout.addWidget(QLabel("Log:"))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        layout.addWidget(self.log_view, stretch=1)

        self.update_controls()

    def set_ps_def(self, path):
        self.le_ps_def.setText(path)

    def browse_ps_def(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Definition File", self.le_ps_def.text(), "PDW Definition Files (*.ps_def);;All Files (*)"
        )
        if path:
            self.set_ps_def(path)

    def refresh_file_list(self):
        files = files_for_basename(self.le_ps_def.text().strip())
        self.l_files.setText(", ".join(os.path.basename(f) for f in files) if files else "-")

    def update_controls(self):
        busy = self.worker is not None
        connected = self.smw is not None
        self.b_connect.setText("Disconnect" if connected else "Connect")
        self.b_connect.setEnabled(not busy)
        self.le_address.setEnabled(not connected and not busy)
        for b in self.action_buttons:
            b.setEnabled(connected and not busy)

    def append_log(self, message):
        self.log_view.appendPlainText(str(message))

    def run_operation(self, operation, on_success=None):
        """Runs operation(log) on a worker thread; on_success is called on the GUI thread."""
        self.worker = InstrumentWorker(operation)
        self.worker.log.connect(self.append_log)
        self.worker.failed.connect(self.operation_failed)
        succeeded = []
        self.worker.failed.connect(lambda _msg: succeeded.append(False))

        def finished():
            self.worker = None
            if on_success and not succeeded:
                on_success()
            self.update_controls()

        self.worker.finished.connect(finished)
        self.update_controls()
        self.worker.start()

    def operation_failed(self, message):
        self.append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Instrument Error", message)

    def toggle_connection(self):
        if self.smw:
            self.smw.close()
            self.smw = None
            self.l_idn.setText("Not connected")
            self.append_log("Disconnected")
            self.update_controls()
            return

        smw = SmwInstrument(self.le_address.text().strip())
        idn = []

        def connect(log):
            log(f"Connecting to {smw.host}...")
            idn.append(smw.connect())
            log(idn[0])
            missing = {'SMW-K503', 'SMW-K504'} - smw.options()
            if missing:
                log(f"WARNING: instrument is missing option(s) {', '.join(sorted(missing))} required for xDW playback")

        def connected():
            self.smw = smw
            self.l_idn.setText(idn[0])

        self.run_operation(connect, on_success=connected)

    def selected_files(self):
        ps_def = self.le_ps_def.text().strip()
        if not os.path.isfile(ps_def):
            QMessageBox.warning(self, "Missing Definition File", "Please select a generated .ps_def file.")
            return None
        return files_for_basename(ps_def)

    def transfer(self, files, log):
        remote_dir = self.le_remote_dir.text().strip()
        for path in files:
            log(f"Transferring {os.path.basename(path)} ({os.path.getsize(path):,} bytes) to {remote_dir}")
            self.smw.upload_file(path, remote_dir)
        return f"{remote_dir.rstrip('/')}/{os.path.basename(files[0])}"

    def transfer_only(self):
        files = self.selected_files()
        if files:
            self.run_operation(lambda log: (self.transfer(files, log), log("Transfer complete")))

    def start_playback(self, transfer):
        files = self.selected_files()
        if not files:
            return
        trigger_mode = TRIGGER_MODES[self.cb_trigger_mode.currentText()]
        trigger_source = TRIGGER_SOURCES[self.cb_trigger_source.currentText()]
        preset = self.chk_preset.isChecked()
        rf_on = self.chk_rf_on.isChecked()
        remote_ps_def = f"{self.le_remote_dir.text().strip().rstrip('/')}/{os.path.basename(files[0])}"

        def play(log):
            ps_def = self.transfer(files, log) if transfer else remote_ps_def
            self.smw.play_file(ps_def, trigger_mode, trigger_source, preset=preset, rf_on=rf_on, log=log)
            if trigger_mode in ('AAUT', 'ARET', 'SING'):
                log("Playback armed - press 'Execute Trigger' to start")
            else:
                log("Playback running")

        self.run_operation(play)

    def stop_playback(self):
        def stop(log):
            self.smw.stop()
            log("Extended Sequencer: OFF")
            if self.chk_rf_on.isChecked():
                self.smw.set_rf(False)
                log("RF: OFF")

        self.run_operation(stop)


def main():
    app = QApplication(sys.argv)
    window = PdwCsvPreviewWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
