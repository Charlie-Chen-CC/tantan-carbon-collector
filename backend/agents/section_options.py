"""
Section 提示词选项字典 - Phase 6.1 反硬编码 (Phase 6.2 将迁到 shared/field_schema.json)

为什么单独成文件：
- LLM 提示词中包含大量选项枚举（燃料类型、制冷剂标号、统计口径…）
- 这些列表会随政策/行业升级变化，不应散落在提示词字符串里
- 集中后便于：
  1. 单元测试（断言选项非空、断言覆盖必要值）
  2. 单点修改（政策变了改一处）
  3. 后续 Phase 6.2 codegen：把这里当 SSOT，生成 JSON 后用脚本注入 SECTION_PROMPTS
"""

# Section 1 - 行业分类引用标准号（按 GB/T 4754 现行版本）
INDUSTRY_STANDARD_REF = "GB/T 4754 现行版本《国民经济行业分类》"

# Section 1 - 常见行业示例（仅作 LLM 理解用，**不是**穷举）
INDUSTRY_EXAMPLES = [
    "化学原料和化学制品制造业",
    "黑色金属冶炼和压延加工业",
    "非金属矿物制品业",
]

# Section 2 - 计量单位
PRODUCT_UNITS = ["t（吨）", "m3（立方米）", "m2（平方米）", "m（米）", "只/个"]

# Section 2 - 副产品最大枚举数
PRODUCT_OTHER_MAX = 5

# Section 3 - 常见燃料类型（**不**穷举；不同企业可能用"生物质成型燃料"等）
COMMON_FUEL_TYPES = [
    "天然气",
    "液化石油气",
    "煤",
    "柴油",
    "汽油",
]

# Section 4 - 二元可统计性
MEASURABLE_OPTIONS = ["可单独统计", "不可单独统计"]

# Section 4 - 光伏发电配置
PHOTOVOLTAIC_CONFIG_OPTIONS = [
    "无",
    "自建光伏-自用",
    "自建光伏-上网出售",
    "出租屋顶服务方投资-绿色权益归己方",
    "出租屋顶服务方投资-绿色权益归投资服务方",
    "出租屋顶服务方投资-绿色权益归属不明",
]

# Section 4 - 绿证购买类型
GREEN_CERTIFICATE_OPTIONS = [
    "无",
    "购买中国绿证GEC",
    "购买国外绿证irec",
    "购买国外绿证TIGR",
    "其他",
]

# Section 4 - 排放权益类型
EMISSION_RIGHTS_OPTIONS = [
    "无",
    "碳配额交易CEA",
    "中国自愿减排量CCER",
    "其他",
]

# Section 5 - 常见制冷剂标号
COMMON_REFRIGERANTS = ["R410A", "R22", "R134a", "R404A", "R407C", "R32"]

# Section 6 - 灭火器类型
FIRE_EXTINGUISHER_TYPES = ["ABC干粉灭火器", "CO2灭火器"]

# Section 7 - 危废处理方式
WASTE_DISPOSAL_METHODS = [
    "委外焚烧",
    "委外资源化",
    "自行焚烧",
    "自行资源化",
]

# Section 8 - 运输方式
TRANSPORT_MODES = ["公路运输", "铁路运输", "水路运输", "管道运输"]

# Section 9 - 统计口径
STATISTICAL_CALIBER_OPTIONS = [
    "全厂生产耗用量",
    "目标产品产线内容耗用量",
    "目标产品单耗",
]
