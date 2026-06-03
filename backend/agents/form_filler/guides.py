"""字段填报引导 - 给 AI/前端参考的字段元信息

FIELD_GUIDES 字典被 8+ 测试用例引用，必须保留。
"""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class FieldGuide:
    """字段填报引导配置"""
    description: str
    data_sources: List[str]
    common_issues: Optional[List[str]] = None
    unit: Optional[str] = None


FIELD_GUIDES: Dict[int, Dict[str, FieldGuide]] = {
    1: {
        "企业名称": FieldGuide(
            description="公司全称（企业全称），应与营业执照登记的名称一致",
            data_sources=["营业执照"],
            common_issues=["应使用工商登记的完整名称", "分公司需注明"]
        ),
        "实际经营地址": FieldGuide(
            description="实际生产经营地址，需精确到区/县",
            data_sources=["营业执照", "租赁合同"],
            common_issues=["多个生产地址需全部填写"]
        ),
        "核算年份": FieldGuide(
            description="本次碳排放核算的数据所属年份",
            data_sources=["历史台账", "财务凭证"],
            common_issues=["应与报告期保持一致"]
        ),
        "核算周期说明": FieldGuide(
            description="核算周期起止日期说明，默认为自然年",
            data_sources=["生产记录", "财务账期"],
            common_issues=["非自然年核算需提供说明"]
        ),
    },
    2: {
        "PCF核算目标产品名称": FieldGuide(
            description="需要进行碳足迹核算的目标产品名称",
            data_sources=["产品销售合同", "产品标签", "生产工艺文件"],
            common_issues=["需与下游客户要求一致", "多种产品需分别核算"]
        ),
        "是否为生产工厂唯一产品": FieldGuide(
            description="该工厂是否只生产这一种产品",
            data_sources=["生产记录", "车间布局图"],
            common_issues=["影响碳排放分摊方法选择"]
        ),
        "计量单位": FieldGuide(
            description="产品产量的计量单位",
            data_sources=["销售合同", "生产统计报表"],
            common_issues=["需与下游客户要求一致", "常用t、m3等"]
        ),
        "目标产品产线内是否有副产品": FieldGuide(
            description="目标产品生产过程中是否产生副产品",
            data_sources=["生产工艺流程图", "生产记录"],
            common_issues=["副产品需单独核算或分摊"]
        ),
    },
    3: {
        "生产用锅炉燃料": FieldGuide(
            description="用于生产的锅炉燃料类型和消耗量",
            data_sources=["能源台账", "采购发票", "锅炉运行记录"],
            unit="吨标准煤或万立方米",
            common_issues=["燃料热值需实测或查表", "区分锅炉用途"]
        ),
        "专用废气焚烧炉燃料": FieldGuide(
            description="废气焚烧装置使用的燃料",
            data_sources=["环保设备运行记录", "采购发票"],
            unit="吨标准煤或万立方米"
        ),
        "危废焚烧炉燃料": FieldGuide(
            description="危险废物焚烧炉使用的燃料",
            data_sources=["危废处置记录", "采购发票"],
            unit="吨标准煤或万立方米"
        ),
        "发电机燃料": FieldGuide(
            description="自备发电机使用的燃料",
            data_sources=["发电运行记录", "燃料采购发票"],
            unit="吨标准煤或万立方米"
        ),
        "食堂炉灶燃料": FieldGuide(
            description="食堂炊事使用的燃料类型",
            data_sources=["食堂采购记录", "燃气账单"],
            unit="吨标准煤或万立方米"
        ),
        "厂内转运叉车燃料": FieldGuide(
            description="厂内物料转运叉车使用的燃料",
            data_sources=["设备运行记录", "燃料采购发票"],
            unit="吨标准煤或万立方米"
        ),
        "自有商务车92#": FieldGuide(
            description="自有商务车使用92号汽油的消耗情况",
            data_sources=["车辆加油记录", "行车里程记录"],
            common_issues=["有/无选择需与实际一致"]
        ),
        "自有商务车95#": FieldGuide(
            description="自有商务车使用95号汽油的消耗情况",
            data_sources=["车辆加油记录", "行车里程记录"]
        ),
        "自有商务车98#": FieldGuide(
            description="自有商务车使用98号汽油的消耗情况",
            data_sources=["车辆加油记录", "行车里程记录"]
        ),
        "自有道路车辆燃料-柴油": FieldGuide(
            description="自有道路运输车辆使用柴油的消耗情况",
            data_sources=["车辆加油记录", "运输合同"]
        ),
        "切割、焊接燃料": FieldGuide(
            description="切割、焊接作业使用的燃料类型",
            data_sources=["采购发票", "作业记录"]
        ),
    },
    4: {
        "全厂用电": FieldGuide(
            description="核算期内全厂总用电量",
            data_sources=["电费发票", "电表读数"],
            unit="MWh",
            common_issues=["应包含外购电与自发电之和"]
        ),
        "行政办公用电": FieldGuide(
            description="行政办公区电力消耗量",
            data_sources=["电费发票", "物业账单"],
            unit="MWh"
        ),
        "目标产品产线用电": FieldGuide(
            description="目标产品专用产线的电力消耗",
            data_sources=["电表分项计量", "生产统计"],
            unit="MWh"
        ),
        "单耗用电": FieldGuide(
            description="单位产品电力消耗量",
            data_sources=["生产统计", "能耗台账"],
            unit="MWh/t或MWh/m3"
        ),
        "光伏发电量": FieldGuide(
            description="自建光伏电站的发电量",
            data_sources=["光伏逆变器数据", "电网调度单"],
            unit="MWh"
        ),
        "光伏发电配置": FieldGuide(
            description="光伏发电设施的装机配置情况",
            data_sources=["光伏项目批复", "设备清单"]
        ),
        "是否购买绿证": FieldGuide(
            description="是否购买绿色电力证书",
            data_sources=["绿证购买合同", "电网结算单"]
        ),
        "是否购买排放权益": FieldGuide(
            description="是否购买碳排放配额或减排量",
            data_sources=["碳交易记录", "CCER购买凭证"]
        ),
        "蒸汽温度": FieldGuide(
            description="外购蒸汽的温度参数",
            data_sources=["蒸汽供应合同", "热力公司参数单"],
            unit="℃"
        ),
        "蒸汽压力": FieldGuide(
            description="外购蒸汽的压力参数",
            data_sources=["蒸汽供应合同", "热力公司参数单"],
            unit="MPa"
        ),
        "全厂用蒸汽": FieldGuide(
            description="核算期内全厂蒸汽消耗总量",
            data_sources=["蒸汽计量表", "热力公司账单"],
            unit="GJ或t"
        ),
        "生产用蒸汽": FieldGuide(
            description="用于生产的蒸汽消耗量",
            data_sources=["蒸汽计量表", "生产统计"],
            unit="GJ或t"
        ),
    },
    5: {
        "空调制冷剂": FieldGuide(
            description="空调系统制冷剂填充量及标号",
            data_sources=["设备铭牌", "维修保养记录", "采购发票"],
            unit="kg",
            common_issues=["制冷剂GWP值需查IPCC报告", "泄漏量按2%估算"]
        ),
        "冷冻机制冷剂": FieldGuide(
            description="冷冻机组制冷剂填充量及标号",
            data_sources=["设备铭牌", "维修保养记录"],
            unit="kg"
        ),
    },
    6: {
        "CO2灭火器填充总量": FieldGuide(
            description="CO2灭火器年度补充填充总量",
            data_sources=["消防设备维护记录", "采购发票"],
            unit="kg",
            common_issues=["仅计算补充量，不含初始充装"]
        ),
        "核算期内员工总工时": FieldGuide(
            description="核算期内全体员工工作时间总和",
            data_sources=["HR考勤系统", "工资发放记录"],
            unit="h",
            common_issues=["含外包人员工时"]
        ),
    },
    7: {
        "废水处理方式": FieldGuide(
            description="废水处理设施及工艺类型",
            data_sources=["环评批复", "污水处理站运行记录"]
        ),
        "废水处理量": FieldGuide(
            description="年度废水处理总量",
            data_sources=["污水处理站运行记录", "在线监测数据"],
            unit="t"
        ),
        "目标产品产线废水": FieldGuide(
            description="目标产品产线产生的废水量",
            data_sources=["生产统计", "水平衡测试报告"],
            unit="t"
        ),
        "COD浓度": FieldGuide(
            description="废水COD排放浓度",
            data_sources=["在线监测数据", "第三方检测报告"],
            unit="mg/L"
        ),
        "废气处理方式": FieldGuide(
            description="废气处理设施及工艺类型",
            data_sources=["环评批复", "废气处理设施运行记录"]
        ),
        "危废委外焚烧总量": FieldGuide(
            description="委托外部机构焚烧的危险废物总量",
            data_sources=["危废转移联单", "处置合同", "发票"],
            unit="t"
        ),
        "危废自行焚烧总量": FieldGuide(
            description="企业自行焚烧的危险废物总量",
            data_sources=["危废处置记录", "台账"],
            unit="t"
        ),
        "危废委外资源化总量": FieldGuide(
            description="委托外部资源化利用的危险废物总量",
            data_sources=["危废转移联单", "资源化利用合同"],
            unit="t"
        ),
        "危废自行资源化总量": FieldGuide(
            description="企业自行资源化利用的危险废物总量",
            data_sources=["危废处置记录", "台账"],
            unit="t"
        ),
    },
    8: {
        "PCF核算目标产品生产工艺流程图": FieldGuide(
            description="目标产品生产工艺流程的文字描述",
            data_sources=["工艺设计文件", "环评报告"],
            common_issues=["需包含主要工序和设备"]
        ),
        "PCF核算目标产品生产工艺流程文字描述": FieldGuide(
            description="生产工艺各环节的详细描述",
            data_sources=["工艺操作规程", "生产技术部文件"]
        ),
        "原材料": FieldGuide(
            description="主要原材料的名称和使用量",
            data_sources=["采购合同", "入库单", "生产配方"],
            unit="t或m3",
            common_issues=["原材料需区分直接材料和间接材料"]
        ),
        "供应商": FieldGuide(
            description="原材料供应商信息及运输距离",
            data_sources=["采购合同", "物流单据"],
            unit="km"
        ),
    },
    9: {
        "新鲜水统计口径": FieldGuide(
            description="新鲜水消耗量的统计口径",
            data_sources=["水平衡测试报告", "用水管理制度"]
        ),
        "新鲜水使用量": FieldGuide(
            description="年度新鲜水消耗总量",
            data_sources=["水费发票", "水表读数记录"],
            unit="t或m3",
            common_issues=["需与自来水公司账单一致"]
        ),
        "氮气使用量": FieldGuide(
            description="年度氮气消耗总量",
            data_sources=["气体采购发票", "流量计记录"],
            unit="m3或t"
        ),
    },
}


def get_field_guide(section: int, field_key: str) -> Optional[FieldGuide]:
    """获取指定字段的引导配置

    Args:
        section: 表单部分编号(1-9)
        field_key: 字段名称

    Returns:
        FieldGuide 对象，未找到则返回 None
    """
    return FIELD_GUIDES.get(section, {}).get(field_key)
