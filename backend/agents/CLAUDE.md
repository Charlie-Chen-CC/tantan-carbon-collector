# Agents - AI Agent模块

基于LangChain/LangGraph的AI Agent实现，用于碳排放数据收集和表单处理。

## Agent类型

### OrchestratorAgent
编排Agent，负责协调整个表单填报流程。
- 使用LangGraph `StateGraph` 管理工作流
- 支持条件路由根据意图分发到不同Agent
- 使用 `MemorySaver` 检查点持久化状态

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

### QAAgent
问答Agent，处理用户专业问题和填报指导。
- 意图识别：专业问题/填报指导/闲聊
- 支持RAG知识库检索
- 基于规则的降级回答

### ModifyAgent
修改验证Agent，处理用户对已填数据的修改请求。
- 验证修改合法性
- 生成修改建议
- 记录修改历史

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