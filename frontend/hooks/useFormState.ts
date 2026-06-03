/**
 * 会话 + 表单状态 hook - 修复 3.6 createSession 闭包 + 重复触发 bug
 *
 * 关键设计：
 *   - 用 useEffect + 状态机（idle/loading/ready/error）确保 createSession 仅触发一次
 *   - 切 section 用稳定引用 updateSection(section) 触发后端同步
 *   - confirmSection 走乐观更新
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { message } from 'antd';
import { sessionApi, formApi, SessionData } from '../services/api';

type LoadState = 'idle' | 'loading' | 'ready' | 'error';

export interface UseFormStateReturn {
  session: SessionData | null;
  loadState: LoadState;
  currentSection: number;
  switchSection: (section: number) => Promise<void>;
  confirmSection: (formValues: Record<string, any>) => Promise<void>;
  reloadSession: () => Promise<void>;
}

export const useFormState = (autoCreate = true): UseFormStateReturn => {
  const [session, setSession] = useState<SessionData | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('idle');
  // 防重入：Strict Mode 或多次 effect 触发时只创建一次
  const createdRef = useRef(false);

  const createSession = useCallback(async () => {
    if (createdRef.current) return;
    createdRef.current = true;
    setLoadState('loading');
    try {
      const resp = await sessionApi.create();
      setSession(resp.data);
      setLoadState('ready');
      message.success('会话创建成功');
    } catch (err) {
      createdRef.current = false; // 允许重试
      setLoadState('error');
      message.error('会话创建失败');
      console.error('[useFormState] createSession failed:', err);
    }
  }, []);

  useEffect(() => {
    if (autoCreate) {
      createSession();
    }
  }, [autoCreate, createSession]);

  const reloadSession = useCallback(async () => {
    if (!session?.session_id) return;
    try {
      const resp = await sessionApi.get(session.session_id);
      setSession(resp.data);
    } catch (err) {
      console.error('[useFormState] reloadSession failed:', err);
    }
  }, [session?.session_id]);

  const switchSection = useCallback(
    async (section: number) => {
      if (!session?.session_id) return;
      try {
        await formApi.setCurrentSection(session.session_id, section);
        setSession((prev) => (prev ? { ...prev, current_section: section } : prev));
      } catch (err) {
        message.error('切换失败');
        console.error('[useFormState] switchSection failed:', err);
      }
    },
    [session?.session_id],
  );

  const confirmSection = useCallback(
    async (formValues: Record<string, any>) => {
      if (!session?.session_id) return;
      const section = session.current_section;
      try {
        await formApi.confirmSection(session.session_id, section, formValues);
        await reloadSession();
        message.success('部分已完成');
      } catch (err) {
        message.error('确认失败');
        console.error('[useFormState] confirmSection failed:', err);
      }
    },
    [session?.session_id, session?.current_section, reloadSession],
  );

  return {
    session,
    loadState,
    currentSection: session?.current_section ?? 1,
    switchSection,
    confirmSection,
    reloadSession,
  };
};
