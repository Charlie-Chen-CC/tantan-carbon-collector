"""
字段映射 SSOT codegen - Phase 6.3

读取 `tantan/shared/field_schema.json`（SSOT），生成 4 个目标文件：
  1. `tantan/backend/agents/form_filler/mapping.py`        - BACKEND_TO_FRONTEND_FIELD_MAP
  2. `tantan/backend/agents/form_filler/section_defs.py`   - FormSection 9 个 sections
  3. `tantan/backend/agents/form_filler/transformers.py`   - MULTI_ROW / NESTED 转换器
  4. `tantan/frontend/config/sectionConfig.ts`             - SECTION_FIELDS

用法：
  cd claude_workspace
  python -m tantan.backend.scripts.codegen_field_schema             # 生成 + 写文件
  python -m tantan.backend.scripts.codegen_field_schema --check     # 仅校验（CI 用）

CI 集成：在 pre-commit hook 跑 `codegen --check`，JSON 与生成文件不一致则 fail。
"""
import argparse
import json
import sys
from pathlib import Path


# ============== 路径解析 ==============

# __file__ = tantan/backend/scripts/codegen_field_schema.py
# 根 = tantan/ 的父目录（claude_workspace/）
SCRIPT_DIR = Path(__file__).resolve().parent
TANTAN_ROOT = SCRIPT_DIR.parent.parent  # tantan/
WORKSPACE_ROOT = TANTAN_ROOT.parent  # claude_workspace/

SSOT_PATH = TANTAN_ROOT / "shared" / "field_schema.json"

MAPPING_OUT = TANTAN_ROOT / "backend" / "agents" / "form_filler" / "mapping.py"
SECTION_DEFS_OUT = TANTAN_ROOT / "backend" / "agents" / "form_filler" / "section_defs.py"
TRANSFORMERS_OUT = TANTAN_ROOT / "backend" / "agents" / "form_filler" / "transformers.py"
FRONTEND_OUT = TANTAN_ROOT / "frontend" / "config" / "sectionConfig.ts"


# ============== 加载 SSOT ==============

def load_schema() -> dict:
    with open(SSOT_PATH, encoding="utf-8") as f:
        return json.load(f)


# ============== 生成器 ==============

HEADER = (
    '"""{title}"""\n'
    "# ⚠️ 此文件由 `python -m tantan.backend.scripts.codegen_field_schema` 自动生成\n"
    "# 不要手动编辑！改 `tantan/shared/field_schema.json` 后重跑 codegen。\n"
    "\n"
    "from typing import Dict, Any\n"
    "\n"
)


def gen_mapping_py(schema: dict) -> str:
    """生成 backend/agents/form_filler/mapping.py"""
    lines = [HEADER.format(title="后端中文字段名 -> 前端英文字段名 映射表")]
    lines.append("\n\n# 后端字段名到前端字段名的映射（由 codegen 自动生成）\n")
    lines.append("BACKEND_TO_FRONTEND_FIELD_MAP: Dict[str, str] = {\n")
    for sec in schema["sections"]:
        lines.append(f"    # Section {sec['id']} - {sec['name']}\n")
        for f in sec["fields"]:
            lines.append(f'    "{f["backend"]}": "{f["frontend"]}",\n')
        # nested 字段的子项也加进 map
        for f in sec["fields"]:
            for sub in (f.get("sub_fields") or []) + (f.get("nested") or []):
                if sub.get("backend") and sub.get("frontend"):
                    lines.append(f'    "{sub["backend"]}": "{sub["frontend"]}",\n')
    lines.append("}\n")
    return "".join(lines)


def gen_section_defs_py(schema: dict) -> str:
    """生成 backend/agents/form_filler/section_defs.py"""
    out = [HEADER.format(title="9 个 section 的字段定义 + FormSection 类（由 codegen 自动生成）")]
    out.append("\n\nclass FormSection:\n")
    out.append('    """表单部分的字段定义"""\n\n')
    out.append("    def __init__(self, section: int, name: str, fields: Dict[str, str]):\n")
    out.append("        self.section = section\n")
    out.append("        self.name = name\n")
    out.append("        self.fields = fields  # field_name -> field_type\n\n\n")
    out.append("def get_section_definitions() -> Dict[int, FormSection]:\n")
    out.append('    """获取所有 9 个 section 的字段定义（返回新字典，每次调用独立）"""\n')
    out.append("    return {\n")
    for sec in schema["sections"]:
        out.append(f"        {sec['id']}: FormSection({sec['id']}, \"{sec['name']}\", {{\n")
        for f in sec["fields"]:
            out.append(f'            "{f["backend"]}": "{f["type"]}",\n')
        out.append("        }),\n")
    out.append("    }\n")
    return "".join(out)


def gen_transformers_py(schema: dict) -> str:
    """生成 backend/agents/form_filler/transformers.py"""
    out = [HEADER.format(title="字段转换器 - 多行动态字段 + 嵌套对象字段（由 codegen 自动生成）")]
    out.append("\n\n# 多行动态字段转换器：将 LLM 提取的平展数据转换为前端嵌套数组结构\n")
    out.append("MULTI_ROW_TRANSFORMERS: Dict[str, Dict[str, Any]] = {\n")
    for sec in schema["sections"]:
        for f in sec["fields"]:
            if f["type"] != "multi-row" or not f.get("sub_fields"):
                continue
            sub_dict = {sf["frontend"]: sf["backend"] for sf in f["sub_fields"]}
            extras = []
            if f.get("is_array"):
                extras.append('"is_array": True')
            if f.get("numeric_suffix"):
                extras.append('"numeric_suffix": True')
            extras_str = (",\n            " + ", ".join(extras)) if extras else ""
            out.append(f'    "{f["backend"]}": {{\n')
            out.append(f'        "frontend_key": "{f["frontend"]}",\n')
            out.append(f'        "sub_fields": {sub_dict!r}{extras_str}\n')
            out.append("    },\n")
    out.append("}\n\n")
    out.append("# 嵌套对象字段转换器：将嵌套字典拆分为扁平字段\n")
    out.append("NESTED_FIELD_TRANSFORMERS: Dict[str, Dict[str, Any]] = {\n")
    for sec in schema["sections"]:
        for f in sec["fields"]:
            if f["type"] != "nested" or not f.get("nested"):
                continue
            out.append(f'    "{f["backend"]}": {{\n')
            out.append(f'        "frontend_key": "{f["frontend"]}",\n')
            out.append(f'        "sub_fields": {{\n')
            for sub in f["nested"]:
                out.append(f'            "{sub["frontend"]}": "{sub["backend"]}",\n')
            out.append("        },\n")
            out.append("    },\n")
    out.append("}\n")
    return "".join(out)


def gen_section_config_ts(schema: dict) -> str:
    """生成 frontend/config/sectionConfig.ts"""
    out = ["// ⚠️ 此文件由 `python -m tantan.backend.scripts.codegen_field_schema` 自动生成\n"]
    out.append("// 不要手动编辑！改 `tantan/shared/field_schema.json` 后重跑 codegen。\n\n")
    out.append("export type FieldType = 'text' | 'number' | 'select' | 'file' | 'multi-row' | 'nested';\n\n")
    out.append("export interface FieldDef {\n")
    out.append("  key: string;\n  label: string;\n  type: FieldType;\n")
    out.append("  placeholder?: string;\n  options?: string[];\n  required?: boolean;\n")
    out.append("  fields?: FieldDef[];\n  maxRows?: number;\n}\n\n")
    out.append("export const SECTION_NAMES: string[] = [\n")
    out.append("  '',\n")
    for sec in schema["sections"]:
        out.append(f"  '{sec['name']}',\n")
    out.append("];\n\n")
    out.append("export const SECTION_FIELDS: { [section: number]: FieldDef[] } = {\n")
    for sec in schema["sections"]:
        out.append(f"  {sec['id']}: [\n")
        for f in sec["fields"]:
            parts = [f"key: '{f['frontend']}'", f"label: '{f['backend']}'", f"type: '{f['type']}'"]
            if f.get("required"):
                parts.append("required: true")
            if f.get("placeholder"):
                parts.append(f"placeholder: '{f['placeholder']}'")
            if f.get("options"):
                opts = ", ".join(f"'{o}'" for o in f["options"])
                parts.append(f"options: [{opts}]")
            if f.get("sub_fields"):
                parts.append("fields: [")
                for sf in f["sub_fields"]:
                    parts.append(f"    {{ key: '{sf['frontend']}', label: '{sf['backend']}', type: 'text' }},")
                parts.append("  ]")
            out.append(f"    {{ {', '.join(parts)} }},\n")
        out.append("  ],\n")
    out.append("};\n")
    return "".join(out)


# ============== 入口 ==============

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="仅校验，文件不一致时 exit 1")
    args = parser.parse_args()

    schema = load_schema()
    print(f"[codegen] 加载 SSOT: {SSOT_PATH}")
    print(f"[codegen] 9 sections, 字段总数: {sum(len(s['fields']) for s in schema['sections'])}")

    targets = {
        MAPPING_OUT: gen_mapping_py(schema),
        SECTION_DEFS_OUT: gen_section_defs_py(schema),
        TRANSFORMERS_OUT: gen_transformers_py(schema),
        FRONTEND_OUT: gen_section_config_ts(schema),
    }

    if args.check:
        failed = 0
        for path, expected in targets.items():
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if actual.strip() != expected.strip():
                print(f"  [DIFF] {path.relative_to(WORKSPACE_ROOT)} 不一致")
                failed += 1
            else:
                print(f"  [OK]   {path.relative_to(WORKSPACE_ROOT)}")
        if failed:
            print(f"\n[FAIL] {failed} 个文件与 SSOT 不一致。请跑 `codegen` 重新生成。")
            sys.exit(1)
        print("\n[PASS] 所有生成文件与 SSOT 同步")
    else:
        for path, content in targets.items():
            path.write_text(content, encoding="utf-8")
            print(f"  [WRITE] {path.relative_to(WORKSPACE_ROOT)}")
        print("\n[OK] 生成完成")


if __name__ == "__main__":
    main()
