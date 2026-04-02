'use client';

import './globals.css';
import { MantineProviderWrapper } from './providers/MantineProvider';
import { QueryProvider } from './providers/QueryProvider';
import { AuthProvider } from './contexts/AuthContext';
import { PadlyTourProvider } from './contexts/TourContext';
import { TourProvider } from '@reactour/tour';
import { AppTour } from './components/tour/AppTour';
import { Analytics } from '@vercel/analytics/next';

const reactourStyles = {
  popover: (base) => ({
    ...base,
    borderRadius: '16px',
    padding: 0,
    boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
    border: 'none',
    background: 'transparent',
  }),
  maskWrapper: (base) => ({
    ...base,
    color: 'rgba(0, 0, 0, 0.45)',
  }),
  maskArea: (base) => ({
    ...base,
    rx: 12,
  }),
  badge: () => ({ display: 'none' }),
  controls: () => ({ display: 'none' }),
  close: () => ({ display: 'none' }),
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
        <title>Padly - Find Your Perfect Housing Match</title>
        <meta name="description" content="A trusted platform for students, interns, and early-career professionals to find housing and compatible roommates." />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>
        <QueryProvider>
          <MantineProviderWrapper>
            <AuthProvider>
              <PadlyTourProvider>
                <TourProvider
                  steps={[]}
                  styles={reactourStyles}
                  showBadge={false}
                  showCloseButton={false}
                  showNavigation={false}
                  disableDotsNavigation
                  disableKeyboardNavigation
                  onClickMask={() => {}}
                  padding={{ mask: 8, popover: [16, 12] }}
                  scrollSmooth
                >
                  <AppTour />
                  {children}
                </TourProvider>
              </PadlyTourProvider>
            </AuthProvider>
          </MantineProviderWrapper>
        </QueryProvider>
        <Analytics />
      </body>
    </html>
  );
}

