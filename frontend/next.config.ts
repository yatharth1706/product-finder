import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Load product images straight from the stores' CDNs. The backend already asks
    // each CDN for a small size, so a resize hop through Vercel only adds latency.
    unoptimized: true,
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
