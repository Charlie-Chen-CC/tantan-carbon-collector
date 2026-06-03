"""9 个 section 的字段定义 + FormSection 类（由 codegen 自动生成）"""
# ⚠️ 此文件由 `python -m tantan.backend.scripts.codegen_field_schema` 自动生成
# 不要手动编辑！改 `tantan/shared/field_schema.json` 后重跑 codegen。

from typing import Dict, Any



class FormSection:
    """表单部分的字段定义"""

    def __init__(self, section: int, name: str, fields: Dict[str, str]):
        self.section = section
        self.name = name
        self.fields = fields  # field_name -> field_type


def get_section_definitions() -> Dict[int, FormSection]:
    """获取所有 9 个 section 的字段定义（返回新字典，每次调用独立）"""
    return {
        1: FormSection(1, "基本信息", {
            "企业名称": "text",
            "所属行业": "text",
            "联系人": "text",
            "联系方式": "text",
            "生产地址": "text",
            "核算年份": "text",
            "核算周期说明": "text",
            "是否为自然年（1月1日-12月31日）": "select",
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
            "副产品超过5种的说明": "text",
        }),
        3: FormSection(3, "燃料使用", {
            "生产用锅炉燃料": "multi-row",
            "专用废气焚烧炉燃料": "multi-row",
            "危废焚烧炉燃料": "multi-row",
            "发电机燃料": "multi-row",
            "食堂炉灶燃料": "multi-row",
            "厂内转运叉车燃料": "multi-row",
            "自有商务车92#": "multi-row",
            "自有商务车95#": "multi-row",
            "自有商务车98#": "multi-row",
            "自有道路车辆燃料-柴油": "multi-row",
            "切割、焊接燃料": "multi-row",
        }),
        4: FormSection(4, "电力、热力使用", {
            "全厂用电": "select",
            "全厂用电量": "text",
            "生产用电": "select",
            "生产用电量": "text",
            "行政办公用电": "select",
            "行政办公用电量": "text",
            "目标产品产线用电": "select",
            "目标产品产线用电量": "text",
            "单耗用电": "select",
            "单耗用电量": "text",
            "光伏发电量": "text",
            "光伏发电配置": "select",
            "是否购买绿证": "select",
            "绿证购买量": "text",
            "是否购买排放权益": "select",
            "排放权益购买量": "text",
            "蒸汽温度": "text",
            "蒸汽压力": "text",
            "全厂用蒸汽": "select",
            "全厂蒸汽量": "text",
            "生产用蒸汽": "select",
            "生产蒸汽量": "text",
            "行政类用蒸汽": "select",
            "行政类蒸汽量": "text",
            "目标产品产线用蒸汽": "select",
            "目标产品产线蒸汽量": "text",
            "单耗用蒸汽": "select",
            "单耗蒸汽量": "text",
        }),
        5: FormSection(5, "制冷剂使用", {
            "空调制冷剂": "multi-row",
            "冷冻机制冷剂": "multi-row",
        }),
        6: FormSection(6, "其他散逸类排放", {
            "CO2灭火器填充总量": "text",
            "核算期内员工总工时": "text",
        }),
        7: FormSection(7, "三废处理", {
            "废水处理方式": "text",
            "废水处理量": "text",
            "目标产品产线废水": "text",
            "COD浓度": "text",
            "污水处理药剂1": "text",
            "污水处理药剂2": "text",
            "污水处理药剂3": "text",
            "废气处理方式": "text",
            "危废委外焚烧总量": "text",
            "危废委外焚烧目标产品产线分解": "text",
            "危废自行焚烧总量": "text",
            "危废自行焚烧目标产品产线分解": "text",
            "危废委外资源化总量": "text",
            "危废委外资源化目标产品产线分解": "text",
            "危废自行资源化总量": "text",
            "危废自行资源化目标产品产线分解": "text",
            "烟气处理药剂1": "text",
            "烟气处理药剂2": "text",
            "烟气处理药剂3": "text",
            "烟气处理药剂4": "text",
        }),
        8: FormSection(8, "原材料使用", {
            "PCF核算目标产品生产工艺流程文字描述": "text",
            "原材料": "multi-row",
            "供应商": "multi-row",
        }),
        9: FormSection(9, "生产耗材", {
            "新鲜水": "nested",
            "新鲜水使用量": "text",
            "氮气": "nested",
        }),
    }
