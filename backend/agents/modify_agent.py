"""
修改Agent - 碳管师收资系统
负责处理用户对表单的修改请求
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from tantan.backend.utils import get_logger

logger = get_logger(__name__)


class ModifyRequest:
    """修改请求"""

    def __init__(self, section: int, field: str, old_value: Any, new_value: Any, reason: str = ""):
        self.section = section
        self.field = field
        self.old_value = old_value
        self.new_value = new_value
        self.reason = reason
        self.request_id = str(uuid.uuid4())
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "section": self.section,
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat()
        }


class ModifyAgent:
    """修改Agent"""

    def __init__(self):
        self.modify_history: List[Dict[str, Any]] = []

    def validate_modify_request(self, request: ModifyRequest) -> Dict[str, Any]:
        """验证修改请求"""
        errors = []

        # 检查部分编号是否有效
        if not 1 <= request.section <= 9:
            errors.append(f"无效的部分编号: {request.section}")

        # 检查字段是否为空
        if not request.field or not request.field.strip():
            errors.append("字段名称不能为空")

        # 检查新值是否有效（根据字段类型）
        if isinstance(request.new_value, str) and len(request.new_value) > 1000:
            errors.append("字段值过长")

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

    def process_modify_request(self, section: int, field: str, old_value: Any, new_value: Any,
                               reason: str = "", current_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """处理修改请求"""
        try:
            request = ModifyRequest(section, field, old_value, new_value, reason)

            # 验证请求
            validation = self.validate_modify_request(request)
            if not validation["valid"]:
                logger.info(f"修改请求验证失败: field={field}, errors={validation['errors']}")
                return {
                    "success": False,
                    "request_id": request.request_id,
                    "errors": validation["errors"]
                }

            # 如果提供了当前数据，验证旧值是否匹配
            if current_data and current_data.get(field) != old_value:
                logger.warning(f"修改请求旧值不匹配: field={field}, expected={old_value}, actual={current_data.get(field)}")
                return {
                    "success": False,
                    "request_id": request.request_id,
                    "error": f"旧值不匹配，当前值为: {current_data.get(field)}"
                }

            # 记录修改历史
            modify_record = {
                "request_id": request.request_id,
                "section": request.section,
                "field": request.field,
                "old_value": request.old_value,
                "new_value": request.new_value,
                "reason": request.reason,
                "timestamp": request.timestamp.isoformat(),
                "status": "completed"
            }
            self.modify_history.append(modify_record)

            logger.info(f"修改请求处理成功: field={field}, section={section}")
            return {
                "success": True,
                "request_id": request.request_id,
                "modify_record": modify_record,
                "message": f"成功修改字段 '{field}'"
            }
        except Exception as e:
            logger.error(f"修改请求处理失败: field={field}, section={section}, error: {str(e)}", exc_info=True)
            return {"success": False, "error": f"修改请求处理失败: {str(e)}"}

    def batch_modify(self, modifications: List[Dict[str, Any]], current_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """批量修改"""
        results = []
        success_count = 0
        failure_count = 0

        for mod in modifications:
            result = self.process_modify_request(
                section=mod.get("section"),
                field=mod.get("field"),
                old_value=mod.get("old_value"),
                new_value=mod.get("new_value"),
                reason=mod.get("reason", ""),
                current_data=current_data
            )

            if result["success"]:
                success_count += 1
            else:
                failure_count += 1

            results.append(result)

        return {
            "total": len(modifications),
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results
        }

    def get_modify_history(self, section: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取修改历史"""
        if section is None:
            return self.modify_history

        return [record for record in self.modify_history if record["section"] == section]

    def rollback(self, request_id: str) -> Dict[str, Any]:
        """回滚修改"""
        for i, record in enumerate(self.modify_history):
            if record["request_id"] == request_id:
                # 执行回滚
                self.modify_history[i]["status"] = "rolled_back"
                self.modify_history[i]["rollback_timestamp"] = datetime.now().isoformat()

                return {
                    "success": True,
                    "request_id": request_id,
                    "rolled_back_to": record["old_value"],
                    "message": f"成功回滚修改 '{record['field']}'"
                }

        return {
            "success": False,
            "error": f"未找到修改请求: {request_id}"
        }


class ModifyValidator:
    """修改验证器"""

    # 各部分的有效字段列表
    VALID_FIELDS = {
        1: ["企业名称", "所属行业", "联系人", "联系方式", "生产地址", "核算年份", "核算周期说明"],
        2: ["PCF核算目标产品名称", "是否为生产工厂唯一产品", "其他产品1名称", "其他产品2名称",
            "其他产品3名称", "其他产品4名称", "其他产品5名称", "其他产品超过5种的说明",
            "计量单位", "目标产品产线内是否有副产品", "副产品1名称", "副产品2名称",
            "副产品3名称", "副产品4名称", "副产品5名称", "副产品超过5种的说明"],
        3: ["生产用锅炉燃料", "专用废气焚烧炉燃料", "危废焚烧炉燃料", "发电机燃料",
            "食堂炉灶燃料", "厂内转运叉车燃料", "自有商务车92#", "自有商务车95#",
            "自有商务车98#", "自有道路车辆燃料-柴油", "切割、焊接燃料"],
        4: ["全厂用电", "生产用电", "行政办公用电", "目标产品产线用电", "单耗用电",
            "光伏发电量", "光伏发电配置", "是否购买绿证", "是否购买排放权益",
            "蒸汽温度", "蒸汽压力", "全厂用蒸汽", "生产用蒸汽", "行政类用蒸汽",
            "目标产品产线用蒸汽", "单耗用蒸汽"],
        5: ["空调制冷剂1标号", "空调制冷剂1填充量", "空调制冷剂2标号", "空调制冷剂2填充量",
            "空调制冷剂3标号", "空调制冷剂3填充量", "空调制冷剂4标号", "空调制冷剂4填充量",
            "空调制冷剂5标号", "空调制冷剂5填充量", "冷冻机制冷剂1标号", "冷冻机制冷剂1填充量",
            "冷冻机制冷剂2标号", "冷冻机制冷剂2填充量", "冷冻机制冷剂3标号", "冷冻机制冷剂3填充量",
            "冷冻机制冷剂4标号", "冷冻机制冷剂4填充量", "冷冻机制冷剂5标号", "冷冻机制冷剂5填充量"],
        6: ["CO2灭火器填充总量", "核算期内员工总工时"],
        7: ["废水处理方式", "废水处理量", "目标产品产线废水", "COD浓度",
            "污水处理药剂1", "污水处理药剂2", "污水处理药剂3", "废气处理方式",
            "危废委外焚烧总量", "危废委外焚烧目标产品产线分解", "危废自行焚烧总量",
            "危废自行焚烧目标产品产线分解", "危废委外资源化总量", "危废委外资源化目标产品产线分解",
            "危废自行资源化总量", "危废自行资源化目标产品产线分解", "烟气处理药剂1",
            "烟气处理药剂2", "烟气处理药剂3", "烟气处理药剂4"],
        8: ["PCF核算目标产品生产工艺流程图", "PCF核算目标产品生产工艺流程文字描述",
            "原材料1名称", "原材料1使用量", "原材料2名称", "原材料2使用量",
            "原材料3名称", "原材料3使用量", "原材料4名称", "原材料4使用量",
            "原材料5名称", "原材料5使用量", "原材料6名称", "原材料6使用量",
            "原材料7名称", "原材料7使用量", "原材料8名称", "原材料8使用量",
            "原材料9名称", "原材料9使用量", "原材料10名称", "原材料10使用量",
            "供应商A", "供应商B", "供应商C", "供应商D", "供应商E", "供应商F",
            "供应商G", "供应商H", "供应商I", "供应商J", "供应商K", "供应商L"],
        9: ["新鲜水统计口径", "新鲜水使用量", "新鲜水单位", "氮气统计口径", "氮气使用量", "氮气单位"]
    }

    @classmethod
    def is_valid_field(cls, section: int, field: str) -> bool:
        """检查字段是否有效"""
        if section not in cls.VALID_FIELDS:
            return False
        return field in cls.VALID_FIELDS[section]

    @classmethod
    def get_valid_fields(cls, section: int) -> List[str]:
        """获取某部分的所有有效字段"""
        return cls.VALID_FIELDS.get(section, [])

    @classmethod
    def validate_field_value(cls, section: int, field: str, value: Any) -> Dict[str, Any]:
        """验证字段值"""
        if not cls.is_valid_field(section, field):
            return {"valid": False, "error": f"字段 '{field}' 不存在于第{section}部分"}

        # 这里可以添加更多验证逻辑
        # 例如检查下拉选项的值是否在允许列表中

        return {"valid": True}
