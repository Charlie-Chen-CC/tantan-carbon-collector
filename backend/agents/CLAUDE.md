# Agents - AI Agent模块

基于LangChain/LangGraph的AI Agent实现，用于碳排放数据收集和表单处理。

## Agent类型

### FileExtractAgent
文件提取Agent，从上传的各类文件中提取结构化数据。
- 支持格式: xlsx, xls, pdf, docx, doc, pptx, md, png, jpg, jpeg
- 通用文本提取 + LLM Section专精提取架构
- 每个Section(1-9)使用专门设计的LLM提示词
- 返回提取状态和错误信息

### FormFillAgent
表单填充Agent，将提取的数据填充到表单字段。
- 字段映射和格式转换
- 验证必填项
- 返回填充结果和错误列表
- **关键**：维护 `BACKEND_TO_FRONTEND_FIELD_MAP` 映射表，将中文后端字段名转换为前端英文字段名
- 代码结构（Phase 2.5 拆模块）：
  - `agents/form_filler/__init__.py` - 重导出 `FormFillAgent` / `FieldGuide` / `FIELD_GUIDES` / `get_field_guide`
  - `agents/form_filler/agent.py` - `FormFillAgent` 主类 + `fill_form` 方法（~150 行）
  - `agents/form_filler/mapping.py` - `BACKEND_TO_FRONTEND_FIELD_MAP`（~160 行；Section 9 重复键已合并）
  - `agents/form_filler/transformers.py` - `MULTI_ROW_TRANSFORMERS` / `NESTED_FIELD_TRANSFORMERS`（~140 行）
  - `agents/form_filler/section_defs.py` - `FormSection` + `get_section_definitions`（~170 行）
  - `agents/form_filler/guides.py` - `FieldGuide` + `FIELD_GUIDES` + `get_field_guide`（~300 行，被 8+ 测试引用）

### QAAgent
问答Agent，处理用户专业问题和填报指导。
- 意图识别：专业问题/填报指导/闲聊
- 支持RAG知识库检索
- 基于规则的降级回答
- **Phase 5.3 真实流式**：`generate_response_stream(message, context) -> Iterator[Dict]`
  - yield 序列：`{"event": "intent", ...}` → `{"event": "message", "chunk": "..."}` (×N) → `{"event": "done", "full_content": "..."}`
  - LLM 流式：`_stream_llm_chat` 直接调 `AliLLMClient.chat(stream=True)`，逐 token yield
  - 规则回答：一次性 yield 整段内容
  - RAG 流式：调 `RAGPipeline.answer_stream()`

### ModifyAgent
修改验证Agent，处理用户对已填数据的修改请求。
- 验证修改合法性
- 生成修改建议
- 每次调用 `process_modify_request` 返回 `modify_record` 详情（不持久化历史；调用方用响应即可）

## 状态类型

```python
class FormAgentState(TypedDict):
    messages: Annotated[list, "append"]  # 对话历史
    current_section: int                 # 当前部分(1-9)
    extracted_data: dict                 # 提取的数据
    fill_result: dict                    # 填充结果
    validation_errors: list               # 验证错误
```

## 文件提取架构

### TextExtractor 通用文本提取
- xlsx/xls: openpyxl 遍历所有sheet
- pdf: pdfplumber 按页提取文本
- docx: python-docx 提取段落+表格
- doc: 直接读二进制文本
- pptx: python-pptx 提取slide文本
- md: 直接读取utf-8文本
- png/jpg/jpeg: PIL读取图片，返回base64编码供多模态LLM处理

### LLMExtractor Section专精提取
- 9个Section各有一套专精提示词
- 从原始文本中用LLM提取对应字段
- 支持多模态（图片+文本混合输入）
- 返回结构化JSON

### 处理流程
原始文件 → TextExtractor → 原始文本 → LLMExtractor(Section专精提示词) → 结构化JSON

## 提示词优化

每个Section的LLM提示词都包含：
1. **业务背景说明**：解释碳排放核算相关概念
2. **数据来源指引**：告诉AI从哪些文档类型提取
3. **格式说明**：明确取值范围和单位要求
4. **字段优先级**：区分必填和可选字段

提示词位于 `tantan/backend/agents/file_extractor.py` 的 `SECTION_PROMPTS` 字典中。

**重要约束：提示词中不得包含硬编码的选项值**。提示词应指导AI理解业务背景和字段含义，但不应限制具体的选项值，以确保对不同格式的文件都能正确提取数据。

### 提示词反硬编码规范（Phase 6.1）

提示词中**禁止**出现的硬编码模式：
- ❌ 枚举类选项写死：`"取值范围: 钢铁/水泥/化工"` → 不同企业可能有 "玻璃纤维/复合材料" 等
- ❌ 数值类阈值写死：`"年综合能耗 > 5000 吨标准煤需要填报"` → 政策可能变
- ❌ 字段名写死在提示词：`"提取 `企业名称` 字段"` → 应引导 LLM 参照 `section_defs` 的字段 schema 自适应
- ❌ 引用具体行业标准编号：`"按 GB/T 2589-2020 计算"` → 标准号会变

正确做法：
- ✅ 引导 LLM 理解业务背景：`"请识别企业所属的国民经济行业分类（GB/T 4754 现行版本）"`
- ✅ 提示参考 `section_defs.schema` 自行推断字段含义与取值范围
- ✅ 把硬编码的选项值（行业、能耗阈值、燃料类型等）放到 `section_options.py`（Phase 6.1 临时 SSOT）→ 未来 Phase 6.2 迁到 `shared/field_schema.json`，由 `scripts/codegen_field_schema.py` codegen 注入 SECTION_PROMPTS
- ✅ SECTION_PROMPTS 通过 `_build_section_prompts()` 函数构建，所有选项列表引用 `section_options` 常量
- ✅ 提示词里出现选项时**必须**加"（**不**是穷举）"或"参考值"修饰语，让 LLM 知道可以识别未列出的合理值

**当前 SSOT 路径**（迁移中）：
- Phase 6.1：`agents/section_options.py`（Python 常量，f-string 注入）
- Phase 6.2：`shared/field_schema.json` + `scripts/codegen_field_schema.py`（JSON SSOT + codegen）

新增硬编码列表：先在 `section_options.py` 加常量，再在 `_build_section_prompts` 引用；后续 Phase 6.2 统一迁到 JSON。

## 字段映射

`FormFillAgent` 维护 `BACKEND_TO_FRONTEND_FIELD_MAP` 映射表，将中文后端字段名转换为前端英文字段名：

```python
class FormFillAgent:
    BACKEND_TO_FRONTEND_FIELD_MAP = {
        "企业名称": "enterpriseName",
        "所属行业": "industry",
        "PCF核算目标产品名称": "targetProductName",
        # ... 共 107 个映射
    }
```

**字段映射 SSOT（Phase 6.2-6.3）**：
- SSOT 位置：`tantan/shared/field_schema.json`（9 sections，107 字段）
- 自动生成：`tantan/backend/agents/form_filler/{mapping,section_defs,transformers}.py` + `tantan/frontend/config/sectionConfig.ts`
- codegen 入口：`python -m tantan.backend.scripts.codegen_field_schema [--check]`
- CI 校验：`codegen --check` 失败时 exit 1
- 头部注释都带 "⚠️ 此文件由 codegen 自动生成"，**不要手动编辑**

**添加新字段时**：
1. 改 `tantan/shared/field_schema.json`（加到对应 section 的 `fields` 数组）
2. 跑 `python -m tantan.backend.scripts.codegen_field_schema`
3. 跑 `python -m pytest tantan/backend/tests/backend/test_codegen_field_schema.py` 验证
4. 提交 JSON + 自动生成文件（一起 commit）

## 多行动态字段转换

`FormFillAgent` 使用 `MULTI_ROW_TRANSFORMERS`（位于 `agents/form_filler/transformers.py`）将LLM提取的平展数据转换为前端期望的嵌套数组格式：

```python
MULTI_ROW_TRANSFORMERS = {
    "生产用锅炉燃料": {
        "frontend_key": "boilerFuel",
        "sub_fields": {"fuelType": "燃料类型", "amount": "使用量", "unit": "单位"}
    },
    "空调制冷剂": {
        "frontend_key": "airConditioners",
        "sub_fields": {"equipmentName": "设备名称", "refrigerantNo": "标号", "fillAmount": "填充量"},
        "is_array": True
    },
    "原材料": {
        "frontend_key": "rawMaterials",
        "sub_fields": {"name": "名称", "spec": "规格", "amount": "使用量", "unit": "单位"},
        "is_array": True, "numeric_suffix": True
    },
}
```

转换逻辑：
- 如果LLM返回数组（如 `[{名称: "硫酸", 使用量: "100"}]`），自动映射中文key到英文key
- 如果LLM返回平铺字段（如 `原材料1名称`, `原材料1使用量`），则按编号聚合为数组