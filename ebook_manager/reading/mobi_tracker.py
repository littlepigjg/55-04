import struct
import os
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
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
class MOBIPageAnchor:
    page_number: int
    record_index: int
    record_offset: int
    byte_position: int
    chapter_index: Optional[int] = None
    text_snippet: str = ""


@dataclass
class MOBIPosition:
    page_number: int
    record_index: int
    record_offset: int
    byte_position: int
    chapter_index: Optional[int] = None
    percentage: float = 0.0
    anchor: Optional[MOBIPageAnchor] = None


class MOBITracker:
    def __init__(self, mobi_path: str):
        self.mobi_path = mobi_path
        self._file_size: int = 0
        self._mobi_info: Optional[MOBIInfo] = None
        self._record_offsets: List[int] = []
        self._chapter_boundaries: List[int] = []
        self._page_anchors: List[MOBIPageAnchor] = []
        self._total_pages: int = 0
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
                self._build_page_anchors(f)
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

    def _build_page_anchors(self, f):
        if not self._record_offsets or len(self._record_offsets) < 2:
            self._total_pages = 1
            self._page_anchors = [MOBIPageAnchor(
                page_number=0,
                record_index=0,
                record_offset=0,
                byte_position=self._mobi_info.header_size if self._mobi_info else 0,
            )]
            return

        try:
            content_records = len(self._record_offsets) - 1
            records_per_page = max(1, content_records // max(1, content_records // 5))
            self._page_anchors = []
            page_num = 0

            for rec_idx in range(1, len(self._record_offsets)):
                if rec_idx % records_per_page == 1 or records_per_page == 1:
                    byte_pos = self._record_offsets[rec_idx]
                    chapter_idx = self._find_chapter_at_byte(byte_pos)
                    snippet = self._read_snippet(f, rec_idx)

                    self._page_anchors.append(MOBIPageAnchor(
                        page_number=page_num,
                        record_index=rec_idx,
                        record_offset=0,
                        byte_position=byte_pos,
                        chapter_index=chapter_idx,
                        text_snippet=snippet,
                    ))
                    page_num += 1

            self._total_pages = max(1, page_num)

            if not self._page_anchors:
                self._page_anchors = [MOBIPageAnchor(
                    page_number=0,
                    record_index=1,
                    record_offset=0,
                    byte_position=self._record_offsets[1] if len(self._record_offsets) > 1 else 0,
                )]
                self._total_pages = 1
        except Exception:
            self._total_pages = 1
            self._page_anchors = [MOBIPageAnchor(
                page_number=0, record_index=0, record_offset=0,
                byte_position=self._mobi_info.header_size if self._mobi_info else 0,
            )]

    def _find_chapter_at_byte(self, byte_pos: int) -> Optional[int]:
        for i, boundary in enumerate(self._chapter_boundaries):
            if byte_pos < boundary:
                return max(0, i - 1) if i > 0 else 0
        return len(self._chapter_boundaries) - 1 if self._chapter_boundaries else None

    def _read_snippet(self, f, record_index: int, max_len: int = 40) -> str:
        if record_index >= len(self._record_offsets):
            return ""
        try:
            start = self._record_offsets[record_index]
            end = self._record_offsets[record_index + 1] if record_index + 1 < len(self._record_offsets) else start + 512
            f.seek(start)
            raw = f.read(min(end - start, 512))
            codec = 'utf-8' if (self._mobi_info and self._mobi_info.encoding == 65001) else 'cp1252'
            text = raw.decode(codec, errors='ignore')
            text = ''.join(c for c in text if c.isprintable() or c.isspace()).strip()
            return text[:max_len]
        except Exception:
            return ""

    def get_total_pages(self) -> int:
        if not self._loaded:
            self._load_metadata()
        return self._total_pages

    def get_total_chapters(self) -> int:
        if not self._loaded:
            self._load_metadata()
        return self._mobi_info.total_chapters if self._mobi_info else 0

    def get_page_anchors(self) -> List[MOBIPageAnchor]:
        if not self._loaded:
            self._load_metadata()
        return list(self._page_anchors)

    def get_position_from_page(self, page_number: int) -> MOBIPosition:
        if not self._loaded:
            self._load_metadata()
        if not self._page_anchors:
            return MOBIPosition(
                page_number=0, record_index=0, record_offset=0,
                byte_position=0, percentage=0.0,
            )

        page_number = max(0, min(page_number, self._total_pages - 1))

        anchor = self._page_anchors[page_number]
        percentage = page_number / max(1, self._total_pages - 1)

        return MOBIPosition(
            page_number=page_number,
            record_index=anchor.record_index,
            record_offset=0,
            byte_position=anchor.byte_position,
            chapter_index=anchor.chapter_index,
            percentage=percentage,
            anchor=anchor,
        )

    def get_position_from_percentage(self, percentage: float) -> MOBIPosition:
        if not self._loaded:
            self._load_metadata()
        percentage = max(0.0, min(1.0, percentage))
        if not self._page_anchors:
            return MOBIPosition(
                page_number=0, record_index=0, record_offset=0,
                byte_position=0, percentage=percentage,
            )
        target_page = int(percentage * (self._total_pages - 1))
        return self.get_position_from_page(target_page)

    def find_page_by_snippet(self, snippet: str) -> Optional[int]:
        if not self._loaded:
            self._load_metadata()
        snippet_lower = snippet.lower()
        for anchor in self._page_anchors:
            if snippet_lower in anchor.text_snippet.lower():
                return anchor.page_number
        return None

    def find_page_by_record(self, record_index: int) -> Optional[int]:
        if not self._loaded:
            self._load_metadata()
        best_page = None
        for anchor in self._page_anchors:
            if anchor.record_index <= record_index:
                best_page = anchor.page_number
            else:
                break
        return best_page

    def get_estimated_word_count(self) -> int:
        if not self._loaded:
            self._load_metadata()
        header_size = self._mobi_info.header_size if self._mobi_info else 0
        readable = max(0, self._file_size - header_size)
        return int(readable / 2.5)

    def get_estimated_pages(self) -> int:
        if not self._loaded:
            self._load_metadata()
        return self._total_pages

    def get_progress_info(self, page_number: int) -> Dict:
        if not self._loaded:
            self._load_metadata()
        pos = self.get_position_from_page(page_number)
        total_words = self.get_estimated_word_count()
        return {
            'page_number': page_number,
            'total_pages': self._total_pages,
            'percentage': pos.percentage,
            'record_index': pos.record_index,
            'chapter_index': pos.chapter_index,
            'estimated_words': int(pos.percentage * total_words),
            'total_words': total_words,
            'pages_remaining': self._total_pages - page_number - 1,
            'anchor_snippet': pos.anchor.text_snippet if pos.anchor else "",
        }

    def get_reading_speed(self, start_page: int, end_page: int,
                         seconds_elapsed: int) -> float:
        if seconds_elapsed <= 0:
            return 0.0
        total_words = self.get_estimated_word_count()
        start_pct = start_page / max(1, self._total_pages - 1)
        end_pct = end_page / max(1, self._total_pages - 1)
        words_read = int((end_pct - start_pct) * total_words)
        minutes = seconds_elapsed / 60.0
        return words_read / minutes if minutes > 0 else 0.0

    def estimate_remaining_time(self, current_page: int,
                                words_per_minute: float) -> Optional[int]:
        if words_per_minute <= 0:
            return None
        remaining_pct = 1.0 - (current_page / max(1, self._total_pages - 1))
        remaining_words = int(remaining_pct * self.get_estimated_word_count())
        return int(remaining_words / words_per_minute)
