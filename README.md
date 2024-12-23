For more detailed information, please open the Python Script SMW200A Instructions.dox

For any issues with this solution, please contact

Luke Grantham -
Application Engineer -
Rohde & Schwarz USA -
luke.grantham@rsa.rohde-schwarz.com -
(619)930-6753

This script was created to convert .csv formatted Pulse Descriptor Word (PDWs) and Timed Control Descriptor Words (TCDWs) to a format that is readable by Rohde & Schwarz vector signal generators. 
Descriptor Words are simple, readable structures that describe a pulse. R&S Pulse Descriptor Words (PDW) can be used to generate pulsed signals in real-time or replay pre-calculated waveform segments. R&S Timed Control Descriptor Words (TCDW) can be used to change instrument RF frequency and/or level or re-arm the Extended Sequencer.

Users provide a .csv with Descriptor Words with information describing a pulse. The script processes the .csv and generates the necessary files to output the pulses on the Rohde & Schwarz SMW200A Vector Signal Generator.



Release Updates:

Version 2.2: Release Date: 10/25/2024
  - Added functionality for setting frequency and level for each RF path. Previously, support was for Path 0 only.
      - Please add a column titled "Path" to existing PDW list documents. Path 0 means RF path A and Path 1 means RF Path B. Only TCDWs require this field as the baseband the file is played on will play out all PDWs. 
      - Please reference the PDWlist_verif.xlsx or .csv for example
