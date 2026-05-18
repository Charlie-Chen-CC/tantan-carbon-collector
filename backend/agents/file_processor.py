"""批量文件处理器 - 碳管师收资系统"""
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import uuid

class FilePriority(Enum):
    """文件优先级：同一字段冲突时，高优先级覆盖低优先级"""
    CONTRACT = 1      # 合同
    REPORT = 2       # 检测报告
    INVOICE = 3      # 发票/清单
    IMAGE = 4        # 图片

@dataclass
class FileSegment:
    """文件分段信息"""
    file_id: str
    filename: str
    file_type: str  # excel, invoice, report, contract, image
    priority: FilePriority
    content: Any    # 提取后的数据

@dataclass
class ProcessingResult:
    """处理结果"""
    status: str  # completed, partial, failed
    extracted: Dict[str, Any]
    warnings: List[Dict]  # 冲突/置信度警告
    failed_files: List[Dict]  # 失败文件详情

class BatchFileProcessor:
    """批量文件处理器"""

    def __init__(self, section: int):
        self.section = section
        from tantan.backend.agents.file_extractor import FileExtractAgent
        self.extractor = FileExtractAgent(section)

    def group_files(self, files: List[Dict]) -> Dict[str, List]:
        """按文件类型分组"""
        groups = {
            'excel': [],
            'invoice': [],
            'report': [],
            'contract': [],
            'image': []
        }
        for f in files:
            file_type = self._detect_file_type(f['filename'])
            groups[file_type].append(f)
        return groups

    def _detect_file_type(self, filename: str) -> str:
        """检测文件类型"""
        ext = filename.split('.')[-1].lower()
        name_lower = filename.lower()

        # 图片扩展名优先检测
        if ext in ['png', 'jpg', 'jpeg']:
            return 'image'
        # 关键词检测优先于扩展名
        elif any(kw in name_lower for kw in ['合同', '协议']):
            return 'contract'
        elif any(kw in name_lower for kw in ['检测', '报告', '分析']):
            return 'report'
        elif any(kw in name_lower for kw in ['发票', '清单', '采购']):
            return 'invoice'
        elif ext in ['xlsx', 'xls']:
            return 'excel'
        return 'invoice'  # 默认发票类

    def _get_priority(self, file_type: str) -> FilePriority:
        """文件类型转优先级"""
        mapping = {
            'contract': FilePriority.CONTRACT,
            'report': FilePriority.REPORT,
            'invoice': FilePriority.INVOICE,
            'image': FilePriority.IMAGE,
            'excel': FilePriority.INVOICE,  # Excel默认为发票类
        }
        return mapping.get(file_type, FilePriority.INVOICE)

    async def process_batch(
        self,
        files: List[Dict],
        progress_callback: Optional[callable] = None
    ) -> ProcessingResult:
        """批量处理文件"""
        grouped = self.group_files(files)
        all_results = []
        total = sum(len(v) for v in grouped.values())
        processed = 0

        for priority_order in [FilePriority.CONTRACT, FilePriority.REPORT,
                               FilePriority.INVOICE, FilePriority.IMAGE]:
            group_key = self._priority_to_group_key(priority_order)
            group_files = grouped.get(group_key, [])

            for f in group_files:
                result = await self._extract_file(f)
                all_results.append(result)
                processed += 1
                if progress_callback:
                    await progress_callback(processed, total)

        return self._merge_results(all_results)

    def _priority_to_group_key(self, priority: FilePriority) -> str:
        """优先级转组名"""
        mapping = {
            FilePriority.CONTRACT: 'contract',
            FilePriority.REPORT: 'report',
            FilePriority.INVOICE: 'invoice',
            FilePriority.IMAGE: 'image',
        }
        return mapping.get(priority, 'invoice')

    async def _extract_file(self, file: Dict) -> Dict:
        """提取单个文件"""
        try:
            result = self.extractor.process(
                file['content'],
                filename=file['filename']
            )
            return {
                'data': result.get('data', {}),
                'source': file['filename'],
                'priority': self._get_priority(self._detect_file_type(file['filename'])).value,
                'status': result.get('status', 'failed'),
                'error': result.get('error')
            }
        except Exception as e:
            return {
                'data': {},
                'source': file['filename'],
                'priority': self._get_priority(self._detect_file_type(file['filename'])).value,
                'status': 'failed',
                'error': str(e)
            }

    def _merge_results(self, all_results: List[Dict]) -> ProcessingResult:
        """智能合并提取结果"""
        merged = {}
        warnings = []
        failed_files = []

        for result in all_results:
            if result['status'] == 'failed':
                failed_files.append({
                    'filename': result['source'],
                    'reason': result.get('error', 'Unknown error')
                })
                continue

            for key, value in result.get('data', {}).items():
                if key not in merged:
                    merged[key] = {
                        'value': value,
                        'source': result['source'],
                        'priority': result['priority']
                    }
                else:
                    existing = merged[key]
                    if existing['value'] != value and existing['priority'] != result['priority']:
                        warnings.append({
                            'field': key,
                            'values': [existing['value'], value],
                            'sources': [existing['source'], result['source']],
                            'message': f"字段{key}存在冲突，自动选择高优先级值"
                        })
                        # 保留高优先级
                        if result['priority'] < existing['priority']:
                            merged[key] = {
                                'value': value,
                                'source': result['source'],
                                'priority': result['priority']
                            }

        return ProcessingResult(
            status='completed' if merged else 'failed',
            extracted={k: v['value'] for k, v in merged.items()},
            warnings=warnings,
            failed_files=failed_files
        )