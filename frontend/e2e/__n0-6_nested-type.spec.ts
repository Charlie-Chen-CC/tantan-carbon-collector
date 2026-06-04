/**
 * P0-6 守门测试 - 'nested' 类型字段必须有处理器
 *
 * WHY:
 *   docs/CODE_REVIEW_2026-06-03.md Agent 2 B-1：sectionConfig.ts:138,140
 *   定义了 type: 'nested' 字段（freshWater/nitrogen，section 9），但
 *   FormSection.tsx switch case 缺 'nested' 分支 → 这些字段永不渲染，
 *   用户没法填，section 9 数据采集静默失败。
 *
 *   修复（用户选 B）：新增 MultiLevelTable 组件 + FormSection 加 'nested' case +
 *   NESTED_FIELD_SCHEMA 定义 freshWater/nitrogen 的 3 个 sub_fields
 *   （caliber/amount/unit，对应后端 NESTED_FIELD_TRANSFORMERS）。
 *
 * 守门 3 件套：
 *   1. sectionConfig.ts 必须有 NESTED_FIELD_SCHEMA 常量（防新增 nested 字段漏 schema）
 *   2. FormSection.tsx switch 必须有 'nested' case
 *   3. components/MultiLevelTable.tsx 必须存在并 export default
 */
import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const SECTION_CONFIG = path.join(REPO_ROOT, 'frontend', 'config', 'sectionConfig.ts');
const FORM_SECTION = path.join(REPO_ROOT, 'frontend', 'components', 'FormSection.tsx');
const MULTI_LEVEL_TABLE = path.join(REPO_ROOT, 'frontend', 'components', 'MultiLevelTable.tsx');

test.describe('P0-6: sectionConfig \'nested\' 类型必须有处理器', () => {
  test('sectionConfig.ts 必须有 NESTED_FIELD_SCHEMA 常量（防新增 nested 字段漏 schema）', async () => {
    const text = fs.readFileSync(SECTION_CONFIG, 'utf-8');
    expect(text, 'sectionConfig.ts 必须 export NESTED_FIELD_SCHEMA').toMatch(
      /export\s+const\s+NESTED_FIELD_SCHEMA/,
    );
  });

  test('FormSection.tsx switch case 必须有 \'nested\' 分支', async () => {
    const text = fs.readFileSync(FORM_SECTION, 'utf-8');
    expect(text, "FormSection.tsx 必须有 case 'nested':").toMatch(/case\s+['"]nested['"]\s*:/);
  });

  test('components/MultiLevelTable.tsx 必须存在并 export default', async () => {
    expect(fs.existsSync(MULTI_LEVEL_TABLE), 'MultiLevelTable.tsx 必须存在').toBe(true);
    const text = fs.readFileSync(MULTI_LEVEL_TABLE, 'utf-8');
    expect(text, 'MultiLevelTable.tsx 必须 export default').toMatch(/export\s+default\s+function\s+MultiLevelTable/);
  });

  test('sectionConfig.ts 中 freshWater/nitrogen 必须有 sub_fields', async () => {
    const text = fs.readFileSync(SECTION_CONFIG, 'utf-8');
    // 提取 NESTED_FIELD_SCHEMA 块
    const match = text.match(/NESTED_FIELD_SCHEMA\s*:\s*Record<string,\s*FieldDef\[\]>\s*=\s*\{([\s\S]*?)\n\};/);
    expect(match, '找不到 NESTED_FIELD_SCHEMA 完整定义').not.toBeNull();
    const body = match![1];
    expect(body, 'NESTED_FIELD_SCHEMA 必须含 freshWater').toMatch(/freshWater/);
    expect(body, 'NESTED_FIELD_SCHEMA 必须含 nitrogen').toMatch(/nitrogen/);
    // 每个 nested 字段必须含 caliber/amount/unit 三个 sub_field
    expect(body, 'freshWater 必须含 caliber sub_field').toMatch(/freshWater[\s\S]{0,500}caliber/);
    expect(body, 'freshWater 必须含 amount sub_field').toMatch(/freshWater[\s\S]{0,500}amount/);
    expect(body, 'freshWater 必须含 unit sub_field').toMatch(/freshWater[\s\S]{0,500}unit/);
  });
});
