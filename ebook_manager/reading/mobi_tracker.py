import struct
import os
from typing import Optional, Dict, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MOBIInfo:
    total_size: int
    header_size: int
    record_count: int
    mobi_type: int
    encoding: int
    title: str
    author: str
    total_chapters: int = 0


@dataclass
class MOBIPosition:
    percentage: float
    position_bytes: int
    record_index: int
    record_offset: int
    chapter_index: Optional[int] = None
    page_number: Optional[int] = None


class MOBITracker:
    def __init__(self, mobi_path: str):
        self.mobi_path = mobi_path
        self._file_size: int = 0
        self._mobi_info: Optional[MOBIInfo] = None
        self._record_offsets: List[int] = []
        self._chapter_boundaries: List[int] = []
        self._loaded = False

    def __enter__(self):
        self._load_metadata()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def _load_metadata(self):
        if self._loaded:
            return
        
        self._file_size = os.path.getsize(self.mobi_path)
        
        try:
            with open(self.mobi_path, 'rb') as f:
                self._parse_palm_header(f)
                self._parse_mobi_header(f)
                self._parse_chapters(f)
        except Exception:
            pass
        
        self._loaded = True

    def _parse_palm_header(self, f):
        f.seek(0)
        header = f.read(78)
        if len(header) < 78:
            return
        
        record_count = struct.unpack('>H', header[76:78])[0]
        
        self._record_offsets = []
        for i in range(record_count):
            f.seek(78 + i * 8)
            offset_data = f.read(4)
            if len(offset_data) == 4:
                offset = struct.unpack('>I', offset_data)[0]
                self._record_offsets.append(offset)
        
        title_bytes = header[0:32].split(b'\x00')[0]
        title = title_bytes.decode('latin-1', errors='ignore').strip()
        
        self._mobi_info = MOBIInfo(
            total_size=self._file_size,
            header_size=78 + record_count * 8,
            record_count=record_count,
            mobi_type=0,
            encoding=0,
            title=title,
            author=""
        )

    def _parse_mobi_header(self, f):
        if not self._mobi_info or not self._record_offsets:
            return
        
        try:
            f.seek(self._record_offsets[0])
            palm_doc_header = f.read(16)
            if len(palm_doc_header) < 16:
                return
            
            mobi_start = struct.unpack('>I', palm_doc_header[12:16])[0]
            f.seek(self._record_offsets[0] + mobi_start)
            mobi_header = f.read(232)
            
            if len(mobi_header) >= 24:
                identifier = mobi_header[0:4]
                if identifier == b'MOBI':
                    mobi_type = struct.unpack('>I', mobi_header[12:16])[0]
                    encoding = struct.unpack('>I', mobi_header[16:20])[0]
                    
                    self._mobi_info.mobi_type = mobi_type
                    self._mobi_info.encoding = encoding
                    
                    title_offset = struct.unpack('>I', mobi_header[84:88])[0]
                    title_length = struct.unpack('>I', mobi_header[88:92])[0]
                    
                    if title_offset and title_length:
                        f.seek(self._record_offsets[0] + mobi_start + title_offset)
                        title_bytes = f.read(title_length)
                        codec = 'utf-8' if encoding == 65001 else 'cp1252'
                        try:
                            self._mobi_info.title = title_bytes.decode(codec, errors='ignore').strip('\x00')
                        except Exception:
                            pass
        except Exception:
            pass

    def _parse_chapters(self, f):
        if not self._record_offsets:
            return
        
        try:
            record0_start = self._record_offsets[0]
            f.seek(record0_start)
            record0 = f.read(4096)
            
            idx_pos = record0.find(b'INDX')
            if idx_pos > 0:
                indx_data = record0[idx_pos:]
                if len(indx_data) >= 24:
                    count = struct.unpack('>I', indx_data[20:24])[0]
                    self._mobi_info.total_chapters = min(count, 1000)
            
            self._chapter_boundaries = []
            total_records = len(self._record_offsets)
            approx_chapters = max(1, total_records // 10)
            for i in range(approx_chapters):
                pos = int((i / approx_chapters) * (self._file_size - self._mobi_info.header_size))
                self._chapter_boundaries.append(pos + self._mobi_info.header_size)
        except Exception:
            pass

    def get_total_size(self) -> int:
        if not self._loaded:
            self._load_metadata()
        return self._file_size

    def get_total_chapters(self) -> int:
        if not self._loaded:
            self._load_metadata()
        return self._mobi_info.total_chapters if self._mobi_info else 0

    def get_readable_size(self) -> int:
        if not self._loaded:
            self._load_metadata()
        header_size = self._mobi_info.header_size if self._mobi_info else 0
        return max(0, self._file_size - header_size)

    def get_position_from_percentage(self, percentage: float) -> MOBIPosition:
        if not self._loaded:
            self._load_metadata()
        
        percentage = max(0.0, min(1.0, percentage))
        readable_size = self.get_readable_size()
        header_size = self._mobi_info.header_size if self._mobi_info else 0
        
        position_bytes = int(percentage * readable_size) + header_size
        position_bytes = min(position_bytes, self._file_size - 1)
        
        record_index = 0
        record_offset = 0
        
        if self._record_offsets:
            for i, offset in enumerate(self._record_offsets):
                if offset <= position_bytes:
                    record_index = i
                    record_offset = position_bytes - offset
                else:
                    break
        
        chapter_index = None
        if self._chapter_boundaries:
            for i, boundary in enumerate(self._chapter_boundaries):
                if position_bytes >= boundary:
                    chapter_index = i
                else:
                    break
        
        total_records = max(1, len(self._record_offsets) - 1)
        page_number = int((record_index / total_records) * 1000)
        
        return MOBIPosition(
            percentage=percentage,
            position_bytes=position_bytes,
            record_index=record_index,
            record_offset=record_offset,
            chapter_index=chapter_index,
            page_number=page_number
        )

    def get_percentage_from_position(self, position_bytes: int) -> float:
        if not self._loaded:
            self._load_metadata()
        
        readable_size = self.get_readable_size()
        if readable_size <= 0:
            return 0.0
        
        header_size = self._mobi_info.header_size if self._mobi_info else 0
        relative_pos = max(0, position_bytes - header_size)
        
        return min(1.0, relative_pos / readable_size)

    def get_estimated_word_count(self) -> int:
        if not self._loaded:
            self._load_metadata()
        
        avg_bytes_per_word = 2.5
        return int(self.get_readable_size() / avg_bytes_per_word)

    def get_estimated_pages(self) -> int:
        if not self._loaded:
            self._load_metadata()
        
        avg_bytes_per_page = 2000
        return max(1, int(self.get_readable_size() / avg_bytes_per_page))

    def get_progress_info(self, percentage: float) -> Dict:
        if not self._loaded:
            self._load_metadata()
        
        percentage = max(0.0, min(1.0, percentage))
        position = self.get_position_from_percentage(percentage)
        
        return {
            'percentage': percentage,
            'position_bytes': position.position_bytes,
            'record_index': position.record_index,
            'chapter_index': position.chapter_index,
            'page_number': position.page_number,
            'estimated_words': int(percentage * self.get_estimated_word_count()),
            'estimated_pages': int(percentage * self.get_estimated_pages()),
            'total_words': self.get_estimated_word_count(),
            'total_pages': self.get_estimated_pages(),
            'bytes_remaining': self._file_size - position.position_bytes,
            'readable_remaining': self.get_readable_size() - (position.position_bytes - (self._mobi_info.header_size if self._mobi_info else 0))
        }

    def get_reading_speed(self, start_percentage: float, end_percentage: float, 
                         seconds_elapsed: int) -> float:
        if seconds_elapsed <= 0:
            return 0.0
        
        total_words = self.get_estimated_word_count()
        words_read = int((end_percentage - start_percentage) * total_words)
        minutes = seconds_elapsed / 60.0
        
        return words_read / minutes if minutes > 0 else 0.0

    def estimate_remaining_time(self, current_percentage: float, 
                                words_per_minute: float) -> Optional[int]:
        if words_per_minute <= 0:
            return None
        
        remaining_words = int((1.0 - current_percentage) * self.get_estimated_word_count())
        return int(remaining_words / words_per_minute)
