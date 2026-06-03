/**
 * Chat E2E 基线 - AI 问答
 *
 * 流程：
 *   - 打开 AI 悬浮窗
 *   - 发送问题
 *   - 等待助手回复消息出现
 *
 * 注：流式响应（3.5）尚未接入，仅断言同步响应的回复气泡。
 */
import { test, expect } from '@playwright/test';
import { genTestUser, register, waitForDashboardReady } from './helpers';

test.describe('Chat 基线', () => {
  test('打开 AI 助手 → 发送问题 → 收到回复', async ({ page }) => {
    const user = genTestUser();
    await register(page, user);
    await waitForDashboardReady(page);

    // 打开 AI 悬浮窗
    await page.getByRole('button', { name: /碳排放助手/i }).click();

    // 等待 chat API 响应
    const chatResponse = page.waitForResponse(
      (r) => r.url().includes('/api/chat') && r.request().method() === 'POST',
      { timeout: 60_000 }
    );

    // 输入并发送
    const input = page.locator('input[placeholder*="输入您的问题"]');
    await input.fill('碳排放因子是什么？');
    await page.locator('button:has(.anticon-send), [class*="aiSendButton"]').click();

    const resp = await chatResponse;
    expect(resp.status()).toBe(200);

    // 断言出现至少 2 条消息（用户 + 助手）
    await expect(page.locator('[class*="aiMessage"]')).toHaveCount(2, { timeout: 30_000 });
  });
});
