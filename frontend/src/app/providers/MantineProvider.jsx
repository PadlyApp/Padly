'use client';

import { MantineProvider, createTheme, rem } from '@mantine/core';

const theme = createTheme({
  primaryColor: 'teal',

  colors: {
    teal: [
      '#e6fcf5',
      '#c3fae8',
      '#96f2d7',
      '#63e6be',
      '#38d9a9',
      '#20c997',
      '#12b886',
      '#0ca678',
      '#099268',
      '#087f5b',
    ],
    slate: [
      '#f8f9fa',
      '#f1f3f5',
      '#e9ecef',
      '#dee2e6',
      '#ced4da',
      '#adb5bd',
      '#868e96',
      '#495057',
      '#343a40',
      '#212529',
    ],
    coral: [
      '#fff5f5',
      '#ffe3e3',
      '#ffc9c9',
      '#ffa8a8',
      '#ff8787',
      '#ff6b6b',
      '#fa5252',
      '#f03e3e',
      '#e03131',
      '#c92a2a',
    ],
  },

  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  fontFamilyMonospace: "'JetBrains Mono', 'Fira Code', monospace",

  headings: {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontWeight: '600',
    sizes: {
      h1: { fontSize: rem(40), lineHeight: '1.15', fontWeight: '700' },
      h2: { fontSize: rem(30), lineHeight: '1.2',  fontWeight: '600' },
      h3: { fontSize: rem(22), lineHeight: '1.3',  fontWeight: '600' },
      h4: { fontSize: rem(18), lineHeight: '1.4',  fontWeight: '600' },
      h5: { fontSize: rem(16), lineHeight: '1.5',  fontWeight: '500' },
      h6: { fontSize: rem(14), lineHeight: '1.5',  fontWeight: '500' },
    },
  },

  fontSizes: {
    xs: rem(11),
    sm: rem(13),
    md: rem(15),
    lg: rem(17),
    xl: rem(20),
  },

  lineHeights: {
    xs: '1.4',
    sm: '1.5',
    md: '1.6',
    lg: '1.65',
    xl: '1.7',
  },

  spacing: {
    xs: rem(6),
    sm: rem(10),
    md: rem(16),
    lg: rem(24),
    xl: rem(36),
  },

  radius: {
    xs: rem(4),
    sm: rem(6),
    md: rem(10),
    lg: rem(16),
    xl: rem(24),
  },
  defaultRadius: 'md',

  shadows: {
    xs: '0 1px 2px rgba(0,0,0,0.04)',
    sm: '0 1px 4px rgba(0,0,0,0.07)',
    md: '0 4px 12px rgba(0,0,0,0.08)',
    lg: '0 8px 24px rgba(0,0,0,0.10)',
    xl: '0 16px 48px rgba(0,0,0,0.12)',
  },

  components: {
    Button: {
      defaultProps: { radius: 'md' },
      styles: {
        root: { fontWeight: 500, letterSpacing: '0.01em' },
      },
    },
    Card: {
      defaultProps: { radius: 'lg', shadow: 'sm' },
    },
    Paper: {
      defaultProps: { radius: 'lg' },
    },
    Badge: {
      defaultProps: { radius: 'sm' },
    },
    ActionIcon: {
      defaultProps: { radius: 'xl' },
    },
    TextInput: {
      defaultProps: { radius: 'md' },
    },
    PasswordInput: {
      defaultProps: { radius: 'md' },
    },
    Select: {
      defaultProps: { radius: 'md' },
    },
    Tabs: {
      styles: { tab: { fontWeight: 500 } },
    },
    Modal: {
      defaultProps: {
        radius: 'lg',
        centered: true,
        overlayProps: { backgroundOpacity: 0.4, blur: 4 },
      },
    },
    Notification: {
      defaultProps: { radius: 'md' },
    },
    Skeleton: {
      defaultProps: { radius: 'md' },
    },
  },

  cursorType: 'pointer',
  focusRing: 'auto',
  respectReducedMotion: true,
});

export function MantineProviderWrapper({ children }) {
  return (
    <MantineProvider theme={theme} defaultColorScheme="light">
      {children}
    </MantineProvider>
  );
}
