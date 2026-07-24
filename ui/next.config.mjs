/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emit a self-contained server bundle for a small production Docker image (deploy/).
  output: 'standalone',
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    // Don't fail `next build` on lint (CI validates types + build; lint is a separate concern).
    ignoreDuringBuilds: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
