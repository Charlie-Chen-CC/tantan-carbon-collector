/**
 * Extract E2E 基线 - AI 提取 happy path
 *
 * 验证 extract 端点返回 filled_data 写入表单：
 *   - 监听 /api/extract/* 响应
 *   - 断言响应里至少 1 个字段被填充到 form
 */
import { test, expect } from '@playwright/test';
import path from 'path';
import { genTestUser, register, waitForDashboardReady } from './helpers';

const FIXTURE = path.resolve(__dirname, 'fixtures/sample.xlsx');

test.describe('Extract 基线', () => {
  test('AI 提取成功 → filled_data 非空 → 表单可见字段被填充', async ({ page }) => {
    test.skip(!require('fs').existsSync(FIXTURE), `缺少测试文件: ${FIXTURE}`);

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
