/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emit a self-contained server bundle for a small production Docker image (deploy/).
  output: 'standalone',
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
