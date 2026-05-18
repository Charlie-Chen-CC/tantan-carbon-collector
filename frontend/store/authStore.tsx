'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authApi, setAuthToken, UserInfo, LoginData, RegisterData } from '../services/api';

interface AuthState {
  user: UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextType extends AuthState {
  login: (data: LoginData) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // 检查认证状态
  const checkAuth = async () => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      setState({ user: null, isAuthenticated: false, isLoading: false });
      return;
    }

    try {
      const response = await authApi.getMe();
      setState({
        user: response.data,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (err: any) {
      console.error('[Auth] 检查认证状态失败:', err);
      setAuthToken(null);
      setState({ user: null, isAuthenticated: false, isLoading: false });
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  const login = async (data: LoginData) => {
    const response = await authApi.login(data);
    setAuthToken(response.data.access_token);
    setState({
      user: {
        user_id: response.data.user_id,
        username: response.data.username,
        created_at: new Date().toISOString(),
      },
      isAuthenticated: true,
      isLoading: false,
    });
  };

  const register = async (data: RegisterData) => {
    console.log('注册数据:', data);
    try {
      const response = await authApi.register(data);
      console.log('注册响应:', response.data);
      setAuthToken(response.data.access_token);
      setState({
        user: {
          user_id: response.data.user_id,
          username: response.data.username,
          created_at: new Date().toISOString(),
        },
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error: any) {
      console.error('注册失败:', error);
      console.error('error.response:', error.response);
      console.error('error.message:', error.message);
      const errorMessage = error.response?.data?.detail || error.message || '注册失败';
      throw new Error(errorMessage);
    }
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } finally {
      setAuthToken(null);
      setState({ user: null, isAuthenticated: false, isLoading: false });
    }
  };

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
