/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      {
        source: '/groups/:path*',
        destination: '/discover',
        permanent: false,
      },
      {
        source: '/invitations',
        destination: '/discover',
        permanent: false,
      },
      {
        source: '/roommates',
        destination: '/discover',
        permanent: false,
      },
    ];
  },
};

module.exports = nextConfig;
