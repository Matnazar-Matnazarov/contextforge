import type { NextConfig } from "next";

// In production Caddy routes /api/* to Django. For `npm run dev` without Caddy, set API_PROXY_URL.
const apiProxy = process.env.API_PROXY_URL;

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return apiProxy ? [{ source: "/api/:path*", destination: `${apiProxy}/api/:path*` }] : [];
  },
};

export default nextConfig;
