"""FormFillAgent 包入口 - 重导出

保留对以下旧式 import 的兼容：
- from tantan.backend.agents.form_filler import FormFillAgent
- from tantan.backend.agents.form_filler import get_field_guide, FieldGuide, FIELD_GUIDES
- from tantan.backend.agents.form_filler import BACKEND_TO_FRONTEND_FIELD_MAP, FormSection
"""
from .agent import FormFillAgent
from .guides import FIELD_GUIDES, FieldGuide, get_field_guide
from .mapping import BACKEND_TO_FRONTEND_FIELD_MAP
from .section_defs import FormSection, get_section_definitions
from .transformers import MULTI_ROW_TRANSFORMERS, NESTED_FIELD_TRANSFORMERS

__all__ = [
    "FormFillAgent",
    "FormSection",
    "FieldGuide",
    "FIELD_GUIDES",
    "get_field_guide",
    "BACKEND_TO_FRONTEND_FIELD_MAP",
    "MULTI_ROW_TRANSFORMERS",
    "NESTED_FIELD_TRANSFORMERS",
    "get_section_definitions",
]
