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
ADVANCED_MARKERS_PER_SEQUENCER = 2
MAX_SEQUENCERS_PER_STREAM = 3
SYSTEM_CONFIG_TIMEOUT = 120.0

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

    # --- Extended Sequencer Advanced mode (System Config > Mode = Extended Sequencer Advanced) ---
    # 'SEQuencer' is always written in long form: the short form 'SEQ' collides with [:TRIGger]:SEQuence.

    def is_advanced_mode(self):
        return self.query('SCON:MODE?') == 'ESEQ'

    def enable_advanced_mode(self):
        """Switches System Config > Fading/Baseband Config > Mode to Extended Sequencer Advanced and applies it.

        SCON:MODE? can report ESEQ before it has been applied, so this always sends SCON:APPLy.
        Re-applying when already active is quick and keeps the loaded sequencer files.
        """
        self.write('SCON:MODE ESEQ')
        self.write('SCON:APPL')
        self.sock.settimeout(SYSTEM_CONFIG_TIMEOUT)
        try:
            self.wait()
        finally:
            self.sock.settimeout(self.timeout)
        self.check_errors('Switching to Extended Sequencer Advanced mode')

    def sequencer_count(self):
        return int(self.query('SOUR1:BB:ESEQ:SEQC?'))

    def stream_count(self):
        return int(self.query('SOUR1:BB:ESEQ:STRC?'))

    def read_advanced_config(self):
        """Returns the per-sequencer and per-stream settings currently on the instrument."""
        bb = 'SOUR1:BB:ESEQ'
        num_streams = self.stream_count()
        sequencers = []
        for st in range(1, self.sequencer_count() + 1):
            stream = next((di for di in range(1, num_streams + 1)
                           if self.query(f'{bb}:STR{di}:SEQuencer{st}:STAT?') == '1'), None)
            sequencers.append({
                'file': self.query(f'{bb}:PLAY:SEQuencer{st}:FILE:SEL?').strip('"'),
                'enabled': self.query(f'{bb}:SEQuencer{st}:STAT?') == '1',
                'stream': stream,
                'freq_offset': float(self.query(f'{bb}:SEQuencer{st}:FOFF?')),
                'attenuation': float(self.query(f'{bb}:SEQuencer{st}:ATT?')),
                'trigger_delay': float(self.query(f'{bb}:SEQuencer{st}:TDEL?')),
            })
        outputs = [self.query(f'{bb}:STR{di}:OUTP?') for di in range(1, num_streams + 1)]
        stream_max = [int(self.query(f'{bb}:STR{di}:SEQC? MAX')) for di in range(1, num_streams + 1)]
        self.check_errors('Reading sequencer configuration')
        return {'mode': self.query(f'{bb}:MODE?'), 'sequencers': sequencers, 'stream_outputs': outputs,
                'stream_max_sequencers': stream_max}

    def load_sequencer_file(self, sequencer: int, ps_def_remote_path: str):
        """Loads a .ps_def onto one sequencer in Playback from File mode."""
        bb = 'SOUR1:BB:ESEQ'
        self.enable_advanced_mode()
        if self.query(f'{bb}:MODE?') != 'PLAY':
            self.write(f'{bb}:STAT OFF')
            self.write(f'{bb}:MODE PLAY')
        self.write(f"{bb}:PLAY:SEQuencer{sequencer}:FILE:SEL '{ps_def_remote_path}'")
        self.wait()
        self.check_errors(f'Loading {ps_def_remote_path} onto S{sequencer}')

    def play_sequencers(self, sequencers, stream_outputs, trigger_source='INT', start=True, rf_on=True, log=print):
        """Applies the sequencer/stream settings and arms all sequencers together.

        Playback from File in advanced mode only supports trigger mode Armed Auto, so the sequencers
        wait for a trigger; with start=True an internal trigger is executed so they all start at once.

        sequencers: list of dicts (index 0 = S1) with enabled, stream, freq_offset, attenuation, trigger_delay
        stream_outputs: list (index 0 = stream A) of 'RFA' | 'RFB' | 'NONE'
        """
        bb = 'SOUR1:BB:ESEQ'
        self.enable_advanced_mode()
        self.write(f'{bb}:STAT OFF')
        self.write(f'{bb}:MODE PLAY')
        # Only change mappings that differ: re-assigning a sequencer that is already mapped to a full
        # stream raises 'maximum number of sequencers already achieved'. Unmap first, then map.
        streams = range(1, len(stream_outputs) + 1)
        pairs = [(di, st) for di in streams for st in range(1, len(sequencers) + 1)]
        current = {(di, st): self.query(f'{bb}:STR{di}:SEQuencer{st}:STAT?') == '1' for di, st in pairs}
        wanted = {(di, st): sequencers[st - 1]['stream'] == di for di, st in pairs}
        for di, st in pairs:
            if current[(di, st)] and not wanted[(di, st)]:
                self.write(f'{bb}:STR{di}:SEQuencer{st}:STAT OFF')
        for di in streams:
            assigned = [st for st in range(1, len(sequencers) + 1) if wanted[(di, st)]]
            self.write(f'{bb}:STR{di}:SEQC {min(max(len(assigned), 1), MAX_SEQUENCERS_PER_STREAM)}')
        for di, st in pairs:
            if wanted[(di, st)] and not current[(di, st)]:
                self.write(f'{bb}:STR{di}:SEQuencer{st}:STAT ON')
        used_outputs = set()
        for di, output in zip(streams, stream_outputs):
            assigned = [st for st in range(1, len(sequencers) + 1) if wanted[(di, st)]]
            if not assigned:  # an empty stream can't be routed to an output
                log(f'Stream {chr(64 + di)}: no sequencers')
                continue
            self.write(f'{bb}:STR{di}:OUTP {output}')
            used_outputs.add(output)
            log(f"Stream {chr(64 + di)}: {', '.join(f'S{st}' for st in assigned)} -> {output}")
        self.check_errors('Configuring output streams')
        for st, seq in enumerate(sequencers, start=1):
            self.write(f"{bb}:SEQuencer{st}:STAT {'ON' if seq['enabled'] else 'OFF'}")
            if not seq['enabled']:
                continue
            self.write(f"{bb}:SEQuencer{st}:FOFF {seq['freq_offset']}")
            self.write(f"{bb}:SEQuencer{st}:ATT {seq['attenuation']}")
            self.write(f"{bb}:SEQuencer{st}:TDEL {seq['trigger_delay']}")
            for ch in range(1, ADVANCED_MARKERS_PER_SEQUENCER + 1):
                self.write(f'{bb}:TRIG:SEQuencer{st}:OUTP{ch}:MODE PDW')
            log(f"S{st}: ON, freq offset {seq['freq_offset']:g} Hz, attenuation {seq['attenuation']:g} dB, "
                f"trigger delay {seq['trigger_delay']:g} s")
        self.check_errors('Configuring sequencers')
        log(f'Trigger mode: Armed Auto, source: {trigger_source}')
        self.write(f'{bb}:SEQ AAUT')
        self.write(f'{bb}:TRIG:SOUR {trigger_source}')
        if rf_on:
            for path in sorted(used_outputs - {'NONE'}):
                log(f'RF {path[-1]}: ON')
                self.write(f"OUTP{'1' if path == 'RFA' else '2'}:STAT ON")
        log('Extended Sequencer: ON')
        self.write(f'{bb}:STAT ON')
        self.wait()
        self.check_errors('Starting playback')
        if start:
            log('Executing trigger')
            self.execute_trigger()


def files_for_basename(ps_def_path: str):
    """Returns the .ps_def plus any .ps_adr/.wv files generated alongside it (same base name)."""
    base, _ext = os.path.splitext(ps_def_path)
    return [p for p in (f'{base}.ps_def', f'{base}.ps_adr', f'{base}.wv') if os.path.isfile(p)]
