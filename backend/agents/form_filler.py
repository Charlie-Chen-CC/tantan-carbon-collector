"""
表单填报Agent基类 - 碳管师收资系统
负责将提取的数据填入表单
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from tantan.backend.utils import get_logger

logger = get_logger(__name__)


class FormSection:
    """表单部分的字段定义"""

    def __init__(self, section: int, name: str, fields: Dict[str, str]):
        self.section = section
        self.name = name
        self.fields = fields  # field_name -> field_type


class FormFillAgent:
    """表单填报Agent"""

    def __init__(self, section: int):
        self.section = section
        self.section_definitions = self._get_section_definitions()

    def _get_section_definitions(self) -> Dict[int, FormSection]:
        """获取所有部分的字段定义"""
        return {
            1: FormSection(1, "基本信息", {
                "企业名称": "text",
                "所属行业": "text",
                "联系人": "text",
                "联系方式": "text",
                "生产地址": "text",
                "核算年份": "text",
                "核算周期说明": "text"
            }),
            2: FormSection(2, "产品", {
                "PCF核算目标产品名称": "text",
                "是否为生产工厂唯一产品": "select",
                "其他产品1名称": "text",
                "其他产品2名称": "text",
                "其他产品3名称": "text",
                "其他产品4名称": "text",
                "其他产品5名称": "text",
                "其他产品超过5种的说明": "text",
                "计量单位": "select",
                "目标产品产线内是否有副产品": "select",
                "副产品1名称": "text",
                "副产品2名称": "text",
                "副产品3名称": "text",
                "副产品4名称": "text",
                "副产品5名称": "text",
                "副产品超过5种的说明": "text"
            }),
            3: FormSection(3, "燃料使用", {
                "生产用锅炉燃料": "select",
                "专用废气焚烧炉燃料": "select",
                "危废焚烧炉燃料": "select",
                "发电机燃料": "select",
                "食堂炉灶燃料": "select",
                "厂内转运叉车燃料": "select",
                "自有商务车92#": "select",
                "自有商务车95#": "select",
                "自有商务车98#": "select",
                "自有道路车辆燃料-柴油": "select",
                "切割、焊接燃料": "select"
            }),
            4: FormSection(4, "电力、热力使用", {
                "全厂用电": "select",
                "生产用电": "select",
                "行政办公用电": "select",
                "目标产品产线用电": "select",
                "单耗用电": "select",
                "光伏发电量": "text",
                "光伏发电配置": "select",
                "是否购买绿证": "select",
                "是否购买排放权益": "select",
                "蒸汽温度": "text",
                "蒸汽压力": "text",
                "全厂用蒸汽": "select",
                "生产用蒸汽": "select",
                "行政类用蒸汽": "select",
                "目标产品产线用蒸汽": "select",
                "单耗用蒸汽": "select"
            }),
            5: FormSection(5, "制冷剂使用", {
                "空调制冷剂1标号": "text",
                "空调制冷剂1填充量": "text",
                "空调制冷剂2标号": "text",
                "空调制冷剂2填充量": "text",
                "空调制冷剂3标号": "text",
                "空调制冷剂3填充量": "text",
                "空调制冷剂4标号": "text",
                "空调制冷剂4填充量": "text",
                "空调制冷剂5标号": "text",
                "空调制冷剂5填充量": "text",
                "冷冻机制冷剂1标号": "text",
                "冷冻机制冷剂1填充量": "text",
                "冷冻机制冷剂2标号": "text",
                "冷冻机制冷剂2填充量": "text",
                "冷冻机制冷剂3标号": "text",
                "冷冻机制冷剂3填充量": "text",
                "冷冻机制冷剂4标号": "text",
                "冷冻机制冷剂4填充量": "text",
                "冷冻机制冷剂5标号": "text",
                "冷冻机制冷剂5填充量": "text"
            }),
            6: FormSection(6, "其他散逸类排放", {
                "CO2灭火器填充总量": "text",
                "核算期内员工总工时": "text"
            }),
            7: FormSection(7, "三废处理", {
                "废水处理方式": "select",
                "废水处理量": "text",
                "目标产品产线废水": "text",
                "COD浓度": "text",
                "污水处理药剂1": "select",
                "污水处理药剂2": "select",
                "污水处理药剂3": "select",
                "废气处理方式": "select",
                "危废委外焚烧总量": "text",
                "危废委外焚烧目标产品产线分解": "text",
                "危废自行焚烧总量": "text",
                "危废自行焚烧目标产品产线分解": "text",
                "危废委外资源化总量": "text",
                "危废委外资源化目标产品产线分解": "text",
                "危废自行资源化总量": "text",
                "危废自行资源化目标产品产线分解": "text",
                "烟气处理药剂1": "select",
                "烟气处理药剂2": "select",
                "烟气处理药剂3": "select",
                "烟气处理药剂4": "select"
            }),
            8: FormSection(8, "原材料使用", {
                "PCF核算目标产品生产工艺流程图": "text",
                "PCF核算目标产品生产工艺流程文字描述": "text",
                "原材料1名称": "text",
                "原材料1使用量": "text",
                "原材料2名称": "text",
                "原材料2使用量": "text",
                "原材料3名称": "text",
                "原材料3使用量": "text",
                "原材料4名称": "text",
                "原材料4使用量": "text",
                "原材料5名称": "text",
                "原材料5使用量": "text",
                "原材料6名称": "text",
                "原材料6使用量": "text",
                "原材料7名称": "text",
                "原材料7使用量": "text",
                "原材料8名称": "text",
                "原材料8使用量": "text",
                "原材料9名称": "text",
                "原材料9使用量": "text",
                "原材料10名称": "text",
                "原材料10使用量": "text",
                "供应商A": "text",
                "供应商B": "text",
                "供应商C": "text",
                "供应商D": "text",
                "供应商E": "text",
                "供应商F": "text",
                "供应商G": "text",
                "供应商H": "text",
                "供应商I": "text",
                "供应商J": "text",
                "供应商K": "text",
                "供应商L": "text"
            }),
            9: FormSection(9, "生产耗材", {
                "新鲜水统计口径": "select",
                "新鲜水使用量": "text",
                "新鲜水单位": "select",
                "氮气统计口径": "select",
                "氮气使用量": "text",
                "氮气单位": "select"
            })
        }

    def fill_form(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """将数据填入表单"""
        try:
            if self.section not in self.section_definitions:
                logger.warning(f"无效的部分编号: {self.section}")
                return {"error": f"无效的部分编号: {self.section}"}

            section_def = self.section_definitions[self.section]
            filled_data = {}
            errors = []

            for field_name, field_type in section_def.fields.items():
                value = data.get(field_name)

                if value is None or (isinstance(value, str) and not value.strip()):
                    continue

                if field_type == "select":
                    if not self._validate_select_value(field_name, value):
                        errors.append(f"字段 '{field_name}' 的值 '{value}' 不在选项列表中")
                        continue

                filled_data[field_name] = value

            logger.info(f"表单填充完成: section={self.section}, filled={len(filled_data)}, errors={len(errors)}")
            return {
                "msg_id": str(uuid.uuid4()),
                "section": self.section,
                "section_name": section_def.name,
                "filled_data": filled_data,
                "errors": errors,
                "timestamp": datetime.now().isoformat(),
                "status": "completed" if not errors else "partial"
            }
        except Exception as e:
            logger.error(f"表单填充失败: section={self.section}, error: {str(e)}", exc_info=True)
            return {"error": f"表单填充失败: {str(e)}"}

    def _validate_select_value(self, field_name: str, value: str) -> bool:
        """验证下拉选项的值"""
        select_options = {
            "是否为生产工厂唯一产品": ["是", "否"],
            "计量单位": ["按重量计量：t", "按体积计量：m3", "按面积计量：m2", "按长度计量：m", "按个数计量：只/个", "其他"],
            "目标产品产线内是否有副产品": ["是", "否"],
            "生产用锅炉燃料": ["液化天然气", "管道天然气", "压缩天然气", "液化石油气", "煤", "石油焦", "其他"],
            "专用废气焚烧炉燃料": ["液化天然气", "管道天然气", "压缩天然气", "液化石油气", "煤", "石油焦", "其他"],
            "危废焚烧炉燃料": ["液化天然气", "管道天然气", "压缩天然气", "液化石油气", "煤", "石油焦", "其他"],
            "发电机燃料": ["液化天然气", "管道天然气", "压缩天然气", "液化石油气", "煤", "石油焦", "其他"],
            "食堂炉灶燃料": ["液化天然气", "管道天然气", "压缩天然气", "液化石油气", "煤", "石油焦", "其他"],
            "厂内转运叉车燃料": ["柴油", "电力", "其他"],
            "自有商务车92#": ["有", "无"],
            "自有商务车95#": ["有", "无"],
            "自有商务车98#": ["有", "无"],
            "自有道路车辆燃料-柴油": ["有", "无"],
            "切割、焊接燃料": ["无", "乙炔", "其他"],
            "全厂用电": ["可单独统计", "不可单独统计"],
            "生产用电": ["可单独统计", "不可单独统计"],
            "行政办公用电": ["可单独统计", "不可单独统计"],
            "目标产品产线用电": ["可单独统计", "不可单独统计"],
            "单耗用电": ["可单独统计", "不可单独统计"],
            "光伏发电配置": ["无", "自建光伏-自用", "自建光伏-上网出售", "出租屋顶服务方投资-绿色权益归己方", "出租屋顶服务方投资-绿色权益归投资服务方", "出租屋顶服务方投资-绿色权益归属不明"],
            "是否购买绿证": ["无", "购买中国绿证GEC", "购买国外绿证irec", "购买国外绿证TIGR", "其他"],
            "是否购买排放权益": ["无", "碳配额交易CEA", "中国自愿减排量CCER", "其他"],
            "全厂用蒸汽": ["可单独统计", "不可单独统计"],
            "生产用蒸汽": ["可单独统计", "不可单独统计"],
            "行政类用蒸汽": ["可单独统计", "不可单独统计"],
            "目标产品产线用蒸汽": ["可单独统计", "不可单独统计"],
            "单耗用蒸汽": ["可单独统计", "不可单独统计"],
            "废水处理方式": ["厂内无废水处理设施", "厂内有废水处理设施-无厌氧工艺单元", "厂内有废水处理设施-有厌氧处理工艺单元"],
            "废气处理方式": ["厂内无废气处理设施", "厂内有废气处理设施-RTO/RCO焚烧处理", "厂内有废气处理设施-活性炭处理", "其他"],
            "新鲜水统计口径": ["全厂生产耗用量", "目标产品产线内容耗用量", "目标产品单耗"],
            "氮气统计口径": ["全厂生产耗用量", "目标产品产线内容耗用量", "目标产品单耗"],
            "新鲜水单位": ["t", "m3"],
            "氮气单位": ["t", "m3"]
        }

        if field_name not in select_options:
            return True

        return value in select_options[field_name]


class FormFillersFactory:
    """表单填报Agent工厂"""

    @staticmethod
    def get_filler(section: int) -> FormFillAgent:
        """获取指定部分的填报Agent"""
        return FormFillAgent(section)

    @staticmethod
    def get_all_fillers() -> Dict[int, FormFillAgent]:
        """获取所有9个部分的填报Agent"""
        return {i: FormFillAgent(i) for i in range(1, 10)}
