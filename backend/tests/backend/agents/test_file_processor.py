import pytest
import sys
import os
import importlib.util

# Load file_processor module directly without triggering package __init__
def load_module_directly():
    # Path from backend/tests/backend/agents/ up to tantan/ then down to backend/agents/
    spec = importlib.util.spec_from_file_location(
        'file_processor',
        os.path.join(os.path.dirname(__file__), '..', '..', '..', 'agents', 'file_processor.py')
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

file_processor = load_module_directly()
BatchFileProcessor = file_processor.BatchFileProcessor
FilePriority = file_processor.FilePriority
ProcessingResult = file_processor.ProcessingResult

def test_group_files():
    processor = BatchFileProcessor(section=1)
    files = [
        {'filename': '采购合同.pdf', 'content': b'...'},
        {'filename': '发票清单.xlsx', 'content': b'...'},
        {'filename': '检测报告.pdf', 'content': b'...'}
    ]
    grouped = processor.group_files(files)
    assert 'contract' in grouped
    assert 'invoice' in grouped
    assert 'report' in grouped
    assert len(grouped['contract']) == 1
    assert len(grouped['invoice']) == 1
    assert len(grouped['report']) == 1

def test_priority_order():
    assert FilePriority.CONTRACT.value < FilePriority.REPORT.value
    assert FilePriority.REPORT.value < FilePriority.INVOICE.value
    assert FilePriority.INVOICE.value < FilePriority.IMAGE.value

def test_file_type_detection():
    processor = BatchFileProcessor(section=1)

    assert processor._detect_file_type('合同.pdf') == 'contract'
    assert processor._detect_file_type('采购协议.docx') == 'contract'
    assert processor._detect_file_type('检测报告.pdf') == 'report'
    assert processor._detect_file_type('水质分析报告.pdf') == 'report'
    assert processor._detect_file_type('发票.pdf') == 'invoice'
    assert processor._detect_file_type('清单.xlsx') == 'invoice'
    assert processor._detect_file_type('工艺流程图.png') == 'image'
    assert processor._detect_file_type('数据.xlsx') == 'excel'

def test_merge_results_with_priority():
    """高优先级应覆盖低优先级"""
    processor = BatchFileProcessor(section=1)

    results = [
        {'data': {'企业名称': 'A公司'}, 'source': '合同.pdf', 'priority': 1, 'status': 'completed', 'error': None},
        {'data': {'企业名称': 'B公司'}, 'source': '发票.pdf', 'priority': 3, 'status': 'completed', 'error': None},
    ]

    merged = processor._merge_results(results)
    assert merged.extracted['企业名称'] == 'A公司'  # 合同优先级高

def test_merge_results_with_warnings():
    """冲突应产生警告"""
    processor = BatchFileProcessor(section=1)

    results = [
        {'data': {'注册资本': '100万'}, 'source': '合同.pdf', 'priority': 1, 'status': 'completed', 'error': None},
        {'data': {'注册资本': '200万'}, 'source': '报告.pdf', 'priority': 2, 'status': 'completed', 'error': None},
    ]

    merged = processor._merge_results(results)
    assert len(merged.warnings) == 1
    assert merged.warnings[0]['field'] == '注册资本'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])