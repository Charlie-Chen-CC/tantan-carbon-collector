'use client';

import { useEffect } from 'react';
import { ConfigProvider } from 'antd';
import { useRouter } from 'next/navigation';
import { initAuthEffects, useAuthStore } from '../store/authStore';

export default function Providers({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();

  useEffect(() => {
    // 启动时检查 cookie 认证 + 监听 401 事件
    initAuthEffects();

    // 401 触发跳转登录页
    const handler = () => {
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        router.push('/login');
      }
    };
    window.addEventListener('auth:logout', handler);
    return () => window.removeEventListener('auth:logout', handler);
  }, [router]);

  return (
    <ConfigProvider>
      {children}
    </ConfigProvider>
  );
}
