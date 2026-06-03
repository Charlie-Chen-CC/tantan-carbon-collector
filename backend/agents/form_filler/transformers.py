"""字段转换器 - 多行动态字段 + 嵌套对象字段（由 codegen 自动生成）"""
# ⚠️ 此文件由 `python -m tantan.backend.scripts.codegen_field_schema` 自动生成
# 不要手动编辑！改 `tantan/shared/field_schema.json` 后重跑 codegen。

from typing import Dict, Any



# 多行动态字段转换器：将 LLM 提取的平展数据转换为前端嵌套数组结构
MULTI_ROW_TRANSFORMERS: Dict[str, Dict[str, Any]] = {
    "生产用锅炉燃料": {
        "frontend_key": "boilerFuel",
        "sub_fields": {'fuelType': '燃料类型', 'amount': '使用量', 'unit': '单位', 'measuredCalorific': '实测热值', 'calorificUnit': '热值单位'}
    },
    "专用废气焚烧炉燃料": {
        "frontend_key": "wasteIncineratorFuel",
        "sub_fields": {'fuelType': '燃料类型', 'amount': '使用量', 'unit': '单位'}
    },
    "危废焚烧炉燃料": {
        "frontend_key": "hazardousWasteBurnerFuel",
        "sub_fields": {'fuelType': '燃料类型', 'amount': '使用量', 'unit': '单位'}
    },
    "发电机燃料": {
        "frontend_key": "generatorFuel",
        "sub_fields": {'fuelType': '燃料类型', 'amount': '使用量', 'unit': '单位'}
    },
    "食堂炉灶燃料": {
        "frontend_key": "canteenFuel",
        "sub_fields": {'fuelType': '燃料类型', 'amount': '使用量', 'unit': '单位'}
    },
    "厂内转运叉车燃料": {
        "frontend_key": "forkliftFuel",
        "sub_fields": {'fuelType': '燃料类型', 'amount': '使用量', 'unit': '单位'}
    },
    "自有商务车92#": {
        "frontend_key": "commercialVehicle92",
        "sub_fields": {'fuelType': '燃料类型'}
    },
    "自有商务车95#": {
        "frontend_key": "commercialVehicle95",
        "sub_fields": {'fuelType': '燃料类型'}
    },
    "自有商务车98#": {
        "frontend_key": "commercialVehicle98",
        "sub_fields": {'fuelType': '燃料类型'}
    },
    "自有道路车辆燃料-柴油": {
        "frontend_key": "roadVehicleDiesel",
        "sub_fields": {'fuelType': '燃料类型'}
    },
    "切割、焊接燃料": {
        "frontend_key": "weldingFuel",
        "sub_fields": {'fuelType': '燃料类型'}
    },
    "空调制冷剂": {
        "frontend_key": "airConditioners",
        "sub_fields": {'equipmentName': '设备名称', 'refrigerantNo': '标号', 'fillAmount': '填充量'},
            "is_array": True
    },
    "冷冻机制冷剂": {
        "frontend_key": "freezers",
        "sub_fields": {'equipmentName': '设备名称', 'refrigerantNo': '标号', 'fillAmount': '填充量'},
            "is_array": True
    },
    "原材料": {
        "frontend_key": "rawMaterials",
        "sub_fields": {'name': '名称', 'spec': '规格', 'amount': '使用量', 'unit': '单位'},
            "is_array": True, "numeric_suffix": True
    },
    "供应商": {
        "frontend_key": "suppliers",
        "sub_fields": {'name': '名称', 'category': '品类', 'transportMode': '运输方式', 'transportDistance': '运距'},
            "is_array": True, "numeric_suffix": True
    },
}

# 嵌套对象字段转换器：将嵌套字典拆分为扁平字段
NESTED_FIELD_TRANSFORMERS: Dict[str, Dict[str, Any]] = {
    "新鲜水": {
        "frontend_key": "freshWater",
        "sub_fields": {
            "freshWaterCaliber": "统计口径",
            "freshWaterAmount": "使用量",
            "freshWaterUnit": "单位",
        },
    },
    "氮气": {
        "frontend_key": "nitrogen",
        "sub_fields": {
            "nitrogenCaliber": "统计口径",
            "nitrogenAmount": "使用量",
            "nitrogenUnit": "单位",
        },
    },
}
