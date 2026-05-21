import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",   // Docker 배포용 standalone 빌드
};

export default nextConfig;
