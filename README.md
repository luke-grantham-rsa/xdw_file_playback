Getting started: see the user guide, "Python Script SMW200A Instructions.docx" (in this repository), for
startup instructions (installing Python and the dependencies and launching the GUI) and for how to use the
GUI to generate xDW files and play them on the SMW200A.

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
See "Python Script SMW200A Instructions.docx" for startup and usage instructions.



Setting up the Python environment:

setup_windows.ps1 (Windows) and setup_linux.sh (Linux) create a virtual environment in .venv and install the
packages in requirements.txt into it. Both need Python 3.12 or later (3.12 recommended). Run them from the
repository folder:
  Windows (PowerShell):  powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
  Linux:                 ./setup_linux.sh
Add -Recreate (Windows) or --recreate (Linux) to delete .venv and start over. If Python 3.12 or later is not
installed, the scripts explain how to get it. See the user guide for how to start and use the GUI.



Building a standalone .exe:

The GUI can be packaged into a single xdw_pdw_gui.exe with PyInstaller, so it can be shared with users who do
not have Python installed. Run these commands from the repository folder in PowerShell.

  1. Set up the Python environment with setup_windows.ps1 (see "Setting up the Python environment" above).
  2. Install PyInstaller into the environment:
       .venv\Scripts\python.exe -m pip install pyinstaller
  3. Build the executable:
       .venv\Scripts\python.exe build_exe.py
     The build takes a few minutes and writes dist\xdw_pdw_gui.exe. The build\ and dist\ folders are not
     committed to git.

  Notes:
  - Copy dist\xdw_pdw_gui.exe anywhere to run it. Each launch takes several seconds while it unpacks itself.
  - Some antivirus software flags single-file PyInstaller builds. If that happens, remove '--onefile' in
    build_exe.py to build a dist\xdw_pdw_gui\ folder instead and share the whole folder.
  - If the .exe shows "Unhandled exception in script ... No module named ...", that module is imported at
    runtime and PyInstaller missed it. Add '--collect-submodules', '<package>' to build_exe.py and rebuild.



Release Updates:

Unreleased:
  - Added setup_windows.ps1 and setup_linux.sh, which create the .venv virtual environment and install the
    packages listed in the new requirements.txt. See "Setting up the Python environment" above.
  - Updated rskfd from 0.5.2 to 0.7.2 and numpy from 1.26.3 to 2.5.3. rskfd 0.5.2 imported numpy.NaN when
    reading ARB waveforms, which numpy 2.x removed; rskfd 0.5.3 and later fixed this. numpy 1.26.3 has no
    packages for Python 3.13 and later, so the old versions could not be installed there. Python 3.12 or later
    is now required. rskfd 0.7.2 also no longer installs scipy.

Version 3.2: Release Date: 10/13/26
  - ARB PDWs now apply the 'Frequency Offset', 'Level Offset' and 'Phase Offset' columns. Previously these
    were read for every other pulse type but ignored for 'arb' rows, so every ARB burst played at the
    center frequency with no level or phase offset. ARB rows must now have a value in all three columns
    (use 0 for no offset). The offset plus half the waveform bandwidth must fit within the baseband
    bandwidth of the SMW path. Files generated with earlier versions used zero offsets for ARB PDWs.
  - The Output base name now updates to match the PDW list each time a new .csv is selected. Previously
    it was only filled in the first time, so later lists kept the name of the first one.
  - SMW Playback now routes Baseband A Marker 1 to the T/M/C 1 local connector (Local Connectors A > Routing)
    when playback starts. Previously T/M/C 1 stayed on its default, Symbol Clock A. Only T/M/C 1 is changed.
  - Fixed bug where Tchirp and Barker PDWs failed on frequency/level offsets such as 1e6 or -3.5 and
    truncated fractional offsets. They are now parsed as floats, like the other pulse types.
  - Added build_exe.py, which packages the GUI into a standalone dist\xdw_pdw_gui.exe with PyInstaller so it
    can be shared with users who do not have Python installed. See "Building a standalone .exe" above.
  - Build requirements: bitstring must be below version 5 (version 5.x removed BitArray(<int>), which
    rsxdwstreaming 2.0.0 still uses), and numpy must stay at 1.26.3 (rskfd 0.5.2 imports numpy.NaN, which
    numpy 2.x removed). Both are pinned in the install command above.

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

