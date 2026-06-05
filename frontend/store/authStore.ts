/**
 * 认证状态 - zustand store（Phase 3.1）
 *
 * 后端用 httpOnly cookie，前端无 token 概念。
 * 401 由 services/api.ts 派发 'auth:logout' 事件，本 store 监听并清状态。
 * 组件用 `useAuth()` 拿当前 state + login/register/logout/checkAuth 方法。
 */
import { create } from 'zustand';
import { authApi, LoginData, RegisterData, UserInfo } from '../services/api';

interface AuthState {
  user: UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginData) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

// P0-5 修复（2026-06-04）：登出 / 401 时清理 localStorage 里残留的 AI 对话历史。
// 之前 logout() 只清服务端 cookie + zustand state，useAIChat.ts:62 的 useEffect
// 会把 conversations 序列化为 'ai_conversations' 写入 localStorage 并留在那里，
// 下一个用户登录后能看到上一用户的对话 → GDPR / 个人信息保护法违规。
// 详见 docs/CODE_REVIEW_2026-06-03.md 4.3
const AI_CONVERSATIONS_KEY = 'ai_conversations';

function clearPersistedAuthState(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(AI_CONVERSATIONS_KEY);
  } catch {
    // localStorage 不可用（隐私模式 / quota）静默失败
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (data) => {
    const response = await authApi.login(data);
    set({
      user: {
        user_id: response.data.user_id,
        username: response.data.username,
        created_at: new Date().toISOString(),
      },
      isAuthenticated: true,
      isLoading: false,
    });
  },

  register: async (data) => {
    const response = await authApi.register(data);
    set({
      user: {
        user_id: response.data.user_id,
        username: response.data.username,
        created_at: new Date().toISOString(),
      },
      isAuthenticated: true,
      isLoading: false,
    });
  },

  logout: async () => {
    try {
      await authApi.logout();
    } finally {
      clearPersistedAuthState();
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  checkAuth: async () => {
    try {
      const response = await authApi.getMe();
      set({ user: response.data, isAuthenticated: true, isLoading: false });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));

/**
 * 兼容旧 React Context API（dashboard / login 页面用）
 * 返回当前 state + 4 个 action
 */
export const useAuth = () => {
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);
  const login = useAuthStore((s) => s.login);
  const register = useAuthStore((s) => s.register);
  const logout = useAuthStore((s) => s.logout);
  const checkAuth = useAuthStore((s) => s.checkAuth);
  return { user, isAuthenticated, isLoading, login, register, logout, checkAuth };
};

/**
 * 启动时调用一次：检查 cookie 认证 + 监听 401 事件。
 * 在 app/providers.tsx 中挂载。
 */
export const initAuthEffects = () => {
  if (typeof window === 'undefined') return;
  useAuthStore.getState().checkAuth();
  window.addEventListener('auth:logout', () => {
    clearPersistedAuthState();
    useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false });
  });
};
