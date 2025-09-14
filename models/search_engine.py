### ./models/search_engine.py ###
import re
import os, sys
import importlib.resources
import logging
import unicodedata


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # When bundled, PyInstaller stores files in sys._MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # When running in development, use the directory of this script
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)



class QuranSearch:
    def __init__(self):
        self._chapters = []
        self._uthmani = {}
        self._simplified = {}
        self._verse_counts = {}  # {surah: total_verses}
        self._load_data()
        self.highlight_color = "#FFD700"  # Gold color for highlighting


    def _load_data(self):
        """Load all required data files from the quran_text package"""
        self._load_chapters()
        self._load_verses('quran_text/uthmani.txt', self._uthmani)
        self._load_verses('quran_text/simplified.txt', self._simplified)
        self._build_verse_counts()

    def _load_chapters(self):
        """Load chapter names from the quran_text package"""
        try:
            text = importlib.resources.read_text("resources", "quran_text/chapters.txt", encoding="utf-8")
            self._chapters = [line.strip() for line in text.splitlines()]
        except Exception as e:
            raise RuntimeError(f"Could not load chapters: {e}")

    def _load_verses(self, filename, target_dict):
        """Generic verse loader for different versions from the quran_text package"""
        try:
            text = importlib.resources.read_text("resources", filename, encoding="utf-8")
            for line in text.splitlines():
                parts = line.strip().split('|')
                if len(parts) < 3:
                    continue
                try:
                    surah = int(parts[0])
                    ayah = int(parts[1])
                    text_line = '|'.join(parts[2:])
                    target_dict[(surah, ayah)] = {
                        'text': text_line,
                        'full': line.strip()
                    }
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            raise RuntimeError(f"Could not load {filename}: {e}")

    def _build_verse_counts(self):
        """Build dictionary of verse counts per surah"""
        counts = {}
        for (surah, ayah) in self._uthmani:
            counts[surah] = max(counts.get(surah, 0), ayah)
        self._verse_counts = counts

    @staticmethod
    def _normalize_hamza(text):
        """Normalize all alif variants to standard ا"""
        replacements = {
            'إ': 'ا',
            'أ': 'ا',
            'آ': 'ا',
            'ٱ': 'ا',  # Alif Wasla
            'ـ': '',   # Tatweel
            #'ء': '',   # Standalone hamza removed
            'ئ': 'ي',
            'ؤ': 'و',
            'ى': 'ي',
            'ة': 'ه',
        }
        for orig, repl in replacements.items():
            text = text.replace(orig, repl)
        return text

    @staticmethod
    def replace_dagger_alif(text):
        """
        For dagger alif (ٰ), remove it when it occurs immediately before 'ن' 
        (as in 'ٱلرَّحْمَـٰنِ' should become 'الرحمن'),
        and in other contexts replace it with a regular 'ا'.
        """
        # Remove dagger alif when followed by ن (lookahead)
        text = re.sub(r'ـ?ٰ(?=ن)', '', text)
        # Replace remaining dagger alif with a regular alif
        text = text.replace('ٰ', 'ا')
        return text

    @staticmethod
    def _remove_diacritics(text):
        """Remove all Arabic diacritics including extended ranges"""
        decomposed = unicodedata.normalize('NFKD', text)
        filtered = ''.join(ch for ch in decomposed if not unicodedata.category(ch).startswith('M'))
        return filtered
    
    @staticmethod   
    def _normalize_text(text="", preserve_hamza=False):
        if not preserve_hamza:
            # Replace dagger alif with a regular alif before diacritics are removed.
            text = QuranSearch.replace_dagger_alif(text)
            # Remove diacritics (all mark characters).
            text = QuranSearch._remove_diacritics(text)
            # Normalize various forms of alif and related characters.
            text = QuranSearch._normalize_hamza(text)
        # Recompose to NFC to standardize the text.
        text = unicodedata.normalize('NFC', text)
        return text.strip()

    def _parse_search_query(self, query):
        """Parse search query for special operators and patterns"""
        preserve_hamza = '@' in query
        query = query.replace('@', '')  # Remove @ symbol if present
        
        # Check for wildcard patterns
        starts_with_wildcard = query.startswith('%')
        ends_with_wildcard = query.endswith('%')
        
        if starts_with_wildcard and ends_with_wildcard and len(query) > 2:
            # %term% - exact word match
            pattern_type = 'exact_word'
            term = query[1:-1]
        elif starts_with_wildcard and len(query) > 1:
            # %term - ends with
            pattern_type = 'ends_with'
            term = query[1:]
        elif ends_with_wildcard and len(query) > 1:
            # term% - starts with
            pattern_type = 'starts_with'
            term = query[:-1]
        else:
            # Regular substring search
            pattern_type = 'substring'
            term = query
        
        return {
            'term': term,
            'pattern_type': pattern_type,
            'preserve_hamza': preserve_hamza
        }
            
    def search_verses(self, query, is_dark_theme=False, highlight_words=[]):
        # Parse the search query
        search_params = self._parse_search_query(query)
        term = search_params['term']
        pattern_type = search_params['pattern_type']
        preserve_hamza = search_params['preserve_hamza']
        
        normalized_query = self._normalize_text(term, preserve_hamza)
        results = []
        total_occurrences = 0

        for (surah, ayah), data in self._simplified.items():
            normalized_text = self._normalize_text(data['text'], preserve_hamza)
            
            # Apply the appropriate search pattern
            match_found = False
            occurrences = 0
            
            if pattern_type == 'substring':
                if normalized_query in normalized_text:
                    match_found = True
                    occurrences = normalized_text.count(normalized_query)
            elif pattern_type == 'starts_with':
                # Split into words and check each word
                words = normalized_text.split()
                for word in words:
                    if word.startswith(normalized_query):
                        match_found = True
                        occurrences += 1
            elif pattern_type == 'ends_with':
                # Split into words and check each word
                words = normalized_text.split()
                for word in words:
                    if word.endswith(normalized_query):
                        match_found = True
                        occurrences += 1
            elif pattern_type == 'exact_word':
                # Split into words and check each word
                words = normalized_text.split()
                for word in words:
                    if word == normalized_query:
                        match_found = True
                        occurrences += 1
            
            if match_found:
                total_occurrences += occurrences

                uthmani_text = self._uthmani.get((surah, ayah), {}).get('text', '')
                
                # Apply search highlighting
                highlighted_simplified = self.highlight(data['text'], query, is_dark_theme)
                highlighted_uthmani = self.highlight(uthmani_text, query, is_dark_theme)

                results.append({
                    'surah': surah,
                    'ayah': ayah,
                    'text_simplified': highlighted_simplified,
                    'text_uthmani': highlighted_uthmani,
                    'chapter': self.get_chapter_name(surah)
                })
        
        return results, total_occurrences

    def get_verse(self, surah, ayah, version='simplified'):
        """
        Get specific verse by surah and ayah number
        :return: Verse text or None if not found
        """
        version_data = self._uthmani if version == 'uthmani' else self._simplified
        return version_data.get((surah, ayah), {}).get('text')

    def get_chapters_names(self):
        return self._chapters
    
    def get_chapter_name(self, surah):
        """Get formatted chapter name"""
        if 1 <= surah <= len(self._chapters):
            return self._chapters[surah-1]
        return "Unknown Chapter"

    def get_verse_count(self, surah):
        """Get total number of verses in a chapter"""
        return self._verse_counts.get(surah, 0)

    def get_surah_range(self):
        """Get valid range of surah numbers"""
        return min(self._verse_counts), max(self._verse_counts)

    def validate_reference(self, surah, ayah=None):
        """
        Validate surah/ayah numbers
        :return: (is_valid, error_message)
        """
        min_surah, max_surah = self.get_surah_range()
        
        if not min_surah <= surah <= max_surah:
            return False, f"Invalid surah number. Must be between {min_surah}-{max_surah}"
        
        if ayah is not None:
            max_ayah = self.get_verse_count(surah)
            if not 1 <= ayah <= max_ayah:
                return False, f"Invalid ayah for surah {surah}. Must be 1-{max_ayah}"
        
        return True, ""
    
    def search_by_surah(self, surah,is_dark_theme=False, highlight_words=[]):
        results = []

        """Retrieve all verses of a given Surah."""
        for ayah in range(1, self.get_verse_count(surah) + 1):
            uthmani_text = self._uthmani.get((surah, ayah), {}).get('text', '')
            simplified_text = self._simplified.get((surah, ayah), {}).get('text', '')
            original_simplified_text = simplified_text
            for word in highlight_words:
                normalized_query = self._normalize_text(word)
                if normalized_query in self._normalize_text(original_simplified_text):

                    # Pass highlight_words to the highlight method
                    simplified_text = self._highlight_search(
                        simplified_text, word, is_dark_theme
                    )
                    uthmani_text = self._highlight_search(
                        uthmani_text, word, is_dark_theme
                    )
                    
            results.append({
                'surah': surah,
                'ayah': ayah,
                'text_simplified': simplified_text,
                'text_uthmani': uthmani_text,
                'chapter': self.get_chapter_name(surah)
            })
        return results

    def search_by_surah_ayah(self, surah, first, last=None,is_dark_theme=False, highlight_words=[]):
        """Retrieve a specific verse by Surah and Ayah number."""
        results = []
        if last is None:
            last = first
        for ayah in range(first, last + 1):
            uthmani_text = self._uthmani.get((surah, ayah), {}).get('text', '')
            simplified_text = self._simplified.get((surah, ayah), {}).get('text', '')
            original_simplified_text = simplified_text
            for word in highlight_words:
                normalized_query = self._normalize_text(word)
                if normalized_query in self._normalize_text(original_simplified_text):

                    # Pass highlight_words to the highlight method
                    simplified_text = self._highlight_search(
                        simplified_text, word, is_dark_theme
                    )
                    uthmani_text = self._highlight_search(
                        uthmani_text, word, is_dark_theme
                    )
                    
            results.append({
                'surah': surah,
                'ayah': ayah,
                'text_simplified': simplified_text,
                'text_uthmani': uthmani_text,
                'chapter': self.get_chapter_name(surah)
            })
        return results
    
    def get_ayah_with_context(self, surah, ayah):
        """
        Retrieve an ayah along with 5 previous and 5 next verses (if available),
        highlighting the requested ayah.

        :param surah: Surah number
        :param ayah: Ayah number
        :return: List of dictionaries containing ayah details
        """
        context_range = 12
        is_valid, error = self.validate_reference(surah, ayah)
        if not is_valid:
            return []
        
        total_ayahs = self.get_verse_count(surah)
        
        # Define the range (max 5 before and 5 after)
        start = max(1, ayah - context_range)
        end = min(total_ayahs, ayah + context_range)

        highlight_bg = "#F7E7A0"  # Soft Yellow
        highlight_text = "#000000"  # Black

        results = []
        for current_ayah in range(start, end + 1):
            text_simplified = self._simplified.get((surah, current_ayah), {}).get('text', '')
            text_uthmani = self._uthmani.get((surah, current_ayah), {}).get('text', '')

            # Highlight the main Ayah
            if current_ayah == ayah:
                text_simplified = f'<span style="background: {highlight_bg}; color: {highlight_text}; padding: 5px; border-radius: 5px;">{text_simplified}</span>'
                text_uthmani = f'<span style="background: {highlight_bg}; color: {highlight_text}; padding: 5px; border-radius: 5px;">{text_uthmani}</span>'

            results.append({
                'surah': surah,
                'ayah': current_ayah,
                'text_simplified': text_simplified,
                'text_uthmani': text_uthmani,
                'chapter': self.get_chapter_name(surah)
            })

        return results

    def search_verses_with_context(self, query):
        """
        Search for verses matching the query (in the simplified text) and, for each match,
        return a result dictionary with a context block. The context block consists of up to
        5 verses before and 5 verses after the matching verse (or as many as available),
        with the matching verse highlighted.
        """
        # Parse the search query
        search_params = self._parse_search_query(query)
        term = search_params['term']
        preserve_hamza = search_params['preserve_hamza']
        
        normalized_query = self._normalize_text(term, preserve_hamza)
        results = []
        
        for (surah, ayah), data in self._simplified.items():
            normalized_text = self._normalize_text(data['text'], preserve_hamza)
            if normalized_query in normalized_text:
                context_list = self.get_ayah_with_context(surah, ayah)
                for r in context_list:
                    results.append(r)
        
        return results
    
    def get_all_simplified_words(self):
        """Return unique words from simplified Quran text with counts"""
        word_counts = {}
        for (surah, ayah), data in self._simplified.items():
            text = self._normalize_text(data['text'])
            for word in text.split():
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Sort by frequency then alphabetically
        return sorted(word_counts.keys(), 
                    key=lambda x: (-word_counts[x], x))

    def get_common_words(self, limit=5000):
        """Get most frequently used words"""
        return self.get_all_simplified_words()[:limit]

    def highlight(self, text, query, is_dark_theme=False, highlight_words=[]):
        """Updated highlight method with permanent word highlighting"""
        # First highlight search matches
        highlighted = self._highlight_search(text, query, is_dark_theme)
        
        # Then apply permanent word highlights
        for word in highlight_words:
            if self._normalize_text(word) == self._normalize_text(query):
                continue
            highlighted = self._highlight_search(highlighted, word, is_dark_theme)
        return highlighted

    def _highlight_search(self, text, query, is_dark_theme):
        # Parse the search query to handle special operators
        search_params = self._parse_search_query(query)
        term = search_params['term']
        pattern_type = search_params['pattern_type']
        preserve_hamza = search_params['preserve_hamza']
        
        normalized_query = self._normalize_text(term, preserve_hamza)
        
        if pattern_type == 'substring':
            return self.highlight_phrase(text, term, is_dark_theme)
        else:
            # For pattern searches, highlight the entire word that matches
            return self.highlight_pattern(text, term, pattern_type, is_dark_theme, preserve_hamza)

    def highlight_pattern(self, text, query, pattern_type, is_dark_theme, preserve_hamza=False):
        """Highlight words based on pattern type"""
        highlight_color = "#FFFF00" if is_dark_theme else "#ff0000"
        normalized_query = self._normalize_text(query, preserve_hamza)
        
        # Split text into words while preserving original whitespace
        words = text.split()
        highlighted = []
        
        for original_word in words:
            # Normalize the current word (with same hamza preservation as search)
            normalized_word = self._normalize_text(original_word, preserve_hamza)
            
            # Check if word matches the pattern
            match = False
            if pattern_type == 'starts_with':
                match = normalized_word.startswith(normalized_query)
            elif pattern_type == 'ends_with':
                match = normalized_word.endswith(normalized_query)
            elif pattern_type == 'exact_word':
                match = normalized_word == normalized_query
            
            if match:
                highlighted.append(
                    f'<span style="font-weight: bold; color: {highlight_color};">{original_word}</span>'
                )
            else:
                highlighted.append(original_word)
        
        return ' '.join(highlighted)

    def highlight_word(self, text, query, is_dark_theme):
        """Highlight entire words containing the query substring."""
        highlight_color = "#FFFF00" if is_dark_theme else "#ff0000"

        normalized_query = self._normalize_text(query)
        
        # Split text into words while preserving original whitespace
        words = text.split()
        highlighted = []
        
        for original_word in words:
            # Normalize the current word
            normalized_word = self._normalize_text(original_word)
            
            # Check if query is a substring of the normalized word
            if normalized_query in normalized_word:
                highlighted.append(
                    f'<span style="font-weight: bold; color: {highlight_color};">{original_word}</span>'
                )
            else:
                highlighted.append(original_word)
        
        return ' '.join(highlighted)

    def highlight_phrase(self, text, query, is_dark_theme):
        """Highlight multi-word phrases while respecting word boundaries."""
        highlight_color = "#FFFF00" if is_dark_theme else "#ff0000"
        normalized_query = self._normalize_text(query)
        if not normalized_query:
            return text

        # Get word boundaries in the original text
        word_boundaries = self._get_word_boundaries(text)
        
        # Normalize each character and build index mapping
        normalized_chars = []
        index_mapping = []
        for idx, char in enumerate(text):
            nc = self._normalize_char(char)
            if nc:
                for c in nc:
                    normalized_chars.append(c)
                    index_mapping.append(idx)
        normalized_text = ''.join(normalized_chars)

        result = []
        last_highlight_end = 0
        start_idx = 0

        while start_idx <= len(normalized_text) - len(normalized_query):
            # Find the next occurrence of the query
            pos = normalized_text.find(normalized_query, start_idx)
            if pos == -1:
                break
            
            end_pos = pos + len(normalized_query)
            
            # Map back to original text positions
            match_start = index_mapping[pos]
            match_end = index_mapping[end_pos - 1] + 1 if end_pos <= len(index_mapping) else len(text)
            
            # Find words overlapping with the match
            overlapping = []
            for (word_start, word_end) in word_boundaries:
                if (word_start <= match_start < word_end) or \
                   (word_start < match_end <= word_end) or \
                   (match_start <= word_start and match_end >= word_end):
                    overlapping.append((word_start, word_end))
            
            # Adjust highlight span to cover full words
            if overlapping:
                adj_start = min(ws for (ws, we) in overlapping)
                adj_end = max(we for (ws, we) in overlapping)
            else:
                adj_start = match_start
                adj_end = match_end
            
            # Add text before the highlight
            if adj_start > last_highlight_end:
                result.append(text[last_highlight_end:adj_start])
            
            # Add highlighted text
            result.append(f'<span style="font-weight: bold; color: {highlight_color};">{text[adj_start:adj_end]}</span>')
            last_highlight_end = adj_end
            start_idx = end_pos  # Continue searching after current match
        
        # Add remaining text after last highlight
        result.append(text[last_highlight_end:])
        
        return ''.join(result)

    def _get_word_boundaries(self, text):
        """Identify start/end indices of words in the original text."""
        boundaries = []
        for match in re.finditer(r'\S+', text):
            start = match.start()
            end = match.end()
            boundaries.append((start, end))
        return boundaries

    def _normalize_char(self, char):
        """Normalize a single character (helper for highlight_phrase)."""
        char = self._remove_diacritics(char)
        char = self._normalize_hamza(char)
        return char


class QuranWordCache:
    _instance = None
    _words = []
    
    def __new__(cls, search_engine):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._search_engine = search_engine
            cls._cache_file = "quran_words.cache"
            cls._load_cache()
        return cls._instance
    
    @classmethod
    def _load_cache(cls):
        """Load cache or generate if missing"""
        try:
            cache_path = resource_path(cls._cache_file)
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cls._words = f.read().splitlines()
            else:
                cls._regenerate_cache()
        except Exception as e:
            logging.error(f"Word cache error: {str(e)}")
            cls._words = cls._search_engine.get_common_words()

    @classmethod
    def _regenerate_cache(cls):
        """Create new cache file"""
        try:
            all_words = cls._search_engine.get_all_simplified_words()
            cache_path = resource_path(cls._cache_file)
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(all_words))
            cls._words = all_words
        except Exception as e:
            logging.error(f"Cache regeneration failed: {str(e)}")
            cls._words = []