from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import re


@dataclass
class PDFPageInfo:
    page_number: int
    total_pages: int
    text_content: str = ""
    word_count: int = 0
    percentage: float = 0.0
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass
class PDFTextPosition:
    page_number: int
    text: str
    word_index: int
    x: float
    y: float
    width: float
    height: float
    context: str = ""


class PDFTracker:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self._reader = None
        self._total_pages: int = 0
        self._total_words: int = 0
        self._page_word_counts: List[int] = []
        self._pages_cache: Dict[int, PDFPageInfo] = {}
        self._loaded = False

    def __enter__(self):
        try:
            from PyPDF2 import PdfReader
            self._reader = PdfReader(self.pdf_path)
            self._total_pages = len(self._reader.pages)
        except ImportError:
            raise RuntimeError("PyPDF2 not installed. Please install PyPDF2 to use PDF tracking.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._reader = None

    def _ensure_loaded(self):
        if self._loaded:
            return
        
        if self._reader is None:
            from PyPDF2 import PdfReader
            self._reader = PdfReader(self.pdf_path)
            self._total_pages = len(self._reader.pages)
        
        self._page_word_counts = []
        self._total_words = 0
        
        for i in range(self._total_pages):
            page_text = self._extract_page_text(i)
            word_count = len(self._split_words(page_text))
            self._page_word_counts.append(word_count)
            self._total_words += word_count
        
        self._loaded = True

    def _extract_page_text(self, page_num: int) -> str:
        try:
            page = self._reader.pages[page_num]
            text = page.extract_text() or ""
            return text
        except Exception:
            return ""

    def _split_words(self, text: str) -> List[str]:
        return re.findall(r'\b[\w\u4e00-\u9fff]+\b', text, re.UNICODE)

    def get_total_pages(self) -> int:
        self._ensure_loaded()
        return self._total_pages

    def get_total_words(self) -> int:
        self._ensure_loaded()
        return self._total_words

    def get_page_info(self, page_number: int) -> Optional[PDFPageInfo]:
        if page_number < 0 or page_number >= self._total_pages:
            return None
        
        if page_number in self._pages_cache:
            return self._pages_cache[page_number]
        
        self._ensure_loaded()
        
        text = self._extract_page_text(page_number)
        word_count = self._page_word_counts[page_number]
        
        words_before = sum(self._page_word_counts[:page_number])
        percentage = words_before / self._total_words if self._total_words > 0 else 0.0
        
        try:
            page = self._reader.pages[page_number]
            if hasattr(page, 'mediabox'):
                width = float(page.mediabox.width)
                height = float(page.mediabox.height)
            else:
                width, height = 612, 792
        except Exception:
            width, height = 612, 792
        
        info = PDFPageInfo(
            page_number=page_number,
            total_pages=self._total_pages,
            text_content=text,
            word_count=word_count,
            percentage=percentage,
            width=width,
            height=height
        )
        
        self._pages_cache[page_number] = info
        return info

    def get_page_from_percentage(self, percentage: float) -> Optional[PDFPageInfo]:
        self._ensure_loaded()
        target_words = int(self._total_words * percentage)
        
        accumulated = 0
        for page_num, word_count in enumerate(self._page_word_counts):
            if accumulated + word_count >= target_words:
                return self.get_page_info(page_num)
            accumulated += word_count
        
        return self.get_page_info(self._total_pages - 1)

    def get_percentage_from_page(self, page_number: int) -> float:
        self._ensure_loaded()
        if page_number < 0:
            return 0.0
        if page_number >= self._total_pages:
            return 1.0
        
        words_before = sum(self._page_word_counts[:page_number])
        return words_before / self._total_words if self._total_words > 0 else 0.0

    def find_text_position(self, search_text: str) -> List[PDFTextPosition]:
        self._ensure_loaded()
        results = []
        
        for page_num in range(self._total_pages):
            page = self.get_page_info(page_num)
            if not page:
                continue
            
            lower_text = page.text_content.lower()
            lower_search = search_text.lower()
            
            pos = 0
            while True:
                idx = lower_text.find(lower_search, pos)
                if idx == -1:
                    break
                
                context_start = max(0, idx - 50)
                context_end = min(len(page.text_content), idx + len(search_text) + 50)
                context = page.text_content[context_start:context_end]
                
                words_before = self._split_words(page.text_content[:idx])
                word_index = len(words_before)
                
                x, y = self._estimate_text_coordinates(page, idx)
                
                results.append(PDFTextPosition(
                    page_number=page_num,
                    text=page.text_content[idx:idx + len(search_text)],
                    word_index=word_index,
                    x=x,
                    y=y,
                    width=len(search_text) * 5,
                    height=12,
                    context=context
                ))
                
                pos = idx + 1
        
        return results

    def _estimate_text_coordinates(self, page: PDFPageInfo, char_index: int) -> Tuple[float, float]:
        if not page.text_content:
            return (0, 0)
        
        line_height = page.height / max(1, page.text_content.count('\n') + 1)
        chars_per_line = max(1, len(page.text_content) / max(1, page.text_content.count('\n') + 1))
        
        line_num = char_index // chars_per_line
        char_in_line = char_index % chars_per_line
        
        x = (char_in_line / chars_per_line) * page.width * 0.8 + page.width * 0.1
        y = page.height - (line_num * line_height) - line_height
        
        return (x, y)

    def get_text_at_position(self, page_number: int, x: float, y: float, 
                            radius: float = 50) -> Optional[str]:
        page = self.get_page_info(page_number)
        if not page or not page.text_content:
            return None
        
        lines = page.text_content.split('\n')
        if not lines:
            return None
        
        line_height = page.height / max(1, len(lines))
        line_index = int((page.height - y) / line_height)
        line_index = max(0, min(line_index, len(lines) - 1))
        
        return lines[line_index].strip()

    def get_current_position(self, page_number: int, x: float = 0.0, y: float = 0.0) -> PDFPageInfo:
        info = self.get_page_info(page_number) or PDFPageInfo(
            page_number=page_number,
            total_pages=self._total_pages
        )
        info.x = x
        info.y = y
        return info

    def get_progress_info(self, current_page: int) -> Dict:
        self._ensure_loaded()
        
        words_before = sum(self._page_word_counts[:current_page])
        words_in_page = 0
        if current_page < len(self._page_word_counts):
            words_in_page = self._page_word_counts[current_page]
        
        total_words_before = words_before
        total_words_remaining = self._total_words - words_before - words_in_page
        
        return {
            'current_page': current_page,
            'total_pages': self._total_pages,
            'words_read': words_before,
            'words_total': self._total_words,
            'percentage': words_before / self._total_words if self._total_words > 0 else 0.0,
            'pages_remaining': self._total_pages - current_page - 1,
            'words_remaining': total_words_remaining,
            'page_percentage': (current_page + 1) / self._total_pages if self._total_pages > 0 else 0.0
        }

    def get_reading_speed(self, start_page: int, end_page: int, seconds_elapsed: int) -> float:
        if seconds_elapsed <= 0:
            return 0.0
        
        self._ensure_loaded()
        
        if start_page < 0:
            start_page = 0
        if end_page >= self._total_pages:
            end_page = self._total_pages - 1
        
        words_read = sum(self._page_word_counts[start_page:end_page + 1])
        minutes = seconds_elapsed / 60.0
        
        return words_read / minutes if minutes > 0 else 0.0

    def estimate_remaining_time(self, current_page: int, words_per_minute: float) -> Optional[int]:
        if words_per_minute <= 0:
            return None
        
        self._ensure_loaded()
        remaining_words = self._total_words - sum(self._page_word_counts[:current_page])
        
        return int(remaining_words / words_per_minute)
