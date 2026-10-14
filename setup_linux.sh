#!/usr/bin/env bash
### Rohde & Schwarz Automation for demonstration use.
### Title  : Sets up the Python environment for xdw_file_playback.py on Linux.
###           Creates a virtual environment in .venv and installs requirements.txt into it.
### Usage  : ./setup_linux.sh              (create .venv, or update the existing one)
###           ./setup_linux.sh --recreate   (delete .venv and start over)
###           Set PYTHON to choose the interpreter, e.g. PYTHON=python3.12 ./setup_linux.sh
###           Requires Python 3.12 or later (3.12 recommended).
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"
VENV_DIR=.venv

RECREATE=0
if [[ "${1:-}" == "--recreate" ]]; then
    RECREATE=1
elif [[ -n "${1:-}" ]]; then
    echo "Unknown option: $1 (use --recreate)" >&2
    exit 2
fi

# numpy 2.5.3 requires Python 3.12 or later; prefer 3.12, the version verified with the user guide
PY_CHECK='import sys; sys.exit(sys.version_info < (3, 12))'

if [[ -z "${PYTHON:-}" ]]; then
    for candidate in python3.12 python3; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "$PY_CHECK"; then
            PYTHON=$candidate
            break
        fi
    done
fi

if [[ -z "${PYTHON:-}" ]] || ! "$PYTHON" -c "$PY_CHECK" 2>/dev/null; then
    echo "Python 3.12 or later was not found." >&2
    echo "If your distribution does not package it, uv (https://docs.astral.sh/uv/) can install it:" >&2
    echo "    uv python install 3.12" >&2
    echo "    PYTHON=\"\$(uv python find 3.12)\" ./setup_linux.sh" >&2
    exit 1
fi
echo "Using $("$PYTHON" --version 2>&1) ($(command -v "$PYTHON"))"

# Removed only after a usable Python is found, so a failed run keeps the existing environment
if [[ $RECREATE == 1 && -e "$VENV_DIR" ]]; then
    echo "Removing $VENV_DIR"
    rm -rf "$VENV_DIR"
fi

if [[ -x "$VENV_DIR/bin/python" ]] && ! "$VENV_DIR/bin/python" -c "$PY_CHECK"; then
    echo "The existing $VENV_DIR uses $("$VENV_DIR/bin/python" --version 2>&1); Python 3.12 or later is required." >&2
    echo "Run ./setup_linux.sh --recreate to rebuild it." >&2
    exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "Creating virtual environment in $VENV_DIR"
    if ! "$PYTHON" -m venv "$VENV_DIR"; then
        rm -rf "$VENV_DIR"
        echo "Could not create the virtual environment. On Debian/Ubuntu install the venv module first:" >&2
        echo "    sudo apt install python3-venv" >&2
        exit 1
    fi
fi

echo "Installing packages from requirements.txt"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements.txt

echo "Checking the installation"
"$VENV_DIR/bin/python" -c 'import xdw_file_playback, PyQt6.QtWidgets'

# Qt 6.5+ needs libxcb-cursor0 for its X11 (xcb) platform plugin, which most desktops use
if command -v dpkg >/dev/null 2>&1 && ! dpkg -s libxcb-cursor0 >/dev/null 2>&1; then
    echo
    echo "NOTE: libxcb-cursor0 is not installed. If the GUI fails to start with a 'Qt platform plugin \"xcb\"'"
    echo "      error, install it with: sudo apt install libxcb-cursor0"
fi

echo
echo "Setup complete. To start the GUI:"
echo "    source $VENV_DIR/bin/activate"
echo "    python xdw_file_playback.py"
