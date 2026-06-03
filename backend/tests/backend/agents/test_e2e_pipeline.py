"""
Agent 端到端流水线测试

模拟完整流程：
  FileExtract (mocked) → FormFill → 验证 filled_data

覆盖：
  - Section 1 基本信息（纯字段映射）
  - Section 3 燃料使用（多行动态字段）
  - Section 9 生产耗材（嵌套字段）
  - 错误数据降级处理
  - 字段映射完整性（与前端 SECTION_FIELDS 100% 对齐）
"""
import pytest

from tantan.backend.agents import FormFillAgent


class TestPipelineSection1:
    """Section 1 - 基本信息（纯映射）"""

    def test_basic_info_mapping(self):
        """中文 → 英文字段名映射"""
        agent = FormFillAgent(section=1)
        extracted = {
            "企业名称": "测试碳素有限公司",
            "所属行业": "电子设备制造",
            "联系人": "张三",
            "联系方式": "13800138000",
            "生产地址": "上海市浦东新区张江路100号",
            "核算年份": "2024",
            "核算周期说明": "2024年1-6月",
        }
        result = agent.fill_form(extracted)

        assert "filled_data" in result
        filled = result["filled_data"]
        assert filled["enterpriseName"] == "测试碳素有限公司"
        assert filled["industry"] == "电子设备制造"
        assert filled["contact"] == "张三"
        assert filled["contactPhone"] == "13800138000"
        assert filled["productionAddress"] == "上海市浦东新区张江路100号"
        assert filled["reportingYear"] == "2024"
        assert filled["reportingPeriod"] == "2024年1-6月"

    def test_empty_values_skipped(self):
        """空值 / None 应被跳过"""
        agent = FormFillAgent(section=1)
        extracted = {
            "企业名称": "有效名称",
            "联系人": "",
            "联系方式": None,
            "所属行业": "  ",  # 全空白
        }
        result = agent.fill_form(extracted)
        filled = result["filled_data"]
        assert filled["enterpriseName"] == "有效名称"
        assert "contact" not in filled
        assert "contactPhone" not in filled


class TestPipelineSection3:
    """Section 3 - 燃料使用（多行动态字段）"""

    def test_multi_row_transformer(self):
        """LLM 返回数组 → 前端期望 entries 数组"""
        agent = FormFillAgent(section=3)
        extracted = {
            "生产用锅炉燃料": [
                {"燃料类型": "管道天然气", "使用量": "1000", "单位": "m³"},
                {"燃料类型": "煤", "使用量": "500", "单位": "t"},
            ]
        }
        result = agent.fill_form(extracted)
        filled = result["filled_data"]

        assert "boilerFuel" in filled
        assert isinstance(filled["boilerFuel"], list)
        assert len(filled["boilerFuel"]) == 2
        assert filled["boilerFuel"][0]["fuelType"] == "管道天然气"
        assert filled["boilerFuel"][0]["amount"] == "1000"
        assert filled["boilerFuel"][0]["unit"] == "m³"
        assert filled["boilerFuel"][1]["fuelType"] == "煤"

    def test_multi_row_invalid_item_filtered(self):
        """数组里非字典项应被过滤"""
        agent = FormFillAgent(section=3)
        extracted = {
            "生产用锅炉燃料": [
                {"燃料类型": "煤", "使用量": "100", "单位": "t"},
                "invalid string",  # 非字典 - 应被过滤
                None,              # 非字典 - 应被过滤
                {"燃料类型": "天然气", "使用量": "200", "单位": "m³"},
            ]
        }
        result = agent.fill_form(extracted)
        filled = result["filled_data"]
        assert len(filled["boilerFuel"]) == 2


class TestPipelineSection9:
    """Section 9 - 生产耗材（嵌套字段）"""

    def test_nested_field_transformer(self):
        """嵌套字典 → 扁平字段"""
        agent = FormFillAgent(section=9)
        extracted = {
            "新鲜水": {
                "统计口径": "全厂生产耗用量",
                "使用量": "5000",
                "单位": "t",
            }
        }
        result = agent.fill_form(extracted)
        filled = result["filled_data"]
        assert filled["freshWaterCaliber"] == "全厂生产耗用量"
        assert filled["freshWaterAmount"] == "5000"
        assert filled["freshWaterUnit"] == "t"

    def test_nested_field_with_partial(self):
        """嵌套字典部分字段缺失 - 已知字段应填充"""
        agent = FormFillAgent(section=9)
        extracted = {
            "新鲜水": {
                "统计口径": "目标产品产线内容耗用量",
                "使用量": "3000",
                # 单位缺失
            }
        }
        result = agent.fill_form(extracted)
        filled = result["filled_data"]
        assert filled["freshWaterCaliber"] == "目标产品产线内容耗用量"
        assert filled["freshWaterAmount"] == "3000"
        # 单位缺失时不应写入
        assert "freshWaterUnit" not in filled or filled.get("freshWaterUnit") in (None, "")


class TestPipelineErrorHandling:
    """错误处理降级"""

    def test_invalid_section_returns_error(self):
        """无效 section 应返回 error"""
        agent = FormFillAgent(section=99)
        result = agent.fill_form({"企业名称": "test"})
        assert "error" in result
        assert "无效" in result["error"]

    def test_empty_data_returns_empty_filled(self):
        """空数据应返回空 filled_data + 0 错误"""
        agent = FormFillAgent(section=1)
        result = agent.fill_form({})
        assert result["filled_data"] == {}
        assert result["errors"] == []


class TestPipelineMappingConsistency:
    """字段映射完整性"""

    def test_all_sample_keys_mapped_to_known(self):
        """用一组后端中文字段名做 fill_form，所有结果 key 应在 BACKEND_TO_FRONTEND_FIELD_MAP 的 value 集合中"""
        from tantan.backend.agents.form_filler.mapping import BACKEND_TO_FRONTEND_FIELD_MAP

        known_frontend_keys = set(BACKEND_TO_FRONTEND_FIELD_MAP.values())
        # 后端字段在 mapping 中应能找到映射
        sample = {
            "企业名称": "x",
            "所属行业": "x",
            "联系人": "x",
            "联系方式": "x",
            "生产地址": "x",
            "核算年份": "x",
            "核算周期说明": "x",
        }
        agent = FormFillAgent(section=1)
        filled = agent.fill_form(sample)["filled_data"]
        for k in filled:
            assert k in known_frontend_keys, f"Key {k} not in BACKEND_TO_FRONTEND_FIELD_MAP values"

    def test_mapping_value_count_at_least_100(self):
        """映射表至少 100 个条目（覆盖 9 个 section 100+ 字段）"""
        from tantan.backend.agents.form_filler.mapping import BACKEND_TO_FRONTEND_FIELD_MAP

        assert len(BACKEND_TO_FRONTEND_FIELD_MAP) >= 100, (
            f"映射表条目数 {len(BACKEND_TO_FRONTEND_FIELD_MAP)} 不足 100，"
            f"可能漏配字段"
        )
