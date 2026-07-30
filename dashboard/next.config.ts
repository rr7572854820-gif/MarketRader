import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pins the workspace root to this directory - without it, Next.js
  // walks up looking for a lockfile and finds an unrelated one in the
  // user's home directory, which produces a spurious "wrong root"
  // warning on every build/dev start.
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
