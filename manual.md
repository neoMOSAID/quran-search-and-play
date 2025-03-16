**Quran Search Application User Manual**  

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
  - **Save**: Save/update notes (shortcut: `Ctrl+S`).  
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

### **4. User Interface Customization**  
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

### **5. Search History & Navigation**  
- **Persistent History**:  
  - Last 50 searches saved automatically.  
  - Accessed via `↑`/`↓` arrow keys in the search bar.  

- **Quick Access**:  
  - `Ctrl+F` focuses the search bar instantly.  
  - `Backspace` returns to results from detail view.  

---

### **6. Keyboard Shortcuts**  
| Shortcut          | Action                                  |  
|-------------------|-----------------------------------------|  
| `Ctrl+H`          | Open help dialog                        |  
| `Ctrl+J`          | Load Surah from selected ayah           |  
| `Ctrl+K`          | Jump to playback Surah                  |  
| `Ctrl+↑`/`Ctrl+↓` | Navigate search history                 |  
| `Enter`           | Show verse context (in results view)    |  

---

### **7. Technical Features**  
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