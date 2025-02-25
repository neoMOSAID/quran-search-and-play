import re
import os, sys
import importlib.resources
import logging



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

    def _load_data(self):
        """Load all required data files from the quran_text package"""
        self._load_chapters()
        self._load_verses('uthmani.txt', self._uthmani)
        self._load_verses('simplified.txt', self._simplified)
        self._build_verse_counts()

    def _load_chapters(self):
        """Load chapter names from the quran_text package"""
        try:
            text = importlib.resources.read_text("quran_text", "chapters.txt", encoding="utf-8")
            self._chapters = [line.strip() for line in text.splitlines()]
        except Exception as e:
            raise RuntimeError(f"Could not load chapters: {e}")

    def _load_verses(self, filename, target_dict):
        """Generic verse loader for different versions from the quran_text package"""
        try:
            text = importlib.resources.read_text("quran_text", filename, encoding="utf-8")
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
        """Normalize different hamza forms"""
        replacements = {
            'إ': 'ا',
            'أ': 'ا',
            'آ': 'ا',
            'ء': '',
            'ى': 'ي',
            'ة': 'ه'
        }
        for orig, repl in replacements.items():
            text = text.replace(orig, repl)
        return text

    @staticmethod
    def _remove_diacritics(text):
        """Remove Arabic diacritical marks"""
        return re.sub(r'[\u064B-\u065F\u0670\u06D6-\u06ED]', '', text)

    @staticmethod
    def _normalize_text(text=""):
        """Full text normalization pipeline"""
        text = QuranSearch._remove_diacritics(text)
        text = QuranSearch._normalize_hamza(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def search_verses(self, query):
        """Always search in simplified version but return both texts"""
        normalized_query = self._normalize_text(query)
        results = []
        
        for (surah, ayah), data in self._simplified.items():
            if normalized_query in self._normalize_text(data['text']):
                uthmani_text = self._uthmani.get((surah, ayah), {}).get('text', '')
                results.append({
                    'surah': surah,
                    'ayah': ayah,
                    'text_simplified': data['text'],
                    'text_uthmani': uthmani_text,
                    'chapter': self.get_chapter_name(surah)
                })
        
        return sorted(results, key=lambda x: (x['surah'], x['ayah']))

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
    
    def search_by_surah(self, surah):
        """Retrieve all verses of a given Surah."""
        results = []
        for ayah in range(1, self.get_verse_count(surah) + 1):
            results.append({
                'surah': surah,
                'ayah': ayah,
                'text_simplified': self._simplified.get((surah, ayah), {}).get('text', ''),
                'text_uthmani': self._uthmani.get((surah, ayah), {}).get('text', ''),
                'chapter': self.get_chapter_name(surah)
            })
        return results

    def search_by_surah_ayah(self, surah, first, last=None):
        """Retrieve a specific verse by Surah and Ayah number."""
        results = []
        if last is None:
            last = first
        for ayah in range(first, last + 1):
            results.append({
                'surah': surah,
                'ayah': ayah,
                'text_simplified': self._simplified.get((surah, ayah), {}).get('text', ''),
                'text_uthmani': self._uthmani.get((surah, ayah), {}).get('text', ''),
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
        is_valid, error = self.validate_reference(surah, ayah)
        if not is_valid:
            return []
        
        total_ayahs = self.get_verse_count(surah)
        
        # Define the range (max 5 before and 5 after)
        start = max(1, ayah - 5)
        end = min(total_ayahs, ayah + 5)

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
        normalized_query = self._normalize_text(query)
        results = []
        
        for (surah, ayah), data in self._simplified.items():
            if normalized_query in self._normalize_text(data['text']):
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