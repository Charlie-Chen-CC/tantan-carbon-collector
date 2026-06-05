/**
 * P0-9 守门测试 - useFileUpload 不再上传文件两次
 *
 * WHY:
 *   docs/CODE_REVIEW_2026-06-03.md 4.6【High】：hooks/useFileUpload.ts:53-54
 *   await fileApi.upload(sessionId, section, file) → 之后
 *   await fileApi.extract(sessionId, section, file) 又把同一个 file append
 *   到 FormData 再发一遍。同一文件 HTTP 上传两次，浪费带宽 + 慢一倍。
 *
 *   修后：
 *   1. fileApi.extract 不再接受 `file: File` 参数
 *   2. fileApi.extract 接受 `fileId: string` 参数
 *   3. useFileUpload 上传完后从 response.file_id 取 ID，再调 extract
 *
 * 守门 3 件套（AST 分析，不跑 e2e）：
 *   1. useFileUpload.ts 不再含 `fileApi.extract(..., file)` 形式调用
 *   2. services/api.ts 的 fileApi.extract 签名不含 `file: File` 参数
 *   3. services/api.ts 的 fileApi.extract 调用 FormData.append('file_id', ...)
 */
import fs from 'fs';
import path from 'path';
import { test, expect } from '@playwright/test';

const USE_FILE_UPLOAD = path.resolve(__dirname, '../hooks/useFileUpload.ts');
const API_TS = path.resolve(__dirname, '../services/api.ts');

test.describe('P0-9 useFileUpload 不再双传文件', () => {
  test('useFileUpload.ts 不再把 file 当参数传给 fileApi.extract', () => {
    const src = fs.readFileSync(USE_FILE_UPLOAD, 'utf-8');
    // 旧 pattern：fileApi.extract(...args, file)
    expect(
      src,
      'useFileUpload.ts 仍调 fileApi.extract(...file) 把 file 二传，违反 P0-9 修复',
    ).not.toMatch(/fileApi\.extract\s*\([^)]*,\s*file\s*\)/);
  });

  test('useFileUpload.ts 上传后必须从 response 取 file_id 再调 extract', () => {
    const src = fs.readFileSync(USE_FILE_UPLOAD, 'utf-8');
    // 新 pattern：fileApi.extract 第二个或第三个参数应是 fileId
    expect(
      src,
      'useFileUpload.ts 调 fileApi.extract 但没传 fileId（应从 upload resp.file_id 取）',
    ).toMatch(/fileApi\.extract\s*\([^)]*fileId[^)]*\)/);
  });

  test('services/api.ts 的 fileApi.extract 签名接受 fileId: string', () => {
    const src = fs.readFileSync(API_TS, 'utf-8');
    // fileApi.extract 函数签名应含 fileId
    const m = src.match(/extract\s*:\s*\([^)]*\)\s*:/);
    expect(m, '找不到 fileApi.extract 函数定义').toBeTruthy();
    const sig = m![0];
    expect(
      sig,
      `fileApi.extract 签名应接受 fileId: string，实际: ${sig}`,
    ).toMatch(/fileId\s*:\s*string/);
    expect(
      sig,
      `fileApi.extract 签名不应再含 file: File，实际: ${sig}`,
    ).not.toMatch(/file\s*:\s*File/);
  });

  test('services/api.ts 的 fileApi.extract 内部用 FormData.append("file_id", ...)', () => {
    const src = fs.readFileSync(API_TS, 'utf-8');
    // 找 extract 方法体（从 `extract: (` 到下一个顶层 `},` 或匹配结束）
    const idx = src.indexOf('extract: (');
    expect(idx, '找不到 fileApi.extract 方法').toBeGreaterThan(-1);
    // 截取 extract 方法体到下一个 `},`
    const endIdx = src.indexOf('},', idx);
    const body = src.slice(idx, endIdx);
    expect(
      body,
      'fileApi.extract 体内未发现 formData.append("file_id", fileId) 调用',
    ).toMatch(/formData\.append\(\s*['"]file_id['"]\s*,\s*fileId\s*\)/);
  });
});
