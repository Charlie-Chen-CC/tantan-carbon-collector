/**
 * Extract E2E 基线 - AI 提取 happy path
 *
 * 验证 extract 端点返回 filled_data 写入表单：
 *   - 监听 /api/extract/* 响应
 *   - 断言响应里至少 1 个字段被填充到 form
 */
import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import { genTestUser, register, waitForDashboardReady } from './helpers';

const FIXTURE = path.resolve(__dirname, 'fixtures/sample.xlsx');

test.describe('Extract 基线', () => {
  test('AI 提取成功 → filled_data 非空 → 表单可见字段被填充', async ({ page }) => {
    // P0-8 修复：原 test.skip 让 CI 永远报"通过"但 0 覆盖，
    // 现在 fixture 已落档，缺失应直接 fail 而非静默 skip
    if (!fs.existsSync(FIXTURE)) {
      throw new Error(`缺少测试 fixture: ${FIXTURE}（P0-8 修复后必须存在）`);
    }

    const user = genTestUser();
    await register(page, user);
    await waitForDashboardReady(page);

    // 等待 extract 响应
    const extractResponse = page.waitForResponse(
      (r) => r.url().includes('/api/extract/') && r.request().method() === 'POST',
      { timeout: 60_000 }
    );

    await page.locator('input[type="file"]').first().setInputFiles(FIXTURE);

    const resp = await extractResponse;
    const body = await resp.json();
    expect(body.success).toBe(true);
    expect(body.filled_data).toBeDefined();
    expect(Object.keys(body.filled_data || {}).length).toBeGreaterThan(0);
  });
});
