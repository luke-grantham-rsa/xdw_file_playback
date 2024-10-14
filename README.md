For more detailed information, please open the Python Script SMW200A Instructions.dox

R&S SMW200A CSV TO XDW PYTHON SCRIPT INSTRUCTIONS
For any issues with this solution, please contact:
    Luke Grantham
    Application Engineer 
    Rohde & Schwarz USA
    luke.grantham@rsa.rohde-schwarz.com
    (619)930-6753

This script was created to convert .csv formatted Pulse Descriptor Word (PDWs) and Timed Control Descriptor Words (TCDWs) to a format that is readable by Rohde & Schwarz vector signal generators. 
Descriptor Words are simple, readable structures that describe a pulse. R&S Pulse Descriptor Words (PDW) can be used to generate pulsed signals in real-time or replay pre-calculated waveform segments. R&S Timed Control Descriptor Words (TCDW) can be used to change instrument RF frequency and/or level or re-arm the Extended Sequencer.

Customers provide a .csv with Descriptor Words with information describing a pulse. The script processes the .csv and generates the necessary files to output the pulses on the Rohde & Schwarz SMW200A Vector Signal Generator.
