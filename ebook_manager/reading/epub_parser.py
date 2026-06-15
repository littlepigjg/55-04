import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from bs4 import BeautifulSoup


@dataclass
class EPUBChapter:
    index: int
    title: str
    file_path: str
    href: str
    content: str = ""
    paragraphs: List['EPUBParagraph'] = field(default_factory=list)
    word_count: int = 0


@dataclass
class EPUBParagraph:
    index: int
    paragraph_id: str
    text: str
    word_count: int
    element_ref: str = ""
    xpath: str = ""


@dataclass
class EPUBReadingPosition:
    chapter_index: int
    chapter_title: str
    paragraph_index: int
    paragraph_id: str
    percentage: float
    word_position: int
    total_words: int


class EPUBParser:
    def __init__(self, epub_path: str):
        self.epub_path = epub_path
        self._zip = None
        self._opf_path: Optional[str] = None
        self._root_dir: str = ""
        self._ns = {
            'opf': 'http://www.idpf.org/2007/opf',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'c': 'urn:oasis:names:tc:opendocument:xmlns:container'
        }
        self.chapters: List[EPUBChapter] = []
        self._manifest: Dict[str, str] = {}
        self._total_words: int = 0
        self._loaded = False

    def __enter__(self):
        self._zip = zipfile.ZipFile(self.epub_path, 'r')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._zip:
            self._zip.close()

    def _find_opf_path(self) -> Optional[str]:
        try:
            container = self._zip.read('META-INF/container.xml').decode('utf-8')
            root = ET.fromstring(container)
            rootfile = root.find('.//c:rootfile', self._ns)
            if rootfile is not None:
                return rootfile.get('full-path')
        except Exception:
            pass
        return None

    def _parse_opf(self):
        if not self._opf_path:
            self._opf_path = self._find_opf_path()
        if not self._opf_path:
            return
        
        self._root_dir = str(Path(self._opf_path).parent)
        if self._root_dir == '.':
            self._root_dir = ''
        
        opf_content = self._zip.read(self._opf_path).decode('utf-8', errors='ignore')
        root = ET.fromstring(opf_content)
        
        manifest = root.find('.//opf:manifest', self._ns)
        if manifest is not None:
            for item in manifest:
                item_id = item.get('id', '')
                href = item.get('href', '')
                self._manifest[item_id] = href
        
        self._parse_spine(root)
        self._parse_toc(root)

    def _parse_spine(self, root: ET.Element):
        spine = root.find('.//opf:spine', self._ns)
        if spine is None:
            return
        
        for idx, itemref in enumerate(spine):
            item_id = itemref.get('idref', '')
            if item_id in self._manifest:
                href = self._manifest[item_id]
                chapter = EPUBChapter(
                    index=idx,
                    title=f"第{idx + 1}章",
                    file_path=href,
                    href=href
                )
                self.chapters.append(chapter)

    def _parse_toc(self, root: ET.Element):
        manifest = root.find('.//opf:manifest', self._ns)
        if manifest is None:
            return
        
        toc_href = None
        for item in manifest:
            properties = item.get('properties', '')
            if 'nav' in properties:
                toc_href = item.get('href', '')
                break
        
        if toc_href and self._root_dir:
            toc_path = str(Path(self._root_dir) / toc_href)
        elif toc_href:
            toc_path = toc_href
        else:
            toc_path = 'toc.ncx'
        
        try:
            if toc_path in self._zip.namelist():
                toc_content = self._zip.read(toc_path).decode('utf-8', errors='ignore')
                self._parse_nav_doc(toc_content)
        except Exception:
            pass

    def _parse_nav_doc(self, content: str):
        soup = BeautifulSoup(content, 'html.parser')
        nav_map = soup.find('nav') or soup.find('navMap')
        if not nav_map:
            return
        
        nav_points = nav_map.find_all(['navPoint', 'li'])
        for idx, point in enumerate(nav_points):
            if idx >= len(self.chapters):
                break
            
            text_elem = point.find(['text', 'a', 'span'])
            if text_elem:
                title = text_elem.get_text(strip=True)
                if title:
                    self.chapters[idx].title = title

    def load_all_chapters(self):
        if self._loaded:
            return
        
        for chapter in self.chapters:
            self._load_chapter_content(chapter)
        
        self._total_words = sum(ch.word_count for ch in self.chapters)
        self._loaded = True

    def _load_chapter_content(self, chapter: EPUBChapter):
        if self._root_dir:
            file_path = str(Path(self._root_dir) / chapter.href)
        else:
            file_path = chapter.href
        
        try:
            content = self._zip.read(file_path).decode('utf-8', errors='ignore')
            chapter.content = content
            self._parse_paragraphs(chapter)
        except Exception:
            pass

    def _parse_paragraphs(self, chapter: EPUBChapter):
        soup = BeautifulSoup(chapter.content, 'html.parser')
        body = soup.find('body')
        if not body:
            return
        
        paragraphs = body.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote'])
        chapter.paragraphs = []
        chapter.word_count = 0
        
        for idx, p in enumerate(paragraphs):
            text = p.get_text(strip=True)
            if not text:
                continue
            
            p_id = p.get('id', f'p_{chapter.index}_{idx}')
            word_count = len(text.split())
            
            xpath = self._generate_xpath(p)
            
            para = EPUBParagraph(
                index=idx,
                paragraph_id=p_id,
                text=text,
                word_count=word_count,
                element_ref=str(p.name),
                xpath=xpath
            )
            chapter.paragraphs.append(para)
            chapter.word_count += word_count

    def _generate_xpath(self, element) -> str:
        parts = []
        current = element
        while current and current.name:
            parent = current.parent
            if parent is None:
                break
            
            siblings = parent.find_all(current.name, recursive=False)
            if len(siblings) > 1:
                pos = list(siblings).index(current) + 1
                parts.append(f'{current.name}[{pos}]')
            else:
                parts.append(current.name)
            current = parent
        
        parts.reverse()
        return '/' + '/'.join(parts)

    def get_total_words(self) -> int:
        if not self._loaded:
            self.load_all_chapters()
        return self._total_words

    def get_total_chapters(self) -> int:
        return len(self.chapters)

    def get_chapter(self, index: int) -> Optional[EPUBChapter]:
        if 0 <= index < len(self.chapters):
            if not self.chapters[index].content:
                self._load_chapter_content(self.chapters[index])
            return self.chapters[index]
        return None

    def get_paragraph(self, chapter_index: int, paragraph_index: int) -> Optional[EPUBParagraph]:
        chapter = self.get_chapter(chapter_index)
        if chapter and 0 <= paragraph_index < len(chapter.paragraphs):
            return chapter.paragraphs[paragraph_index]
        return None

    def get_position_from_percentage(self, percentage: float) -> Optional[EPUBReadingPosition]:
        if not self._loaded:
            self.load_all_chapters()
        
        target_words = int(self._total_words * percentage)
        accumulated = 0
        
        for ch_idx, chapter in enumerate(self.chapters):
            if accumulated + chapter.word_count >= target_words:
                words_into_chapter = target_words - accumulated
                para_accumulated = 0
                
                for para_idx, para in enumerate(chapter.paragraphs):
                    if para_accumulated + para.word_count >= words_into_chapter:
                        return EPUBReadingPosition(
                            chapter_index=ch_idx,
                            chapter_title=chapter.title,
                            paragraph_index=para_idx,
                            paragraph_id=para.paragraph_id,
                            percentage=percentage,
                            word_position=target_words,
                            total_words=self._total_words
                        )
                    para_accumulated += para.word_count
            accumulated += chapter.word_count
        
        return None

    def get_percentage_from_position(self, chapter_index: int, paragraph_index: int) -> float:
        if not self._loaded:
            self.load_all_chapters()
        
        if chapter_index >= len(self.chapters):
            return 1.0
        
        accumulated = 0
        for i in range(chapter_index):
            accumulated += self.chapters[i].word_count
        
        chapter = self.chapters[chapter_index]
        for i in range(min(paragraph_index, len(chapter.paragraphs))):
            accumulated += chapter.paragraphs[i].word_count
        
        return accumulated / self._total_words if self._total_words > 0 else 0.0

    def find_paragraph_by_id(self, paragraph_id: str) -> Optional[Tuple[int, int, EPUBParagraph]]:
        for ch_idx, chapter in enumerate(self.chapters):
            if not chapter.paragraphs:
                self._load_chapter_content(chapter)
            for para_idx, para in enumerate(chapter.paragraphs):
                if para.paragraph_id == paragraph_id:
                    return (ch_idx, para_idx, para)
        return None

    def get_current_position(self, chapter_index: int, paragraph_index: int) -> Optional[EPUBReadingPosition]:
        chapter = self.get_chapter(chapter_index)
        if not chapter:
            return None
        
        paragraph = self.get_paragraph(chapter_index, paragraph_index)
        if not paragraph:
            return None
        
        percentage = self.get_percentage_from_position(chapter_index, paragraph_index)
        accumulated = 0
        for i in range(chapter_index):
            accumulated += self.chapters[i].word_count
        for i in range(paragraph_index):
            accumulated += chapter.paragraphs[i].word_count
        
        return EPUBReadingPosition(
            chapter_index=chapter_index,
            chapter_title=chapter.title,
            paragraph_index=paragraph_index,
            paragraph_id=paragraph.paragraph_id,
            percentage=percentage,
            word_position=accumulated,
            total_words=self._total_words
        )

    def get_table_of_contents(self) -> List[Dict]:
        return [
            {
                'index': ch.index,
                'title': ch.title,
                'href': ch.href,
                'word_count': ch.word_count,
                'paragraph_count': len(ch.paragraphs)
            }
            for ch in self.chapters
        ]
