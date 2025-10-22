'use client';

import { Container, Group, Text, UnstyledButton } from '@mantine/core';
import Link from 'next/link';

export function Navigation() {
  return (
    <header style={{ borderBottom: '1px solid #f1f1f1' }}>
      <Container size="xl" style={{ padding: '1.25rem 3rem' }}>
        <Group justify="space-between" style={{ height: '50px' }}>
          {/* Logo */}
          <Link href="/" style={{ textDecoration: 'none' }}>
            <Text size="xl" fw={600} c="#111">
              Padly
            </Text>
          </Link>
          
          {/* Navigation Links */}
          <Group gap={40} visibleFrom="md">
            <Link href="/" style={{ textDecoration: 'none' }}>
              <UnstyledButton>
                <Text size="md" c="#666" style={{ transition: 'color 0.2s' }}>
                  Home
                </Text>
              </UnstyledButton>
            </Link>
            <Link href="/preferences" style={{ textDecoration: 'none' }}>
              <UnstyledButton>
                <Text size="md" c="#666" style={{ transition: 'color 0.2s' }}>
                  Preferences
                </Text>
              </UnstyledButton>
            </Link>
            <Link href="/matches" style={{ textDecoration: 'none' }}>
              <UnstyledButton>
                <Text size="md" c="#666" style={{ transition: 'color 0.2s' }}>
                  Recommendations
                </Text>
              </UnstyledButton>
            </Link>
            <Link href="/account" style={{ textDecoration: 'none' }}>
              <UnstyledButton>
                <Text size="md" c="#666" style={{ transition: 'color 0.2s' }}>
                  Account
                </Text>
              </UnstyledButton>
            </Link>
          </Group>
        </Group>
      </Container>
    </header>
  );
}

