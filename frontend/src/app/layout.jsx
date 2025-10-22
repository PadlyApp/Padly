'use client';

import './globals.css';
import { MantineProviderWrapper } from './providers/MantineProvider';
import { QueryProvider } from './providers/QueryProvider';

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <title>Padly - Find Your Perfect Housing Match</title>
        <meta name="description" content="A trusted platform for students, interns, and early-career professionals to find housing and compatible roommates." />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>
        <QueryProvider>
          <MantineProviderWrapper>
            {children}
          </MantineProviderWrapper>
        </QueryProvider>
      </body>
    </html>
  );
}

