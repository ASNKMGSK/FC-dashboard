/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  experimental: {
    optimizePackageImports: [
      'lucide-react',
      'recharts',
      'framer-motion',
    ],
  },
  // 프로덕션 빌드 시 console.log 제거 (SmartFactory)
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production' ? { exclude: ['error', 'warn'] } : false,
  },
  images: {
    remotePatterns: [],
  },
  async rewrites() {
    const backendBase = process.env.BACKEND_INTERNAL_URL || 'http://127.0.0.1:8001';
    const backend = String(backendBase).replace(/\/$/, '');

    return [
      // /api/* 는 전부 백엔드로 프록시 → 브라우저는 항상 같은 오리진만 호출
      { source: '/api/:path*', destination: `${backend}/api/:path*` },
    ];
  },
};

module.exports = nextConfig;
