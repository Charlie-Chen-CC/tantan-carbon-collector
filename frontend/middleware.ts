/**
 * 路由守卫 - 服务端 middleware
 *
 * 拦截 /dashboard/* 路径：
 *   - 有 httpOnly `auth_token` cookie → 放行
 *   - 无 cookie → 重定向 /login
 *
 * 实际认证校验仍由后端 /api/auth/me 完成（防止伪造 cookie）。
 * 这里只做"未登录用户不渲染 dashboard 页面"的快速分流，避免闪烁。
 *
 * 配套：客户端 useAuth + 401 事件做兜底（middleware 跑在 edge，复杂校验交客户端）。
 */
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PROTECTED_PATHS = ['/dashboard'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (!isProtected) {
    return NextResponse.next();
  }

  const token = request.cookies.get('auth_token');
  if (!token) {
    const loginUrl = new URL('/login', request.url);
    // 保留原始路径，登录成功后跳回
    loginUrl.searchParams.set('from', pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*'],
};
