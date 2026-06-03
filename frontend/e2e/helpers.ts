/**
 * E2E 测试公共工具
 */
import { Page, expect } from '@playwright/test';

export interface TestUser {
  username: string;
  password: string;
}

/** 生成唯一测试用户（避免跨测试污染） */
export function genTestUser(): TestUser {
  return {
    username: `e2e_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    password: 'TestPwd123!',
  };
}

/** 登录（前提：用户已注册） */
export async function login(page: Page, user: TestUser) {
  await page.goto('/login');
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.ant-tabs-tab', { timeout: 10_000 });
  await page.fill('input[placeholder="用户名"]', user.username);
  await page.fill('input[placeholder="密码"]', user.password);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard', { timeout: 15_000 });
  await page.waitForLoadState('networkidle').catch(() => {});
}

/** 注册新用户（完成后处于已登录态） */
export async function register(page: Page, user: TestUser) {
  await page.goto('/login');
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.ant-tabs-tab', { timeout: 10_000 });
  await page.locator('.ant-tabs-tab:has-text("注册")').click();
  await page.waitForSelector('.ant-tabs-tabpane-active', { timeout: 5_000 });
  await page.locator('.ant-tabs-tabpane-active input').first().fill(user.username);
  await page.locator('input[placeholder*="密码"]').last().fill(user.password);
  await page.locator('.ant-tabs-tabpane-active button[type="submit"]').click();
  await page.waitForURL('**/dashboard', { timeout: 15_000 });
  await page.waitForLoadState('networkidle').catch(() => {});
}

/** 登出（点击 header 登出按钮） */
export async function logout(page: Page) {
  await page.locator('[class*="headerLogout"]').click();
  // 弹窗确认
  await page.locator('.ant-modal-confirm-btns button').last().click();
  await page.waitForURL('**/login', { timeout: 10_000 });
}

/** 等待 dashboard 核心区域就绪 */
export async function waitForDashboardReady(page: Page) {
  await page.locator('.ant-layout-sider').waitFor({ timeout: 10_000 });
  await page.locator('.ant-layout-content').waitFor({ timeout: 10_000 });
  // 等待卡片标题出现（说明 session 已创建、form 已挂载）
  await expect(page.locator('h4, .ant-typography').first()).toBeVisible({ timeout: 10_000 });
}
