"""FormFillAgent 主类 - 将 LLM 提取的数据填入表单"""
import uuid
from datetime import datetime
from typing import Any, Dict

from tantan.backend.utils import get_logger

from .mapping import BACKEND_TO_FRONTEND_FIELD_MAP
from .section_defs import FormSection, get_section_definitions
from .transformers import MULTI_ROW_TRANSFORMERS, NESTED_FIELD_TRANSFORMERS

logger = get_logger(__name__)


class FormFillAgent:
    """表单填报 Agent - 把 LLM 提取的字段转换为前端期望结构"""

    # 类属性别名，保持向后兼容（测试用 `agent.BACKEND_TO_FRONTEND_FIELD_MAP`）
    BACKEND_TO_FRONTEND_FIELD_MAP = BACKEND_TO_FRONTEND_FIELD_MAP
    MULTI_ROW_TRANSFORMERS = MULTI_ROW_TRANSFORMERS
    NESTED_FIELD_TRANSFORMERS = NESTED_FIELD_TRANSFORMERS

    def __init__(self, section: int):
        self.section = section
        self.section_definitions: Dict[int, FormSection] = get_section_definitions()

    def fill_form(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """将数据填入表单"""
        try:
            if self.section not in self.section_definitions:
                logger.warning(f"无效的部分编号: {self.section}")
                return {"error": f"无效的部分编号: {self.section}"}

            section_def = self.section_definitions[self.section]
            errors = []

            # 数据转换主循环
            mapped_data: Dict[str, Any] = {}
            for backend_field, value in data.items():
                if value is None or (isinstance(value, str) and not value.strip()):
                    continue

                if backend_field in MULTI_ROW_TRANSFORMERS and isinstance(value, list):
                    mapped_data = self._transform_multi_row(
                        backend_field, value, mapped_data
                    )
                elif backend_field in NESTED_FIELD_TRANSFORMERS and isinstance(value, dict):
                    mapped_data = self._transform_nested(
                        backend_field, value, mapped_data
                    )
                else:
                    frontend_field = BACKEND_TO_FRONTEND_FIELD_MAP.get(backend_field, backend_field)
                    mapped_data[frontend_field] = value

            logger.info(
                f"表单填充完成: section={self.section}, "
                f"filled={len(mapped_data)}, errors={len(errors)}"
            )
            return {
                "msg_id": str(uuid.uuid4()),
                "section": self.section,
                "section_name": section_def.name,
                "filled_data": mapped_data,
                "errors": errors,
                "timestamp": datetime.now().isoformat(),
                "status": "completed" if not errors else "partial"
            }
        except Exception as e:
            logger.error(
                f"表单填充失败: section={self.section}, error: {str(e)}",
                exc_info=True,
            )
            return {"error": f"表单填充失败: {str(e)}"}

    def _transform_multi_row(
        self,
        backend_field: str,
        value: list,
        mapped_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """将 LLM 返回的数组格式转换为前端嵌套数组结构"""
        transformer = MULTI_ROW_TRANSFORMERS[backend_field]
        frontend_key = transformer["frontend_key"]
        sub_fields = transformer["sub_fields"]

        entries = []
        for item in value:
            if not isinstance(item, dict):
                continue
            entry = self._build_entry_from_variants(item, sub_fields)
            if entry:
                entries.append(entry)

        if entries:
            mapped_data[frontend_key] = entries
            logger.info(
                f"转换多行动态字段: {backend_field} -> {frontend_key}, "
                f"{len(entries)}条记录"
            )
        return mapped_data

    @staticmethod
    def _build_entry_from_variants(item: Dict[str, Any], sub_fields: Dict[str, str]) -> Dict[str, Any]:
        """尝试多种 key 变体抽取字段"""
        entry: Dict[str, Any] = {}
        for frontend_sub, backend_sub in sub_fields.items():
            val = _try_pick_key(item, backend_sub, frontend_sub)
            if val is not None and str(val).strip():
                entry[frontend_sub] = val
        return entry

    @staticmethod
    def _transform_nested(
        backend_field: str,
        value: Dict[str, Any],
        mapped_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """将嵌套字典拆分为扁平字段（Section 9 新鲜水/氮气）"""
        transformer = NESTED_FIELD_TRANSFORMERS[backend_field]
        sub_fields = transformer["sub_fields"]
        for frontend_key, backend_key in sub_fields.items():
            v = value.get(backend_key)
            if v not in (None, "", " "):
                mapped_data[frontend_key] = v
                continue
            # fallback: 模糊匹配（去掉前缀/后缀的 key）
            for k, candidate in value.items():
                if k == backend_key:
                    if candidate not in (None, "", " "):
                        mapped_data[frontend_key] = candidate
                    break
        logger.info(f"转换嵌套对象字段: {backend_field} -> {list(sub_fields.keys())}")
        return mapped_data


def _try_pick_key(item: Dict[str, Any], backend_sub: str, frontend_sub: str):
    """按多个变体 key 顺序尝试取值"""
    keys_to_try = [
        backend_sub,
        frontend_sub,
        backend_sub.replace("制冷剂", "").replace("使用", "").replace("填充", "").replace("设备", ""),
        backend_sub.replace("名称", "名"),
        backend_sub.replace("使用量", "量").replace("填充量", "量"),
        "名称", "名", "标号", "使用量", "使用", "填充量", "填充",
    ]
    for k in keys_to_try:
        v = item.get(k)
        if v:
            return v
    return None
