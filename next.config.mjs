/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    // Lint is optional here; do not fail production builds on lint.
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
