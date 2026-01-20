/** @type {import('next').NextConfig} */
const nextConfig = {
    // 注意：API 代理由 Nginx 处理，Next.js 不再做 rewrite
    // 本地开发时如果需要代理，可以取消注释下面的配置
    // async rewrites() {
    //     return [
    //         {
    //             source: '/api/:path*',
    //             destination: 'http://localhost:8000/api/:path*',
    //         },
    //     ]
    // },
}

module.exports = nextConfig
