"""
文件提取Agent - 碳管师收资系统
负责从用户上传的各类文件中提取对应部分的数据
支持格式: xlsx, xls, pdf, docx, doc, pptx, md
每个Section使用专精的LLM提示词进行数据提取
"""

import uuid
import os
import base64
from datetime import datetime
from typing import Dict, Any, Optional, List
from io import BytesIO

import openpyxl
import docx
import pptx
import pdfplumber
from PIL import Image

from tantan.backend.utils import get_logger
from tantan.backend.rag import get_llm_client
from tantan.backend.agents.pdf_splitter import PDFSplitter

logger = get_logger(__name__)


# ============== 通用文本提取器 ==============

class TextExtractor:
    """从各类文件提取原始文本"""
    _pdf_splitter = PDFSplitter(page_split_threshold=5)

    @staticmethod
    def extract_from_bytes(file_content: bytes, filename: str) -> str:
        """根据文件扩展名调用对应提取器"""
        _, ext = os.path.splitext(filename or '')
        ext = ext.lower()

        extractors = {
            '.xlsx': TextExtractor._extract_xlsx,
            '.xls': TextExtractor._extract_xls,
            '.pdf': TextExtractor._extract_pdf,
            '.docx': TextExtractor._extract_docx,
            '.doc': TextExtractor._extract_doc,
            '.pptx': TextExtractor._extract_pptx,
            '.md': TextExtractor._extract_md,
            '.png': TextExtractor._extract_image,
            '.jpg': TextExtractor._extract_image,
            '.jpeg': TextExtractor._extract_image,
        }

        extractor = extractors.get(ext)
        if not extractor:
            raise ValueError(f"不支持的文件类型: {ext}")

        return extractor(file_content)

    @staticmethod
    def _extract_xlsx(file_content: bytes) -> str:
        """从 xlsx 提取文本"""
        try:
            wb = openpyxl.load_workbook(BytesIO(file_content), data_only=True)
            texts = []
            for sheet in wb.worksheets:
                texts.append(f"[Sheet: {sheet.title}]")
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value is not None:
                            texts.append(str(cell.value))
            return "\n".join(texts)
        except Exception as e:
            logger.error(f"xlsx 提取失败: {e}")
            return ""

    @staticmethod
    def _extract_xls(file_content: bytes) -> str:
        """从 xls 提取文本（复用 xlsx 逻辑）"""
        return TextExtractor._extract_xlsx(file_content)

    @staticmethod
    def _extract_pdf(file_content: bytes) -> str:
        """从 pdf 提取文本（支持分页分割）"""
        try:
            segments = TextExtractor._pdf_splitter.split(file_content)
            return "\n\n".join(segments)
        except Exception as e:
            logger.error(f"pdf 提取失败: {e}")
            return ""

    @staticmethod
    def _extract_docx(file_content: bytes) -> str:
        """从 docx 提取文本"""
        try:
            doc = docx.Document(BytesIO(file_content))
            texts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    texts.append(para.text)
            # 提取表格
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        texts.append(" | ".join(row_text))
            return "\n".join(texts)
        except Exception as e:
            logger.error(f"docx 提取失败: {e}")
            return ""

    @staticmethod
    def _extract_doc(file_content: bytes) -> str:
        """从 doc 提取文本（尝试直接读取二进制）"""
        # python-docx 不支持 .doc，但可以直接读二进制文本
        try:
            text = file_content.decode("utf-8", errors="ignore")
            # 简单过滤不可见字符
            import re
            text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)
            return text
        except Exception as e:
            logger.error(f"doc 提取失败: {e}")
            return ""

    @staticmethod
    def _extract_pptx(file_content: bytes) -> str:
        """从 pptx 提取文本"""
        try:
            prs = pptx.Presentation(BytesIO(file_content))
            texts = []
            for i, slide in enumerate(prs.slides):
                texts.append(f"[Slide {i+1}]")
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        texts.append(shape.text)
            return "\n".join(texts)
        except Exception as e:
            logger.error(f"pptx 提取失败: {e}")
            return ""

    @staticmethod
    def _extract_md(file_content: bytes) -> str:
        """从 markdown 提取文本"""
        try:
            return file_content.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"md 提取失败: {e}")
            return ""

    @staticmethod
    def _extract_image(file_content: bytes) -> str:
        """从图片提取文本：返回base64编码供LLM处理"""
        try:
            image = Image.open(BytesIO(file_content))
            width, height = image.size

            # 检测图片尺寸，过小的图片可能是截图或图标
            if width < 300 or height < 300:
                return "[图片尺寸过小，跳过]"

            # 将图片内容转为base64供多模态LLM使用
            b64_content = base64.b64encode(file_content).decode('utf-8')

            # 判断图片格式
            img_format = image.format.lower() if hasattr(image, 'format') else 'jpeg'
            mime_type = f"image/{img_format}" if img_format != 'jpeg' else "image/jpeg"

            return f"[IMAGE_DATA]{b64_content}[/IMAGE_DATA] mime:{mime_type} size:{width}x{height}"
        except Exception as e:
            logger.error(f"图片 提取失败: {e}")
            return ""


# ============== Section 专精提示词 ==============

SECTION_PROMPTS = {
    1: """你是一个碳排放数据填写助手，专门从文档中提取【基本信息】部分的数据。

需要提取的字段：
- 企业名称
- 所属行业
- 联系人
- 联系方式
- 生产地址
- 核算年份
- 核算周期说明（如开始日期、结束日期）

请从提供的原始文本中提取上述字段，以JSON格式返回。字段名为key，值为字符串，如果某字段不存在则返回null。
只返回JSON，不要有其他解释。""",

    2: """你是一个碳排放数据填写助手，专门从文档中提取【产品】部分的数据。

需要提取的字段：
- PCF核算目标产品名称
- 是否为生产工厂唯一产品
- 其他产品1-5 名称
- 其他产品超过5种的说明
- 计量单位
- 目标产品产线内是否有副产品
- 副产品1-5 名称
- 副产品超过5种的说明

请从提供的原始文本中提取上述字段，以JSON格式返回。只返回JSON。""",

    3: """你是一个碳排放数据填写助手，专门从文档中提取【燃料使用】部分的数据。

需要提取的字段：
- 生产用锅炉燃料（类型和用量）
- 专用废气焚烧炉燃料
- 危废焚烧炉燃料
- 发电机燃料
- 食堂炉灶燃料
- 厂内转运叉车燃料
- 自有商务车92#/95#/98#燃料
- 自有道路车辆燃料-柴油
- 切割、焊接燃料

请从提供的原始文本中提取上述字段，以JSON格式返回。只返回JSON。""",

    4: """你是一个碳排放数据填写助手，专门从文档中提取【电力、热力使用】部分的数据。

需要提取的字段：
- 全厂用电/生产用电/行政办公用电/目标产品产线用电/单耗用电（统计情况）
- 光伏发电量
- 光伏发电配置
- 是否购买绿证
- 是否购买排放权益
- 蒸汽温度/蒸汽压力
- 全厂用蒸汽/生产用蒸汽/行政类用蒸汽/目标产品产线用蒸汽/单耗用蒸汽

请从提供的原始文本中提取上述字段，以JSON格式返回。只返回JSON。""",

    5: """你是一个碳排放数据填写助手，专门从文档中提取【制冷剂使用】部分的数据。

需要提取的字段：
- 空调制冷剂1-5：标号、填充量(kg)
- 冷冻机制冷剂1-5：标号、填充量(kg)

请从提供的原始文本中提取上述字段，以JSON格式返回，格式如：
{"空调制冷剂1标号": "R410A", "空调制冷剂1填充量": "10.5", ...}
只返回JSON。""",

    6: """你是一个碳排放数据填写助手，专门从文档中提取【其他散逸类排放】部分的数据。

需要提取的字段：
- CO2灭火器填充总量(kg)
- 核算期内员工总工时(h)

请从提供的原始文本中提取上述字段，以JSON格式返回。只返回JSON。""",

    7: """你是一个碳排放数据填写助手，专门从文档中提取【三废处理】部分的数据。

需要提取的字段：
- 废水处理方式
- 废水处理量
- 目标产品产线废水
- COD浓度
- 污水处理药剂1-3
- 废气处理方式
- 危废委外焚烧/自行焚烧/委外资源化/自行资源化：总量、目标产品产线分解
- 烟气处理药剂1-4

请从提供的原始文本中提取上述字段，以JSON格式返回。只返回JSON。""",

    8: """你是一个碳排放数据填写助手，专门从文档中提取【原材料使用】部分的数据。

需要提取的字段：
- PCF核算目标产品生产工艺流程文字描述
- 原材料1-10：名称、使用量
- 供应商A-L 信息

【重要-工艺流程图识别规则】
1. 用户可能上传了工艺流程图，请仔细识别
2. 只有当图片明确展示生产工艺流程时（如有箭头指示的工艺步骤、明确的工序名称）才描述
3. 工艺流程图特征：
   - 有箭头连接各个工序
   - 有明确的工艺步骤名称（如"原料准备"、"混合"、"成型"、"烧结"等）
   - 通常有多个步骤框和连接线
4. 非工艺流程图示例（请明确识别）：
   - 设备照片（如窑炉外观、设备铭牌）
   - 工厂外景图、车间场景照
   - 组织架构图
   - 简单的示意草图（非工艺流程）
5. 如果没有找到工艺流程图，请明确返回 "工艺流程图": null
6. 宁可返回null也不要错误描述

【重要-宁可空不要错】
当不确定图片是否为工艺流程图时，回复null而非错误描述。

请从提供的原始文本和图片中提取上述字段，以JSON格式返回。只返回JSON。""",

    9: """你是一个碳排放数据填写助手，专门从文档中提取【生产耗材】部分的数据。

需要提取的字段：
- 新鲜水：统计口径、使用量、单位
- 氮气：统计口径、使用量、单位

请从提供的原始文本中提取上述字段，以JSON格式返回。只返回JSON。""",
}


class LLMExtractor:
    """使用 LLM 从文本中提取结构化数据"""

    def __init__(self, section: int):
        self.section = section
        self.prompt = SECTION_PROMPTS.get(section, "")

    def extract(self, raw_text: str) -> Dict[str, Any]:
        """调用 LLM 提取数据"""
        if not raw_text.strip():
            return {}

        try:
            llm_client = get_llm_client()

            # 检查是否包含图片数据
            if "[IMAGE_DATA]" in raw_text:
                # 构建多模态消息
                messages = self._build_multimodal_message(raw_text)
                result = llm_client.chat(messages)
            else:
                # 纯文本消息
                messages = [
                    {"role": "system", "content": self.prompt},
                    {"role": "user", "content": f"原始文本：\n{raw_text[:8000]}"}
                ]
                result = llm_client.chat(messages)

            if isinstance(result, dict) and result.get("content"):
                answer = result["content"]
                # 尝试解析 JSON
                return self._parse_json(answer)
        except Exception as e:
            logger.error(f"LLM提取失败 section={self.section}: {e}")

        return {}

    def _build_multimodal_message(self, raw_text: str) -> List[Dict[str, Any]]:
        """构建多模态消息，处理图片和文本混合内容"""
        import re
        messages = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": []}
        ]

        # 分割文本和图片数据
        parts = re.split(r'\[IMAGE_DATA\](.*?)\[/IMAGE_DATA\]', raw_text, flags=re.DOTALL)

        content = messages[1]["content"]

        for i, part in enumerate(parts):
            if i % 2 == 1:
                # 这是图片数据
                b64_data = part.split(" dimensions:")[0]
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_data}"
                    }
                })
            elif part.strip() and part.strip() != "dimensions:":
                # 这是普通文本
                content.append({
                    "type": "text",
                    "text": part.strip()
                })

        # 过滤空内容
        messages[1]["content"] = [c for c in content if isinstance(c, dict) and (c.get("text") or c.get("image_url"))]

        return messages

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """从 LLM 输出中解析 JSON"""
        import re
        import json
        # 找 JSON 块
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return {}
class BaseExtractor:
    """文件提取Agent基类"""

    def __init__(self, section: int):
        self.section = section
        self.section_ranges = {
            1: (2, 9),    # 基本信息
            2: (10, 27),  # 产品
            3: (28, 41),  # 燃料使用
            4: (42, 59),  # 电力、热力使用
            5: (60, 72),  # 制冷剂使用
            6: (73, 76),  # 其他散逸类排放
            7: (77, 102), # 三废处理
            8: (103, 129),# 原材料使用
            9: (130, 133),# 生产耗材
        }

    def parse_excel(self, file_content: bytes) -> Optional[openpyxl.worksheet.worksheet.Worksheet]:
        """解析Excel文件，返回数据收集表工作表"""
        try:
            wb = openpyxl.load_workbook(BytesIO(file_content))
            ws = wb["数据收集表"]
            return ws
        except Exception as e:
            logger.error(f"Excel解析错误: section={self.section}, error: {str(e)}", exc_info=True)
            return None

    def extract_section_data(self, worksheet, section: int) -> Dict[str, Any]:
        """从工作表中提取指定部分的数据"""
        if section not in self.section_ranges:
            return {}

        start_row, end_row = self.section_ranges[section]
        data = {}

        for row in range(start_row, end_row + 1):
            cell_a = worksheet.cell(row=row, column=1).value
            cell_b = worksheet.cell(row=row, column=2).value

            if cell_a:
                field_name = str(cell_a).strip()
                data[field_name] = cell_b

        return data

    def process_file(self, file_content: bytes) -> Dict[str, Any]:
        """处理文件并提取数据"""
        worksheet = self.parse_excel(file_content)
        if not worksheet:
            return {"error": "无法解析Excel文件"}

        extracted_data = self.extract_section_data(worksheet, self.section)
        validated_data = self.validate_data(extracted_data)

        return {
            "msg_id": str(uuid.uuid4()),
            "section": self.section,
            "data": validated_data,
            "timestamp": datetime.now().isoformat(),
            "status": "completed" if validated_data else "failed"
        }

    def validate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """验证和清理数据"""
        validated = {}
        for key, value in data.items():
            if value is not None and str(value).strip():
                validated[key] = str(value).strip()
        return validated


class FileExtractAgent:
    """文件提取Agent - 支持多格式文件 + LLM专精提取"""

    def __init__(self, section: int):
        self.section = section
        self.llm_extractor = LLMExtractor(section)

    def process(self, file_content: bytes, filename: str = "unknown") -> Dict[str, Any]:
        """处理文件提取：通用文本提取 + LLM专精字段提取"""
        # 1. 从任意格式提取原始文本
        try:
            raw_text = TextExtractor.extract_from_bytes(file_content, filename)
        except ValueError as e:
            return {
                "msg_id": str(uuid.uuid4()),
                "section": self.section,
                "data": {},
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "status": "failed"
            }

        if not raw_text.strip():
            return {
                "msg_id": str(uuid.uuid4()),
                "section": self.section,
                "data": {},
                "error": "未能从文件中提取到文本内容",
                "timestamp": datetime.now().isoformat(),
                "status": "failed"
            }

        # 2. 用专精LLM提取结构化数据
        extracted_data = self.llm_extractor.extract(raw_text)

        return {
            "msg_id": str(uuid.uuid4()),
            "section": self.section,
            "data": extracted_data,
            "timestamp": datetime.now().isoformat(),
            "status": "completed" if extracted_data else "partial"
        }


class ExtractorsFactory:
    """提取器工厂 - 为每个部分创建对应的提取器"""

    @staticmethod
    def get_extractor(section: int) -> FileExtractAgent:
        """获取指定部分的提取器"""
        return FileExtractAgent(section)

    @staticmethod
    def get_all_extractors() -> Dict[int, FileExtractAgent]:
        """获取所有9个部分的提取器"""
        return {i: FileExtractAgent(i) for i in range(1, 10)}


def extract_section_1(worksheet) -> Dict[str, Any]:
    """提取基本信息部分"""
    data = {}
    # 企业名称
    data["企业名称"] = worksheet.cell(row=3, column=2).value
    # 所属行业
    data["所属行业"] = worksheet.cell(row=4, column=2).value
    # 联系人
    data["联系人"] = worksheet.cell(row=5, column=2).value
    # 联系方式
    data["联系方式"] = worksheet.cell(row=6, column=2).value
    # 生产地址
    data["生产地址"] = worksheet.cell(row=7, column=2).value
    # 核算年份
    data["核算年份"] = worksheet.cell(row=8, column=2).value
    # 核算周期说明
    data["核算周期说明"] = worksheet.cell(row=9, column=2).value
    return data


def extract_section_2(worksheet) -> Dict[str, Any]:
    """提取产品部分"""
    data = {}
    # PCF核算目标产品名称
    data["PCF核算目标产品名称"] = worksheet.cell(row=12, column=2).value
    # 是否为生产工厂唯一产品
    data["是否为生产工厂唯一产品"] = worksheet.cell(row=13, column=2).value
    # 其他产品1-5
    for i in range(1, 6):
        data[f"其他产品{i}名称"] = worksheet.cell(row=13 + i, column=2).value
    # 其他产品超过5种的说明
    data["其他产品超过5种的说明"] = worksheet.cell(row=19, column=2).value
    # 计量单位
    data["计量单位"] = worksheet.cell(row=20, column=2).value
    # 目标产品产线内是否有副产品
    data["目标产品产线内是否有副产品"] = worksheet.cell(row=21, column=2).value
    # 副产品1-5
    for i in range(1, 6):
        data[f"副产品{i}名称"] = worksheet.cell(row=21 + i, column=2).value
    # 副产品超过5种的说明
    data["副产品超过5种的说明"] = worksheet.cell(row=27, column=2).value
    return data


def extract_section_3(worksheet) -> Dict[str, Any]:
    """提取燃料使用部分"""
    data = {}
    # 燃烧设备/燃料类型
    fuel_types = ["生产用锅炉燃料", "专用废气焚烧炉燃料", "危废焚烧炉燃料", "发电机燃料", "食堂炉灶燃料"]
    for idx, fuel_type in enumerate(fuel_types):
        data[fuel_type] = worksheet.cell(row=30 + idx, column=2).value

    # 车辆燃料
    vehicle_types = ["厂内转运叉车燃料", "自有商务车92#", "自有商务车95#", "自有商务车98#", "自有道路车辆燃料-柴油"]
    for idx, vehicle_type in enumerate(vehicle_types):
        data[vehicle_type] = worksheet.cell(row=36 + idx, column=2).value

    # 切割、焊接燃料
    data["切割、焊接燃料"] = worksheet.cell(row=41, column=2).value
    return data


def extract_section_4(worksheet) -> Dict[str, Any]:
    """提取电力、热力使用部分"""
    data = {}
    # 用电/热单元 - 可统计情况
    stat_types = ["全厂用电", "生产用电", "行政办公用电", "目标产品产线用电", "单耗用电"]
    for idx, stat_type in enumerate(stat_types):
        data[stat_type] = worksheet.cell(row=44 + idx, column=2).value

    # 光伏发电量
    data["光伏发电量"] = worksheet.cell(row=49, column=2).value
    data["光伏发电配置"] = worksheet.cell(row=50, column=2).value

    # 绿证购买
    data["是否购买绿证"] = worksheet.cell(row=51, column=2).value

    # 排放权益
    data["是否购买排放权益"] = worksheet.cell(row=52, column=2).value

    # 蒸汽参数
    data["蒸汽温度"] = worksheet.cell(row=54, column=2).value
    data["蒸汽压力"] = worksheet.cell(row=55, column=2).value

    # 用蒸汽统计
    steam_types = ["全厂用蒸汽", "生产用蒸汽", "行政类用蒸汽", "目标产品产线用蒸汽", "单耗用蒸汽"]
    for idx, steam_type in enumerate(steam_types):
        data[steam_type] = worksheet.cell(row=55 + idx, column=2).value
    return data


def extract_section_5(worksheet) -> Dict[str, Any]:
    """提取制冷剂使用部分"""
    data = {}
    # 空调制冷剂1-5
    for i in range(1, 6):
        data[f"空调制冷剂{i}标号"] = worksheet.cell(row=61 + i, column=2).value
        data[f"空调制冷剂{i}填充量"] = worksheet.cell(row=61 + i, column=4).value

    # 冷冻机制冷剂1-5
    for i in range(1, 6):
        data[f"冷冻机制冷剂{i}标号"] = worksheet.cell(row=67 + i, column=2).value
        data[f"冷冻机制冷剂{i}填充量"] = worksheet.cell(row=67 + i, column=4).value
    return data


def extract_section_6(worksheet) -> Dict[str, Any]:
    """提取其他散逸类排放部分"""
    data = {}
    # CO2灭火器
    data["CO2灭火器填充总量"] = worksheet.cell(row=75, column=2).value
    # 员工总工时
    data["核算期内员工总工时"] = worksheet.cell(row=76, column=2).value
    return data


def extract_section_7(worksheet) -> Dict[str, Any]:
    """提取三废处理部分"""
    data = {}
    # 废水处理方式
    data["废水处理方式"] = worksheet.cell(row=78, column=2).value
    # 废水处理量
    data["废水处理量"] = worksheet.cell(row=79, column=2).value
    # 目标产品产线废水
    data["目标产品产线废水"] = worksheet.cell(row=80, column=2).value
    # COD浓度
    data["COD浓度"] = worksheet.cell(row=81, column=2).value

    # 污水处理药剂
    for i in range(1, 4):
        data[f"污水处理药剂{i}"] = worksheet.cell(row=83 + i, column=2).value

    # 废气处理方式
    data["废气处理方式"] = worksheet.cell(row=86, column=2).value

    # 危废处理量
    waste_types = ["危废委外焚烧", "危废自行焚烧", "危废委外资源化", "危废自行资源化"]
    for idx, waste_type in enumerate(waste_types):
        data[f"{waste_type}总量"] = worksheet.cell(row=87 + idx, column=2).value
        data[f"{waste_type}目标产品产线分解"] = worksheet.cell(row=87 + idx, column=4).value

    # 烟气处理药剂
    for i in range(1, 5):
        data[f"烟气处理药剂{i}"] = worksheet.cell(row=94 + i, column=2).value
    return data


def extract_section_8(worksheet) -> Dict[str, Any]:
    """提取原材料使用部分"""
    data = {}
    # 生产工艺流程图
    data["PCF核算目标产品生产工艺流程图"] = worksheet.cell(row=104, column=2).value
    # 生产工艺流程文字描述
    data["PCF核算目标产品生产工艺流程文字描述"] = worksheet.cell(row=105, column=2).value

    # 原材料
    for i in range(1, 11):
        data[f"原材料{i}名称"] = worksheet.cell(row=106 + i, column=2).value
        data[f"原材料{i}使用量"] = worksheet.cell(row=106 + i, column=3).value

    # 供应商A-L
    supplier_cols = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
    for idx, supplier in enumerate(supplier_cols):
        data[f"供应商{supplier}"] = worksheet.cell(row=117 + idx, column=2).value
    return data


def extract_section_9(worksheet) -> Dict[str, Any]:
    """提取生产耗材部分"""
    data = {}
    # 新鲜水
    data["新鲜水统计口径"] = worksheet.cell(row=132, column=2).value
    data["新鲜水使用量"] = worksheet.cell(row=132, column=3).value
    data["新鲜水单位"] = worksheet.cell(row=132, column=4).value

    # 氮气
    data["氮气统计口径"] = worksheet.cell(row=133, column=2).value
    data["氮气使用量"] = worksheet.cell(row=133, column=3).value
    data["氮气单位"] = worksheet.cell(row=133, column=4).value
    return data
