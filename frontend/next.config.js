// Next.js配置
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Phase 6.9：standalone 输出让 Docker 镜像能不带 node_modules 运行（约 80MB 镜像）
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*'
      }
    ]
  }
}

module.exports = nextConfig
