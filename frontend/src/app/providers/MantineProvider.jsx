'use client';

import { MantineProvider, createTheme } from '@mantine/core';

const theme = createTheme({
  primaryColor: 'teal',
  fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Oxygen, Ubuntu, Cantarell, Fira Sans, Droid Sans, Helvetica Neue, sans-serif',
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
  },
  defaultRadius: 'md',
});

export function MantineProviderWrapper({ children }) {
  return (
    <MantineProvider theme={theme}>
      {children}
    </MantineProvider>
  );
}

