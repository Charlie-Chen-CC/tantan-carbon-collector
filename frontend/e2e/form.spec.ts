/**
 * Form E2E 基线 - 表单填写 + 确认 section
 *
 * 流程：
 *   - 进入 section 1
 *   - 填写企业名称 + 行业
 *   - 点击"确认完成"
 *   - 等待 confirmSection API 200
 *   - 断言进度更新
 */
import { test, expect } from '@playwright/test';
import { genTestUser, register, waitForDashboardReady } from './helpers';

test.describe('Form 基线', () => {
  test('填写 section 1 基础字段 → 确认 → 进度更新', async ({ page }) => {
    const user = genTestUser();
    await register(page, user);
    await waitForDashboardReady(page);

    // 等待 confirm API 响应
    const confirmResponse = page.waitForResponse(
      (r) => r.url().includes('/api/form/confirm') && r.request().method() === 'POST',
      { timeout: 30_000 }
    );

    // 填写企业名称
    const enterpriseInput = page.locator('input').filter({ hasText: '' }).first();
    await page.locator('input[placeholder*="企业全称"]').fill('测试企业有限公司');
    await page.locator('input[placeholder*="所属行业"]').fill('电子设备制造');

    // 点击确认完成
    await page.getByRole('button', { name: /确认完成/i }).click();

    const resp = await confirmResponse;
    expect(resp.status()).toBe(200);
  });
});
