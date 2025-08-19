
import os
import logging

from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5 import QtCore,  QtWidgets
from PyQt5.QtCore import QUrl, QTimer
from utils.helpers import get_audio_directory

class AudioController:
    def __init__(self, parent):
        self.parent = parent
        self.player = QMediaPlayer()
        self.search_engine = self.parent.search_engine
        self.current_surah = 0
        self.current_start_ayah = 0
        self.sequence_files = []
        self.current_sequence_index = 0
        self.playing_one = False
        self.playing_context = 0
        self.playing_range = 0
        self.repeat_all = False
        self.repeat_count = 0
        self.max_repeats = 0
        self.playing_range_max = 0
        self.playing_ayah_range = False
        self.playing_basmalah = False
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

    def on_media_status_changed(self, status):
        from PyQt5.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.EndOfMedia:
            if self.playing_basmalah:
                # Basmalah finished, now play the original ayah
                self.playing_basmalah = False
                file_path = self.sequence_files[self.pending_sequence_index]  # Get original file
                # Extract surah and ayah from the pending file
                current_surah = int(os.path.basename(file_path)[:3])
                current_ayah = int(os.path.basename(file_path)[3:6])
                
                # Scroll to the ayah now
                if self.parent.results_view.isVisible():
                    self.parent._scroll_to_ayah(current_surah, current_ayah)

                url = QUrl.fromLocalFile(file_path)
                self.player.setMedia(QMediaContent(url))
                self.player.play()  # Play the original ayah (no index increment yet)
                self.current_sequence_index = self.pending_sequence_index + 1
            else:
                # Normal playback finished, proceed to next file
                QTimer.singleShot(100, self.play_next_file)

    def stop_playback(self):
        """Stop any current audio playback and reset player state"""
        self.player.stop()
        self.player.setMedia(QMediaContent())  # Clear current media
        self.repeat_all = False
        self.playing_one = False
        self.playing_context = 0
        self.playing_range = 0
        self.repeat_count = 0
        self.max_repeats = 0
        self.playing_range_max = 0
        self.playing_ayah_range = False
        self.playing_basmalah = False

    def play_current(self, surah=None, ayah=None, count=1):
        """
        Play a single audio file or a sequence of files.

        If surah and ayah are provided, they are used directly; otherwise,
        the currently selected verse in the results view is used.

        If count == 1, play a single file.
        If count > 1, build a list of files and play them sequentially.
        Audio files are expected to be named with padded numbers (e.g., "001001.mp3").
        """
        # If surah/ayah are not provided, use the currently selected item.
        if surah is None or ayah is None:
            index = self.parent.results_view.currentIndex()
            if not index.isValid():
                self.parent.showMessage("No verse selected", 7000, bg="red")
                return
            result = self.parent.model.data(index, QtCore.Qt.UserRole)
            try:
                surah = int(result.get('surah'))
                ayah = int(result.get('ayah'))
            except Exception as e:
                self.parent.showMessage("Invalid verse data", 2000, bg="red")
                return

        # Retrieve the audio directory from the INI file.
        audio_dir = get_audio_directory()

        # Single-file playback:
        if count == 1:
            audio_file = os.path.join(audio_dir, f"{int(surah):03d}{int(ayah):03d}.mp3")
            if os.path.exists(audio_file):
                url = QUrl.fromLocalFile(os.path.abspath(audio_file))
                self.player.setMedia(QMediaContent(url))
                self.player.play()
                self.parent.showMessage(f"Playing audio for Surah {surah}, Ayah {ayah}", 2000)
            else:
                self.parent.showMessage("Audio file not found", 3000, bg="red")
            return
        # For sequence playback, store the surah and starting ayah.
        self.current_surah = int(surah)
        self.current_start_ayah = int(ayah)
        self.sequence_files = []
        # Build a list of files for 'count' files (starting from the provided ayah).
        for offset in range(count):
            current_ayah = self.current_start_ayah + offset
            file_path = os.path.join(audio_dir, f"{self.current_surah:03d}{current_ayah:03d}.mp3")
            if os.path.exists(file_path):
                self.sequence_files.append(os.path.abspath(file_path))
            else:
                # Optionally, notify that a file was not found and break out.
                self.parent.showMessage(f"Audio file not found: {file_path}", 2000, bg="red")
                break

        if not self.sequence_files:
            self.parent.showMessage("No audio files found for sequence", 3000, bg="red")
            return

        # Initialize sequence index and start playback.
        self.current_sequence_index = 0
        self.play_next_file()

    def play_next_file(self):
        """
        Play the next file in the current sequence (if any) and update the UI selection.
        When the current surah finishes, automatically load the next surah (or surah 1 if current is 114)
        and begin playback from ayah 1.
        """
        maxx = len(self.sequence_files)
        if self.current_sequence_index < maxx:
            file_path = self.sequence_files[self.current_sequence_index]
            current_surah = int(os.path.basename(file_path)[:3])
            current_ayah = int(os.path.basename(file_path)[3:6])

            # Check if Basmalah should be played
            if current_ayah == 1 and current_surah != 9 and not self.playing_basmalah:
                # Scroll to the ayah even before playing Basmalah
                if self.parent.results_view.isVisible():
                    self.parent._scroll_to_ayah(current_surah, current_ayah)
                
                audio_dir = get_audio_directory()
                basmalah_path = os.path.join(audio_dir, f"{current_surah:03d}000.mp3")
                if os.path.exists(basmalah_path):
                    # Play Basmalah first
                    self.playing_basmalah = True
                    self.pending_sequence_index = self.current_sequence_index
                    # Update status message
                    chapter = self.search_engine.get_chapter_name(current_surah)
                    self.parent.status_msg = f"<span dir='rtl'>إستماع إلى البسملة من سورة {chapter}</span>"
                    # Load and play Basmalah
                    url = QUrl.fromLocalFile(basmalah_path)
                    self.player.setMedia(QMediaContent(url))
                    self.player.play()
                    return  # Exit without incrementing index

            chapter = self.search_engine.get_chapter_name(current_surah)
            
            self.parent.status_msg = f"<span dir='rtl' style='text-align: right'> إستماع إلى الآية {current_ayah}   من سورة {chapter}  {self.current_sequence_index+1}/{maxx}</span>"
            if self.repeat_all or self.playing_range:
                self.parent.status_msg += " repeating"
                if self.max_repeats > 0:
                    self.parent.status_msg += f" ({self.repeat_count+1}/{self.max_repeats}) "
            # Continue playing the current surah.
            url = QUrl.fromLocalFile(file_path)
            self.player.setMedia(QMediaContent(url))
            self.player.play()

            # Calculate the current ayah being played.
            if self.parent.results_view.isVisible():
                self.parent._scroll_to_ayah(current_surah, current_ayah)
            self.current_sequence_index += 1
        else:
            if self.repeat_all: 
                if self.max_repeats > 0:
                    self.repeat_count += 1
                    if self.repeat_count >= self.max_repeats:
                        self.repeat_all = False
                        self.repeat_count = 0
                        self.max_repeats = 0
                        self.parent.showMessage("Repeat limit reached", 3000)
                        return
                self.current_sequence_index = 0
                self.play_next_file()
                return 
            if self.playing_one:
                self.playing_one = False
                return
            if self.playing_context:
                if self.playing_context < 6:
                    self.playing_context += 1
                else:
                    self.playing_context = 0
                    self.status_msg = ""
                return
            if self.playing_range:
                if self.playing_range <= self.playing_range_max:
                    self.playing_range += 1
                else:
                    self.playing_range = 1
                    self.current_sequence_index = 0
                self.play_next_file()
                return
            if self.playing_ayah_range:
                self.playing_ayah_range = False
                return

            # End of current surah reached: increment surah (wrap around if needed).
            if self.current_surah < 114:
                self.current_surah += 1
            else:
                self.current_surah = 1  # Wrap around to surah 1

            self.current_start_ayah = 1  # New surah always starts at ayah 1

            # Build new sequence for the next surah.
            audio_dir = get_audio_directory()
            new_sequence_files = []
            for ayah in range(1, 300):  # A safe upper bound for number of ayahs.
                file_path = os.path.join(audio_dir, f"{self.current_surah:03d}{ayah:03d}.mp3")
                if os.path.exists(file_path):
                    new_sequence_files.append(os.path.abspath(file_path))
                else:
                    break

            if new_sequence_files:
                self.parent.handle_surah_selection(self.current_surah-1)
                self.parent.surah_combo.setCurrentIndex(self.current_surah - 1)
                self.sequence_files = new_sequence_files
                self.current_sequence_index = 0
                self.parent.showMessage(f"Moving to surah {self.current_surah}", 5000)
                self.play_next_file()  # Start playback of the new surah.
            else:
                self.parent.showMessage(f"No audio files found for surah {self.current_surah}. Playback finished.", 2000)
                self.sequence_files = []
                self.current_sequence_index = 0
                self.status_msg = ""


    def play_all_results(self):
        """Play all verses in the current search results list, skipping pinned verses not in actual results."""
        if not self.parent.model.results:
            self.parent.showMessage("No results to play", 3000, bg="red")
            return

        # Create set of actual result verse identifiers
        actual_verse_ids = set()
        for result in self.parent.model.results:
            if not result.get('is_pinned', False):  # Only non-pinned are actual results
                verse_id = f"{result['surah']}-{result['ayah']}"
                actual_verse_ids.add(verse_id)
        audio_dir = get_audio_directory()
        self.sequence_files = []

        # Build list of valid audio files
        for result in self.parent.model.results:
            # Skip pinned verses not in actual results
            if result.get('is_pinned', False):
                verse_id = f"{result['surah']}-{result['ayah']}"
                if verse_id not in actual_verse_ids:
                    continue
                    
            try:
                surah = int(result['surah'])
                ayah = int(result['ayah'])
            except (KeyError, ValueError):
                continue

            file_path = os.path.join(audio_dir, f"{surah:03d}{ayah:03d}.mp3")
            if os.path.exists(file_path):
                self.sequence_files.append(os.path.abspath(file_path))

        if self.sequence_files:
            # ... rest of the method unchanged ...
            index = self.parent.results_view.currentIndex()
            self.current_sequence_index = 0
            if index.isValid():
                result = self.parent.model.data(index, QtCore.Qt.UserRole)
                try:
                    surah = int(result.get('surah'))
                    ayah = int(result.get('ayah'))
                    expected_filename = f"{surah:03d}{ayah:03d}.mp3"
                    # Iterate over the list of sequence files to find a match
                    for idx, file_path in enumerate(self.sequence_files):
                        if os.path.basename(file_path) == expected_filename:
                            self.current_sequence_index = idx
                            break
                except Exception as e:
                    pass
            self.playing_ayah_range = True
            self.parent.showMessage(f"Playing {len(self.sequence_files)} results...", 3000)
            self.play_next_file()
        else:
            self.parent.showMessage("No audio files found in results", 3000, bg="red")

    def handle_space(self):
        if self.player.mediaStatus() != QMediaPlayer.NoMedia:
            if self.player.state() == QMediaPlayer.PlayingState:
                self.player.pause()
                return "paused"
            else:
                self.player.play()
                return "resumed"
        else:
            # Handle starting a new playback
            self.playing_one = True
            return "new_playback"


    def play_current_surah(self):
        """
        Play the entire surah of the currently selected verse.
        This method works only in the results view.
        It builds a sequence from ayah 1 upward until no file is found,
        then starts playback at the currently selected ayah.
        """
        # Ensure we are in results view.
        if not self.parent.results_view.isVisible():
            self.parent.showMessage("Switch to results view to play current surah", 2000, bg="red")
            return

        index = self.parent.results_view.currentIndex()
        if index.isValid():
            result = self.parent.model.data(index, QtCore.Qt.UserRole)
            try:
                surah = int(result.get('surah'))
                selected_ayah = int(result.get('ayah'))
            except Exception as e:
                self.parent.showMessage("Invalid surah or ayah information", 2000, bg="red")
                return
        else:
            surah = self.parent.current_view.get('surah',1)
            selected_ayah = 0

        is_dark = self.parent.theme_action.isChecked()
        results = self.parent.search_engine.search_by_surah(surah, is_dark, [])
        if not results:
            return

        # Retrieve the audio directory from the INI file.
        audio_dir = get_audio_directory()
        sequence_files = []

        # Loop through possible ayahs (from 1 to 300 is a safe upper bound).
        for res in results:
            try:
                ayah_num = int(res['ayah'])
                file_path = os.path.join(audio_dir, f"{surah:03d}{ayah_num:03d}.mp3")
                if os.path.exists(file_path):
                    sequence_files.append(os.path.abspath(file_path))
            except (KeyError, ValueError):
                continue

        if not sequence_files:
            self.parent.showMessage("No audio files found for current surah", 3000, bg="red")
            return

        # Store the sequence and initialize the index.
        self.current_surah = surah
        self.sequence_files = sequence_files
        self.playing_ayah_range = False
        self.current_start_ayah = 1  # Our sequence is built from ayah 1.
        # Set the current sequence index to the selected ayah (adjusted for 0-based indexing).
        self.current_sequence_index = selected_ayah -1

        # Sanity check: if the selected ayah is out of range, default to 0.
        if self.current_sequence_index < 0 or self.current_sequence_index >= len(sequence_files):
            self.current_sequence_index = 0

        self.play_next_file()  # This method will chain playback for the sequence.


    def choose_audio_directory(self):
        """
        Open a dialog to choose an audio directory.
        If a directory is chosen, update the INI file with the new value.
        """
        # Get the current audio directory from the INI file.
        current_dir = get_audio_directory()

        # Open a directory chooser dialog.
        chosen_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self.parent,
            "Select Audio Directory",
            current_dir
        )

        # If the user selected a directory, update the INI file.
        if chosen_dir:
            self.parent.settings.set("AudioDirectory", chosen_dir)
            self.parent.showMessage(f"Audio directory set to: {chosen_dir}", 3000)
            
            # Stop any current playback and reset player state
            self.stop_playback()
            self.reset_player_state()

    def reset_player_state(self):
        """Reset all player state variables"""
        self.sequence_files = []
        self.current_sequence_index = 0
        self.current_surah = 0
        self.current_start_ayah = 0
        self.pending_sequence_index = 0


    def load_surah_from_current_playback(self):
        """
        If a playback sequence is active, use its current surah and the
        last played (or currently playing) ayah to load that surah and scroll to it.
        Bind this method to Ctrl+K.
        """
        current_media = self.player.media()
        if current_media is not None:
            url = current_media.canonicalUrl()
            if url.isLocalFile():
                file_path = url.toLocalFile()
                current_surah = int(os.path.basename(file_path)[:3])
                current_ayah = int(os.path.basename(file_path)[3:6])
                self.parent.load_surah_from_current_ayah(surah=current_surah, selected_ayah=current_ayah)
