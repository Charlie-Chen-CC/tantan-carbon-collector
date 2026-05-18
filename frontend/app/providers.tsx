'use client';

import { ConfigProvider } from 'antd';
import { AuthProvider } from '../store/authStore';

export default function Providers({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ConfigProvider>
      <AuthProvider>
        {children}
      </AuthProvider>
    </ConfigProvider>
  );
}