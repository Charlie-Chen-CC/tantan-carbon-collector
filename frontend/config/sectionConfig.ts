// ⚠️ 此文件由 `python -m tantan.backend.scripts.codegen_field_schema` 自动生成
// 不要手动编辑！改 `tantan/shared/field_schema.json` 后重跑 codegen。

export type FieldType = 'text' | 'number' | 'select' | 'file' | 'multi-row' | 'nested';

export interface FieldDef {
  key: string;
  label: string;
  type: FieldType;
  placeholder?: string;
  options?: string[];
  required?: boolean;
  fields?: FieldDef[];
  maxRows?: number;
}

export const SECTION_NAMES: string[] = [
  '',
  '基本信息',
  '产品',
  '燃料使用',
  '电力、热力使用',
  '制冷剂使用',
  '其他散逸类排放',
  '三废处理',
  '原材料使用',
  '生产耗材',
];

export const SECTION_FIELDS: { [section: number]: FieldDef[] } = {
  1: [
    { key: 'enterpriseName', label: '企业名称', type: 'text', required: true, placeholder: '请输入企业全称' },
    { key: 'industry', label: '所属行业', type: 'text', required: true, placeholder: '请输入所属行业' },
    { key: 'contact', label: '联系人', type: 'text', placeholder: '请输入联系人姓名' },
    { key: 'contactPhone', label: '联系方式', type: 'text', placeholder: '请输入电话或邮箱' },
    { key: 'productionAddress', label: '生产地址', type: 'text', placeholder: '请输入生产地址' },
    { key: 'reportingYear', label: '核算年份', type: 'text', placeholder: '如 2024' },
    { key: 'reportingPeriod', label: '核算周期说明', type: 'text', placeholder: '如 2024.1.1~2024.12.31' },
    { key: 'isCalendarYear', label: '是否为自然年（1月1日-12月31日）', type: 'select', options: ['是', '否'] },
  ],
  2: [
    { key: 'targetProductName', label: 'PCF核算目标产品名称', type: 'text', required: true },
    { key: 'isOnlyProduct', label: '是否为生产工厂唯一产品', type: 'select', options: ['是', '否'] },
    { key: 'otherProduct1Name', label: '其他产品1名称', type: 'text' },
    { key: 'otherProduct2Name', label: '其他产品2名称', type: 'text' },
    { key: 'otherProduct3Name', label: '其他产品3名称', type: 'text' },
    { key: 'otherProduct4Name', label: '其他产品4名称', type: 'text' },
    { key: 'otherProduct5Name', label: '其他产品5名称', type: 'text' },
    { key: 'otherProductsNote', label: '其他产品超过5种的说明', type: 'text' },
    { key: 'unit', label: '计量单位', type: 'select', options: ['t', 'm3', 'm2', 'm', '只/个'] },
    { key: 'hasByproduct', label: '目标产品产线内是否有副产品', type: 'select', options: ['是', '否'] },
    { key: 'byproduct1Name', label: '副产品1名称', type: 'text' },
    { key: 'byproduct2Name', label: '副产品2名称', type: 'text' },
    { key: 'byproduct3Name', label: '副产品3名称', type: 'text' },
    { key: 'byproduct4Name', label: '副产品4名称', type: 'text' },
    { key: 'byproduct5Name', label: '副产品5名称', type: 'text' },
    { key: 'byproductsNote', label: '副产品超过5种的说明', type: 'text' },
  ],
  3: [
    { key: 'boilerFuel', label: '生产用锅炉燃料', type: 'multi-row', fields: [,     { key: 'fuelType', label: '燃料类型', type: 'text' },,     { key: 'amount', label: '使用量', type: 'text' },,     { key: 'unit', label: '单位', type: 'text' },,     { key: 'measuredCalorific', label: '实测热值', type: 'text' },,     { key: 'calorificUnit', label: '热值单位', type: 'text' },,   ] },
    { key: 'wasteIncineratorFuel', label: '专用废气焚烧炉燃料', type: 'multi-row', fields: [,     { key: 'fuelType', label: '燃料类型', type: 'text' },,     { key: 'amount', label: '使用量', type: 'text' },,     { key: 'unit', label: '单位', type: 'text' },,   ] },
    { key: 'hazardousWasteBurnerFuel', label: '危废焚烧炉燃料', type: 'multi-row', fields: [,     { key: 'fuelType', label: '燃料类型', type: 'text' },,     { key: 'amount', label: '使用量', type: 'text' },,     { key: 'unit', label: '单位', type: 'text' },,   ] },
    { key: 'generatorFuel', label: '发电机燃料', type: 'multi-row', fields: [,     { key: 'fuelType', label: '燃料类型', type: 'text' },,     { key: 'amount', label: '使用量', type: 'text' },,     { key: 'unit', label: '单位', type: 'text' },,   ] },
    { key: 'canteenFuel', label: '食堂炉灶燃料', type: 'multi-row', fields: [,     { key: 'fuelType', label: '燃料类型', type: 'text' },,     { key: 'amount', label: '使用量', type: 'text' },,     { key: 'unit', label: '单位', type: 'text' },,   ] },
    { key: 'forkliftFuel', label: '厂内转运叉车燃料', type: 'multi-row', fields: [,     { key: 'fuelType', label: '燃料类型', type: 'text' },,     { key: 'amount', label: '使用量', type: 'text' },,     { key: 'unit', label: '单位', type: 'text' },,   ] },
    { key: 'commercialVehicle92', label: '自有商务车92#', type: 'multi-row', fields: [,     { key: 'fuelType', label: '燃料类型', type: 'text' },,   ] },
    { key: 'commercialVehicle95', label: '自有商务车95#', type: 'multi-row', fields: [,     { key: 'fuelType', label: '燃料类型', type: 'text' },,   ] },
    { key: 'commercialVehicle98', label: '自有商务车98#', type: 'multi-row', fields: [,     { key: 'fuelType', label: '燃料类型', type: 'text' },,   ] },
    { key: 'roadVehicleDiesel', label: '自有道路车辆燃料-柴油', type: 'multi-row', fields: [,     { key: 'fuelType', label: '燃料类型', type: 'text' },,   ] },
    { key: 'weldingFuel', label: '切割、焊接燃料', type: 'multi-row', fields: [,     { key: 'fuelType', label: '燃料类型', type: 'text' },,   ] },
  ],
  4: [
    { key: 'totalElectricityMeasurable', label: '全厂用电', type: 'select', options: ['可单独统计', '不可单独统计'] },
    { key: 'totalElectricityAmount', label: '全厂用电量', type: 'text' },
    { key: 'productionElectricityMeasurable', label: '生产用电', type: 'select', options: ['可单独统计', '不可单独统计'] },
    { key: 'productionElectricityAmount', label: '生产用电量', type: 'text' },
    { key: 'officeElectricityMeasurable', label: '行政办公用电', type: 'select', options: ['可单独统计', '不可单独统计'] },
    { key: 'officeElectricityAmount', label: '行政办公用电量', type: 'text' },
    { key: 'productLineElectricityMeasurable', label: '目标产品产线用电', type: 'select', options: ['可单独统计', '不可单独统计'] },
    { key: 'productLineElectricityAmount', label: '目标产品产线用电量', type: 'text' },
    { key: 'unitConsumptionElectricityMeasurable', label: '单耗用电', type: 'select', options: ['可单独统计', '不可单独统计'] },
    { key: 'unitConsumptionElectricityAmount', label: '单耗用电量', type: 'text' },
    { key: 'solarGeneration', label: '光伏发电量', type: 'text' },
    { key: 'solarConfig', label: '光伏发电配置', type: 'select' },
    { key: 'greenCertificate', label: '是否购买绿证', type: 'select' },
    { key: 'greenCertificateAmount', label: '绿证购买量', type: 'text' },
    { key: 'emissionRights', label: '是否购买排放权益', type: 'select' },
    { key: 'emissionRightsAmount', label: '排放权益购买量', type: 'text' },
    { key: 'steamTemperature', label: '蒸汽温度', type: 'text' },
    { key: 'steamPressure', label: '蒸汽压力', type: 'text' },
    { key: 'totalSteamMeasurable', label: '全厂用蒸汽', type: 'select', options: ['可单独统计', '不可单独统计'] },
    { key: 'totalSteamAmount', label: '全厂蒸汽量', type: 'text' },
    { key: 'productionSteamMeasurable', label: '生产用蒸汽', type: 'select', options: ['可单独统计', '不可单独统计'] },
    { key: 'productionSteamAmount', label: '生产蒸汽量', type: 'text' },
    { key: 'officeSteamMeasurable', label: '行政类用蒸汽', type: 'select', options: ['可单独统计', '不可单独统计'] },
    { key: 'officeSteamAmount', label: '行政类蒸汽量', type: 'text' },
    { key: 'productLineSteamMeasurable', label: '目标产品产线用蒸汽', type: 'select', options: ['可单独统计', '不可单独统计'] },
    { key: 'productLineSteamAmount', label: '目标产品产线蒸汽量', type: 'text' },
    { key: 'unitConsumptionSteamMeasurable', label: '单耗用蒸汽', type: 'select', options: ['可单独统计', '不可单独统计'] },
    { key: 'unitConsumptionSteamAmount', label: '单耗蒸汽量', type: 'text' },
  ],
  5: [
    { key: 'airConditioners', label: '空调制冷剂', type: 'multi-row', fields: [,     { key: 'equipmentName', label: '设备名称', type: 'text' },,     { key: 'refrigerantNo', label: '标号', type: 'text' },,     { key: 'fillAmount', label: '填充量', type: 'text' },,   ] },
    { key: 'freezers', label: '冷冻机制冷剂', type: 'multi-row', fields: [,     { key: 'equipmentName', label: '设备名称', type: 'text' },,     { key: 'refrigerantNo', label: '标号', type: 'text' },,     { key: 'fillAmount', label: '填充量', type: 'text' },,   ] },
  ],
  6: [
    { key: 'co2Extinguisher', label: 'CO2灭火器填充总量', type: 'text' },
    { key: 'employeeHours', label: '核算期内员工总工时', type: 'text' },
  ],
  7: [
    { key: 'wastewaterTreatmentMethod', label: '废水处理方式', type: 'text' },
    { key: 'wastewaterAmount', label: '废水处理量', type: 'text' },
    { key: 'productLineWastewater', label: '目标产品产线废水', type: 'text' },
    { key: 'codConcentration', label: 'COD浓度', type: 'text' },
    { key: 'wastewaterAgent1', label: '污水处理药剂1', type: 'text' },
    { key: 'wastewaterAgent2', label: '污水处理药剂2', type: 'text' },
    { key: 'wastewaterAgent3', label: '污水处理药剂3', type: 'text' },
    { key: 'exhaustGasTreatmentMethod', label: '废气处理方式', type: 'text' },
    { key: 'outsourcedIncinerationTotal', label: '危废委外焚烧总量', type: 'text' },
    { key: 'outsourcedIncinerationProductLine', label: '危废委外焚烧目标产品产线分解', type: 'text' },
    { key: 'selfIncinerationTotal', label: '危废自行焚烧总量', type: 'text' },
    { key: 'selfIncinerationProductLine', label: '危废自行焚烧目标产品产线分解', type: 'text' },
    { key: 'outsourcedRecyclingTotal', label: '危废委外资源化总量', type: 'text' },
    { key: 'outsourcedRecyclingProductLine', label: '危废委外资源化目标产品产线分解', type: 'text' },
    { key: 'selfRecyclingTotal', label: '危废自行资源化总量', type: 'text' },
    { key: 'selfRecyclingProductLine', label: '危废自行资源化目标产品产线分解', type: 'text' },
    { key: 'flueGasAgent1', label: '烟气处理药剂1', type: 'text' },
    { key: 'flueGasAgent2', label: '烟气处理药剂2', type: 'text' },
    { key: 'flueGasAgent3', label: '烟气处理药剂3', type: 'text' },
    { key: 'flueGasAgent4', label: '烟气处理药剂4', type: 'text' },
  ],
  8: [
    { key: 'productionProcess', label: 'PCF核算目标产品生产工艺流程文字描述', type: 'text' },
    { key: 'rawMaterials', label: '原材料', type: 'multi-row', fields: [,     { key: 'name', label: '名称', type: 'text' },,     { key: 'spec', label: '规格', type: 'text' },,     { key: 'amount', label: '使用量', type: 'text' },,     { key: 'unit', label: '单位', type: 'text' },,   ] },
    { key: 'suppliers', label: '供应商', type: 'multi-row', fields: [,     { key: 'name', label: '名称', type: 'text' },,     { key: 'category', label: '品类', type: 'text' },,     { key: 'transportMode', label: '运输方式', type: 'text' },,     { key: 'transportDistance', label: '运距', type: 'text' },,   ] },
  ],
  9: [
    { key: 'freshWater', label: '新鲜水', type: 'nested' },
    { key: 'freshWaterUsage', label: '新鲜水使用量', type: 'text' },
    { key: 'nitrogen', label: '氮气', type: 'nested' },
  ],
};
