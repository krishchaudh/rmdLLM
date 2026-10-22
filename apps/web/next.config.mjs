/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // standalone output is for the Docker image; Vercel manages its own output format.
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
};
export default nextConfig;
