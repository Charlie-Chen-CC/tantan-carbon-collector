/**
 * Auth E2E 基线 - 登录 / 登出
 */
import { test, expect } from '@playwright/test';
import { genTestUser, register, login, logout, waitForDashboardReady } from './helpers';

test.describe('Auth 基线', () => {
  test('新用户注册 → 自动登录 → 看到 dashboard', async ({ page }) => {
    const user = genTestUser();
    await register(page, user);
    await waitForDashboardReady(page);
    expect(page.url()).toContain('/dashboard');
  });

  test('已注册用户登录 → 看到 dashboard', async ({ page }) => {
    const user = genTestUser();
    await register(page, user);
    // 登出后再次登录
    await logout(page);
    await login(page, user);
    await waitForDashboardReady(page);
  });

  test('未登录访问 /dashboard 被 middleware 重定向到 /login', async ({ page, context }) => {
    // 清理 cookie 模拟未登录
    await context.clearCookies();
    await page.goto('/dashboard');
    await page.waitForURL('**/login*', { timeout: 10_000 });
    expect(page.url()).toContain('/login');
  });
});
