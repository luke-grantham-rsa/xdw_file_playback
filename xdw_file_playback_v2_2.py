### Rohde & Schwarz Automation for demonstration use.
### Title  : Creates xDW (PDW and TCDW) List, Container Waveform and Address Look-Up files for direct import into SMW200A
### Date   : 2024/06/06
### HW Config: SMW200A vector signal generator with FW version 5.30.047.xx or later and
### SMW Options:-B9, -B13XT,-K502,-K503,-K525,-K527
from rsxdwstreaming import xdw, pdw_expert, ctrl_xdw, xdw_payload, xdw_extension
from datetime import datetime
from rskfd.iq_data_handling import iqdata
import numpy as np
from enum import Enum
from create_pulse import WriteWv
import csv



class XdwList:
    def __init__(self, filename: str = 'IQ'):
        self.filename = filename
        self.b = bytearray()
        self.b_pdw_raw = bytearray()

        self.init_bytearray()

    def init_bytearray(self):
        self.b.extend('PDW'.encode())
        self.b.extend([0])  # stream ID
        self.b.extend([0])  # target ID, base band index
        # self.b.extend([int('12', 16)])  # version & sysclock
        self.b.extend([0])  # version & sysclock
        self.b.extend([0])  # skip segments

        wv_name = f'{self.filename}.wv'.encode()
        if has_arb_pdw:
            self.b.extend(wv_name)
            self.b.extend([0] * (256 - len(wv_name)))
        else:
            self.b.extend([0] * (256))

        adr_name = f'{self.filename}.ps_adr'.encode()
        if has_arb_pdw:
            self.b.extend(adr_name)
            self.b.extend([0] * (256 - len(adr_name)))
        else:
            self.b.extend([0] * (256))

        # write date and time
        now = datetime.now()
        now_enc = now.strftime('%d.%m.%Y %H:%M').encode()
        self.b.extend(now_enc)
        self.b.extend([0] * (64 - len(now_enc)))

        # comment
        #comment_name = 'python generated'.encode()
        comment_name = input("Please enter comments: ").encode()
        self.b.extend(comment_name)
        self.b.extend([0] * (256 - len(comment_name)))

        # self.b.extend(np.uint32(0).byteswap())  # bandwidth
        # self.b.extend(np.uint64(1).byteswap())  # nof PDWs
        # self.b.extend([255] * (256 - 12))  # reserved
        self.b.extend([255] * 256)  # reserved

    def append_xdw(self, pdw):
        # add PDWs
        self.b_pdw_raw += pdw.get_xdw()

    def write_ps_def(self):
        """filename shall be absolute path"""
        ps_def = open(f'{self.filename}.ps_def', "wb")
        print(f'Generating {self.filename}.ps_def')
        ps_def.write(self.b)
        ps_def.write(bytes(self.b_pdw_raw))
        ps_def.close()

class ContainerWv:
    def __init__(self, filename: str = 'IQ'):
        self.filename = filename
        self.filename_list = []
        self.iqdata = []
        self.num_elements = 0
        self.sampling_rate = 0

    def append_wv(self, new_iq, segment_name):
        self.iqdata.extend(new_iq)
        self.filename_list.append(segment_name)
        self.num_elements += 1

    def write_container_wv(self):
        WriteWv(self.iqdata, self.sampling_rate, f'{self.filename}.wv')
        print(f'Generating {self.filename}.wv')

class LookUp:
    def __init__(self, filename):
        self.filename = filename
        self.next_start_bit = 0
        self.seg_samples_bits = 0
        self.b = bytearray()
        self.init_look_up()

    def init_look_up(self):
        self.b.extend('ADR'.encode())
        self.b.extend([1])  # version & sysclock
        self.b.extend(int(2).to_bytes(4, 'little'))  # rsvd
        self.b.extend(int(3).to_bytes(4, 'little'))  # rsvd
        self.b.extend(int(4).to_bytes(4, 'little'))  # rsvd
        self.b.extend(int(5).to_bytes(4, 'little'))  # rsvd
        self.b.extend(int(6).to_bytes(4, 'little'))  # rsvd
        self.b.extend(int(7).to_bytes(4, 'little'))  # rsvd
        self.b.extend(int(8).to_bytes(4, 'little'))  # rsvd

    def write_ps_adr(self):
        """filename shall be absolute path"""
        ps_adr = open(f'{self.filename}.ps_adr', "wb")
        print(f'Generating {self.filename}.ps_adr')
        ps_adr.write(self.b)
        ps_adr.close()

    def add_address(self, segment_length):
        new_address = bytearray()
        start_address = self.next_start_bit
        self.seg_samples_bits += segment_length * 4 * 8 # 4 bytes per sample, 8 bits per byte
        pad_bits = (32 - (segment_length%32))%32
        stop_address = self.seg_samples_bits - 1
        new_address.extend((start_address<<4).to_bytes(5, 'big'))
        new_address.extend((stop_address<<4).to_bytes(5, 'big'))
        new_address.extend(int(0).to_bytes(6, 'big'))

        self.seg_samples_bits += pad_bits
        self.next_start_bit = stop_address + 1
        self.b.extend(new_address)

class XdwFilePlayback:
    def __init__(self, filename: str = ''):
        self.filename = filename
        self.xdw_list = XdwList(filename)
        self.container_wv = ContainerWv(filename)
        self.look_up = LookUp(filename)

    def append_entry(self, new_xdw: xdw.Xdw, arb_segment: str = ''):
        if arb_segment and (new_xdw.payload.__class__ == xdw_payload.XdwPayloadSegmentArb):
            if arb_segment not in self.container_wv.filename_list:
                new_iq, self.container_wv.sampling_rate = iqdata.ReadWv(arb_segment)
                if len(new_iq) % 8: # this zero padding is to assure that the stop address fulfills the condition (n*256) - 1
                    pad_bits = 8 - (len(new_iq)%8)
                    new_iq.extend(pad_bits * [0+0j])
                self.look_up.add_address(len(new_iq)) #add iq samples before zero padding, so that stop address is not including zeros
                if len(new_iq) % 128:
                    pad_bits = 128 - (len(new_iq)%128)
                    new_iq.extend(pad_bits * [0+0j])
                self.container_wv.append_wv(new_iq, arb_segment)
            idx = self.container_wv.num_elements - 1 # TODO: return correct index
            new_xdw.payload.segment_idx = idx
        self.xdw_list.append_xdw(new_xdw)



    def generate_files(self):
        self.xdw_list.write_ps_def()
        if self.container_wv.iqdata: #if we need to generate wv file
            self.container_wv.write_container_wv()
            self.look_up.write_ps_adr()


"""Method for finding substring in list. Used for column indexing."""
def index_containing_substring(the_list, substring):
    for i, s in enumerate(the_list):
        if substring in s:
            return i
    return -1


"""if __name__ == "__main__":
    file_playback = XdwFilePlayback('IQ_expert')
    arb_file1 = 'pulse1.wv'
    pdw1 = pdw_expert.PdwExpert(toa=0, payload=xdw_payload.XdwPayloadSegmentArb(segment_idx=0))
    file_playback.append_entry(pdw1, arb_file1)

    pdw2 = pdw_expert.PdwExpert(toa=200e-6, payload=xdw_payload.XdwPayloadSegmentArb(segment_idx=0))
    file_playback.append_entry(pdw2, arb_file1)

    arb_file2 = 'pulse2.wv'
    pdw3 = pdw_expert.PdwExpert(toa=400e-6, payload=xdw_payload.XdwPayloadSegmentArb(segment_idx=0))
    file_playback.append_entry(pdw3, arb_file2)

    pdw4 = pdw_expert.PdwExpert(toa=600e-6, payload=xdw_payload.PdwPayloadRtUnmod(t_on=8e-6))
    file_playback.append_entry(pdw4)

    cdw1 = ctrl_xdw.TcdwExpert(toa = 1e-3, path=0, fval = 4e9, cmd=ctrl_xdw.CtrlXdwCmd.FREQ)
    file_playback.append_entry(cdw1)
#
    pdw5 = pdw_expert.PdwExpert(toa=5e-3, payload=xdw_payload.XdwPayloadSegmentArb(segment_idx=0))
    file_playback.append_entry(pdw5, arb_file2)
#
    cdw2 = ctrl_xdw.TcdwExpert(toa=10e-3, path=0, fval=5e9, cmd=ctrl_xdw.CtrlXdwCmd.FREQ)
    file_playback.append_entry(cdw2)

    cdw3 = ctrl_xdw.TcdwExpert(toa=20e-3  - (1 / 2.4e9),  cmd=ctrl_xdw.CtrlXdwCmd.EOF)
    file_playback.append_entry(cdw3)

    file_playback.generate_files()"""

if __name__ == "__main__":
    print(r"""
 _____   ____  _    _ _____  ______             _____  _____ _    ___          __     _____   ______
 |  __ \ / __ \| |  | |  __ \|  ____|   ___     / ____|/ ____| |  | \ \        / /\   |  __ \ |___  /
 | |__) | |  | | |__| | |  | | |__     ( _ )   | (___ | |    | |__| |\ \  /\  / /  \  | |__) |   / / 
 |  _  /| |  | |  __  | |  | |  __|    / _ \/\  \___ \| |    |  __  | \ \/  \/ / /\ \ |  _  /   / /  
 | | \ \| |__| | |  | | |__| | |____  | (_>  <  ____) | |____| |  | |  \  /\  / ____ \| | \ \  / /__ 
 |_|  \_\\____/|_|  |_|_____/|______|  \___/\/ |_____/ \_____|_|  |_|   \/  \/_/    \_\_|  \_\/_____|
 
               \_/ |  \ |  |    /__`  |  |__) |__   /\   |\/| | |\ | / _` 
               / \ |__/ |/\|    .__/  |  |  \ |___ /~~\  |  | | | \| \__> 
                                                                                                      
                    """)


    print('Welcome to the Rohde & Schwarz XDW Streaming CSV Conversion Tool.')
    print('This Tool creates xDW (PDW and TCDW) List, Container Waveform, and Address Look-Up files for direct import into SMW200A.')
    pdw_list = input("Please enter your PDW List .csv file: ")
    has_arb_pdw = 0
    with open(pdw_list, newline='') as csvfile: #scan file for arb PDWs.
        csvreader = csv.reader(csvfile, delimiter=',', quotechar='|')
        header = next(csvreader)
        for row in csvreader:
            if row[index_containing_substring(header, 'Type')] == 'pdw':
                if row[index_containing_substring(header, 'Mod')] == 'arb':
                    has_arb_pdw = 1
                    break



    arb_files = ['pulse1.wv', 'pulse2.wv']
    has_EOF = 0
    file_playback = XdwFilePlayback('IQ_expert')
    #with open('PDWlist.csv', newline='') as csvfile:
    with open(pdw_list, newline='') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',', quotechar='|')
        header = next(csvreader)
        for row in csvreader:
            if row[index_containing_substring(header, 'Type')] == 'pdw':
                print(f"Processing {row[index_containing_substring(header, 'Type')]} with {row[index_containing_substring(header, 'Mod')]} waveform with {row[index_containing_substring(header, 'Number of Pulses')]} pulse(s).")
                if int(row[index_containing_substring(header, 'Number of Pulses')]) == 0:
                    continue
                if row[index_containing_substring(header, 'Mod')] == 'arb':
                    pdw = pdw_expert.PdwExpert(toa=float(row[index_containing_substring(header,'TOA')]),
                                               payload=xdw_payload.XdwPayloadSegmentArb(segment_idx=0),
                                               extension3=xdw_extension.XdwExtensionBurst(pri=float(row[index_containing_substring(header, 'Burst PRI')]),
                                                                                          add_pulses=int(row[index_containing_substring(header, 'Number of Pulses')]) - 1),
                                               m1=float(row[index_containing_substring(header, 'Marker 1')]),
                                               m2=float(row[index_containing_substring(header, 'Marker 2')]),
                                               m3=float(row[index_containing_substring(header, 'Marker 3')]))
                    file_playback.append_entry(pdw,arb_files[0])
                if row[index_containing_substring(header, 'Mod')] == "Rectangular":
                    pdw = pdw_expert.PdwExpert(toa=float(row[index_containing_substring(header, 'TOA')]),
                                               payload=xdw_payload.PdwPayloadRtUnmod(t_on=float(row[index_containing_substring(header,'Pulse Width')])),
                                               extension3=xdw_extension.XdwExtensionBurst(pri=float(row[index_containing_substring(header, 'Burst PRI')]),
                                                                                          add_pulses=int(row[index_containing_substring(header, 'Number of Pulses')]) - 1),
                                               freq_offset=float(row[index_containing_substring(header,'Frequency Offset')]),
                                               level_offset=float(row[index_containing_substring(header,'Level Offset')]),
                                               phase_offset=float(row[index_containing_substring(header,'Phase Offset')]),
                                               m1=float(row[index_containing_substring(header,'Marker 1')]),
                                               m2=float(row[index_containing_substring(header, 'Marker 2')]),
                                               m3=float(row[index_containing_substring(header, 'Marker 3')]))
                    file_playback.append_entry(pdw)
                if row[index_containing_substring(header, 'Mod')] == "Linear Chirp":
                    pdw = pdw_expert.PdwExpert(toa=float(row[index_containing_substring(header, 'TOA')]),
                                               payload=xdw_payload.PdwPayloadRtChirpLinear(t_on=float(row[index_containing_substring(header,'Pulse Width')]),
                                                                                           freq_step=float(row[index_containing_substring(header,'Freq Step')])),
                                               extension3=xdw_extension.XdwExtensionBurst(pri=float(row[index_containing_substring(header, 'Burst PRI')]),
                                                                                          add_pulses=int(row[index_containing_substring(header, 'Number of Pulses')]) - 1),
                                               freq_offset=float(row[index_containing_substring(header,'Frequency Offset')]),
                                               level_offset=float(row[index_containing_substring(header,'Level Offset')]),
                                               phase_offset=float(row[index_containing_substring(header,'Phase Offset')]),
                                               m1=float(row[index_containing_substring(header, 'Marker 1')]),
                                               m2=float(row[index_containing_substring(header, 'Marker 2')]),
                                               m3=float(row[index_containing_substring(header, 'Marker 3')]))
                    file_playback.append_entry(pdw)
                if row[index_containing_substring(header, 'Mod')] == "Tchirp":
                    pdw = pdw_expert.PdwExpert(toa=float(row[index_containing_substring(header, 'TOA')]),
                                               payload=xdw_payload.PdwPayloadRtChirpTriangular(t_on=float(row[index_containing_substring(header,'Pulse Width')]),
                                                                                               freq_step=float(row[index_containing_substring(header,'Freq Step')])),
                                               extension3=xdw_extension.XdwExtensionBurst(pri=float(row[index_containing_substring(header, 'Burst PRI')]),
                                                                                          add_pulses=int(row[index_containing_substring(header, 'Number of Pulses')]) - 1),
                                               freq_offset=int(row[index_containing_substring(header,'Frequency Offset')]),
                                               level_offset=int(row[index_containing_substring(header,'Level Offset')]),
                                               phase_offset=float(row[index_containing_substring(header,'Phase Offset')]),
                                               m1=float(row[index_containing_substring(header, 'Marker 1')]),
                                               m2=float(row[index_containing_substring(header, 'Marker 2')]),
                                               m3=float(row[index_containing_substring(header, 'Marker 3')]))
                    file_playback.append_entry(pdw)
                if row[index_containing_substring(header, 'Mod')] == "Barker":
                    pdw = pdw_expert.PdwExpert(toa=float(row[index_containing_substring(header, 'TOA')]),
                                               payload=xdw_payload.PdwPayloadRtBarker(chip_width=float(row[index_containing_substring(header,'Chip Width')]),
                                                                                      code=int(row[index_containing_substring(header,'Bkr Code')]),
                                                                                      stuff=int(row[index_containing_substring(header,'Stuff')])),
                                               extension3=xdw_extension.XdwExtensionBurst(pri=float(row[index_containing_substring(header, 'Burst PRI')]),
                                                                                          add_pulses=int(row[index_containing_substring(header, 'Number of Pulses')]) - 1),
                                               freq_offset=int(row[index_containing_substring(header,'Frequency Offset')]),
                                               level_offset=int(row[index_containing_substring(header,'Level Offset')]),
                                               phase_offset=float(row[index_containing_substring(header,'Phase Offset')]),
                                               m1=float(row[index_containing_substring(header, 'Marker 1')]),
                                               m2=float(row[index_containing_substring(header, 'Marker 2')]),
                                               m3=float(row[index_containing_substring(header, 'Marker 3')]))
                    file_playback.append_entry(pdw)
            if row[index_containing_substring(header, 'Type')] == "tcdw":
                if row[index_containing_substring(header, 'RF')] == "rffreq":
                    print(f"Processing {row[index_containing_substring(header, 'Type')]} to set frequency to {row[index_containing_substring(header, 'RF Freq')]} Hz on path {row[index_containing_substring(header, 'Path')]}")
                    cdw = ctrl_xdw.TcdwExpert(toa=float(row[index_containing_substring(header, 'TOA')]),
                                              path=int(row[index_containing_substring(header, 'Path')]),
                                              fval=float(row[index_containing_substring(header, 'RF Freq')]),
                                              cmd=ctrl_xdw.CtrlXdwCmd.FREQ)
                    file_playback.append_entry(cdw)
                if row[index_containing_substring(header, 'RF')] == "rflevel":
                    print(f"Processing {row[index_containing_substring(header, 'Type')]} to change level to {row[index_containing_substring(header, 'Level')]} dBm on path {row[index_containing_substring(header, 'Path')]}")
                    cdw = ctrl_xdw.TcdwExpert(toa=float(row[index_containing_substring(header, 'TOA')]),
                                              path=int(row[index_containing_substring(header, 'Path')]),
                                              lval=float(row[index_containing_substring(header, 'Level')]),
                                              cmd=ctrl_xdw.CtrlXdwCmd.AMPL)
                    file_playback.append_entry(cdw)
                if row[index_containing_substring(header, 'Mod')] == "EOF":
                    print(f"Processing {row[index_containing_substring(header, 'Type')]} for {row[index_containing_substring(header, 'Mod')]}")
                    cdw = ctrl_xdw.TcdwExpert(toa=20e-3  - (1 / 2.4e9),
                                              cmd=ctrl_xdw.CtrlXdwCmd.EOF)
                    file_playback.append_entry(cdw)
                    has_EOF = 1

    if has_EOF == 0:  #if no EOF at the end of the PDW list, append one.
        print(f"Appending EOF TCDW")
        cdw = ctrl_xdw.TcdwExpert(toa=20e-3 - (1 / 2.4e9),
                                  cmd=ctrl_xdw.CtrlXdwCmd.EOF)
        file_playback.append_entry(cdw)
    file_playback.generate_files()
    print(f'--------Successfully generated files-----------')
