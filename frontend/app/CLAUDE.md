# App - Next.js页面

## page.tsx

主页面组件，包含表单填写和AI悬浮窗。

### 状态

```typescript
interface FormState {
  session_id: string;
  current_section: number;  // 1-9
  progress: {[section: number]: string};
  form_data: {[section: number]: {[key: string]: any}};
}

// 悬浮球拖动状态
const [floatingPos, setFloatingPos] = useState({ x: 0, y: 0 });
const [isDragging, setIsDragging] = useState(false);
const [wasJustDragged, setWasJustDragged] = useState(false);
const [windowClosedPos, setWindowClosedPos] = useState({ x: 24, y: 20 }); // 悬浮窗关闭时的位置

// 悬浮窗拖动状态
const [windowPos, setWindowPos] = useState<{ x: number; y: number } | null>(null);
const [isWindowDragging, setIsWindowDragging] = useState(false);
```

### 悬浮球拖动

悬浮球和悬浮窗都支持拖动定位：
- 悬浮球：按住鼠标拖动，使用 hasMoved ref 区分拖动和点击
- 悬浮窗：按住标题栏拖动，位置变化通过 onPositionChange 回调通知父组件
- 使用 `mouseDown`/`mouseMove`/`mouseUp` 事件实现
- 悬浮窗再次打开时使用上次关闭时的位置 (windowClosedPos)

### 文件上传验证

前端文件上传前验证：
- 最大文件大小: 10MB
- 允许的文件类型: `.xlsx`, `.xls`, `.pdf`
- validateFile 函数返回错误信息或 null

### 条件字段渲染

条件字段检查逻辑：
- 检查 conditionField 是否存在且有值
- 只有当条件字段值等于 conditionValue 时才显示
- 空值或未定义会隐藏条件字段

### AI对话

```typescript
interface AIConversation {
  id: string;
  title: string;       // 第一条消息前20字符
  messages: ChatMessage[];
  createdAt: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  timestamp?: string;
}
```

### 悬浮球拖动

悬浮球和悬浮窗都支持拖动定位：
- 悬浮球：按住鼠标拖动，使用 hasMoved ref 区分拖动和点击
- 悬浮窗：按住标题栏拖动
- 使用 `mouseDown`/`mouseMove`/`mouseUp` 事件实现
- 悬浮窗初始位置由悬浮球位置决定 (initialPos prop)

### 文件上传与AI提取

handleFileUpload 函数流程：
1. 上传文件到 /api/upload
2. 调用 /api/extract/{session_id}/section/{section} 提取数据
3. 将提取的数据填充到表单 form_data
4. 打开AI悬浮窗显示结果

## 表单部分

| 部分 | 名称 | 主要字段 |
|------|------|----------|
| 1 | 基本信息 | 企业名称、所属行业、联系人、联系方式、生产地址、核算年份、是否为自然年、核算周期说明（条件显示） |
| 2 | 产品 | 目标产品名称、是否唯一产品、其他产品（多行）、计量单位、是否有副产品 |
| 3 | 燃料使用 | 生产用锅炉燃料、专用废气焚烧炉燃料、危废焚烧炉燃料、发电机燃料、食堂炉灶燃料（每种含：类型+使用量+单位+实测热值）、厂内叉车燃料、92#/95#/98#商务车燃料、柴油车燃料、切割焊接燃料 |
| 4 | 电力、热力使用 | 全厂/生产/行政办公/目标产品产线/单耗用电量、光伏发电量及配置、绿证购买（条件显示）、排放权益购买（条件显示）、蒸汽参数、全厂/生产/行政/目标产品产线/单耗用蒸汽量 |
| 5 | 制冷剂使用 | 空调制冷剂（设备名称+标号+填充量，多行）、冷冻机制冷剂 |
| 6 | 其他散逸类排放 | CO2灭火器填充总量、员工总工时 |
| 7 | 三废处理 | 废水处理方式+处理量+产线废水量+进出水COD、污水处理药剂（多行）、废气处理方式、危废委外/自行焚烧量和资源化量（各含产线分解）、烟气处理药剂（多行） |
| 8 | 原材料使用 | 生产工艺流程图（文件上传）+文字描述、原材料（名称+规格+使用量+单位，多行）、供应商（名称+品类+运输方式+运距，多行） |
| 9 | 生产耗材 | 新鲜水（统计口径+使用量+说明）、氮气（统计口径+使用量+说明） |

## SECTION_FIELDS 配置

每个部分的字段定义，包含：
- key: 字段标识
- label: 显示名称
- type: 'text' | 'number' | 'select' | 'file' | 'multi-row'
- placeholder: 占位文本
- options: select选项
- unit: 数字字段单位
- maxRows: 多行最大行数
- fields: 多行子字段定义
- conditionField: 条件字段key，满足条件时才显示
- conditionValue: 条件字段值

## 子组件

### TextField / NumberField / SelectField
单行输入字段。

### FileField
文件上传字段，显示为可点击的上传区域。

### MultiRowField
动态多行表格，支持添加/删除行。
- 子字段渲染为表格列
- 支持 select/number/text 类型子字段

### FloatingAI
AI助手悬浮窗组件。
- 对话列表（左侧）
- 聊天区域（右侧）
- localStorage持久化 (key: 'ai_conversations')
- 支持拖动定位
- props: isOpen, onClose, onExtractComplete, formState, initialPos, onPositionChange

## 样式

`page.module.css` 包含所有组件样式：
- 表单字段样式 (.fieldGroup, .fieldLabel, .fieldInput, .fieldSelect)
- 多行表格样式 (.multiRowContainer, .multiRowTable, .tableCell, .tableInput, .tableSelect)
- 文件上传样式 (.fileUploadArea, .filePlaceholder)
- AI悬浮窗样式 (.floatingButton, .floatingWindow, .floatingHeader, .conversationList, .chatArea)
- 侧边栏样式 (.sidebar, .sectionItem, .statusBadge)
- 内容区域padding: 20px 30px
