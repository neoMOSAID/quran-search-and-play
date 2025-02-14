

# Quran Search

![Project Logo](https://raw.githubusercontent.com/neoMOSAID/quran-search-and-play/main/icon.png)



[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-green)](https://python.org)
[![Website](https://img.shields.io/badge/Website-mosaid.xyz-blue)]( https://mosaid.xyz/quran-search)


**Website:** [https://mosaid.xyz/quran-search](https://mosaid.xyz/quran-search)  
**GitHub:** [https://github.com/neoMOSAID/quran-search-and-play](https://github.com/neoMOSAID/quran-search-and-play)


An advanced Quran browser application built with Python and PyQt5. This project offers a modern, feature-rich interface for searching Quranic text, viewing contextual verses, and playing high-quality audio recitations. With asynchronous search capabilities, persistent user settings, and a clean, responsive UI, Quran Search is designed to provide an excellent user experience for both study and recitation.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Audio Directory and File Naming](#audio-directory-and-file-naming)
- [Customization](#customization)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)
- [Contact](#contact)

---

## Overview

**Quran Search** is a PyQt5-based desktop application that allows users to:
- **Search Quranic Text:** Quickly locate verses by text, surah number, or a combination of surah and ayah numbers.
- **View Contextual Verses:** Click on a verse to see its context (with several verses before and after) for better understanding.
- **Audio Playback:** Enjoy integrated audio playback where recitations are played either one by one or as a sequence.
- **Modern UI/UX:** Benefit from a clean, modern interface with a split-view layout that makes navigation and readability easy.
- **Persistent Settings:** Save your preferences such as theme, version display (Uthmani or Simplified), and last viewed surah between sessions.

---

## Features

- **Model–View Architecture:** Uses `QAbstractListModel` for efficient and scalable display of Quran verses.
- **Asynchronous Search:** Implements a background thread (`QThread`) to ensure smooth and responsive search operations.
- **Integrated Audio Playback:** Leverages `QMediaPlayer` for playing audio files, with support for sequential playback and automatic surah transition.
- **Persistent User Settings:** Uses `QSettings` to save and restore user preferences, window geometry, and theme choices.
- **Customizable Interface:** Includes options to toggle between dark and light themes, select between different Quran text versions (Uthmani vs Simplified), and adjust the layout.
- **Keyboard Shortcuts:** Extensive use of keyboard shortcuts for navigation, search, and audio controls.
- **Error Handling & Logging:** Built-in logging mechanism for easier debugging and error tracking.
- **Audio Directory Management:** Easily set or change the audio directory through an intuitive menu option.

---

## Installation

### Prerequisites

- **Python 3.6 or higher**
- **PyQt5**

### Installing Dependencies

1. **Clone the repository:**

   ```bash
   git clone https://github.com/neoMOSAID/quran-search-and-play.git
   cd quran-search
   ```

2. **Install required packages:**

   If you use `pip` run:

   ```bash
   pip install -r requirements.txt
   ```

---

## Usage

### Running the Application

After installing the dependencies, you can start the application with:

```bash
python3 gui.py
```

The main window will appear with a compact search bar at the top. You can then:

- **Search by Text:** Enter Arabic words or phrases and press Enter.
- **Surah Search:** Select a surah from the dropdown menu or enter the surah number directly.
- **Direct Verse Lookup:** Use the “Surah FirstAyah LastAyah” method by entering numbers (e.g., `2 255` or `2 255 280`).

### Navigating the Interface

- **Results View:** Displays the list of Quranic verses matching your query. Double-click or press Enter on a verse to see its detailed context.
- **Detail View:** Shows a detailed view of the selected verse along with additional context (5 verses before and after).
- **Status Bar:** Displays helpful messages including the number of search results and playback status.

---

## Keyboard Shortcuts

To streamline your workflow, Quran Search includes a variety of keyboard shortcuts:

- **Ctrl+F:** Focus the search input.
- **Ctrl+D:** Toggle between dark and light themes.
- **Space:** Play the audio for the currently selected verse.
- **Ctrl+P:** Play the current verse and the next five verses sequentially.
- **Ctrl+S:** Stop audio playback.
- **Ctrl+A:** (In results view) Play the entire surah starting from the selected verse.
- **Ctrl+J:** Load surah from the current ayah.
- **Ctrl+K:** Jump back to the current playing surah and ayah.
- **Backspace:** Return from the detailed view to the results view.
- **Escape:** Toggle the displayed text version (Uthmani vs Simplified).

---

## Audio Directory and File Naming

### Setting the Audio Directory

- Navigate to **Menu > Set Audio Directory** to choose a directory that contains your audio files.
- The selected directory is saved persistently in an INI file (e.g., `.quran_audio.ini`) located in your home directory.

### File Naming Convention

Audio files should be named using the following pattern:

```
SSSAAA.mp3
```

Where:
- **SSS**: Surah number padded to three digits (e.g., 002 for Surah 2).
- **AAA**: Ayah number padded to three digits (e.g., 005 for Ayah 5).

For example, the file for Surah 2, Ayah 5 should be named `002005.mp3`.

---

## Customization

- **Theme Switching:** Toggle between dark and light themes via the menu or using the `Ctrl+D` shortcut.
- **Text Version:** Choose between Uthmani and Simplified Arabic scripts using the dropdown.
- **Window Layout:** The application automatically saves your window geometry and state between sessions.

---

## Contributing

Contributions are very welcome! If you have suggestions, bug fixes, or new features, please feel free to open an issue or submit a pull request.

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -am 'Add some feature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a pull request.

For major changes, please open an issue first to discuss what you would like to change.

---

## License

This project is licensed under the [GPL v3 License](https://www.gnu.org/licenses/gpl-3.0.html). See the [LICENSE](LICENSE) file for more details.

---

## Acknowledgements

- **MOSAID:** Developed by MOSAID.
- **Quran Text:** Sourced from [Tanzil.net](http://tanzil.net).
- **PyQt5:** Thanks to the developers of PyQt5 for an excellent framework.
- **Community Contributions:** Thanks to all contributors who help improve this project.

---

## Contact

For any questions or feedback, please contact the project maintainer or visit [https://mosaid.xyz/quran-search](https://mosaid.xyz/quran-search).

---

Enjoy using Quran Search and feel free to contribute improvements or report issues!

---

# **Quran Search Application User Manual**  

The Quran Search application is a feature-rich tool designed to enhance your Quranic study experience. Below is a comprehensive breakdown of its features and functionalities:  

---

### **1. Quran Search Features**  
- **Search Methods**:  
  - **Text Search**:  
    - Search for Arabic words/phrases across the entire Quran.  
    - Example: Search "الرحمن" to find all verses containing this name of Allah.  
    - Results are ranked by relevance and displayed in context.  

  - **Surah Search**:  
    - Enter a Surah number (e.g., "2") to view all verses from that chapter.  
    - Auto-syncs with the Surah dropdown menu.  

  - **Surah + Ayah Range**:  
    - Enter a query like "2 255 256" to display Surah 2, Ayahs 255-256.  
    - Partial ranges (e.g., "2 255") show from Ayah 255 to the end of the Surah.  

- **Gradual Results Loading**:  
  - Displays the first 50 results instantly for quick access.  
  - Remaining results load seamlessly in the background.  

---

### **2. Notes System**  
- **Per-Ayah Notes**:  
  - Create, edit, and delete unlimited notes for any ayah.  
  - Notes persist between sessions (stored in a local SQLite database).  

- **Notes Interface**:  
  - **Split View**: Vertically divided between verse context (top) and notes (bottom).  
  - **List Preview**: Notes appear truncated (first 80 characters) in a scrollable list.  
  - **Rich Editor**: Full-featured text editor with Arabic support.  
  - **Confirmation Dialogs**: Prevents accidental note deletion.  

- **Toolbar Actions**:  
  - **New**: Start a fresh note (shortcut: `Ctrl+N`).  
  - **Delete**: Remove selected note (confirmation required).  

---

### **3. Audio Playback**  
- **Controls**:  
  - **Play Current Ayah**: `Space` to play the selected verse.  
  - **Play Context**: `Ctrl+P` plays the current ayah + next 5 verses.  
  - **Play Full Surah**: `Ctrl+A` streams the entire Surah of the selected verse.  
  - **Stop**: `Ctrl+S` halts playback.  

- **Auto-Advance**:  
  - After finishing a Surah, playback automatically continues to the next Surah.  
  - Use `Ctrl+B` to jump back to the currently playing Surah.  

---

### **4. AUDIO FILE SETUP**
- **Directory Configuration**:
  * **Set Location**:
    1. Go to Menu > Set Audio Directory
    2. Choose folder containing audio files
    3. Valid files must be named as: SSSAAA.mp3 
       (SSS = 3-digit surah number, AAA = 3-digit ayah number)
       Example: 002255.mp3 = Surah 2 Ayah 255

---

### **5. User Interface Customization**  
- **Themes**:  
  - **Dark/Light Mode**: Toggle with `Ctrl+D`.  
  - Automatic text color adjustment for readability.  

- **Arabic Display**:  
  - **Font Styles**: Uthmani or Simplified script (toggle with `Escape`).  
  - **Right-to-Left (RTL) Support**: Proper Arabic text alignment.  
  - **Font Sizing**: Larger text in notes list for readability.  

- **Layout**:  
  - Adjustable splitter between search results and detail view.  
  - Resizable notes section for optimal workspace.  

---

### **6. Search History & Navigation**  
- **Persistent History**:  
  - Last 50 searches saved automatically.  
  - Accessed via `↑`/`↓` arrow keys in the search bar.  

- **Quick Access**:  
  - `Ctrl+F` focuses the search bar instantly.  
  - `Backspace` returns to results from detail view.  

---

### **7. Keyboard Shortcuts**  
| Shortcut          | Action                                  |  
|-------------------|-----------------------------------------|  
| `Ctrl+H`          | Open help dialog                        |  
| `Ctrl+J`          | Load Surah from selected ayah           |  
| `Ctrl+K`          | Jump to playback Surah                  |  
| `Ctrl+↑`/`Ctrl+↓` | Navigate search history                 |  
| `Enter`           | Show verse context (in results view)    |  

---

### **8. Technical Features**  
- **Asynchronous Search**: No UI freeze during long searches.  
- **Error Handling**: Clear status bar messages for invalid queries.  
- **Cross-Platform**: Works on Windows, macOS, and Linux.  

---

### **Getting Started Tips**  
1. Use `Ctrl+F` to quickly start a new search.  
2. Double-click results to view context + notes.  
3. Bookmark frequently used ayahs via notes.  
4. Adjust the splitter between results/detail views for your workflow.  

For additional support, visit the application website: [https://mosaid.xyz/quran-search](https://mosaid.xyz/quran-search).  

*May this tool enhance your connection with the Quran. Happy studying!* 📖✨
