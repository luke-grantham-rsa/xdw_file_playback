### Rohde & Schwarz Automation for demonstration use.
### Title  : Builds a standalone xdw_pdw_gui.exe with PyInstaller, so the GUI can be shared with
###           users who do not have Python or the rsxdwstreaming/rskfd packages installed.
### Usage  : pip install pyinstaller
###           python build_exe.py
###           The executable is written to dist/xdw_pdw_gui.exe
import os

import PyInstaller.__main__

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(ROOT, 'build')

if __name__ == "__main__":
    PyInstaller.__main__.run([
        os.path.join(ROOT, 'xdw_pdw_gui.py'),
        '--name', 'xdw_pdw_gui',
        '--onefile',
        '--windowed',
        '--noconfirm',
        '--clean',
        # bitstring (used by rsxdwstreaming) imports its storage backend by name at runtime
        '--collect-submodules', 'bitstring',
        '--distpath', os.path.join(ROOT, 'dist'),
        '--workpath', BUILD_DIR,
        '--specpath', BUILD_DIR,
    ])
