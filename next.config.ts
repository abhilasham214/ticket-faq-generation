import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // On Vercel, vercel.json already routes /api/* to the Python function before Next.js
  // sees the request. Locally with plain `next dev` (no `vercel dev`), proxy /api/* to a
  // FastAPI server run separately, e.g. `uvicorn api.index:app --reload --port 8000`.
  async rewrites() {
    if (process.env.VERCEL) return [];
    const localApiUrl = process.env.LOCAL_API_URL || "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${localApiUrl}/api/:path*` }];
  },
};

export default nextConfig;
