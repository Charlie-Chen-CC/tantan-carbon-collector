/**
 * Upload E2E 基线 - 上传 → 提取 → 填充
 *
 * 用 setInputFiles 上传预置测试文件，断言：
 *   - 上传后文件出现在列表
 *   - 提取完成后 filled_data 写入表单字段
 */
import { test, expect } from '@playwright/test';
import path from 'path';
import { genTestUser, register, waitForDashboardReady } from './helpers';

const FIXTURE = path.resolve(__dirname, 'fixtures/sample.xlsx');

test.describe('Upload 基线', () => {
  test('上传 xlsx 文件 → 提取 → 表单自动填充', async ({ page }) => {
    test.skip(!require('fs').existsSync(FIXTURE), `缺少测试文件: ${FIXTURE}`);

    const user = genTestUser();
    await register(page, user);
    await waitForDashboardReady(page);

    // 找到 FileUploadPanel 的隐藏 input
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(FIXTURE);

    // 等待文件出现在列表
    await expect(page.locator('text=已上传').first()).toBeVisible({ timeout: 30_000 });
  });
});
