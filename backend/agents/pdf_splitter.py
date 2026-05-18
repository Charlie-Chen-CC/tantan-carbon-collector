"""PDF逻辑分割器 - 处理跨页表格"""
import pdfplumber
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class PageSegment:
    """页面分段"""
    page_number: int
    text: str
    tables: List[List[List[str]]]  # 页面内的表格

class PDFSplitter:
    """PDF按逻辑单元分割"""

    def __init__(self, page_split_threshold: int = 5):
        self.page_split_threshold = page_split_threshold

    def split(self, file_content: bytes) -> List[str]:
        """分割PDF返回文本片段"""
        with pdfplumber.open(file_content) as pdf:
            pages = self._extract_all_pages(pdf)

            if len(pages) <= self.page_split_threshold:
                # 少于阈值，不分割
                return [self._merge_pages(pages)]

            # 超过阈值，按逻辑单元分割
            segments = []
            current_segment_pages = []

            for page in pages:
                if self._is_new_section_page(page):
                    if current_segment_pages:
                        segments.append(self._merge_pages(current_segment_pages))
                    current_segment_pages = [page]
                else:
                    current_segment_pages.append(page)

            if current_segment_pages:
                segments.append(self._merge_pages(current_segment_pages))

            return segments

    def _extract_all_pages(self, pdf) -> List[PageSegment]:
        """提取所有页面"""
        pages = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            pages.append(PageSegment(
                page_number=i + 1,
                text=text,
                tables=tables
            ))
        return pages

    def _is_new_section_page(self, page: PageSegment) -> bool:
        """判断是否是新章节页面"""
        title_patterns = ['一、', '1.', '第一章', '表 ', '清单 ', '附件']
        return any(pattern in page.text[:200] for pattern in title_patterns)

    def _merge_pages(self, pages: List[PageSegment]) -> str:
        """合并页面文本"""
        texts = []
        for p in pages:
            texts.append(f"[页{p.page_number}]\n{p.text}")
            if p.tables:
                for table in p.tables:
                    texts.append(self._format_table(table))
        return "\n".join(texts)

    def _format_table(self, table: List[List[str]]) -> str:
        """格式化表格为文本"""
        if not table:
            return ""
        rows = []
        for row in table:
            rows.append(" | ".join(str(cell or "") for cell in row))
        return "\n".join(rows)