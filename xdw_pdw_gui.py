### Rohde & Schwarz Automation for demonstration use.
### Title  : PyQt6 GUI to load a PDW List .csv file, preview its contents, and generate the
###           xDW (.ps_def), Container Waveform (.wv), and Address Look-Up (.ps_adr) files.
###           Replaces the input()-driven command line flow in xdw_file_playback_v2_3.py.
import csv
import os
import sys

from PyQt6.QtWidgets import (
    QApplication,
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
    QVBoxLayout,
    QWidget,
)

from xdw_file_playback_v2_3 import build_xdw_files

MAX_PREVIEW_ROWS = 500


def index_containing_substring(the_list, substring):
    """Method for finding substring in list. Used for column indexing."""
    for i, s in enumerate(the_list):
        if substring in s:
            return i
    return -1


class PdwCsvPreviewWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("R&S xDW PDW List Preview")
        self.resize(733, 600)

        self.has_arb_pdw = False

        central = QWidget()
        self.setCentralWidget(central)
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
            QMessageBox.information(self, "Success", f"Successfully generated files for '{output_basename}'.")
        finally:
            self.b_generate.setEnabled(True)

    def append_log(self, message):
        self.log_view.appendPlainText(str(message))
        QApplication.processEvents()


def main():
    app = QApplication(sys.argv)
    window = PdwCsvPreviewWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
