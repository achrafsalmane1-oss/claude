import type { NextConfig } from 'next';

const config: NextConfig = {
  // The API and dashboard both read the DB directly; nothing here is statically
  // rendered, so bail out of the build-time data fetch entirely.
  experimental: {
    serverActions: { bodySizeLimit: '1mb' },
  },
  // `postgres` and `pg-boss` are node-only; keep them out of any bundling attempt.
  serverExternalPackages: ['postgres', 'pg', 'pg-boss', 'undici'],
  output: 'standalone',
};

export default config;
