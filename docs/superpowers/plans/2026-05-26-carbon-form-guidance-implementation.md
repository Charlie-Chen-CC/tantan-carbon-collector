# 碳排放表单填报引导系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现字段级引导、Section级引导、前置数据校验、多Section文件提取四个功能，提升用户填报体验和数据质量

**Architecture:**
- 后端：在 `form_filler.py` 中扩展字段引导配置，新建 `form_validator.py` 处理校验逻辑，扩展 `file_extractor.py` 支持多Section提取
- 前端：在 `sectionConfig.ts` 中添加字段引导配置，新增 `FieldGuide` 组件集成到表单，新建 `ValidationFeedback` 和 `ExtractionResultPanel` 组件

**Tech Stack:** FastAPI, SQLAlchemy, React/Next.js, TypeScript, Ant Design

---

## 文件结构

```
tantan/
├── backend/
│   ├── agents/
│   │   ├── form_filler.py          # 扩展：添加字段引导配置
│   │   ├── file_extractor.py       # 扩展：支持多Section提取
│   │   └── form_validator.py       # 新建：校验规则引擎
├── frontend/
│   ├── app/
│   │   ├── dashboard/
│   │   │   └── page.tsx            # 扩展：集成字段引导和校验
│   │   └── components/
│   │       ├── FieldGuide.tsx      # 新建：字段引导组件
│   │       ├── ValidationFeedback.tsx  # 新建：校验反馈组件
│   │       └── ExtractionResultPanel.tsx # 新建：提取结果面板
│   └── config/
│       └── sectionConfig.ts        # 扩展：添加字段引导配置
└── docs/superpowers/specs/
    └── 2026-05-26-carbon-form-guidance-design.md  # 设计文档
```

---

## Task 1: 字段级引导 - 后端配置扩展

**Files:**
- Modify: `tantan/backend/agents/form_filler.py`

- [ ] **Step 1: 阅读现有 section_definitions 结构**

Run: `head -100 tantan/backend/agents/form_filler.py`
目标：理解 `FormSection` 和 `FormField` 的定义

- [ ] **Step 2: 添加字段引导配置结构**

在 `form_filler.py` 末尾添加：

```python
@dataclass
class FieldGuide:
    description: str
    data_sources: list[str]
    common_issues: list[str] | None = None
    unit: str | None = None

# 字段引导配置：section_key -> field_key -> FieldGuide
FIELD_GUIDES: dict[int, dict[str, FieldGuide]] = {
    1: {
        "enterpriseName": FieldGuide(
            description="企业全称，应与营业执照一致",
            data_sources=["营业执照", "企业官网"],
            unit=None
        ),
        "industry": FieldGuide(
            description="企业所属国民经济行业分类",
            data_sources=["营业执照经营范围"],
            common_issues=["请选择最接近的行业类别"]
        ),
        # ... 根据实际字段补充
    },
    3: {
        "fuelType": FieldGuide(
            description="燃料类型",
            data_sources=["采购发票", "能源台账", "供应商合同"],
            unit=None
        ),
        "fuelConsumption": FieldGuide(
            description="年度燃料消耗量",
            data_sources=["能源台账", "采购发票汇总"],
            unit="吨或万立方米",
            common_issues=["应与发票数量一致，注意单位换算"]
        ),
        # ... 燃料使用 section 字段
    },
    # ... 其他 section 配置
}
```

- [ ] **Step 3: 添加获取字段引导的辅助函数**

```python
def get_field_guide(section: int, field_key: str) -> FieldGuide | None:
    """获取指定字段的引导配置"""
    return FIELD_GUIDES.get(section, {}).get(field_key)
```

- [ ] **Step 4: 编写测试**

创建 `tantan/backend/tests/test_form_filler.py`：

```python
from tantan.backend.agents.form_filler import get_field_guide, FIELD_GUIDES

def test_get_field_guide_returns_config():
    guide = get_field_guide(1, "enterpriseName")
    assert guide is not None
    assert "企业全称" in guide.description
    assert len(guide.data_sources) > 0

def test_get_field_guide_returns_none_for_unknown():
    guide = get_field_guide(99, "unknown")
    assert guide is None
```

- [ ] **Step 5: 运行测试验证**

Run: `cd /c/Users/25776/Desktop/work/claude_workspace/tantan && source tantan/backend/.venv/Scripts/activate && python -m pytest tantan/backend/tests/test_form_filler.py::test_get_field_guide_returns_config -v`

- [ ] **Step 6: 提交**

```bash
cd tantan
git add backend/agents/form_filler.py backend/tests/test_form_filler.py
git commit -m "feat: add field guide configuration structure"
```

---

## Task 2: 字段级引导 - 前端配置与组件

**Files:**
- Modify: `tantan/frontend/config/sectionConfig.ts`
- Create: `tantan/frontend/app/components/FieldGuide.tsx`

- [ ] **Step 1: 阅读现有 sectionConfig.ts 结构**

Run: `head -150 tantan/frontend/config/sectionConfig.ts`
目标：理解 `FieldDef` 类型定义和 `SECTION_FIELDS` 结构

- [ ] **Step 2: 扩展 FieldDef 类型添加引导字段**

修改 `sectionConfig.ts`：

```typescript
export interface FieldGuide {
  description: string;
  dataSources: string[];
  commonIssues?: string[];
  unit?: string;
}

export interface FieldDef {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  placeholder?: string;
  options?: string[];      // for select
  maxRows?: number;         // for multi-row
  fields?: FieldDef[];      // for multi-row
  guide?: FieldGuide;       // 新增：字段引导
}
```

- [ ] **Step 3: 为 SECTION_FIELDS 添加 guide 配置**

示例：

```typescript
export const SECTION_FIELDS: { [section: number]: FieldDef[] } = {
  1: [
    {
      key: 'enterpriseName',
      label: '企业名称',
      type: 'text',
      guide: {
        description: '请填写与企业营业执照一致的全称',
        dataSources: ['营业执照', '企业官网'],
      }
    },
    // ...
  ],
  // ...
}
```

- [ ] **Step 4: 创建 FieldGuide 组件**

创建 `tantan/frontend/app/components/FieldGuide.tsx`：

```typescript
'use client';

import { Collapse } from 'antd';
import { FieldGuide } from '@/config/sectionConfig';

interface FieldGuideProps {
  guide: FieldGuide;
}

export function FieldGuideComponent({ guide }: FieldGuideProps) {
  const items = [
    {
      key: 'description',
      label: '填写说明',
      children: <p>{guide.description}</p>,
    },
    {
      key: 'sources',
      label: '数据来源',
      children: (
        <ul>
          {guide.dataSources.map((source, i) => (
            <li key={i}>{source}</li>
          ))}
        </ul>
      ),
    },
  ];

  if (guide.commonIssues?.length) {
    items.push({
      key: 'issues',
      label: '常见问题',
      children: (
        <ul>
          {guide.commonIssues.map((issue, i) => (
            <li key={i}>{issue}</li>
          ))}
        </ul>
      ),
    });
  }

  return (
    <div className="field-guide" style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
      <Collapse
        items={items}
        size="small"
        defaultActiveKey={[]}
        ghost
      />
    </div>
  );
}
```

- [ ] **Step 5: 在表单中集成 FieldGuide**

在 `dashboard/page.tsx` 的 MultiRowTable 或表单渲染处，当 field 有 guide 时渲染：

```typescript
{field.guide && <FieldGuideComponent guide={field.guide} />}
```

- [ ] **Step 6: 测试验证**
- 启动前端 `cd tantan/frontend && npm run dev`
- 访问 http://localhost:3000/dashboard
- 检查表单字段下方是否显示引导内容

- [ ] **Step 7: 提交**

```bash
cd tantan
git add frontend/config/sectionConfig.ts frontend/app/components/FieldGuide.tsx frontend/app/dashboard/page.tsx
git commit -m "feat: add FieldGuide component and guide configuration"
```

---

## Task 3: 前置数据校验 - 后端校验引擎

**Files:**
- Create: `tantan/backend/validators/form_validator.py`
- Create: `tantan/backend/tests/test_form_validator.py`

- [ ] **Step 1: 创建校验引擎模块**

创建 `tantan/backend/validators/form_validator.py`：

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ValidationRule:
    field: str
    rule_type: str  # "required" | "min" | "max" | "pattern" | "custom"
    value: Any = None
    message: str = ""

@dataclass
class ValidationError:
    field: str
    message: str
    severity: str = "error"  # "error" | "warning"

class FormValidator:
    def __init__(self, section: int, rules: list[ValidationRule]):
        self.section = section
        self.rules = {r.field: r for r in rules}

    def validate(self, data: dict[str, Any]) -> list[ValidationError]:
        errors = []

        for field, rule in self.rules.items():
            value = data.get(field)

            if rule.rule_type == "required" and not value:
                errors.append(ValidationError(field, rule.message or f"{field} 为必填项"))

            elif rule.rule_type == "min" and value is not None:
                if float(value) < float(rule.value):
                    errors.append(ValidationError(field, rule.message or f"{field} 不能小于 {rule.value}"))

            elif rule.rule_type == "max" and value is not None:
                if float(value) > float(rule.value):
                    errors.append(ValidationError(field, rule.message or f"{field} 不能大于 {rule.value}"))

            elif rule.rule_type == "pattern" and value:
                import re
                if not re.match(rule.value, str(value)):
                    errors.append(ValidationError(field, rule.message or f"{field} 格式不正确"))

        return errors
```

- [ ] **Step 2: 定义各Section校验规则**

在 `form_validator.py` 中添加：

```python
# 各Section校验规则配置
SECTION_VALIDATION_RULES: dict[int, list[ValidationRule]] = {
    1: [
        ValidationRule("enterpriseName", "required", message="企业名称为必填项"),
        ValidationRule("industry", "required", message="所属行业为必填项"),
    ],
    3: [
        ValidationRule("fuelConsumption", "min", 0, message="燃料消耗量不能为负数"),
        ValidationRule("fuelConsumption", "max", 999999999, message="燃料消耗量数值过大，请核实"),
    ],
    # ... 其他section规则
}
```

- [ ] **Step 3: 创建校验API端点**

在 `tantan/backend/api/` 创建或扩展验证相关API。检查现有API结构：

Run: `ls tantan/backend/api/`

- [ ] **Step 4: 编写测试**

创建 `tantan/backend/tests/test_form_validator.py`：

```python
from tantan.backend.validators.form_validator import FormValidator, ValidationRule, ValidationError

def test_required_field_missing():
    rules = [ValidationRule("name", "required", message="名称必填")]
    validator = FormValidator(1, rules)
    errors = validator.validate({})
    assert len(errors) == 1
    assert errors[0].field == "name"

def test_min_value_validation():
    rules = [ValidationRule("amount", "min", 0)]
    validator = FormValidator(1, rules)
    errors = validator.validate({"amount": -5})
    assert len(errors) == 1
    assert "不能小于" in errors[0].message

def test_valid_data_no_errors():
    rules = [ValidationRule("name", "required")]
    validator = FormValidator(1, rules)
    errors = validator.validate({"name": "测试企业"})
    assert len(errors) == 0
```

- [ ] **Step 5: 运行测试验证**

Run: `cd /c/Users/25776/Desktop/work/claude_workspace/tantan && source tantan/backend/.venv/Scripts/activate && python -m pytest tantan/backend/tests/test_form_validator.py -v`

- [ ] **Step 6: 提交**

```bash
cd tantan
git add backend/validators/form_validator.py backend/tests/test_form_validator.py
git commit -m "feat: add form validation engine"
```

---

## Task 4: 前置数据校验 - 前端集成

**Files:**
- Create: `tantan/frontend/app/components/ValidationFeedback.tsx`
- Modify: `tantan/frontend/app/dashboard/page.tsx`

- [ ] **Step 1: 创建 ValidationFeedback 组件**

创建 `tantan/frontend/app/components/ValidationFeedback.tsx`：

```typescript
'use client';

import { Alert, Button } from 'antd';
import { ValidationError } from '@/types/validation';

interface ValidationFeedbackProps {
  errors: ValidationError[];
  onFieldClick?: (field: string) => void;
  onDismiss: () => void;
}

export function ValidationFeedback({ errors, onFieldClick, onDismiss }: ValidationFeedbackProps) {
  if (errors.length === 0) return null;

  const errors_list = errors.filter(e => e.severity === 'error');
  const warnings = errors.filter(e => e.severity === 'warning');

  return (
    <div className="validation-feedback" style={{ marginBottom: 16 }}>
      {errors_list.length > 0 && (
        <Alert
          type="error"
          message={`请修正以下 ${errors_list.length} 个问题`}
          showIcon
          closable
          onClose={onDismiss}
          action={
            <Button size="small" onClick={onDismiss}>忽略</Button>
          }
        >
          {errors_list.map((err, i) => (
            <div key={i}>
              <a onClick={() => onFieldClick?.(err.field)}>{err.field}</a>: {err.message}
            </div>
          ))}
        </Alert>
      )}

      {warnings.length > 0 && (
        <Alert
          type="warning"
          message={`${warnings.length} 个数据可能存在异常`}
          showIcon
          style={{ marginTop: 8 }}
        >
          {warnings.map((warn, i) => (
            <div key={i}>{warn.field}: {warn.message}</div>
          ))}
        </Alert>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 添加 ValidationError 类型**

创建 `tantan/frontend/types/validation.ts`：

```typescript
export interface ValidationError {
  field: string;
  message: string;
  severity: 'error' | 'warning';
}
```

- [ ] **Step 3: 在 Dashboard 集成校验**

在 `dashboard/page.tsx` 中：

```typescript
const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);

// 表单提交前校验
const handleSubmit = async () => {
  const errors = await validateForm(formData);
  if (errors.length > 0) {
    setValidationErrors(errors);
    return;
  }
  // 提交逻辑
};

// 字段点击跳转
const handleFieldClick = (field: string) => {
  // 滚动到对应字段
  document.getElementById(`field-${field}`)?.scrollIntoView({ behavior: 'smooth' });
};
```

- [ ] **Step 4: 测试验证**
- 填写表单，故意留空必填项或输入异常值
- 点击提交，检查是否显示校验错误
- 点击错误信息，检查是否跳转至对应字段

- [ ] **Step 5: 提交**

```bash
cd tantan
git add frontend/app/components/ValidationFeedback.tsx frontend/types/validation.ts frontend/app/dashboard/page.tsx
git commit -m "feat: integrate form validation feedback in dashboard"
```

---

## Task 5: 多Section文件提取

**Files:**
- Modify: `tantan/backend/agents/file_extractor.py`
- Create: `tantan/frontend/app/components/ExtractionResultPanel.tsx`
- Modify: `tantan/frontend/app/dashboard/page.tsx`

- [ ] **Step 1: 阅读现有 file_extractor.py 结构**

Run: `head -200 tantan/backend/agents/file_extractor.py`
目标：理解 `LLMExtractor.extract()` 返回结构和调用方式

- [ ] **Step 2: 扩展提取结果结构**

修改 `LLMExtractor` 返回值，添加置信度和来源信息：

```python
@dataclass
class ExtractedField:
    field_key: str
    value: Any
    confidence: float  # 0-1
    source_cell: str | None = None

@dataclass
class ExtractionResult:
    section: int
    section_name: str
    status: str  # "success" | "partial" | "failed"
    fields: list[ExtractedField]
```

- [ ] **Step 3: 创建多Section提取函数**

在 `file_extractor.py` 中添加：

```python
def extract_all_sections(text: str) -> list[ExtractionResult]:
    """从文本中提取所有可能section的数据"""
    results = []

    for section_num in range(1, 10):
        try:
            result = extract_single_section(text, section_num)
            if result.fields:
                results.append(result)
        except Exception:
            continue

    return results
```

- [ ] **Step 4: 创建 ExtractionResultPanel 组件**

创建 `tantan/frontend/app/components/ExtractionResultPanel.tsx`：

```typescript
'use client';

import { Modal, Table, Tag, Button } from 'antd';
import { ExtractionResult, ExtractedField } from '@/types/extraction';

interface ExtractionResultPanelProps {
  open: boolean;
  results: ExtractionResult[];
  onConfirm: (confirmedData: Record<string, any>) => void;
  onCancel: () => void;
}

export function ExtractionResultPanel({ open, results, onConfirm, onCancel }: ExtractionResultPanelProps) {
  const lowConfidenceFields = (fields: ExtractedField[]) =>
    fields.filter(f => f.confidence < 0.7);

  return (
    <Modal
      title="文件提取结果"
      open={open}
      onCancel={onCancel}
      width={800}
      footer={[
        <Button key="cancel" onClick={onCancel}>取消</Button>,
        <Button key="confirm" type="primary" onClick={onConfirm}>确认填充</Button>
      ]}
    >
      {results.length === 0 ? (
        <p>未识别到任何有效数据</p>
      ) : (
        results.map((result, i) => (
          <div key={i} style={{ marginBottom: 24 }}>
            <h4>【Section {result.section} - {result.section_name}】</h4>
            <Table
              dataSource={result.fields}
              rowKey="fieldKey"
              size="small"
              pagination={false}
              columns={[
                { title: '字段', dataIndex: 'fieldKey' },
                { title: '提取值', dataIndex: 'value' },
                {
                  title: '置信度',
                  dataIndex: 'confidence',
                  render: (c: number) => (
                    <Tag color={c >= 0.7 ? 'green' : 'orange'}>
                      {Math.round(c * 100)}%
                    </Tag>
                  )
                },
                { title: '来源', dataIndex: 'sourceCell' }
              ]}
            />
            {lowConfidenceFields(result.fields).length > 0 && (
              <Alert
                type="warning"
                message={`${lowConfidenceFields(result.fields).length} 个字段置信度较低，请核对`
              />
            )}
          </div>
        ))
      )}
    </Modal>
  );
}
```

- [ ] **Step 5: 在 Dashboard 集成提取结果面板**

在 `dashboard/page.tsx` 中处理文件上传结果：

```typescript
const [extractionResults, setExtractionResults] = useState<ExtractionResult[]>([]);

const handleFileUpload = async (file: File) => {
  const results = await extractAllSections(file);
  setExtractionResults(results);
};

const handleExtractionConfirm = (data: Record<string, any>) => {
  // 将提取的数据填充到表单
  fillFormData(data);
  setExtractionResults([]);
};
```

- [ ] **Step 6: 测试验证**
- 上传包含多Section数据的Excel文件
- 检查是否显示所有识别到的Section
- 检查低置信度字段是否高亮

- [ ] **Step 7: 提交**

```bash
cd tantan
git add backend/agents/file_extractor.py frontend/app/components/ExtractionResultPanel.tsx frontend/types/extraction.ts frontend/app/dashboard/page.tsx
git commit -m "feat: support multi-section file extraction"
```

---

## Task 6: Section级引导

**Files:**
- Create: `tantan/frontend/app/components/SectionOnboarding.tsx`
- Modify: `tantan/frontend/app/dashboard/page.tsx`

- [ ] **Step 1: 创建 SectionOnboarding 组件**

创建 `tantan/frontend/app/components/SectionOnboarding.tsx`：

```typescript
'use client';

import { Modal, Button } from 'antd';
import { SectionGuide } from '@/config/sectionConfig';

interface SectionOnboardingProps {
  guide: SectionGuide | null;
  onDismiss: () => void;
  onDontShowAgain: () => void;
}

export function SectionOnboarding({ guide, onDismiss, onDontShowAgain }: SectionOnboardingProps) {
  if (!guide) return null;

  return (
    <Modal
      title={guide.title}
      open={true}
      onCancel={onDismiss}
      footer={[
        <Button key="dontshow" onClick={onDontShowAgain}>不再显示</Button>,
        <Button key="close" type="primary" onClick={onDismiss}>开始填报</Button>
      ]}
    >
      <div className="section-guide">
        <h4>📋 需要收集什么</h4>
        <p>{guide.what}</p>

        <h4>❓ 为什么需要</h4>
        <p>{guide.why}</p>

        <h4>📁 数据来源</h4>
        <ul>
          {guide.where.map((source, i) => (
            <li key={i}>{source}</li>
          ))}
        </ul>

        {guide.examples && (
          <>
            <h4>💡 填写示例</h4>
            <ul>
              {guide.examples.map((ex, i) => (
                <li key={i}>{ex}</li>
              ))}
            </ul>
          </>
        )}
      </div>
    </Modal>
  );
}
```

- [ ] **Step 2: 添加 SectionGuide 类型到 sectionConfig.ts**

```typescript
export interface SectionGuide {
  title: string;
  what: string;
  why: string;
  where: string[];
  examples?: string[];
}

export const SECTION_ONBOARDING_GUIDES: { [section: number]: SectionGuide } = {
  1: {
    title: '基本信息填报指南',
    what: '企业基本信息和核算范围确认',
    why: '确定碳核算的主体边界和数据统计范围',
    where: ['营业执照', '组织架构图', '生产工艺说明'],
    examples: ['年产值2亿元', '员工人数500人']
  },
  // ... 其他section
};
```

- [ ] **Step 3: 在 Dashboard 集成首次进入检测**

```typescript
const [showOnboarding, setShowOnboarding] = useState(false);
const STORAGE_KEY = 'section_onboarding_shown';

useEffect(() => {
  const shown = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  if (!shown[currentSection]) {
    setShowOnboarding(true);
  }
}, [currentSection]);

const handleOnboardingDismiss = () => {
  setShowOnboarding(false);
};

const handleOnboardingDontShow = () => {
  const shown = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  shown[currentSection] = true;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(shown));
  setShowOnboarding(false);
};
```

- [ ] **Step 4: 测试验证**
- 首次进入某Section，检查是否显示引导弹窗
- 点击"不再显示"，刷新页面，检查是否不再显示

- [ ] **Step 5: 提交**

```bash
cd tantan
git add frontend/app/components/SectionOnboarding.tsx frontend/config/sectionConfig.ts frontend/app/dashboard/page.tsx
git commit -m "feat: add section onboarding guidance"
```

---

## 自检清单

完成所有任务后，检查以下内容：

- [ ] 所有测试通过
- [ ] 字段引导在所有9个Section中正确显示
- [ ] 校验规则正确触发
- [ ] 多Section文件提取返回正确结果
- [ ] Section引导首次进入显示，再次进入不显示
- [ ] 前端无TypeScript错误
- [ ] 所有修改已提交

---

## 执行方式

**Plan complete and saved to `docs/superpowers/plans/2026-05-26-carbon-form-guidance-implementation.md`**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
