# Backend Scripts - 自动化脚本层

辅助 codegen / 维护 / 部署的 Python 脚本。每个脚本对应 `python -m tantan.backend.scripts.<name>` 调用。

## 目录

```
scripts/
├── codegen_field_schema.py       # 字段映射 SSOT codegen（Phase 6.3）
└── CLAUDE.md
```

## 现有脚本

### codegen_field_schema.py

字段映射 SSOT → 4 个目标文件 codegen。

**SSOT**：`tantan/shared/field_schema.json`（9 sections + 字段定义）

**生成 4 个文件**：
1. `backend/agents/form_filler/mapping.py`        - `BACKEND_TO_FRONTEND_FIELD_MAP`
2. `backend/agents/form_filler/section_defs.py`   - `FormSection` 9 个 sections
3. `backend/agents/form_filler/transformers.py`   - `MULTI_ROW` / `NESTED` 转换器
4. `frontend/config/sectionConfig.ts`             - `SECTION_FIELDS`

**调用方式**：
```bash
cd claude_workspace/
source tantan/backend/.venv/Scripts/activate

# 生成 + 写文件
python -m tantan.backend.scripts.codegen_field_schema

# 仅校验（CI / pre-commit hook 用）
python -m tantan.backend.scripts.codegen_field_schema --check
```

**P0-7 修复**：multi-row 字段的 `fields:` 数组从 `parts + ', '.join` 改为 sub_fields 独立多行拼接，避免产出 broken TS（`[, {key:..}, ]` 空元素模式）。

## 与 P0-7 守门测试的关系

`backend/tests/backend/scripts/test_codegen_output_validity.py` 跑 5 个守门测试：
1. 跑 codegen 重新生成 4 目标文件存在
2. `[, ` / `, ,` broken TS 数组模式检测
3. multi-row 字段 `fields:` 数组紧凑格式
4. `codegen --check` 自反一致性
5. typescript AST `parseDiagnostics` 解析

## 最近变更 (2026-06-05)

### P0-7 修复 - codegen 输出合法性
- 修 `gen_section_config_ts`：multi-row 字段 sub_fields 改为独立多行字符串拼接
- 修后：`fields: [\n      {key:'..'},\n      {key:'..'}\n    ]`（紧凑多行）
- 修前：`fields: [, {key:'..'}, {key:'..'}, ]`（broken TS，tsc 报 `Type 'undefined' is not assignable to type 'FieldDef'`）

### 守门测试
- 新建 `backend/tests/backend/scripts/test_codegen_output_validity.py`（5 cases）
- 用 `ts.createSourceFile` + `parseDiagnostics` 跑 AST 解析（不需 tsc 全量编译）
- 子进程用 `encoding='utf-8'` 解决 Windows gbk 解码中文 stdout 问题
- 子进程用 `cwd=REPO_ROOT / 'frontend'` 让 node 找到 typescript module
