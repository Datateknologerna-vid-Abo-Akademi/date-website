import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const backendOrigin =
      process.env.BACKEND_API_ORIGIN ?? process.env.NEXT_PUBLIC_BACKEND_API_ORIGIN;
    if (!backendOrigin) return [];

    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendOrigin}/api/v1/:path*`,
      },
      {
        source: "/media/:path*",
        destination: `${backendOrigin}/media/:path*`,
      },
      {
        source: "/static/:path*",
        destination: `${backendOrigin}/static/:path*`,
      },
      {
        source: "/favicon.ico",
        destination: `${backendOrigin}/static/core/images/logo.ico`,
      },
    ];
  },
};

export default nextConfig;
