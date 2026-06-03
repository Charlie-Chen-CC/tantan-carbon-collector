"""
字段映射 SSOT codegen 测试 - Phase 6.3

验证：
- `shared/field_schema.json` 是合法 JSON，含 9 个 sections
- codegen 生成的 4 个文件与 SSOT 同步（`--check` 通过）
- BACKEND_TO_FRONTEND_FIELD_MAP 至少 100 个条目
- 关键字段（企业名称/CO2灭火器填充总量/核算期内员工总工时 等）映射正确
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

# 项目根目录
TANTAN_ROOT = Path(__file__).resolve().parents[3]  # tests/backend/ → tantan/
WORKSPACE_ROOT = TANTAN_ROOT.parent
SSOT_PATH = TANTAN_ROOT / "shared" / "field_schema.json"


@pytest.fixture(scope="module")
def schema():
    with open(SSOT_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestSSOTSchema:
    """SSOT JSON 结构"""

    def test_ssot_exists(self):
        assert SSOT_PATH.exists(), f"SSOT 不存在: {SSOT_PATH}"

    def test_ssot_is_valid_json(self, schema):
        assert isinstance(schema, dict)

    def test_ssot_has_9_sections(self, schema):
        sections = schema["sections"]
        assert len(sections) == 9, f"应为 9 个 sections，实际 {len(sections)}"
        ids = sorted(s["id"] for s in sections)
        assert ids == list(range(1, 10)), f"Section id 序列: {ids}"

    def test_all_sections_have_name_and_fields(self, schema):
        for sec in schema["sections"]:
            assert "id" in sec and "name" in sec and "fields" in sec
            assert isinstance(sec["fields"], list)
            assert len(sec["fields"]) > 0, f"Section {sec['id']} 无字段"

    def test_all_fields_have_backend_and_frontend(self, schema):
        for sec in schema["sections"]:
            for f in sec["fields"]:
                assert "backend" in f and "frontend" in f, f"Section {sec['id']} 字段缺 backend/frontend: {f}"
                assert f["backend"] and f["frontend"]

    def test_no_duplicate_backend_keys(self, schema):
        """backend 字段名必须唯一（dict key 唯一）"""
        seen = set()
        for sec in schema["sections"]:
            for f in sec["fields"]:
                assert f["backend"] not in seen, f"重复 backend 字段: {f['backend']}"
                seen.add(f["backend"])


class TestCodegenOutput:
    """codegen 生成的 4 个文件"""

    def test_codegen_check_passes(self):
        """`codegen --check` 应 PASS（SSOT 与生成文件同步）"""
        result = subprocess.run(
            [sys.executable, "-m", "tantan.backend.scripts.codegen_field_schema", "--check"],
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={"PYTHONIOENCODING": "utf-8", "PATH": __import__("os").environ.get("PATH", "")},
        )
        assert result.returncode == 0, f"codegen --check 失败:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_mapping_has_at_least_100_entries(self):
        """BACKEND_TO_FRONTEND_FIELD_MAP >= 100"""
        from tantan.backend.agents.form_filler.mapping import BACKEND_TO_FRONTEND_FIELD_MAP
        assert len(BACKEND_TO_FRONTEND_FIELD_MAP) >= 100, (
            f"映射表条目数 {len(BACKEND_TO_FRONTEND_FIELD_MAP)} 不足 100"
        )

    def test_section6_field_names_match_test_expectation(self):
        """Section 6 字段名必须与 test_form_filler.py 期望一致"""
        from tantan.backend.agents.form_filler.mapping import BACKEND_TO_FRONTEND_FIELD_MAP
        assert BACKEND_TO_FRONTEND_FIELD_MAP.get("CO2灭火器填充总量") == "co2Extinguisher"
        assert BACKEND_TO_FRONTEND_FIELD_MAP.get("核算期内员工总工时") == "employeeHours"

    def test_section1_calendar_year_field(self):
        """Section 1 '是否为自然年' 必须存在"""
        from tantan.backend.agents.form_filler.mapping import BACKEND_TO_FRONTEND_FIELD_MAP
        assert "是否为自然年（1月1日-12月31日）" in BACKEND_TO_FRONTEND_FIELD_MAP

    def test_multi_row_transformers_generated(self):
        """MULTI_ROW_TRANSFORMERS 至少含生产用锅炉燃料"""
        from tantan.backend.agents.form_filler.transformers import MULTI_ROW_TRANSFORMERS
        assert "生产用锅炉燃料" in MULTI_ROW_TRANSFORMERS
        assert MULTI_ROW_TRANSFORMERS["生产用锅炉燃料"]["frontend_key"] == "boilerFuel"
        assert "fuelType" in MULTI_ROW_TRANSFORMERS["生产用锅炉燃料"]["sub_fields"]

    def test_section_defs_has_9_sections(self):
        from tantan.backend.agents.form_filler.section_defs import get_section_definitions
        defs = get_section_definitions()
        assert set(defs.keys()) == set(range(1, 10))
        assert defs[1].name == "基本信息"
        assert "企业名称" in defs[1].fields

    def test_frontend_section_config_generated(self, schema):
        """frontend sectionConfig.ts 应含 Section 1 + enterpriseName key（TS 不能直接 Python import）"""
        ts_path = TANTAN_ROOT / "frontend" / "config" / "sectionConfig.ts"
        assert ts_path.exists()
        content = ts_path.read_text(encoding="utf-8")
        # 关键 token 必须在生成文件里
        assert "SECTION_NAMES" in content
        assert "SECTION_FIELDS" in content
        assert "'基本信息'" in content
        assert "enterpriseName" in content
        assert "industry" in content
        # 必须含 codegen 标记
        assert "自动生成" in content or "auto-generated" in content.lower()
