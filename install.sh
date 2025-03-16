#!/bin/bash
# install.sh – Improved Install Script for Quran Search on Linux/Unix
#
# This script performs the following:
# 1. Copies necessary files from the cloned repository to a user-writable directory.
# 2. Creates a virtual environment in that directory.
# 3. Installs required packages from requirements.txt.
#    If version conflicts or "no available match" errors occur,
#    it will attempt to install PyQt5 and PyQtWebEngine manually.
# 4. Creates command line launchers and desktop entries for both launching and uninstalling the application.
# 5. Installs the man page.
#
# Usage: ./install.sh

# Global Variables
DEST_DIR="$HOME/.local/share/quranSearch"
VENV_DIR="$DEST_DIR/env"
DESKTOP_ENTRY_DIR="$HOME/.local/share/applications"
WRAPPER_PATH="/usr/local/bin/quranSearch"
UNINSTALL_WRAPPER="/usr/local/bin/uninstall_quranSearch"


# Colors
RED='\033[0;31m'
GR='\033[0;32m'
YEL='\033[1;33m'
NC='\033[0m' # No Color



# Function: Copy repository files to the destination directory.
copy_files() {
    echo -e "$RED Installing Quran Search to $DEST_DIR...$NC"
    mkdir -p "$DEST_DIR"
    echo -e "$GR Copying files to installation directory...$NC"
    rsync -av \
        --exclude='**/__pycache__' \
        --exclude='**/*.pyc' \
        gui.py help help_quransearch.1 icon.ico icon.png quran_text search.py requirements.txt "$DEST_DIR/"
}

# Function: Create a Python virtual environment.
create_virtualenv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "$GR Creating virtual environment in $VENV_DIR...$NC"
        python3 -m venv "$VENV_DIR"
        if [ $? -ne 0 ]; then
            echo -e "$RED Error creating virtual environment.$NC"
            exit 1
        fi
    else
        echo -e "$YEL Virtual environment already exists at $VENV_DIR"
    fi
    # Set executable paths
    PYTHON_EXEC="$VENV_DIR/bin/python"
    PIP_EXEC="$VENV_DIR/bin/pip"
}

# Function: Upgrade pip and install required packages.
install_requirements() {
    echo -e "$GR Upgrading pip...$NC"
    "$PIP_EXEC" install --upgrade pip
    REQ_FILE="$DEST_DIR/requirements.txt"
    if [ -f "$REQ_FILE" ]; then
        echo -e "$GR Installing requirements from $REQ_FILE...$NC"
        if ! "$PIP_EXEC" install -r "$REQ_FILE"; then
            echo -e "$RED Error installing packages from requirements.txt.$NC"
            echo -e "$GR Attempting to install PyQt5 and PyQtWebEngine manually...$NC"
            if ! "$PIP_EXEC" install PyQt5 PyQtWebEngine; then
                echo -e "$RED Error installing PyQt5 and PyQtWebEngine manually.$NC"
                exit 1
            fi
        fi
    else
        echo -e "$YEL No requirements.txt found in $DEST_DIR $NC"
    fi
}

# Function: Create the CLI launcher in /usr/local/bin.
create_cli_launcher() {
    echo -e "$GR Creating command line launcher at $WRAPPER_PATH...$NC"
    sudo tee "$WRAPPER_PATH" > /dev/null <<EOF
#!/bin/bash
"$PYTHON_EXEC" "$DEST_DIR/gui.py" & disown
EOF
    sudo chmod +x "$WRAPPER_PATH"
}

# Function: Create the desktop entry for launching the application.
create_desktop_entry() {
    LAUNCHER_DESKTOP_ENTRY="$DESKTOP_ENTRY_DIR/quranSearch.desktop"
    echo -e "$GR Creating desktop entry at $LAUNCHER_DESKTOP_ENTRY...$NC"
    mkdir -p "$DESKTOP_ENTRY_DIR"
    cat > "$LAUNCHER_DESKTOP_ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Quran Search
Comment=Search and listen to Quran verses
Exec=$WRAPPER_PATH
Icon=$DEST_DIR/icon.png
Terminal=false
Categories=Audio;Education;
EOF
}

# Function: Install the man page.
install_manpage() {
    echo -e "$GR Installing man page...$NC"
    sudo cp help_quransearch.1 /usr/local/share/man/man1/quransearch.1
    echo -e "$GR Updating mandb... $NC"
    sudo mandb >/dev/null
}

# Function: Create the uninstall script in the installation directory.
create_uninstall_script() {
    UNINSTALL_SCRIPT="$DEST_DIR/uninstall.sh"
    echo -e "$GR Creating uninstall script at $UNINSTALL_SCRIPT...$NC"
    cat > "$UNINSTALL_SCRIPT" <<'EOF'
#!/bin/bash
echo "Uninstalling Quran Search..."
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
WRAPPER_PATH="/usr/local/bin/quranSearch"
UNINSTALL_WRAPPER="/usr/local/bin/uninstall_quranSearch"
read -p "Are you sure you want to remove the installation directory $INSTALL_DIR? [y/N]: " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    rm -rf "$INSTALL_DIR"
    echo "Removing man page..."
    sudo rm /usr/local/share/man/man1/quransearch.1
    sudo rm "$WRAPPER_PATH"
    sudo rm "$UNINSTALL_WRAPPER"
    echo "Uninstallation completed."
else
    echo "Uninstallation cancelled."
fi
EOF
    chmod +x "$UNINSTALL_SCRIPT"
}

# Function: Create a CLI wrapper for uninstallation.
create_uninstall_wrapper() {
    echo -e "$GR Creating CLI uninstallation wrapper at $UNINSTALL_WRAPPER...$NC"
    sudo tee "$UNINSTALL_WRAPPER" > /dev/null <<EOF
#!/bin/bash
"$UNINSTALL_SCRIPT"
EOF
    sudo chmod +x "$UNINSTALL_WRAPPER"
}

# # Function: Create the desktop entry for uninstallation.
# create_uninstall_desktop_entry() {
#     UNINSTALL_DESKTOP_ENTRY="$DESKTOP_ENTRY_DIR/uninstall_quranSearch.desktop"
#     echo "Creating desktop entry for uninstallation at $UNINSTALL_DESKTOP_ENTRY..."
#     cat > "$UNINSTALL_DESKTOP_ENTRY" <<EOF
# [Desktop Entry]
# Type=Application
# Name=Uninstall Quran Search
# Comment=Remove Quran Search installation
# Exec=$UNINSTALL_WRAPPER
# Icon=application-x-trash
# Terminal=true
# Categories=Utility;
# EOF
# }

# Main function to orchestrate installation.
main() {
    copy_files
    create_virtualenv
    install_requirements
    create_cli_launcher
    create_desktop_entry
    install_manpage
    create_uninstall_script
    create_uninstall_wrapper
    # create_uninstall_desktop_entry

    echo -e "$GR Installation completed successfully.$NC"
    echo "To launch Quran Search, run 'quranSearch' from the command line or use the desktop entry."
    echo "To uninstall, run 'uninstall_quranSearch'"
    echo "If you have any suggestions for further improvements, please let me know."
}

# Execute the main function.
main
