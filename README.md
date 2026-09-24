For more detailed information, please open the Python Script SMW200A Instructions.docx

For any issues with this solution, please contact

Luke Grantham -
Application Engineer -
Rohde & Schwarz USA -
luke.grantham@rsa.rohde-schwarz.com -
(619)930-6753

This script was created to convert .csv formatted Pulse Descriptor Word (PDWs) and Timed Control Descriptor Words (TCDWs) to a format that is readable by Rohde & Schwarz vector signal generators. 
Descriptor Words are simple, readable structures that describe a pulse. R&S Pulse Descriptor Words (PDW) can be used to generate pulsed signals in real-time or replay pre-calculated waveform segments. R&S Timed Control Descriptor Words (TCDW) can be used to change instrument RF frequency and/or level or re-arm the Extended Sequencer.

Users provide a .csv with Descriptor Words with information describing a pulse. The script processes the .csv and generates the necessary files to output the pulses on the Rohde & Schwarz SMW200A Vector Signal Generator.
The GUI can then transfer the files to the SMW200A over LAN and play them, on a single baseband or on multiple
sequencers in Extended Sequencer Advanced mode.



Release Updates:

Version 3.1: Release Date: 9/24/26
  - Added an 'SMW Playback' tab that transfers the generated .ps_def, .ps_adr and .wv files to the SMW200A
    over LAN (SCPI on port 5025, default folder /var/user) and plays them with the Extended Sequencer in
    'Playback from File' mode — no more FTP copy or manual Extended Sequencer setup. Choose the trigger
    mode/source, optionally preset the instrument and turn RF on, then Transfer & Play, Execute Trigger or Stop.
  - Added a 'Multi-Sequencer' tab for Extended Sequencer Advanced mode. Load a different scenario onto each
    sequencer (S1-S6, as many as the instrument supports), set per-sequencer stream, frequency offset,
    attenuation and trigger delay, route streams to RF A/RF B, then Play All to start every sequencer together.
    The tab switches System Config > Fading/Baseband Config > Mode to Extended Sequencer Advanced
    automatically. Playback uses trigger mode Armed Auto (the only mode supported for Playback from File in
    advanced mode); with the internal trigger source, Play All fires the trigger so all sequencers start at once.
  - Both instrument tabs share one connection and fill in the last generated .ps_def automatically.
    Instrument control lives in smw_control.py and smw_playback_tabs.py.
  - Fixed bug where the .ps_def stored the full local path of the .wv and .ps_adr files, so the instrument
    could not find them when an absolute output path was used. Only the file names are stored now.
  - Added PDWlist_RF_B.csv, an example PDW list with its TCDW on path 1 (RF B) for multi-sequencer use.
  - Requires the R&S SMW-K503/-K504 options on the SMW200A (checked on connect).

Version 3.0: Release Date: 9/22/26
  - Added a PyQt6 GUI (xdw_pdw_gui.py) that replaces the command line interface. This enables browsing
    for a PDW list .csv, preview PDW/TCDW counts and the raw data before generating anything. Enter the
    output name and comment, and click Generate — no more typing file paths or comments into the terminal.
  - Added support for multiple ARB waveform segments. The value in the 'Pulse Width' column on
    'arb' PDW rows now selects which waveform file to use (0, 1, 2, ...). The GUI lets you add,
    remove, and reorder any number of ARB waveform (.wv) files to match.
  - Renamed xdw_file_playback_v2_3.py to xdw_file_playback.py. Running it now launches the GUI
    directly instead of the old input()-driven CLI flow.
  - Fixed bug where EOF was not placed at the end of the file which was gating automatic replay of the file.
    The instrument now loops without need for external triggering/marker

Version 2.3: Release Date: 2/12/2024
  - Added rffreqlevel option for TCDWs which allows for frequency and level changes with one TCDW. Thanks Yale!

Version 2.2: Release Date: 10/25/2024
  - Added functionality for setting frequency and level for each RF path. Previously, support was for Path 0 only.
      - Please add a column titled "Path" to existing PDW list documents. Path 0 means RF path A and Path 1 means RF Path B. Only TCDWs require this field as the baseband the file is played on will play out all PDWs. 
      - Please reference the PDWlist_verif.xlsx or .csv for example

TODO:
video tutorial

