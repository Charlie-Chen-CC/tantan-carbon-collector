"""
Section 提示词反硬编码测试 - Phase 6.1

确保：
- SECTION_PROMPTS 1-9 全部非空
- 关键选项列表（来自 section_options）已注入对应 section 的 prompt
- section_options 模块所有常量非空列表
"""
from tantan.backend.agents import section_options
from tantan.backend.agents.file_extractor import SECTION_PROMPTS


class TestSectionOptionsModule:
    """section_options 模块结构"""

    def test_all_constants_non_empty(self):
        constants = [
            "INDUSTRY_STANDARD_REF",
            "INDUSTRY_EXAMPLES",
            "PRODUCT_UNITS",
            "PRODUCT_OTHER_MAX",
            "COMMON_FUEL_TYPES",
            "MEASURABLE_OPTIONS",
            "PHOTOVOLTAIC_CONFIG_OPTIONS",
            "GREEN_CERTIFICATE_OPTIONS",
            "EMISSION_RIGHTS_OPTIONS",
            "COMMON_REFRIGERANTS",
            "FIRE_EXTINGUISHER_TYPES",
            "WASTE_DISPOSAL_METHODS",
            "TRANSPORT_MODES",
            "STATISTICAL_CALIBER_OPTIONS",
        ]
        for name in constants:
            value = getattr(section_options, name)
            assert value, f"{name} is empty"
            if isinstance(value, list):
                assert len(value) > 0, f"{name} is empty list"

    def test_industry_standard_ref_includes_version(self):
        """行业标准引用必须含"现行版本"提示，避免标准号硬编码"""
        assert "现行版本" in section_options.INDUSTRY_STANDARD_REF

    def test_product_other_max_is_positive_int(self):
        assert isinstance(section_options.PRODUCT_OTHER_MAX, int)
        assert section_options.PRODUCT_OTHER_MAX >= 1


class TestSectionPromptsInjection:
    """SECTION_PROMPTS 必须含注入的选项"""

    def test_all_9_sections_present(self):
        assert set(SECTION_PROMPTS.keys()) == set(range(1, 10))

    def test_all_prompts_non_empty(self):
        for sec, prompt in SECTION_PROMPTS.items():
            assert prompt and len(prompt) > 100, f"Section {sec} prompt too short"

    def test_section1_injects_industry_standard(self):
        assert section_options.INDUSTRY_STANDARD_REF in SECTION_PROMPTS[1]

    def test_section1_injects_industry_examples(self):
        # 至少含第一个行业示例
        assert section_options.INDUSTRY_EXAMPLES[0] in SECTION_PROMPTS[1]

    def test_section2_injects_units_and_max(self):
        for unit in section_options.PRODUCT_UNITS:
            assert unit in SECTION_PROMPTS[2], f"Unit {unit!r} missing"
        # 副产品最大数已注入（出现 ≥ 1 次）
        assert str(section_options.PRODUCT_OTHER_MAX) in SECTION_PROMPTS[2]

    def test_section3_injects_fuel_types(self):
        for fuel in section_options.COMMON_FUEL_TYPES:
            assert fuel in SECTION_PROMPTS[3], f"Fuel {fuel!r} missing"

    def test_section4_injects_measurable_and_pv_and_green(self):
        for opt in section_options.MEASURABLE_OPTIONS:
            assert opt in SECTION_PROMPTS[4], f"Measurable {opt!r} missing"
        for opt in section_options.PHOTOVOLTAIC_CONFIG_OPTIONS:
            assert opt in SECTION_PROMPTS[4], f"PV {opt!r} missing"
        for opt in section_options.GREEN_CERTIFICATE_OPTIONS:
            assert opt in SECTION_PROMPTS[4], f"Green cert {opt!r} missing"
        for opt in section_options.EMISSION_RIGHTS_OPTIONS:
            assert opt in SECTION_PROMPTS[4], f"Emission rights {opt!r} missing"

    def test_section5_injects_refrigerants(self):
        for r in section_options.COMMON_REFRIGERANTS:
            assert r in SECTION_PROMPTS[5], f"Refrigerant {r!r} missing"

    def test_section6_injects_fire_extinguisher_types(self):
        for t in section_options.FIRE_EXTINGUISHER_TYPES:
            assert t in SECTION_PROMPTS[6], f"Fire type {t!r} missing"

    def test_section7_injects_waste_methods(self):
        for m in section_options.WASTE_DISPOSAL_METHODS:
            assert m in SECTION_PROMPTS[7], f"Waste method {m!r} missing"

    def test_section8_injects_transport_modes(self):
        for m in section_options.TRANSPORT_MODES:
            assert m in SECTION_PROMPTS[8], f"Transport {m!r} missing"

    def test_section9_injects_statistical_caliber(self):
        for o in section_options.STATISTICAL_CALIBER_OPTIONS:
            assert o in SECTION_PROMPTS[9], f"Caliber {o!r} missing"
