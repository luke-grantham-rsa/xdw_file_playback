### Rohde & Schwarz Automation for demonstration use.
### Title  : Minimal SCPI-over-LAN control of the SMW200A for transferring xDW files
###           (.ps_def, .ps_adr, .wv) and playing them with the Extended Sequencer
###           in 'Playback from File' mode.
import os
import socket

SCPI_PORT = 5025
DEFAULT_REMOTE_DIR = '/var/user'
UPLOAD_CHUNK_BYTES = 1024 * 1024
NUM_MARKERS = 3

TRIGGER_MODES = {
    'Auto': 'AUTO',
    'Retrigger': 'RETR',
    'Armed Auto': 'AAUT',
    'Armed Retrigger': 'ARET',
    'Single': 'SING',
}

TRIGGER_SOURCES = {
    'Internal': 'INT',
    'External Global Trigger 1': 'EGT1',
    'External Global Trigger 2': 'EGT2',
}


class ScpiError(Exception):
    pass


class SmwInstrument:
    def __init__(self, host: str, port: int = SCPI_PORT, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.reader = None

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.reader = self.sock.makefile('rb')
        self.write('*CLS')
        return self.query('*IDN?')

    def close(self):
        if self.sock:
            try:
                self.reader.close()
                self.sock.close()
            finally:
                self.sock = None
                self.reader = None

    def write(self, cmd: str):
        self.sock.sendall((cmd + '\n').encode())

    def query(self, cmd: str) -> str:
        self.write(cmd)
        response = self.reader.readline()
        while response.count(b'"') % 2:  # quoted strings (e.g. error messages) can contain newlines
            response += self.reader.readline()
        return response.decode().strip()

    def wait(self):
        """Blocks until all previous commands have completed."""
        self.query('*OPC?')

    def check_errors(self, context: str = ''):
        """Raises ScpiError if the instrument error queue is not empty."""
        response = self.query('SYST:ERR:ALL?')
        if not response.startswith('0,'):
            raise ScpiError(f"{context}: {response}" if context else response)

    def options(self):
        return set(self.query('*OPT?').split(','))

    def upload_file(self, local_path: str, remote_dir: str = DEFAULT_REMOTE_DIR, progress=None):
        """Writes a local file to the instrument with MMEM:DATA as an IEEE 488.2 binary block."""
        with open(local_path, 'rb') as f:
            data = f.read()
        remote_path = f"{remote_dir.rstrip('/')}/{os.path.basename(local_path)}"
        length = str(len(data))
        self.sock.sendall(f"MMEM:DATA '{remote_path}',#{len(length)}{length}".encode())
        for offset in range(0, len(data), UPLOAD_CHUNK_BYTES):
            self.sock.sendall(data[offset:offset + UPLOAD_CHUNK_BYTES])
            if progress:
                progress(min(offset + UPLOAD_CHUNK_BYTES, len(data)), len(data))
        self.sock.sendall(b'\n')
        self.wait()
        self.check_errors(f"Uploading {remote_path}")
        return remote_path

    def play_file(self, ps_def_remote_path: str, trigger_mode: str = 'AUTO', trigger_source: str = 'INT',
                  preset: bool = False, rf_on: bool = True, baseband: int = 1, log=print):
        """Loads a .ps_def in Extended Sequencer 'Playback from File' mode and starts playback."""
        bb = f'SOUR{baseband}:BB:ESEQ'
        if preset:
            log('Presetting instrument')
            self.write('*RST')
            self.wait()
        log('Extended Sequencer mode: Playback from File')
        self.write(f'{bb}:STAT OFF')
        self.write(f'{bb}:MODE PLAY')
        log(f'Definition file: {ps_def_remote_path}')
        self.write(f"{bb}:PLAY:FILE '{ps_def_remote_path}'")
        self.wait()
        self.check_errors('Loading definition file')
        log(f'Trigger mode: {trigger_mode}, source: {trigger_source}')
        self.write(f'{bb}:SEQ {trigger_mode}')
        self.write(f'{bb}:TRIG:SOUR {trigger_source}')
        log('Markers: PDW')
        for ch in range(1, NUM_MARKERS + 1):
            self.write(f'{bb}:TRIG:OUTP{ch}:MODE PDW')
        self.check_errors('Configuring trigger/markers')
        if rf_on:
            log(f'RF {baseband}: ON')
            self.write(f'OUTP{baseband}:STAT ON')
        log('Extended Sequencer: ON')
        self.write(f'{bb}:STAT ON')
        self.wait()
        self.check_errors('Starting playback')

    def execute_trigger(self, baseband: int = 1):
        self.write(f'SOUR{baseband}:BB:ESEQ:TRIG:EXEC')
        self.wait()
        self.check_errors('Execute trigger')

    def stop(self, baseband: int = 1):
        self.write(f'SOUR{baseband}:BB:ESEQ:STAT OFF')
        self.wait()
        self.check_errors('Stopping playback')

    def set_rf(self, on: bool, baseband: int = 1):
        self.write(f"OUTP{baseband}:STAT {'ON' if on else 'OFF'}")
        self.wait()
        self.check_errors('Setting RF state')


def files_for_basename(ps_def_path: str):
    """Returns the .ps_def plus any .ps_adr/.wv files generated alongside it (same base name)."""
    base, _ext = os.path.splitext(ps_def_path)
    return [p for p in (f'{base}.ps_def', f'{base}.ps_adr', f'{base}.wv') if os.path.isfile(p)]
