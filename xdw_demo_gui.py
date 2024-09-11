import math
import sys
from rsxdwstreaming import xdw_streaming, adw, pdw_basic, pdw_expert, ctrl_xdw, xdw_payload, xdw_extension, xdw_format

from PyQt5.QtCore import (
    QTimer,
    QLocale,
    pyqtSlot
)

from PyQt5.QtGui import (
    QDoubleValidator,
    QIntValidator
)

from PyQt5.QtWidgets import (
    QMainWindow,
    QDesktopWidget,
    QApplication,
    QWidget,
    QLabel,
    QCheckBox,
    QComboBox,
    QPushButton,
    QLineEdit,
    QGridLayout,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
)

# TODO:
# - Marker Support
# - ADW: Segment_Interrupt


class XdwDemoGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'R&S xDW Demo GUI'
        self.left = 0
        self.top = 0
        self.width = 440
        self.height = 700
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        resolution = QDesktopWidget().screenGeometry()
        self.move(int((resolution.width() - self.width) / 2), int((resolution.height() - self.height) / 2))

        self.tabs_widget = TabsWidget(self)
        self.setCentralWidget(self.tabs_widget)

class TabsWidget(QWidget):
    def __init__(self, parent):
        super(QWidget, self).__init__(parent)
        self.layout = QVBoxLayout(self)

        # Initialize tab screen
        self.tabs = QTabWidget()
        self.tab_basic_pdw = BasicPdwTab()
        self.tab_basic_tcdw = BasicTcdwTab()
        self.tab_expert_pdw = ExpertPdwTab()
        self.tab_expert_tcdw = ExpertTcdwTab()
        self.tab_adw = AdwTab()
        self.tab_cdw = CdwTab()

        # Add tabs
        self.tabs.addTab(self.tab_basic_pdw, "Basic PDW")
        self.tabs.addTab(self.tab_basic_tcdw, "Basic TCDW")
        self.tabs.addTab(self.tab_expert_pdw, "Expert PDW")
        self.tabs.addTab(self.tab_expert_tcdw, "Expert TCDW")
        self.tabs.addTab(self.tab_adw, "ADW")
        self.tabs.addTab(self.tab_cdw, "CDW")

        # Add interface part
        self.xDWinterface = None
        self.xDWinterfaceIP = None

        self.interfaceInfo = QWidget()
        interfaceInfoLayout = QHBoxLayout()
        self.l_ip = QLabel("xDW Interface IP: ")
        self.le_ip = QLineEdit()
        self.b_connect = QPushButton("Connect")
        self.b_connect.clicked.connect(self.connect)
        self.state = QLabel(self)
        self.state.setFixedSize(20, 20)
        self.state.setStyleSheet("background-color: red;")

        interfaceInfoLayout.addWidget(self.l_ip)
        interfaceInfoLayout.addWidget(self.le_ip)
        interfaceInfoLayout.addWidget(self.b_connect)
        interfaceInfoLayout.addWidget(self.state)

        self.interfaceInfo.setLayout(interfaceInfoLayout)

        self.timer = QTimer(self)
        self.timer.setInterval(500)          # Throw event timeout with an interval of 1000 milliseconds
        self.timer.timeout.connect(self.get_state) # each time timer counts a second, call self.blink
        self.connection_flag = False
        self.timer.start()

        buttons = QWidget()
        hButtonsLayout = QHBoxLayout()
        self.b_clear = QPushButton("Set To Default")
        self.b_clear.clicked.connect(self.SetToDefault)
        self.b_send = QPushButton("Send xDW")
        self.b_send.clicked.connect(self.sendxDW)
        #self.b_close = QPushButton("Close")
        #self.b_close.clicked.connect(self.exitApplication)


        hButtonsLayout.addWidget(self.b_clear)
        hButtonsLayout.addWidget(self.b_send)
        #hButtonsLayout.addWidget(self.b_close)
        buttons.setLayout(hButtonsLayout)

        # Add Qwidgets to widget
        self.layout.addWidget(self.tabs)
        self.layout.addWidget(self.interfaceInfo)
        self.layout.addWidget(buttons)

        self.setLayout(self.layout)
        self.le_ip.setText('10.215.0.160')

    @pyqtSlot()
    def get_state(self):
        if self.xDWinterface:
                #self.xDWinterface.xdw_interface.recv(1)
                self.state.setStyleSheet("background-color: red;")
                #self.state.setStyleSheet("background-color: green;")

    def connect(self):
        self.xDWinterfaceIP = self.le_ip.text()
        try:
            self.xDWinterface = xdw_streaming.XdwStreaming(self.xDWinterfaceIP)
        except:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Could not connect!")
            msg.setWindowTitle("Connection Error")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        else:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText(f"Successfully connected to {self.le_ip.text()}!")
            msg.setWindowTitle("Connection successful")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()

    def SetToDefault(self):
        self.tabs.currentWidget().SetToDefault()

    def sendxDW(self):
        try:
            xDW = self.tabs.currentWidget().createXdw()
            self.xDWinterface.send_xdw(xDW)
        except:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Could not send xDW!")
            msg.setWindowTitle("Parameter Error")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()

    #def exitApplication(self):
    #    self.close()

class AdwTab(QWidget):
    def __init__(self, parent=None):
        super(AdwTab, self).__init__(parent)

        self.val_freq_offset  = QDoubleValidator(-2.4e9 / 2, 2.4e9 * (1/2 - 1/(1 << 32)), 10)
        self.val_level_offset = QDoubleValidator(0, math.inf, 10)
        self.val_phase_offset = QDoubleValidator(0, 360 * (1 - 1/(1 << 16)), 10)
        self.val_segment      = QIntValidator(0, (1 << 24) - 1)
        self.val_burst_pri    = QDoubleValidator(0, ((1 << 32) - 1) / 2.4e9, 10)
        self.val_burst_rep    = QDoubleValidator(0, (1 << 16) - 1, 10)

        self.loc_double_validation = QLocale("en")
        self.val_freq_offset.setLocale(self.loc_double_validation)
        self.val_level_offset.setLocale(self.loc_double_validation)
        self.val_phase_offset.setLocale(self.loc_double_validation)
        self.val_segment.setLocale(self.loc_double_validation)
        self.val_burst_pri.setLocale(self.loc_double_validation)
        self.val_burst_rep.setLocale(self.loc_double_validation)

        self.layout = QVBoxLayout()

        self.initWidgetAdw()

        self.layout.addWidget(self.widget_adw)

        self.setLayout(self.layout)
        self.setWindowTitle("xDW streaming demo")
        self.SetToDefault()

    def initWidgetAdw(self):
        self.widget_adw = QWidget()
        layout = QFormLayout()
        self.l_seg = QLabel("Segment ID: ")
        self.le_seg = QLineEdit()
        self.l_freqoffset = QLabel("Frequency offset: [Hz]")
        self.le_freqoffset = QLineEdit()
        self.l_leveloffset = QLabel("Level offset: [dB]")
        self.le_leveloffset = QLineEdit()
        self.l_phaseoffset = QLabel("Phase offset: [deg]")
        self.le_phaseoffset = QLineEdit()
        self.l_burstN = QLabel("Burst additional pulses: ")
        self.le_burstN = QLineEdit()
        self.l_burstPRI = QLabel("Burst PRI: [s]")
        self.le_burstPRI = QLineEdit()

        self.le_burstN.setValidator(self.val_burst_rep)
        self.le_burstPRI.setValidator(self.val_burst_pri)


        self.le_seg.setValidator(self.val_segment)
        self.le_freqoffset.setValidator(self.val_freq_offset)
        self.le_leveloffset.setValidator(self.val_level_offset)
        self.le_phaseoffset.setValidator(self.val_phase_offset)
        self.le_burstN.setValidator(self.val_burst_rep)
        self.le_burstPRI.setValidator(self.val_burst_pri)


        layout.addRow(self.l_seg, self.le_seg)
        layout.addRow(self.l_freqoffset, self.le_freqoffset)
        layout.addRow(self.l_leveloffset, self.le_leveloffset)
        layout.addRow(self.l_phaseoffset, self.le_phaseoffset)
        layout.addRow(self.l_burstN, self.le_burstN)
        layout.addRow(self.l_burstPRI, self.le_burstPRI)
        self.widget_adw.setLayout(layout)

    def SetToDefault(self):
        self.le_seg.setText('0')
        self.le_freqoffset.setText('0.0')
        self.le_leveloffset.setText('0.0')
        self.le_phaseoffset.setText('0.0')
        self.le_burstN.setText('0')
        self.le_burstPRI.setText('100e-6')

    def checkInput(self, label, lineedit):
        if not lineedit.isEnabled() or lineedit.hasAcceptableInput():
            return True

        msg = QMessageBox()
        msg.setWindowTitle("Invalid Input Data")
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"Please check the value for {label.text()} {lineedit.text()} to be in accordance to the ICD.")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

        return False

    def atof(self, lineedit):
        ret, ok = self.loc_double_validation.toDouble(lineedit.text())
        assert ok, f"Validation with QDoubleValidator succeeded but toDouble() failed (both using the same locale). Problematic value: {lineedit.text()}"
        return ret

    def createXdw(self):
        toa = self.atof(self.le_toa)

        # Check all inputs valid (this has to be done manually, because doubles can be in state QValidator::Intermediate, which is not valid as is but not blockable by the validator)
        inputsValid = True
        inputsValid = inputsValid & self.checkInput(self.l_seg, self.le_seg)
        inputsValid = inputsValid & self.checkInput(self.l_freqoffset, self.le_freqoffset)
        inputsValid = inputsValid & self.checkInput(self.l_leveloffset, self.le_leveloffset)
        inputsValid = inputsValid & self.checkInput(self.l_phaseoffset, self.le_phaseoffset)

        if not inputsValid:
            return

        level_offset = self.atof(self.le_leveloffset)
        freq_offset = self.atof(self.le_freqoffset)
        phase_offset = self.atof(self.le_phaseoffset)
        # address pre-calculated segment
        if self.cb_SEG.isChecked():
            segment = int(self.le_seg.text())
            new_pdw = adw.Adw(seg_interrupt=0, payload=xdw_payload.XdwPayloadSegmentArb(segment),
                              level_offset=level_offset, freq_offset=freq_offset, phase_offset=phase_offset)

        return new_pdw.get_xdw()

class CdwTab(QWidget):
    def __init__(self, parent=None):
        super(CdwTab, self).__init__(parent)

        self.val_fval         = QDoubleValidator(0, (1 << 40) - 1, 10)
        self.val_lval         = QDoubleValidator(-((1 << 7) - 1), (1 << 7) - 1, 2)

        self.loc_double_validation = QLocale("en")
        self.val_fval.setLocale(self.loc_double_validation)
        self.val_lval.setLocale(self.loc_double_validation)

        self.layout = QVBoxLayout()

        self.initWidgetCommon()

        self.layout.addWidget(self.widget_common)

        self.setLayout(self.layout)
        self.setWindowTitle("xDW streaming demo")
        self.SetToDefault()

    def initWidgetCommon(self):
        self.widget_common = QWidget()
        layout = QFormLayout()

        self.l_freq = QLabel("RF Frequency: [Hz]")
        self.le_freq = QLineEdit()
        self.l_level = QLabel("RF Level: [dBm]")
        self.le_level = QLineEdit()
        self.l_path = QLabel("Path:")
        self.cb_path = QComboBox()
        self.cb_path.addItems(["A", "B"])

        self.le_freq.setValidator(self.val_fval)
        self.le_level.setValidator(self.val_lval)

        layout.addRow(self.l_freq, self.le_freq)
        layout.addRow(self.l_level, self.le_level)
        layout.addRow(self.l_path, self.cb_path)
        self.widget_common.setLayout(layout)

    def SetToDefault(self):
        self.le_freq.setText('10e9')
        self.le_level.setText('0.0')
        self.cb_path.setCurrentIndex(0)

    def checkInput(self, label, lineedit):
        if not lineedit.isEnabled() or lineedit.hasAcceptableInput():
            return True

        msg = QMessageBox()
        msg.setWindowTitle("Invalid Input Data")
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"Please check the value for {label.text()} {lineedit.text()} to be in accordance to the ICD.")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

        return False

    def atof(self, lineedit):
        ret, ok = self.loc_double_validation.toDouble(lineedit.text())
        assert ok, f"Validation with QDoubleValidator succeeded but toDouble() failed (both using the same locale). Problematic value: {lineedit.text()}"
        return ret

    def createXdw(self):
        # Check all inputs valid (this has to be done manually, because doubles can be in state QValidator::Intermediate, which is not valid as is but not blockable by the validator)
        inputsValid = True
        inputsValid = inputsValid & self.checkInput(self.l_freq, self.le_freq)
        inputsValid = inputsValid & self.checkInput(self.l_level, self.le_level)

        if not inputsValid:
            return

        freq = self.atof(self.le_freq)
        level = self.atof(self.le_level)
        path = self.cb_path.currentIndex()
        new_pdw = ctrl_xdw.Cdw(cmd=ctrl_xdw.CtrlXdwCmd.FREQ_AMPL, path=path, fval=freq, lval=level)

        return new_pdw.get_xdw()

class BasicPdwTab(QWidget):
    def __init__(self, parent=None):
        super(BasicPdwTab, self).__init__(parent)

        self.val_toa_basic    = QDoubleValidator(0, ((1 << 44) - 1) / 2.4e9, 10)
        self.val_freq_offset  = QDoubleValidator(-2.4e9 / 2, 2.4e9 * (1/2 - 1/(1 << 32)), 10)
        self.val_level_offset = QDoubleValidator(0, math.inf, 10)
        self.val_phase_offset = QDoubleValidator(0, 360 * (1 - 1/(1 << 16)), 10)
        self.val_segment      = QIntValidator(0, (1 << 24) - 1)
        self.val_t_on25       = QDoubleValidator(0, ((1 << 25) - 1) / 2.4e9, 10)
        self.val_t_on44       = QDoubleValidator(0, ((1 << 44) - 1) / 2.4e9, 10)
        self.val_freq_inc     = QDoubleValidator(-2.4e9, 2.4e9, 10)
        self.val_barker_code  = QIntValidator(0, 8)

        self.loc_double_validation = QLocale("en")
        self.val_toa_basic.setLocale(self.loc_double_validation)
        self.val_freq_offset.setLocale(self.loc_double_validation)
        self.val_level_offset.setLocale(self.loc_double_validation)
        self.val_phase_offset.setLocale(self.loc_double_validation)
        self.val_segment.setLocale(self.loc_double_validation)
        self.val_t_on25.setLocale(self.loc_double_validation)
        self.val_t_on44.setLocale(self.loc_double_validation)
        self.val_freq_inc.setLocale(self.loc_double_validation)
        self.val_barker_code.setLocale(self.loc_double_validation)

        self.layout = QVBoxLayout()

        self.initWidgetCommon()

        self.layout.addWidget(self.widget_common)

        self.setLayout(self.layout)
        self.setWindowTitle("xDW streaming demo")
        self.bSEG()
        self.SetToDefault()

    def initWidgetCommon(self):
        self.widget_common = QWidget()
        layout = QFormLayout()

        self.l_toa = QLabel("TOA: [s]")
        self.le_toa = QLineEdit()
        self.l_pw = QLabel("Pulse width: [s]")
        self.le_pw = QLineEdit()
        self.l_seg = QLabel("Segment ID: ")
        self.le_seg = QLineEdit()
        self.l_freqoffset = QLabel("Frequency offset: [Hz]")
        self.le_freqoffset = QLineEdit()
        self.l_leveloffset = QLabel("Level offset: [dB]")
        self.le_leveloffset = QLineEdit()
        self.l_phaseoffset = QLabel("Phase offset: [deg]")
        self.le_phaseoffset = QLineEdit()
        self.l_SEG = QLabel("Use ARB Segment")
        self.cb_SEG = QCheckBox()
        self.cb_SEG.stateChanged.connect(self.bSEG)
        self.l_modulation = QLabel("MOP: ")
        self.cb_modulation = QComboBox()
        self.cb_modulation.addItems(["Unmod", "Linear Chirp", "Triangular Chirp", "Barker"])
        self.cb_modulation.currentIndexChanged.connect(self.selectModulation)
        self.l_freqdev = QLabel("Frequency Deviation: [Hz]")
        self.le_freqdev = QLineEdit()
        self.l_barker = QLabel("Barker Code")
        self.le_barker = QLineEdit()

        self.le_toa.setValidator(self.val_toa_basic)
        self.le_seg.setValidator(self.val_segment)
        self.le_freqoffset.setValidator(self.val_freq_offset)
        self.le_leveloffset.setValidator(self.val_level_offset)
        self.le_phaseoffset.setValidator(self.val_phase_offset)
        self.le_freqdev.setValidator(self.val_freq_inc)
        self.le_barker.setValidator(self.val_barker_code)

        layout.addRow(self.l_toa, self.le_toa)
        layout.addRow(self.l_SEG, self.cb_SEG)
        layout.addRow(self.l_pw, self.le_pw)
        layout.addRow(self.l_seg, self.le_seg)
        layout.addRow(self.l_freqoffset, self.le_freqoffset)
        layout.addRow(self.l_leveloffset, self.le_leveloffset)
        layout.addRow(self.l_phaseoffset, self.le_phaseoffset)
        layout.addRow(self.l_modulation, self.cb_modulation)
        layout.addRow(self.l_freqdev, self.le_freqdev)
        layout.addRow(self.l_barker, self.le_barker)
        self.widget_common.setLayout(layout)

    def bSEG(self):
        if self.cb_SEG.isChecked():
            self.le_pw.setEnabled(False)
            self.le_seg.setEnabled(True)
            self.cb_modulation.setEnabled(False)
            self.le_freqdev.setEnabled(False)
            self.le_barker.setEnabled(False)
        else:
            self.le_pw.setEnabled(True)
            self.le_seg.setEnabled(False)
            self.cb_modulation.setEnabled(True)
            self.selectModulation()

    def selectModulation(self):
        if self.cb_modulation.currentIndex() == 0:
            self.le_freqdev.setEnabled(False)
            self.le_barker.setEnabled(False)
            self.le_pw.setValidator(self.val_t_on44)
        elif self.cb_modulation.currentIndex() == 1 or self.cb_modulation.currentIndex() == 2:
            self.le_freqdev.setEnabled(True)
            self.le_barker.setEnabled(False)
            self.le_pw.setValidator(self.val_t_on25)
        else:
            self.le_freqdev.setEnabled(False)
            self.le_barker.setEnabled(True)
            self.le_pw.setValidator(self.val_t_on44)

    def SetToDefault(self):
        self.le_toa.setText('0.0')
        self.cb_SEG.setChecked(False)
        self.le_pw.setText('10e-6')
        self.le_seg.setText('0')
        self.le_freqoffset.setText('0.0')
        self.le_leveloffset.setText('0.0')
        self.le_phaseoffset.setText('0.0')
        self.cb_modulation.setCurrentIndex(0)
        self.le_freqdev.setText('0.0')
        self.le_barker.setText('0000')

    def checkInput(self, label, lineedit):
        if not lineedit.isEnabled() or lineedit.hasAcceptableInput():
            return True

        msg = QMessageBox()
        msg.setWindowTitle("Invalid Input Data")
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"Please check the value for {label.text()} {lineedit.text()} to be in accordance to the ICD.")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

        return False

    def atof(self, lineedit):
        ret, ok = self.loc_double_validation.toDouble(lineedit.text())
        assert ok, f"Validation with QDoubleValidator succeeded but toDouble() failed (both using the same locale). Problematic value: {lineedit.text()}"
        return ret

    def createXdw(self):
        toa = self.atof(self.le_toa)

        # Check all inputs valid (this has to be done manually, because doubles can be in state QValidator::Intermediate, which is not valid as is but not blockable by the validator)
        inputsValid = True
        inputsValid = inputsValid & self.checkInput(self.l_toa, self.le_toa)
        inputsValid = inputsValid & self.checkInput(self.l_pw, self.le_pw)
        inputsValid = inputsValid & self.checkInput(self.l_seg, self.le_seg)
        inputsValid = inputsValid & self.checkInput(self.l_freqoffset, self.le_freqoffset)
        inputsValid = inputsValid & self.checkInput(self.l_leveloffset, self.le_leveloffset)
        inputsValid = inputsValid & self.checkInput(self.l_phaseoffset, self.le_phaseoffset)
        inputsValid = inputsValid & self.checkInput(self.l_freqdev, self.le_freqdev)
        inputsValid = inputsValid & self.checkInput(self.l_barker, self.le_barker)

        if not inputsValid:
            return

        level_offset = self.atof(self.le_leveloffset)
        freq_offset = self.atof(self.le_freqoffset)
        phase_offset = self.atof(self.le_phaseoffset)
        # address pre-calculated segment
        if self.cb_SEG.isChecked():
            segment = int(self.le_seg.text())
            new_pdw = pdw_basic.PdwBasic(toa=toa, payload=xdw_payload.XdwPayloadSegmentArb(segment),
                                    level_offset=level_offset, freq_offset=freq_offset,
                                    phase_offset=phase_offset)
        # real-time Pulse
        else:
            pw = self.atof(self.le_pw)
            # unmod
            if self.cb_modulation.currentIndex() == 0:
                new_pdw = pdw_basic.PdwBasic(toa=toa, payload=xdw_payload.PdwPayloadRtUnmod(t_on=pw),
                                        level_offset=level_offset, freq_offset=freq_offset,
                                        phase_offset=phase_offset)
            # linear chirp
            elif self.cb_modulation.currentIndex() == 1:
                n_samples = int(pw * 2.4e9)
                freq_inc = (2 * self.atof(self.le_freqdev)) / (n_samples - 1)
                new_pdw = pdw_basic.PdwBasic(toa=toa, payload=xdw_payload.PdwPayloadRtChirpLinear(t_on=pw, freq_step=freq_inc),
                                        level_offset=level_offset, freq_offset=freq_offset,
                                        phase_offset=phase_offset)

            # triangular chirp
            elif self.cb_modulation.currentIndex() == 2:
                n_samples = int(pw * 2.4e9)
                freq_inc = (2 * self.atof(self.le_freqdev)) / (n_samples - 1)
                new_pdw = pdw_basic.PdwBasic(toa=toa, payload=xdw_payload.PdwPayloadRtChirpTriangular(t_on=pw, freq_step=freq_inc),
                                        level_offset=level_offset, freq_offset=freq_offset,
                                        phase_offset=phase_offset)
            # barker
            elif self.cb_modulation.currentIndex() == 3:
                barker = int(self.le_barker.text(),2)
                new_pdw = pdw_basic.PdwBasic(toa=toa, payload=xdw_payload.PdwSegmentRtBarker(t_on=pw, code=barker),
                                        level_offset=level_offset, freq_offset=freq_offset,
                                        phase_offset=phase_offset)

        return new_pdw.get_xdw()

class BasicTcdwTab(QWidget):
    def __init__(self, parent=None):
        super(BasicTcdwTab, self).__init__(parent)

        self.val_toa_basic = QDoubleValidator(0, ((1 << 44) - 1) / 2.4e9, 10)
        self.val_fval = QDoubleValidator(0, (1 << 40) - 1, 10)
        self.val_lval = QDoubleValidator(-((1 << 7) - 1), (1 << 7) - 1, 2)

        self.loc_double_validation = QLocale("en")
        self.val_toa_basic.setLocale(self.loc_double_validation)
        self.val_fval.setLocale(self.loc_double_validation)
        self.val_lval.setLocale(self.loc_double_validation)

        self.layout = QVBoxLayout()

        self.initWidgetCommon()

        self.layout.addWidget(self.widget_common)

        self.setLayout(self.layout)
        self.setWindowTitle("xDW streaming demo")
        self.SetToDefault()

    def initWidgetCommon(self):
        self.widget_common = QWidget()
        layout = QFormLayout()

        self.l_toa = QLabel("TOA: [s]")
        self.le_toa = QLineEdit()
        self.l_freq = QLabel("RF Frequency: [Hz]")
        self.le_freq = QLineEdit()
        self.l_level = QLabel("RF Level: [dBm]")
        self.le_level = QLineEdit()
        self.l_path = QLabel("Path:")
        self.cb_path = QComboBox()
        self.cb_path.addItems(["A", "B"])

        self.le_toa.setValidator(self.val_toa_basic)
        self.le_freq.setValidator(self.val_fval)
        self.le_level.setValidator(self.val_lval)

        layout.addRow(self.l_toa, self.le_toa)
        layout.addRow(self.l_freq, self.le_freq)
        layout.addRow(self.l_level, self.le_level)
        layout.addRow(self.l_path, self.cb_path)
        self.widget_common.setLayout(layout)

    def SetToDefault(self):
        self.le_toa.setText('0.0')
        self.le_freq.setText('10e9')
        self.le_level.setText('0.0')
        self.cb_path.setCurrentIndex(0)

    def checkInput(self, label, lineedit):
        if not lineedit.isEnabled() or lineedit.hasAcceptableInput():
            return True

        msg = QMessageBox()
        msg.setWindowTitle("Invalid Input Data")
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"Please check the value for {label.text()} {lineedit.text()} to be in accordance to the ICD.")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

        return False

    def atof(self, lineedit):
        ret, ok = self.loc_double_validation.toDouble(lineedit.text())
        assert ok, f"Validation with QDoubleValidator succeeded but toDouble() failed (both using the same locale). Problematic value: {lineedit.text()}"
        return ret

    def createXdw(self):
        toa = self.atof(self.le_toa)

        # Check all inputs valid (this has to be done manually, because doubles can be in state QValidator::Intermediate, which is not valid as is but not blockable by the validator)
        inputsValid = True
        inputsValid = inputsValid & self.checkInput(self.l_toa, self.le_toa)
        inputsValid = inputsValid & self.checkInput(self.l_freq, self.le_freq)
        inputsValid = inputsValid & self.checkInput(self.l_level, self.le_level)

        if not inputsValid:
            return

        # ctrl PDW
        freq = self.atof(self.le_freq)
        level = self.atof(self.le_level)
        path = self.cb_path.currentIndex()
        new_pdw = ctrl_xdw.TcdwBasic(toa=toa, cmd=ctrl_xdw.CtrlXdwCmd.FREQ_AMPL, path=path, fval=freq, lval=level)

        return new_pdw.get_xdw()

class ExpertPdwTab(QWidget):
    def __init__(self, parent=None):
        super(ExpertPdwTab, self).__init__(parent)

        self.val_toa_expert   = QDoubleValidator(0, ((1 << 52) - 1) / 2.4e9, 10)
        self.val_edge_time    = QDoubleValidator(0, ((1 << 22) - 1) / 2.4e9, 10)
        self.val_burst_pri    = QDoubleValidator(0, ((1 << 32) - 1) / 2.4e9, 10)
        self.val_burst_rep    = QDoubleValidator(0, (1 << 16) - 1, 10)

        self.loc_double_validation = QLocale("en")
        self.val_toa_expert.setLocale(self.loc_double_validation)
        self.val_edge_time.setLocale(self.loc_double_validation)
        self.val_burst_pri.setLocale(self.loc_double_validation)
        self.val_burst_rep.setLocale(self.loc_double_validation)

        self.layout = QGridLayout()

        self.widget_basic = BasicPdwTab()

        self.widget_expert = self.widget_basic.widget_common
        self.initWidgetExpert()

        self.layout.addWidget(self.widget_expert)

        self.setLayout(self.layout)
        self.bParams()
        self.bExtension()

        self.SetToDefault()

    def initWidgetExpert(self):
        #self.widget_expert = QWidget()
        layout = self.widget_expert.layout()
        self.l_extension = QLabel("Use Extension")
        self.cb_extension = QCheckBox()
        self.cb_extension.stateChanged.connect(self.bExtension)

        self.l_params = QLabel("Basic Edge Shaping:")
        self.cb_params = QCheckBox()
        self.cb_params.stateChanged.connect(self.bParams)

        self.l_edgetype = QLabel("Edge Type: ")
        self.cb_edgetype = QComboBox()
        self.cb_edgetype.addItems(["Linear", "Cosine"])

        self.l_multiplier = QLabel("Multiplier: ")
        self.cb_multiplier = QComboBox()
        self.cb_multiplier.addItems(["1x", "8x"])

        self.l_risefalltime = QLabel("Rise/Fall time: [s]")
        self.le_risefalltime = QLineEdit()

        self.l_risetime = QLabel("Rise time: [s]")
        self.le_risetime = QLineEdit()

        self.l_falltime = QLabel("Fall time: [s]")
        self.le_falltime = QLineEdit()

        self.l_burstN = QLabel("Burst additional pulses: ")
        self.le_burstN = QLineEdit()

        self.l_burstPRI = QLabel("Burst PRI: [s]")
        self.le_burstPRI = QLineEdit()

        self.widget_basic.le_toa.setValidator(self.val_toa_expert)
        self.le_risefalltime.setValidator(self.val_edge_time)
        self.le_risetime.setValidator(self.val_edge_time)
        self.le_falltime.setValidator(self.val_edge_time)
        self.le_burstN.setValidator(self.val_burst_rep)
        self.le_burstPRI.setValidator(self.val_burst_pri)

        layout.addRow(self.l_params, self.cb_params)
        layout.addRow(self.l_extension, self.cb_extension)
        layout.addRow(self.l_edgetype, self.cb_edgetype)
        layout.addRow(self.l_multiplier, self.cb_multiplier)
        layout.addRow(self.l_risefalltime, self.le_risefalltime)
        layout.addRow(self.l_risetime, self.le_risetime)
        layout.addRow(self.l_falltime, self.le_falltime)
        layout.addRow(self.l_burstN, self.le_burstN)
        layout.addRow(self.l_burstPRI, self.le_burstPRI)
        self.widget_expert.setLayout(layout)

    def SetToDefault(self):
        self.widget_basic.SetToDefault()
        self.cb_params.setChecked(False)
        self.cb_edgetype.setCurrentIndex(0)
        self.cb_multiplier.setCurrentIndex(0)
        self.le_risefalltime.setText('0.0')
        self.cb_extension.setChecked(False)
        self.le_risetime.setText('0.0')
        self.le_falltime.setText('0.0')
        self.le_burstN.setText('0')
        self.le_burstPRI.setText('100e-6')

    def bParams(self):
        if self.cb_params.isChecked() and self.cb_params.isEnabled():
            self.le_risefalltime.setEnabled(True)
            self.cb_multiplier.setEnabled(True)
            self.cb_edgetype.setEnabled(True)
        else:
            self.le_risefalltime.setEnabled(False)
            if self.cb_extension.isChecked():
                self.cb_multiplier.setEnabled(True)
                self.cb_edgetype.setEnabled(True)
            else:
                self.cb_multiplier.setEnabled(False)
                self.cb_edgetype.setEnabled(False)

    def bExtension(self):
        if self.cb_extension.isChecked():
            self.cb_params.setEnabled(False)
            self.bParams()
            self.le_risetime.setEnabled(True)
            self.le_falltime.setEnabled(True)
            self.le_burstN.setEnabled(True)
            self.le_burstPRI.setEnabled(True)
        else:
            self.cb_params.setEnabled(True)
            self.bParams()
            self.le_risetime.setEnabled(False)
            self.le_falltime.setEnabled(False)
            self.le_burstN.setEnabled(False)
            self.le_burstPRI.setEnabled(False)

    def checkInput(self, label, lineedit):
        if not lineedit.isEnabled() or lineedit.hasAcceptableInput():
            return True

    def atof(self, lineedit):
        ret, ok = self.loc_double_validation.toDouble(lineedit.text())
        assert ok, f"Validation with QDoubleValidator succeeded but toDouble() failed (both using the same locale). Problematic value: {lineedit.text()}"
        return ret

    def createXdw(self):
        toa = self.atof(self.widget_basic.le_toa)

        # Check all inputs valid (this has to be done manually, because doubles can be in state QValidator::Intermediate, which is not valid as is but not blockable by the validator)
        inputsValid = True
        inputsValid = inputsValid & self.checkInput(self.widget_basic.l_toa, self.widget_basic.le_toa)
        inputsValid = inputsValid & self.checkInput(self.widget_basic.l_pw, self.widget_basic.le_pw)
        inputsValid = inputsValid & self.checkInput(self.widget_basic.l_seg, self.widget_basic.le_seg)
        inputsValid = inputsValid & self.checkInput(self.widget_basic.l_freqoffset, self.widget_basic.le_freqoffset)
        inputsValid = inputsValid & self.checkInput(self.widget_basic.l_leveloffset, self.widget_basic.le_leveloffset)
        inputsValid = inputsValid & self.checkInput(self.widget_basic.l_phaseoffset, self.widget_basic.le_phaseoffset)
        inputsValid = inputsValid & self.checkInput(self.widget_basic.l_freqdev, self.widget_basic.le_freqdev)
        inputsValid = inputsValid & self.checkInput(self.widget_basic.l_barker, self.widget_basic.le_barker)
        inputsValid = inputsValid & self.checkInput(self.l_risefalltime, self.le_risefalltime)
        inputsValid = inputsValid & self.checkInput(self.l_risetime, self.le_risetime)
        inputsValid = inputsValid & self.checkInput(self.l_falltime, self.le_falltime)
        inputsValid = inputsValid & self.checkInput(self.l_burstN, self.le_burstN)
        inputsValid = inputsValid & self.checkInput(self.l_burstPRI, self.le_burstPRI)

        if not inputsValid:
            return

        level_offset = self.atof(self.widget_basic.le_leveloffset)
        freq_offset = self.atof(self.widget_basic.le_freqoffset)
        phase_offset = self.atof(self.widget_basic.le_phaseoffset)
        # address pre-calculated segment
        if self.widget_basic.cb_SEG.isChecked():
            segment = int(self.widget_basic.le_seg.text())
            new_pdw = pdw_expert.PdwExpert(toa=toa, payload=xdw_payload.XdwPayloadSegmentArb(segment),
                                           level_offset=level_offset, freq_offset=freq_offset,
                                           phase_offset=phase_offset)
        # real-time Pulse
        else:
            pw = self.atof(self.widget_basic.le_pw)
            # unmod
            if self.widget_basic.cb_modulation.currentIndex() == 0:
                new_pdw = pdw_expert.PdwExpert(toa=toa, payload=xdw_payload.PdwPayloadRtUnmod(t_on=pw),
                                               level_offset=level_offset, freq_offset=freq_offset,
                                               phase_offset=phase_offset)
            # linear chirp
            elif self.widget_basic.cb_modulation.currentIndex() == 1:
                n_samples = int(pw * 2.4e9)
                freq_inc = (2 * self.atof(self.widget_basic.le_freqdev)) / (n_samples - 1)
                if self.cb_extension.isChecked():
                    tr_tf = (self.atof(self.le_risetime) + self.atof(self.le_falltime))
                    if self.cb_multiplier.currentIndex() == 1:
                        tr_tf = tr_tf * 8
                    pw_tr_tf = pw + tr_tf
                    n_samples = int(pw_tr_tf * 2.4e9)
                    freq_inc = (2 * self.atof(self.widget_basic.le_freqdev)) / (n_samples - 1)
                elif self.cb_params.isChecked():
                    tr_tf = 2 * self.atof(self.le_risefalltime)
                    if self.cb_multiplier.currentIndex() == 1:
                        tr_tf = tr_tf * 8
                    pw_tr_tf = pw + tr_tf
                    n_samples = int(pw_tr_tf * 2.4e9)
                    freq_inc = (2 * self.atof(self.widget_basic.le_freqdev)) / (n_samples - 1)

                new_pdw = pdw_expert.PdwExpert(toa=toa, payload=xdw_payload.PdwPayloadRtChirpLinear(t_on=pw, freq_step=freq_inc),
                                               level_offset=level_offset, freq_offset=freq_offset,
                                               phase_offset=phase_offset)
            # triangular chirp
            elif self.widget_basic.cb_modulation.currentIndex() == 2:
                n_samples = int(pw * 2.4e9)
                freq_inc = (2 * self.atof(self.widget_basic.le_freqdev)) / (n_samples - 1)
                if self.cb_extension.isChecked():
                    pw_tr_tf = pw + self.atof(self.le_risetime) + self.atof(self.le_falltime)
                    n_samples = int(pw_tr_tf * 2.4e9)
                    freq_inc = (2 * self.atof(self.widget_basic.le_freqdev)) / (n_samples - 1)
                elif self.cb_params.isChecked():
                    pw_tr_tf = pw + 2 * self.atof(self.le_risefalltime)
                    n_samples = int(pw_tr_tf * 2.4e9)
                    freq_inc = (2 * self.atof(self.widget_basic.le_freqdev)) / (n_samples - 1)

                new_pdw = pdw_expert.PdwExpert(toa=toa, payload=xdw_payload.PdwPayloadRtChirpTriangular(t_on=pw,
                                                                                                        freq_step=freq_inc),
                                               level_offset=level_offset, freq_offset=freq_offset,
                                               phase_offset=phase_offset)
            # barker
            elif self.widget_basic.cb_modulation.currentIndex() == 3:
                barker = int(self.widget_basic.le_barker.text(), 2)
                new_pdw = pdw_expert.PdwExpert(toa=toa,
                                               payload=xdw_payload.PdwSegmentRtBarker(t_on=pw, code=barker),
                                               level_offset=level_offset, freq_offset=freq_offset,
                                               phase_offset=phase_offset)
            if self.cb_extension.isChecked():
                new_pdw.extensions[0] = xdw_extension.XdwExtensionEdge(
                    edge_type=self.cb_edgetype.currentIndex(),
                    multiplier=self.cb_multiplier.currentIndex(),
                    rise_time=self.atof(self.le_risetime),
                    fall_time=self.atof(self.le_falltime)
                )
                if int(self.le_burstN.text()) >= 1:
                    new_pdw.extensions[1] = xdw_extension.XdwExtensionBurst(
                        pri=self.atof(self.le_burstPRI),
                        add_pulses=int(self.le_burstN.text())
                    )
            elif self.cb_params.isChecked():
                new_pdw.param = xdw_extension.PdwParamsEdge(
                    edge_type=self.cb_edgetype.currentIndex(),
                    multiplier=self.cb_multiplier.currentIndex(),
                    rise_fall_time=self.atof(self.le_risefalltime)
                )

        return new_pdw.get_xdw()

class ExpertTcdwTab(QWidget):
    def __init__(self, parent=None):
        super(ExpertTcdwTab, self).__init__(parent)

        self.val_toa_expert = QDoubleValidator(0, ((1 << 52) - 1) / 2.4e9, 10)

        self.loc_double_validation = QLocale("en")
        self.val_toa_expert.setLocale(self.loc_double_validation)

        self.layout = QGridLayout()

        self.widget_basic = BasicTcdwTab()
        self.widget_basic.le_toa.setValidator(self.val_toa_expert)
        self.layout.addWidget(self.widget_basic.widget_common)

        self.setLayout(self.layout)

        self.SetToDefault()

    def SetToDefault(self):
        self.widget_basic.SetToDefault()

    def checkInput(self, label, lineedit):
        if not lineedit.isEnabled() or lineedit.hasAcceptableInput():
            return True

    def atof(self, lineedit):
        ret, ok = self.loc_double_validation.toDouble(lineedit.text())
        assert ok, f"Validation with QDoubleValidator succeeded but toDouble() failed (both using the same locale). Problematic value: {lineedit.text()}"
        return ret

    def createXdw(self):
        toa = self.atof(self.widget_basic.le_toa)

        # Check all inputs valid (this has to be done manually, because doubles can be in state QValidator::Intermediate, which is not valid as is but not blockable by the validator)
        inputsValid = True
        inputsValid = inputsValid & self.checkInput(self.widget_basic.l_toa, self.widget_basic.le_toa)
        inputsValid = inputsValid & self.checkInput(self.widget_basic.l_freq, self.widget_basic.le_freq)

        if not inputsValid:
            return

        # ctrl PDW

        freq = self.atof(self.widget_basic.le_freq)
        level = self.atof(self.widget_basic.le_level)
        path = self.widget_basic.cb_path.currentIndex()
        new_pdw = ctrl_xdw.TcdwExpert(toa=toa, cmd=ctrl_xdw.CtrlXdwCmd.FREQ_AMPL, path=path, fval=freq, lval=level)

        return new_pdw.get_xdw()

def main():
    app = QApplication(sys.argv)
    ex = XdwDemoGui()
    ex.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()