/**
 * P0-8 守门测试 - Playwright fixtures 不再"假 skip 真 disabled"
 *
 * WHY:
 *   docs/CODE_REVIEW_2026-06-03.md 4.5【Critical】：frontend/e2e/fixtures/
 *   目录不存在，upload.spec.ts:16 + extract.spec.ts:16 用 test.skip 让 CI
 *   永远报"通过"但 0 覆盖——给的是假绿灯。
 *
 *   修后：
 *   1. e2e/fixtures/sample.xlsx 必须存在（落档真实 xlsx）
 *   2. 两个 spec 文件不得再含 `test.skip`（缺失应直接 throw）
 *
 * 守门 3 件套：
 *   1. fixture 文件存在
 *   2. fixture 文件大小 > 0（不是 0 字节占位）
 *   3. 两个 spec 文件不含 `test.skip(!fs.existsSync(FIXTURE))` 模式
 */
import fs from 'fs';
import path from 'path';
import { test, expect } from '@playwright/test';

const FIXTURE = path.resolve(__dirname, 'fixtures/sample.xlsx');
const UPLOAD_SPEC = path.resolve(__dirname, 'upload.spec.ts');
const EXTRACT_SPEC = path.resolve(__dirname, 'extract.spec.ts');

test.describe('P0-8 fixtures 守门', () => {
  test('e2e/fixtures/sample.xlsx 存在且非空', () => {
    expect(fs.existsSync(FIXTURE), `fixture 缺失: ${FIXTURE}`).toBe(true);
    const stat = fs.statSync(FIXTURE);
    expect(stat.size, `fixture 是 0 字节: ${FIXTURE}`).toBeGreaterThan(0);
  });

  test('upload.spec.ts 不再含 test.skip fixture 缺失模式', () => {
    const src = fs.readFileSync(UPLOAD_SPEC, 'utf-8');
    expect(
      src,
      'upload.spec.ts 仍含 `test.skip(!fs.existsSync(FIXTURE), ...)`，P0-8 修复后必须 throw 而非 skip',
    ).not.toMatch(/test\.skip\s*\(\s*!.*existsSync\s*\(\s*FIXTURE\s*\)/);
  });

  test('extract.spec.ts 不再含 test.skip fixture 缺失模式', () => {
    const src = fs.readFileSync(EXTRACT_SPEC, 'utf-8');
    expect(
      src,
      'extract.spec.ts 仍含 `test.skip(!fs.existsSync(FIXTURE), ...)`，P0-8 修复后必须 throw 而非 skip',
    ).not.toMatch(/test\.skip\s*\(\s*!.*existsSync\s*\(\s*FIXTURE\s*\)/);
  });
});
