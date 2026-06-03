# 碳排放表单填报引导系统设计方案

## Context

### 问题背景
碳管师收资系统需要收集专业性很强的碳排放数据，但填报用户往往缺乏相关专业知识，不知道该填什么、从哪找数据、怎么填对。

### 现有痛点
1. **缺乏主动性** - 现有AI悬浮窗是被动的，用户不会主动提问
2. **无法识别困惑** - 用户遇到问题时系统无法感知并介入
3. **无文件时束手无策** - AI提取只针对已有文件，无法引导手动填报
4. **数据质量无保障** - 没有预校验机制，收上来的数据可能完全不符合要求
5. **二次确认缺失** - 数据中包含有效信息但未充分挖掘确认

### 目标
在不打扰用户的前提下，提供清晰的填报引导，提高数据质量和填报效率。

---

## 解决方案概述

本方案包含四个核心功能：

| 功能 | 描述 | 触发方式 |
|------|------|----------|
| 字段级引导 | 每个字段下方常驻引导提示 | 用户可见 |
| Section级引导 | 进入section前展示填报须知 | 节点触发 |
| 前置数据校验 | 提交前校验数据合理性 | 提交时触发 |
| 多Section文件提取 | 一次上传自动填充多个Section | 上传文件时触发 |

---

## 功能设计

### 1. 字段级引导（Field Guidance）

#### 数据结构
```typescript
interface FieldGuide {
  fieldKey: string;           // 字段标识
  label: string;               // 字段名称（冗余，便于调试）
  description: string;         // 字段含义说明
  dataSources: string[];        // 数据来源指引
  commonIssues?: string[];     // 常见问题/错误
  unit?: string;               // 计量单位
  validation?: FieldValidation; // 字段级校验规则
}

interface FieldValidation {
  min?: number;
  max?: number;
  pattern?: string;
  customMessage?: string;
}
```

#### 呈现方式
- 每个表单字段下方常驻显示引导文案
- 布局：`[字段标签] [输入框] [单位]`，下方展示 `[引导提示]`
- 引导提示包含：字段含义说明 + 数据来源指引
- 可折叠的"常见问题"区域

#### 示例
```
化石燃料燃烧CO2排放量
[_______________] [吨CO2]

请填写生产过程中燃煤、燃油、燃气等化石燃料燃烧产生的CO2排放量。
数据来源：企业能源台账、燃料采购发票、能源账单等

[▼ 常见问题]
```

### 2. Section级引导（Section Onboarding）

#### 触发时机
用户首次进入某个section时，展示该section的整体说明。

#### 呈现方式
- 模态弹窗形式，突出显示
- 包含 What / Why / Where 三段式结构
- 用户可选择"不再显示"记住选择

#### 内容结构
```typescript
interface SectionGuide {
  sectionKey: string;
  title: string;
  what: string;           // 这个section需要收集什么
  why: string;           // 为什么需要这些数据
  where: string[];        // 一般从哪些渠道获取
  examples?: string[];    // 填写示例
}
```

### 3. 多Section文件提取（Multi-Section File Extraction）

#### 场景
用户上传的Excel文件可能包含多个Section的数据（如同时包含"能源消耗"和"碳排放"数据），系统应自动识别并填充到对应Section。

#### 数据结构
```typescript
interface ExtractionResult {
  fileName: string;
  extractedSections: {
    sectionKey: string;
    sectionName: string;
    fieldsExtracted: number;
    extractionStatus: 'success' | 'partial' | 'failed';
    fields: {
      fieldKey: string;
      value: any;
      confidence: number;      // 置信度 0-1
      sourceCell?: string;     // 来源单元格，便于核对
    }[];
  }[];
  unprocessedData?: string;    // 未识别处理的数据摘要
}
```

#### 呈现方式
- 文件上传后，弹出结果汇总面板
- 清晰列出哪些Section被成功提取、提取了多少字段
- 未识别的数据单独展示，供用户手动处理
- 置信度低于阈值（如0.7）的字段高亮标记，供用户确认

#### 用户交互流程
```
文件上传
    ↓
AI提取分析
    ↓
展示提取结果面板
    ↓
用户确认/修改自动填充的数据
    ↓
数据写入对应Section
```

#### 反馈内容示例
```
✅ 已自动填充 2 个Section：

【Section 1 - 能源消耗】- 提取 5 个字段
  • 煤炭消耗量：12,500 吨（来源：B2单元格，高置信度）
  • 天然气消耗量：3,200 m³（来源：B3单元格，高置信度）
  ⚠️ 电力消耗量：预估 8,500 MWh（置信度0.65，请核对）

【Section 3 - 碳排放核算】- 提取 3 个字段
  • 直接CO2排放：28,600 吨（来源：C5单元格，高置信度）

❓ 以下数据未能识别：
  • 第15-18行：原材料消耗数据（无对应Section）

[查看全部详情]  [开始填报]
```

---

### 4. 前置数据校验（Pre-submission Validation）

#### 校验层级

**字段级校验**
- 类型校验：数字字段不能输入文字
- 范围校验：数值在合理区间内
- 必填校验：必填字段不能为空

**跨字段校验**
- 关联逻辑：部分A之和 ≤ 部分B
- 业务规则：如"燃料消耗量"和"CO2排放量"应成比例

**异常检测**
- 与历史数据偏差过大的标记
- 明显异常值预警

#### 校验反馈
- 提交前拦截：阻止提交，提示具体错误
- 警告不拦截：提示异常但允许提交，数据标记待复核
- 错误定位：点击错误跳转至对应字段

---

## 技术实现

### 后端

#### 字段引导配置
- 文件位置：`backend/agents/form_filler.py`
- 新增 `SECTION_FIELD_GUIDES` 配置结构
- 复用现有 `section_definitions` 结构扩展

#### 多Section提取
- 扩展现有文件提取逻辑，一次处理识别多个Section
- 新增 `backend/agents/multi_section_extractor.py`（或扩展现有extractor）
- AI prompt 需支持多Section联合识别

#### 校验规则
- 文件位置：`backend/validators/form_validator.py`（新建）
- 支持规则：min/max/pattern/required/custom
- 支持跨字段校验函数注册

### 前端

#### 字段引导组件
- 组件位置：`frontend/app/components/FieldGuide.tsx`
- 在现有表单组件中集成
- 响应式布局，移动端友好

#### Section引导组件
- 组件位置：`frontend/app/components/SectionOnboarding.tsx`
- 使用 next/dialog 或自定义模态
- localStorage 存储"不再显示"状态

#### 多Section提取结果组件
- 组件位置：`frontend/app/components/ExtractionResultPanel.tsx`
- 展示提取结果汇总，支持字段级确认/修改
- 低置信度字段高亮提示

#### 校验反馈组件
- 组件位置：`frontend/app/components/ValidationFeedback.tsx`
- 实时校验 + 提交前全局校验
- 错误列表可点击跳转

---

## 数据流

```
用户进入Section
    ↓
首次进入？ → 是 → 显示 SectionOnboarding 弹窗
    ↓
用户填写字段
    ↓
实时字段级校验（前端）
    ↓
用户点击提交
    ↓
后端二次校验
    ↓
通过 → 提交成功
失败 → 返回错误列表 → 用户修改后重试
```

---

## 关键文件

| 文件 | 作用 |
|------|------|
| `backend/agents/form_filler.py` | 扩展字段引导配置 |
| `backend/agents/multi_section_extractor.py` | 新建多Section提取逻辑（扩展现有） |
| `backend/validators/form_validator.py` | 新建校验规则引擎 |
| `frontend/app/components/FieldGuide.tsx` | 新建字段引导组件 |
| `frontend/app/components/SectionOnboarding.tsx` | 新建section引导组件 |
| `frontend/app/components/ExtractionResultPanel.tsx` | 新建提取结果展示组件 |
| `frontend/app/components/ValidationFeedback.tsx` | 新建校验反馈组件 |
| `frontend/app/schemas/form_schemas.ts` | 扩展表单schema含引导信息 |

---

## 测试验证

### 功能测试
1. 字段引导文案正确显示
2. Section引导首次进入弹出，再次进入不弹出
3. 多Section文件正确识别，填充到对应区域
4. 低置信度字段高亮提示
5. 字段校验在边界值处正确拦截/警告
6. 跨字段校验正确执行
7. 校验错误能正确定位到字段

### 用户体验测试
1. 字段引导不影响正常填报操作
2. 移动端布局正常
3. 校验反馈清晰易懂

---

## 优先级建议

| 阶段 | 内容 | 价值 |
|------|------|------|
| P0 | 字段级引导 + 前置校验 + 多Section提取 | 核心痛点解决 |
| P1 | Section级引导 | 增强认知 |
| P2 | 智能预填（行业标准值） | 进一步减负 |

**说明**：多Section提取可复用现有文件提取能力，建议与P0其他功能一并实施。

---

## 下一步

请审阅本设计方案，如有修改意见请反馈。批准后可进入实施计划阶段。
