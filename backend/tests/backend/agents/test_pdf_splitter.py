import pytest
import sys
import os
import importlib.util

# Load pdf_splitter module directly without triggering package __init__
def load_module_directly():
    spec = importlib.util.spec_from_file_location(
        'pdf_splitter',
        os.path.join(os.path.dirname(__file__), '..', '..', '..', 'agents', 'pdf_splitter.py')
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

pdf_splitter = load_module_directly()
PDFSplitter = pdf_splitter.PDFSplitter
PageSegment = pdf_splitter.PageSegment

def test_page_segment_dataclass():
    seg = PageSegment(page_number=1, text="test", tables=[])
    assert seg.page_number == 1
    assert seg.text == "test"

def test_splitter_initialization():
    splitter = PDFSplitter(page_split_threshold=5)
    assert splitter.page_split_threshold == 5

def test_is_new_section_page():
    splitter = PDFSplitter()

    # 有标题模式
    page_with_title = PageSegment(
        page_number=1,
        text="一、基本信息\n企业名称：XXX",
        tables=[]
    )
    assert splitter._is_new_section_page(page_with_title) == True

    # 无标题模式
    page_continuation = PageSegment(
        page_number=2,
        text="续上页内容...",
        tables=[]
    )
    assert splitter._is_new_section_page(page_continuation) == False

def test_format_table():
    splitter = PDFSplitter()
    table = [["名称", "值"], ["A", "100"], ["B", "200"]]
    result = splitter._format_table(table)
    assert "名称 | 值" in result
    assert "A | 100" in result

if __name__ == '__main__':
    pytest.main([__file__, '-v'])