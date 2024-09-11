from rskfd.iq_data_handling import iqdata
import numpy as np

def Complex2Iqiq(complexList):
    """Returns a list of I/Q samples from a complex list.
    iqiqiqList = Complex2Iqiq(complexList)"""

    f = lambda iq, i: iq.real if i == 0 else iq.imag
    iqiqiqList = [f(iq, i) for iq in complexList for i in range(2)]

    return iqiqiqList

def WriteWv(iqData, fSamplingRate, FileName):
    """Writes a WV file.
    iqData can be a list of complex or list of floats (iqiqiq format mandatory).
    writtenSamples = WriteWv("MyFile.wv",complexList, fs)"""

    import struct
    from datetime import date
    import math
    import logging

    # check if iqData is complex
    if isinstance(iqData[0], complex):
        iqData = Complex2Iqiq(iqData)

    NumberOfSamples = len(iqData) // 2

    # Find maximum magnitude and scale for max to be FullScale (1.0)
    power = []
    for n in range(NumberOfSamples):
        power.append(abs(iqData[2 * n] ** 2 + iqData[2 * n + 1] ** 2))
    scaling = math.sqrt(max(power))

    # normalize to magnitude 1
    iqData = [iq / scaling for iq in iqData]

    # calculate rms in dB (below full scale)
    rms = math.sqrt(sum(power) / NumberOfSamples) / scaling
    rms = abs(20 * math.log10(rms))
    # Convert to int16, use floor function, otherwise distribution is not correct
    iqData = [math.floor(iq * 32767 + .5) for iq in iqData]

    try:
        file = open(FileName, "wb")

        file.write("{TYPE: SMU-WV,0}".encode("ASCII"))
        file.write("{COMMENT: R&S WaveForm, TheAE-RA}".encode("ASCII"))
        file.write(("{DATE: " + str(date.today()) + "}").encode("ASCII"))
        file.write(("{CLOCK:" + str(fSamplingRate) + "}").encode("ASCII"))
        file.write(("{LEVEL OFFS:0,0}").encode("ASCII"))
        file.write(("{SAMPLES:" + str(NumberOfSamples) + "}").encode("ASCII"))
        # TODO: markers
        #     if( m1start > 0 && m1stop > 0)
        #        %Control Length only needed for markers
        #        fprintf(file_id,'%s',['{CONTROL LENGTH:' num2str(data_length) '}']);
        #        fprintf(file_id,'%s',['{CLOCK MARKER:' num2str(fSamplingRate) '}']);
        #        fprintf(file_id,'%s',['{MARKER LIST 1: ' num2str(m1start) ':1;' num2str(m1stop) ':0}']);
        #    end
        file.write(("{WAVEFORM-" + str(4 * NumberOfSamples + 1) + ": #").encode("ASCII"))

        # binary block
        file.write(struct.pack("h" * len(iqData), *iqData))

        file.write("}".encode("ASCII"))

        file.close()
    except:
        logging.error("File (" + FileName + ") write error!")

    return NumberOfSamples

if __name__ == "__main__":
    iq = np.ones(240000)
    iq[120000:] = 0

    WriteWv(iq, 2.4e9, '../pulse1.wv')

