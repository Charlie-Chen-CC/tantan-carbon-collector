/**
 * API服务层 - 碳管师收资系统
 * 封装axios，使用httpOnly Cookie进行认证
 */

import axios, { AxiosInstance, AxiosResponse } from 'axios';

// 创建axios实例
const apiClient: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  // 必须开启 withCredentials，浏览器才会自动携带 httpOnly cookie
  withCredentials: true,
});

// [已废弃] 旧版用 Bearer Token + localStorage；新版本统一用 httpOnly Cookie
// 这里保留为 no-op 是为了不破坏外部 import，但所有调用方应停止使用
export const setAuthToken = (_token: string | null): void => {
  // no-op: token 由后端 Set-Cookie 写入，前端无权限也无必要接触
};
export const getAuthToken = (): string | null => null;

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 添加请求ID便于追踪
    const requestId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    config.headers['X-Request-ID'] = requestId;
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 处理错误
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    const status = error.response?.status;
    const data = error.response?.data ?? {};
    // 新错误体系（S3.12）：后端 AppException 返回 { error_code, user_message }
    const errorCode = data.error_code;
    const userMessage = data.user_message;

    if (status === 401) {
      // 401 表示 Cookie 过期或被踢出，通过 custom event 通知 AuthProvider / router
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('auth:logout'));
      }
    }

    // 把 AppException 的 user_message 挂到 error 对象上，方便业务层 catch 时直接用
    if (errorCode) {
      (error as any).appErrorCode = errorCode;
      (error as any).appUserMessage = userMessage;
    }

    // 控制台仅打精简错误（不打印 stack、Authorization、请求体）
    if (status && status >= 500) {
      console.error('[API Error]', status, userMessage || error.message);
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

  // 使用httpOnly cookie认证获取当前用户
  getMeCookie: (): Promise<AxiosResponse<UserInfo>> =>
    apiClient.get('/auth/me/cookie'),

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

export interface SectionFile {
  id: number;
  name: string;
  size: number;
  type: string;
  status: string;
  created_at: string;
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
    fileId: string
  ): Promise<AxiosResponse<any>> => {
    // P0-9 修复：不再传 File 重新上传，而是把 upload 阶段拿到的 file_id
    // 发给后端，后端按 file_id 在 uploads/ 找文件
    const formData = new FormData();
    formData.append('file_id', fileId);
    return apiClient.post(`/extract/${sessionId}/section/${section}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  getSectionFiles: (
    sessionId: string,
    section: number
  ): Promise<AxiosResponse<{ files: SectionFile[] }>> =>
    apiClient.get(`/files/${sessionId}/section/${section}`),

  deleteFile: (fileId: number): Promise<AxiosResponse<{ success: boolean; message: string }>> =>
    apiClient.delete(`/files/${fileId}`),
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
