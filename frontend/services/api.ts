/**
 * API服务层 - 碳管师收资系统
 * 封装axios，统一Bearer Token处理
 */

import axios, { AxiosInstance, AxiosResponse } from 'axios';

// 创建axios实例
const apiClient: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Token存储
let authToken: string | null = null;

export const setAuthToken = (token: string | null) => {
  authToken = token;
  if (token) {
    localStorage.setItem('auth_token', token);
  } else {
    localStorage.removeItem('auth_token');
  }
};

export const getAuthToken = (): string | null => {
  if (authToken) return authToken;
  authToken = localStorage.getItem('auth_token');
  return authToken;
};

// 请求拦截器 - 添加Token
apiClient.interceptors.request.use(
  (config) => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // 添加请求ID便于追踪
    const requestId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    config.headers['X-Request-ID'] = requestId;
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url} [${requestId}]`);
    return config;
  },
  (error) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

// 响应拦截器 - 处理错误
apiClient.interceptors.response.use(
  (response) => {
    const requestId = response.config.headers['X-Request-ID'] as string;
    console.log(`[API Response] ${response.config.method?.toUpperCase()} ${response.config.url} [${requestId}] ${response.status}`);
    return response;
  },
  (error) => {
    const requestId = error.config?.headers?.['X-Request-ID'] as string;
    const status = error.response?.status;
    const url = error.config?.url;
    const method = error.config?.method?.toUpperCase();
    const errorMessage = error.response?.data?.detail || error.message;

    // 构建详细错误日志
    const errorLog = {
      type: 'API Error',
      requestId,
      method,
      url,
      status,
      message: errorMessage,
      stack: error.stack,
      timestamp: new Date().toISOString()
    };

    console.error('[API Error]', errorLog);

    if (status === 401) {
      // Token过期或无效，清除登录状态
      console.warn('[API Auth] Token expired or invalid, redirecting to login');
      setAuthToken(null);
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);

// ============== 认证相关API ==============

export interface RegisterData {
  username: string;
  password: string;
  email?: string;
  enterprise_name?: string;
  industry?: string;
}

export interface LoginData {
  username: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
}

export interface UserInfo {
  user_id: string;
  username: string;
  email?: string;
  enterprise_name?: string;
  industry?: string;
  created_at: string;
}

export const authApi = {
  register: (data: RegisterData): Promise<AxiosResponse<AuthResponse>> =>
    apiClient.post('/auth/register', data),

  login: (data: LoginData): Promise<AxiosResponse<AuthResponse>> =>
    apiClient.post('/auth/login', data),

  getMe: (): Promise<AxiosResponse<UserInfo>> =>
    apiClient.get('/auth/me'),

  logout: (): Promise<AxiosResponse<{ message: string }>> =>
    apiClient.post('/auth/logout'),

  updateProfile: (data: Partial<UserInfo>): Promise<AxiosResponse<{ message: string }>> =>
    apiClient.put('/auth/profile', null, { params: data }),
};

// ============== 会话相关API ==============

export interface SessionData {
  session_id: string;
  progress: Record<string, string>;
  current_section: number;
  created_at: string;
  form_data?: Record<string, any>;
  status?: string;
}

export interface CreateSessionResponse {
  session_id: string;
  progress: Record<string, string>;
  current_section: number;
  created_at: string;
}

export const sessionApi = {
  create: (): Promise<AxiosResponse<CreateSessionResponse>> =>
    apiClient.post('/session'),

  get: (sessionId: string): Promise<AxiosResponse<SessionData>> =>
    apiClient.get(`/session/${sessionId}`),

  list: (): Promise<AxiosResponse<{ sessions: SessionData[] }>> =>
    apiClient.get('/sessions'),

  delete: (sessionId: string): Promise<AxiosResponse<{ message: string }>> =>
    apiClient.delete(`/session/${sessionId}`),
};

// ============== 表单相关API ==============

export const formApi = {
  getForm: (sessionId: string): Promise<AxiosResponse<any>> =>
    apiClient.get(`/form/${sessionId}`),

  updateSection: (
    sessionId: string,
    section: number,
    field: string,
    value: any
  ): Promise<AxiosResponse<any>> =>
    apiClient.patch(
      `/form/${sessionId}/section/${section}?field=${field}&value=${value}`
    ),

  confirmSection: (
    sessionId: string,
    section: number,
    data: Record<string, any>
  ): Promise<AxiosResponse<any>> =>
    apiClient.post(`/form/${sessionId}/section/${section}/confirm`, { data }),

  setCurrentSection: (
    sessionId: string,
    section: number
  ): Promise<AxiosResponse<any>> =>
    apiClient.post(`/form/${sessionId}/current-section?section=${section}`),
};

// ============== 文件上传API ==============

export interface UploadResponse {
  file_id: string;
  file_path: string;
  status: string;
}

export const fileApi = {
  upload: (
    sessionId: string,
    section: number,
    file: File
  ): Promise<AxiosResponse<UploadResponse>> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('section', section.toString());
    formData.append('session_id', sessionId);

    return apiClient.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  extract: (
    sessionId: string,
    section: number,
    file: File
  ): Promise<AxiosResponse<any>> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post(`/extract/${sessionId}/section/${section}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// ============== AI对话API ==============

export interface ChatResponse {
  content: string;
  intent: string;
  suggestions?: string[];
}

export const chatApi = {
  send: (
    sessionId: string,
    message: string,
    context?: Record<string, any>
  ): Promise<AxiosResponse<ChatResponse>> =>
    apiClient.post('/chat', { session_id: sessionId, message, context }),
};

// ============== 修改API ==============

export interface ModifyData {
  section: number;
  field: string;
  old_value: any;
  new_value: any;
  reason?: string;
}

export const modifyApi = {
  modify: (
    sessionId: string,
    data: ModifyData
  ): Promise<AxiosResponse<any>> =>
    apiClient.post(`/modify/${sessionId}`, data),
};

// ============== 历史记录API ==============

export const historyApi = {
  get: (
    sessionId: string,
    limit: number = 100
  ): Promise<AxiosResponse<{ session_id: string; history: any[] }>> =>
    apiClient.get(`/history/${sessionId}?limit=${limit}`),
};

export default apiClient;
