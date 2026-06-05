/**
 * P0-5 隐私 E2E - 登出后清 localStorage（GDPR / 个保法合规）
 *
 * WHY:
 *   docs/CODE_REVIEW_2026-06-03.md 4.3：useAIChat.ts:62 把 conversations
 *   序列化到 localStorage['ai_conversations']；authStore.logout() 之前
 *   只清服务端 cookie + zustand state，从未清 localStorage → 下一个用户
 *   登录后能看到上一用户的 AI 对话。
 *
 * 验证：
 *   - 登出前 localStorage 至少有一条对话
 *   - 登出后 localStorage['ai_conversations'] 键被删除（不应残留旧用户数据）
 */
import { test, expect } from '@playwright/test';
import { genTestUser, register, logout, waitForDashboardReady } from './helpers';

const AI_CONVERSATIONS_KEY = 'ai_conversations';

test.describe('P0-5: 登出清 localStorage', () => {
  test('用户 A 聊天后登出 → localStorage 中 AI 对话历史被清空', async ({ page }) => {
    const user = genTestUser();
    await register(page, user);
    await waitForDashboardReady(page);

    // 打开 AI 悬浮窗
    await page.getByRole('button', { name: /碳排放助手/i }).click();

    // 等 chat 响应以确保 useAIChat 把对话写入 localStorage
    const chatResponse = page.waitForResponse(
      (r) => r.url().includes('/api/chat') && r.request().method() === 'POST',
      { timeout: 60_000 }
    );
    const input = page.locator('input[placeholder*="输入您的问题"]');
    await input.fill('测试对话 P0-5');
    await page.locator('button:has(.anticon-send), [class*="aiSendButton"]').click();
    const resp = await chatResponse;
    expect(resp.status()).toBe(200);
    await expect(page.locator('[class*="aiMessage"]')).toHaveCount(2, { timeout: 30_000 });

    // 断言 localStorage 里有对话（登出前应该有数据）
    const before = await page.evaluate(
      (k) => localStorage.getItem(k),
      AI_CONVERSATIONS_KEY,
    );
    expect(before, '登出前 localStorage 应有 AI 对话').not.toBeNull();
    const parsed = JSON.parse(before!);
    expect(Array.isArray(parsed) ? parsed.length : 0).toBeGreaterThan(0);

    // 登出
    await logout(page);

    // 关键断言：登出后 localStorage 键被删除
    const after = await page.evaluate(
      (k) => localStorage.getItem(k),
      AI_CONVERSATIONS_KEY,
    );
    expect(after, '登出后 localStorage["ai_conversations"] 必须被清空').toBeNull();
  });
});
