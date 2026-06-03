import { test, expect, Page } from '@playwright/test';

// 测试账户 - 静态用户名避免冲突
const TEST_USER = {
  username: `e2e_test_user_${Date.now()}`,
  password: 'testpassword123'
};

// 辅助函数：注册（只执行一次）
async function register(page: Page) {
  await page.goto('/login');
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.ant-tabs-tab', { timeout: 10000 });

  // 点击注册tab
  await page.click('.ant-tabs-tab:has-text("注册")');
  await page.waitForTimeout(500);

  await page.waitForSelector('.ant-tabs-tabpane-active', { timeout: 5000 });

  // 填写用户名
  const usernameInput = page.locator('.ant-tabs-tabpane-active input').first();
  await usernameInput.fill(TEST_USER.username);

  // 填写密码
  const passwordInput = page.locator('input[placeholder*="密码"]').last();
  await passwordInput.fill(TEST_USER.password);

  // 点击注册按钮
  await page.click('.ant-tabs-tabpane-active button[type="submit"]');

  // 等待跳转到dashboard
  await page.waitForURL('**/dashboard', { timeout: 15000 });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(2000);
}

// ============ 登录页面测试 ============
test.describe('登录页面', () => {
  test('应该显示登录表单', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('.ant-tabs-tab', { timeout: 10000 });

    await expect(page.locator('input[placeholder="用户名"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('input[placeholder="密码"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('应该可以切换到注册页面', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    const registerTab = page.locator('.ant-tabs-tab').filter({ hasText: /^注册$/ });
    if (await registerTab.isVisible()) {
      await registerTab.click();
      await page.waitForSelector('.ant-tabs-tabpane-active', { timeout: 5000 });
      const usernameInput = page.locator('.ant-tabs-tabpane-active input').first();
      await expect(usernameInput).toBeVisible();
    }
  });
});

// ============ 注册测试 ============
test.describe('注册功能', () => {
  test('应该可以成功注册并跳转dashboard', async ({ page }) => {
    await register(page);
    expect(page.url()).toContain('/dashboard');
  });
});

// ============ Dashboard 核心测试 ============
test.describe('Dashboard 核心功能', () => {
  test.beforeEach(async ({ page }) => {
    // 复用已注册的会话
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('.ant-tabs-tab', { timeout: 10000 });

    // 登录
    await page.fill('input[placeholder="用户名"]', TEST_USER.username);
    await page.fill('input[placeholder="密码"]', TEST_USER.password);
    await page.click('button[type="submit"]');

    await page.waitForURL('**/dashboard', { timeout: 15000 });
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForTimeout(2000);
  });

  test('应该显示侧边栏', async ({ page }) => {
    const sidebar = page.locator('.ant-layout-sider');
    await expect(sidebar).toBeVisible({ timeout: 5000 });
  });

  test('应该显示顶部导航', async ({ page }) => {
    const header = page.locator('.ant-layout-header');
    await expect(header).toBeVisible({ timeout: 5000 });
  });

  test('应该显示确认完成按钮', async ({ page }) => {
    const confirmButton = page.getByRole('button', { name: /确认完成/i });
    await expect(confirmButton).toBeVisible({ timeout: 5000 });
  });

  test('应该显示AI助手按钮', async ({ page }) => {
    const aiButton = page.getByText(/AI助手/i);
    await expect(aiButton).toBeVisible({ timeout: 5000 });
  });

  test('应该显示上传文件AI提取按钮', async ({ page }) => {
    const uploadButton = page.getByText(/上传文件AI提取/i);
    await expect(uploadButton).toBeVisible({ timeout: 5000 });
  });
});

// ============ Section 5 测试 ============
test.describe('Section 5 制冷剂使用', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('.ant-tabs-tab', { timeout: 10000 });

    await page.fill('input[placeholder="用户名"]', TEST_USER.username);
    await page.fill('input[placeholder="密码"]', TEST_USER.password);
    await page.click('button[type="submit"]');

    await page.waitForURL('**/dashboard', { timeout: 15000 });
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForTimeout(2000);

    // 点击 Section 5
    const section5 = page.locator('.ant-menu-item').filter({ hasText: /^5$/ });
    await section5.click();
    await page.waitForTimeout(1000);
  });

  test('应该显示空调制冷剂卡片', async ({ page }) => {
    const acCard = page.locator('.ant-card').filter({ hasText: /空调制冷剂/i });
    await expect(acCard).toBeVisible({ timeout: 5000 });
  });

  test('应该显示冷冻机制冷剂卡片', async ({ page }) => {
    const freezerCard = page.locator('.ant-card').filter({ hasText: /冷冻机制冷剂/i });
    await expect(freezerCard).toBeVisible({ timeout: 5000 });
  });

  test('应该显示添加按钮', async ({ page }) => {
    const addButton = page.getByRole('button', { name: /添加/i });
    await expect(addButton.first()).toBeVisible({ timeout: 5000 });
  });
});
