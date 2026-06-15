import struct
import os
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import bisect
import hashlib


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
    first_content_record: int = 1
    first_non_book_record: int = 0


@dataclass
class MOBIPageAnchor:
    page_number: int
    record_index: int
    record_offset: int
    byte_position: int
    chapter_index: Optional[int] = None
    content_hash: str = ""
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
        self._record_sizes: List[int] = []
        self._chapter_records: List[int] = []
        self._page_anchors: List[MOBIPageAnchor] = []
        self._total_pages: int = 0
        self._loaded = False
        self._first_content_record: int = 1
        self._last_content_record: int = 0

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
                self._parse_ncx_chapters(f)
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
        self._record_sizes = []
        for i in range(len(self._record_offsets)):
            if i + 1 < len(self._record_offsets):
                self._record_sizes.append(self._record_offsets[i + 1] - self._record_offsets[i])
            else:
                self._record_sizes.append(4096)
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

                    if len(mobi_header) >= 88:
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

                    if len(mobi_header) >= 84:
                        first_content = struct.unpack('>I', mobi_header[80:84])[0]
                        if first_content > 0:
                            self._first_content_record = first_content

                    if len(mobi_header) >= 200:
                        first_non_book = struct.unpack('>I', mobi_header[196:200])[0]
                        if first_non_book > 0:
                            self._mobi_info.first_non_book_record = first_non_book
                            self._last_content_record = first_non_book - 1

            self._last_content_record = self._last_content_record or (len(self._record_offsets) - 1)
            self._first_content_record = max(1, self._first_content_record)
        except Exception:
            pass

    def _parse_ncx_chapters(self, f):
        if not self._record_offsets:
            return
        try:
            record0_start = self._record_offsets[0]
            f.seek(record0_start)
            record0 = f.read(min(65536, self._record_offsets[1] - record0_start if len(self._record_offsets) > 1 else 65536))

            ncx_records = self._find_ncx_record_indices(f)

            if ncx_records:
                self._chapter_records = ncx_records
                self._mobi_info.total_chapters = len(ncx_records)
            else:
                cand1 = record0.find(b'<nav')
                cand2 = record0.find(b'<guide')
                cand3 = record0.find(b'<html')
                if cand1 >= 0 or cand2 >= 0 or cand3 >= 0:
                    self._chapter_records = []
                    self._mobi_info.total_chapters = 0

            if not self._chapter_records:
                self._chapter_records = self._estimate_chapter_records()
                self._mobi_info.total_chapters = len(self._chapter_records)

        except Exception:
            self._chapter_records = self._estimate_chapter_records()
            self._mobi_info.total_chapters = len(self._chapter_records)

    def _find_ncx_record_indices(self, f) -> List[int]:
        ncx_records = []
        try:
            for rec_idx in range(self._first_content_record, min(self._last_content_record + 1, len(self._record_offsets))):
                start = self._record_offsets[rec_idx]
                end = self._record_offsets[rec_idx + 1] if rec_idx + 1 < len(self._record_offsets) else start + 512
                f.seek(start)
                chunk = f.read(min(end - start, 256))
                lower = chunk.lower()
                if b'<navpoint' in lower or b'<navmap' in lower:
                    ncx_records.append(rec_idx)
        except Exception:
            pass
        return ncx_records

    def _estimate_chapter_records(self) -> List[int]:
        if not self._record_offsets:
            return []
        total_content = self._last_content_record - self._first_content_record + 1
        if total_content <= 0:
            return [self._first_content_record]
        num_chapters = max(1, total_content // 10)
        step = total_content // num_chapters
        return [self._first_content_record + i * step for i in range(num_chapters)]

    def _build_page_anchors(self, f):
        if not self._record_offsets or len(self._record_offsets) < 2:
            self._total_pages = 1
            self._page_anchors = [MOBIPageAnchor(
                page_number=0,
                record_index=self._first_content_record,
                record_offset=0,
                byte_position=self._record_offsets[self._first_content_record] if self._first_content_record < len(self._record_offsets) else 0,
            )]
            return

        try:
            self._page_anchors = []
            page_num = 0

            for rec_idx in range(self._first_content_record, self._last_content_record + 1):
                if rec_idx >= len(self._record_offsets):
                    break

                byte_pos = self._record_offsets[rec_idx]
                chapter_idx = self._find_chapter_for_record(rec_idx)
                content_hash = self._compute_record_hash(f, rec_idx)
                snippet = self._read_snippet(f, rec_idx)

                self._page_anchors.append(MOBIPageAnchor(
                    page_number=page_num,
                    record_index=rec_idx,
                    record_offset=0,
                    byte_position=byte_pos,
                    chapter_index=chapter_idx,
                    content_hash=content_hash,
                    text_snippet=snippet,
                ))
                page_num += 1

            self._total_pages = max(1, page_num)

            if not self._page_anchors:
                self._page_anchors = [MOBIPageAnchor(
                    page_number=0,
                    record_index=self._first_content_record,
                    record_offset=0,
                    byte_position=self._record_offsets[self._first_content_record] if self._first_content_record < len(self._record_offsets) else 0,
                )]
                self._total_pages = 1
        except Exception:
            self._total_pages = 1
            self._page_anchors = [MOBIPageAnchor(
                page_number=0, record_index=self._first_content_record, record_offset=0,
                byte_position=self._record_offsets[self._first_content_record] if self._first_content_record < len(self._record_offsets) else 0,
            )]

    def _find_chapter_for_record(self, rec_idx: int) -> Optional[int]:
        if not self._chapter_records:
            return None
        idx = bisect.bisect_right(self._chapter_records, rec_idx)
        return max(0, idx - 1)

    def _compute_record_hash(self, f, record_index: int) -> str:
        if record_index >= len(self._record_offsets):
            return ""
        try:
            start = self._record_offsets[record_index]
            size = self._record_sizes[record_index] if record_index < len(self._record_sizes) else 512
            f.seek(start)
            raw = f.read(min(size, 512))
            return hashlib.md5(raw).hexdigest()[:12]
        except Exception:
            return ""

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

    def get_position_from_record(self, record_index: int, record_offset: int = 0) -> MOBIPosition:
        if not self._loaded:
            self._load_metadata()
        if not self._page_anchors:
            return MOBIPosition(
                page_number=0, record_index=record_index,
                record_offset=record_offset, byte_position=0, percentage=0.0,
            )

        page_num = self._find_page_by_record_index(record_index)
        anchor = self._page_anchors[page_num]
        percentage = page_num / max(1, self._total_pages - 1)

        return MOBIPosition(
            page_number=page_num,
            record_index=anchor.record_index,
            record_offset=record_offset,
            byte_position=anchor.byte_position,
            chapter_index=anchor.chapter_index,
            percentage=percentage,
            anchor=anchor,
        )

    def _find_page_by_record_index(self, record_index: int) -> int:
        lo, hi = 0, len(self._page_anchors) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self._page_anchors[mid].record_index < record_index:
                lo = mid + 1
            elif self._page_anchors[mid].record_index > record_index:
                hi = mid - 1
            else:
                return mid
        return max(0, hi)

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

    def find_page_by_hash(self, content_hash: str) -> Optional[int]:
        if not self._loaded:
            self._load_metadata()
        for anchor in self._page_anchors:
            if anchor.content_hash == content_hash:
                return anchor.page_number
        return None

    def find_page_by_record(self, record_index: int) -> Optional[int]:
        if not self._loaded:
            self._load_metadata()
        return self._find_page_by_record_index(record_index)

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
            'anchor_hash': pos.anchor.content_hash if pos.anchor else "",
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
