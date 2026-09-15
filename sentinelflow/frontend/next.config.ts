import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    // standalone is for Docker/self-hosted. Vercel manages its own output format.
    output: process.env.VERCEL ? undefined : "standalone",
    reactStrictMode: true,
    poweredByHeader: false,
    deploymentId: process.env.DEPLOYMENT_VERSION,
    generateBuildId: async () => process.env.DEPLOYMENT_VERSION ?? "local-dev",
    async headers() {
        return [
            {
                source: "/:path*",
                headers: [
                    { key: "X-Accel-Buffering", value: "no" },
                    { key: "X-Content-Type-Options", value: "nosniff" },
                    { key: "Referrer-Policy", value: "same-origin" },
                ],
            },
        ];
    },
};

export default nextConfig;
