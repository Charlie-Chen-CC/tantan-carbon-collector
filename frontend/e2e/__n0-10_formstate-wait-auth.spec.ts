/**
 * P0-10 守门测试 - useFormState 不在 auth check 完成前触发 createSession
 *
 * WHY:
 *   docs/CODE_REVIEW_2026-06-03.md 4.2【Critical】：useFormState(true) 总是立刻
 *   挂载，useEffect 立即 createSession()。providers.tsx 的 initAuthEffects
 *   也在同一帧 checkAuth()，两条请求赛跑。401 噪声 + 时序脆弱——
 *   后端若放行 /api/session 未认证调用会产生孤儿 session。
 *
 *   修后：
 *   1. useFormState 接收 enabled: boolean 参数
 *   2. enabled=false 时不触发 createSession
 *   3. dashboard 调用 useFormState(true) 改为 useFormState(!!user)——
 *      auth check 完成且 user 非空才创建 session
 *
 * 守门 3 件套（AST 分析，不跑 e2e）：
 *   1. useFormState 签名含 enabled 参数
 *   2. useFormState useEffect 仅在 enabled=true 时调 createSession
 *   3. dashboard page.tsx 调 useFormState 时传 !!user（或等价动态条件），
 *      不是 hardcoded true
 */
import fs from 'fs';
import path from 'path';
import { test, expect } from '@playwright/test';

const USE_FORM_STATE = path.resolve(__dirname, '../hooks/useFormState.ts');
const DASHBOARD = path.resolve(__dirname, '../app/dashboard/page.tsx');

test.describe('P0-10 useFormState 等待 auth check', () => {
  test('useFormState 签名接受 enabled 参数', () => {
    const src = fs.readFileSync(USE_FORM_STATE, 'utf-8');
    // 函数签名：useFormState = (enabled = true): UseFormStateReturn =>
    expect(
      src,
      'useFormState 函数签名应接受 enabled: boolean 参数',
    ).toMatch(/useFormState\s*=\s*\(\s*enabled[^)]*\)\s*:/);
  });

  test('useFormState useEffect 仅在 enabled=true 时调 createSession', () => {
    const src = fs.readFileSync(USE_FORM_STATE, 'utf-8');
    // 期望模式：if (enabled) { createSession(); }
    // 或      if (autoCreate && enabled) { ... }
    expect(
      src,
      'useFormState useEffect 体内未在 enabled 守卫下调用 createSession',
    ).toMatch(/if\s*\(\s*enabled\s*\)\s*\{[\s\S]*?createSession\s*\(/);
  });

  test('dashboard/page.tsx 调 useFormState 时传动态条件（不是 hardcoded true）', () => {
    const src = fs.readFileSync(DASHBOARD, 'utf-8');
    // 不能是 useFormState(true) 或 useFormState() 默认 true
    // 应该是 useFormState(!!user) / useFormState(enabled) / useFormState(isReady)
    expect(
      src,
      'dashboard 仍用 useFormState(true) 或默认 true 调用，P0-10 修复未生效',
    ).not.toMatch(/useFormState\s*\(\s*true\s*\)/);
    expect(
      src,
      'dashboard 仍用 useFormState() 默认 true 调用，P0-10 修复未生效',
    ).not.toMatch(/useFormState\s*\(\s*\)/);
    // 应有动态条件
    expect(
      src,
      'dashboard 未传动态 enabled 条件（应传 !!user / enabled / isAuthenticated）',
    ).toMatch(/useFormState\s*\(\s*(!!\w+|\w+\s*&&|\w+\s*\?)/);
  });
});
