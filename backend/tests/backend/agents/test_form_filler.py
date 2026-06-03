"""
表单填报Agent测试 - 验证字段映射功能
"""
import pytest
from tantan.backend.agents.form_filler import FormFillAgent, get_field_guide, FieldGuide


class TestFieldGuide:
    """测试字段引导配置"""

    def test_get_field_guide_returns_config(self):
        """测试获取字段引导配置"""
        guide = get_field_guide(1, "企业名称")
        assert guide is not None
        assert isinstance(guide, FieldGuide)
        assert "企业全称" in guide.description

    def test_get_field_guide_with_data_sources(self):
        """测试字段引导包含数据来源"""
        guide = get_field_guide(1, "企业名称")
        assert guide is not None
        assert len(guide.data_sources) > 0
        assert "营业执照" in guide.data_sources

    def test_get_field_guide_with_unit(self):
        """测试字段引导包含计量单位"""
        guide = get_field_guide(4, "全厂用电")
        assert guide is not None
        assert guide.unit is not None
        assert "MWh" in guide.unit

    def test_get_field_guide_with_common_issues(self):
        """测试字段引导包含常见问题"""
        guide = get_field_guide(1, "企业名称")
        assert guide is not None
        assert guide.common_issues is not None
        assert len(guide.common_issues) > 0

    def test_get_field_guide_returns_none_for_unknown_section(self):
        """测试未知section返回None"""
        guide = get_field_guide(99, "企业名称")
        assert guide is None

    def test_get_field_guide_returns_none_for_unknown_field(self):
        """测试未知字段返回None"""
        guide = get_field_guide(1, "不存在的字段")
        assert guide is None

    def test_get_field_guide_section3_fuel(self):
        """测试Section 3燃料字段引导"""
        guide = get_field_guide(3, "生产用锅炉燃料")
        assert guide is not None
        assert "锅炉" in guide.description
        assert guide.unit is not None

    def test_get_field_guide_section9_freshwater(self):
        """测试Section 9新鲜水字段引导"""
        guide = get_field_guide(9, "新鲜水使用量")
        assert guide is not None
        assert "新鲜水" in guide.description
        assert "水费发票" in guide.data_sources

    def test_field_guide_all_sections_have_guides(self):
        """测试所有section都有引导配置"""
        from tantan.backend.agents.form_filler import FIELD_GUIDES
        for section in range(1, 10):
            assert section in FIELD_GUIDES, f"Section {section} missing from FIELD_GUIDES"
            assert len(FIELD_GUIDES[section]) > 0, f"Section {section} has no field guides"


class TestFieldMapping:
    """测试字段映射功能"""

    def test_section1_field_mapping(self):
        """测试Section 1字段映射 - 基本信息"""
        agent = FormFillAgent(section=1)

        # 模拟LLM提取的数据（使用中文字段名）
        extracted_data = {
            "企业名称": "浙江光华科技股份有限公司",
            "所属行业": "化学原料和化学制品制造业",
            "联系人": "张三",
            "联系方式": "13800138000",
            "生产地址": "浙江省某市某区某路",
            "核算年份": "2024",
            "是否为自然年（1月1日-12月31日）": "是",
        }

        result = agent.fill_form(extracted_data)

        assert "error" not in result
        assert result["status"] == "completed"
        filled_data = result["filled_data"]

        # 验证中文字段名已转换为前端英文字段名
        assert filled_data.get("enterpriseName") == "浙江光华科技股份有限公司"
        assert filled_data.get("industry") == "化学原料和化学制品制造业"
        assert filled_data.get("contact") == "张三"
        assert filled_data.get("contactPhone") == "13800138000"

    def test_section2_field_mapping(self):
        """测试Section 2字段映射 - 产品"""
        agent = FormFillAgent(section=2)

        extracted_data = {
            "PCF核算目标产品名称": "聚酯树脂",
            "是否为生产工厂唯一产品": "是",
            "计量单位": "按重量计量：t",
        }

        result = agent.fill_form(extracted_data)

        assert "error" not in result
        filled_data = result["filled_data"]

        assert filled_data.get("targetProductName") == "聚酯树脂"
        assert filled_data.get("isOnlyProduct") == "是"
        assert filled_data.get("unit") == "按重量计量：t"

    def test_section6_field_mapping(self):
        """测试Section 6字段映射 - 其他散逸类排放"""
        agent = FormFillAgent(section=6)

        extracted_data = {
            "CO2灭火器填充总量": "200",
            "核算期内员工总工时": "50000",
        }

        result = agent.fill_form(extracted_data)

        assert "error" not in result
        filled_data = result["filled_data"]

        assert filled_data.get("co2Extinguisher") == "200"
        assert filled_data.get("employeeHours") == "50000"

    def test_empty_data(self):
        """测试空数据处理"""
        agent = FormFillAgent(section=1)
        result = agent.fill_form({})

        assert "error" not in result
        assert result["filled_data"] == {}

    def test_partial_data(self):
        """测试部分数据提取"""
        agent = FormFillAgent(section=1)

        # 只提供部分字段
        extracted_data = {
            "企业名称": "测试公司",
        }

        result = agent.fill_form(extracted_data)

        assert "error" not in result
        filled_data = result["filled_data"]
        assert filled_data.get("enterpriseName") == "测试公司"
        # 其他未提供的字段不应存在
        assert "industry" not in filled_data

    def test_backend_to_frontend_mapping_completeness(self):
        """测试反向映射完整性"""
        agent = FormFillAgent(section=1)

        # 检查反向映射是否正确
        assert agent.BACKEND_TO_FRONTEND_FIELD_MAP.get("企业名称") == "enterpriseName"
        assert agent.BACKEND_TO_FRONTEND_FIELD_MAP.get("所属行业") == "industry"


class TestFormFillAgent:
    """测试FormFillAgent基本功能"""

    def test_invalid_section(self):
        """测试无效的section编号"""
        agent = FormFillAgent(section=10)  # 无效的section
        result = agent.fill_form({})

        assert "error" in result
        assert "无效的部分编号" in result["error"]

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
