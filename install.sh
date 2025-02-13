#!/bin/bash
# install.sh – Install script for Quran Search on Linux/Unix

# Determine the installation directory (the directory containing this script)
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

# Define the Python executable in the virtual environment
PYTHON_EXEC="$INSTALL_DIR/env/bin/python"

# Check if the Python executable exists
if [ ! -f "$PYTHON_EXEC" ]; then
    echo "Error: Python executable not found at $PYTHON_EXEC"
    exit 1
fi

# Create command line wrapper in /usr/local/bin
WRAPPER_PATH="/usr/local/bin/quranSearch"
echo "Creating command line wrapper at $WRAPPER_PATH..."
sudo tee "$WRAPPER_PATH" > /dev/null <<EOF
#!/bin/bash
"$PYTHON_EXEC" "$INSTALL_DIR/gui.py" & disown
EOF
sudo chmod +x "$WRAPPER_PATH"
echo "Wrapper created successfully."

# Create desktop entry
DESKTOP_ENTRY_NAME="quranSearch.desktop"
DESKTOP_ENTRY_PATH="$HOME/.local/share/applications/$DESKTOP_ENTRY_NAME"
echo "Creating desktop entry at $DESKTOP_ENTRY_PATH..."
mkdir -p "$HOME/.local/share/applications"
cat > "$DESKTOP_ENTRY_PATH" <<EOF
[Desktop Entry]
Type=Application
Name=Quran Search
Comment=Search and listen to Quran verses
Exec=$WRAPPER_PATH
Icon=$INSTALL_DIR/icon.png
Terminal=false
Categories=Audio;Education;
EOF
echo "Desktop entry created successfully."

echo "Installation completed."

