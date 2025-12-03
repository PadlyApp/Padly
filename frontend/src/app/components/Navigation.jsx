'use client';

import { useState } from 'react';
import { Container, Group, Text, UnstyledButton, Button, Burger, Drawer, Stack, Divider } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import Link from 'next/link';
import { useAuth } from '../contexts/AuthContext';

export function Navigation() {
  const { isAuthenticated, user, signout, isLoading } = useAuth();
  const [opened, { open, close }] = useDisclosure(false);

  const handleSignout = async () => {
    await signout();
    close(); // Close drawer after signout
  };

  const handleLinkClick = () => {
    close(); // Close drawer when a link is clicked
  };

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
          
          {/* Desktop Navigation Links */}
          {!isLoading && (
            <>
              {isAuthenticated ? (
                // Authenticated Navigation - Desktop
                <Group gap={40} visibleFrom="md">
                  <Link href="/" style={{ textDecoration: 'none' }}>
                    <UnstyledButton>
                      <Text size="md" c="#666" style={{ transition: 'color 0.2s' }}>
                        Home
                      </Text>
                    </UnstyledButton>
                  </Link>
                  <Link href="/groups" style={{ textDecoration: 'none' }}>
                    <UnstyledButton>
                      <Text size="md" c="#666" style={{ transition: 'color 0.2s' }}>
                        Groups
                      </Text>
                    </UnstyledButton>
                  </Link>
                  <Link href="/invitations" style={{ textDecoration: 'none' }}>
                    <UnstyledButton>
                      <Text size="md" c="#666" style={{ transition: 'color 0.2s' }}>
                        Invitations
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
                  <Button
                    variant="subtle"
                    color="gray"
                    onClick={handleSignout}
                    style={{ fontSize: '0.875rem' }}
                  >
                    Sign Out
                  </Button>
                </Group>
              ) : (
                // Unauthenticated Navigation - Desktop
                <Group gap="md" visibleFrom="sm">
                  <Link href="/login" style={{ textDecoration: 'none' }}>
                    <Button variant="subtle" color="gray">
                      Log In
                    </Button>
                  </Link>
                  <Link href="/signup" style={{ textDecoration: 'none' }}>
                    <Button
                      style={{
                        backgroundColor: '#20c997',
                      }}
                    >
                      Sign Up
                    </Button>
                  </Link>
                </Group>
              )}

              {/* Mobile Burger Menu */}
              <Burger
                opened={opened}
                onClick={opened ? close : open}
                hiddenFrom={isAuthenticated ? "md" : "sm"}
                size="sm"
              />
            </>
          )}
        </Group>
      </Container>

      {/* Mobile Drawer */}
      <Drawer
        opened={opened}
        onClose={close}
        position="right"
        size="xs"
        padding="md"
        title={
          <Text size="xl" fw={600} c="#111">
            Padly
          </Text>
        }
      >
        {!isLoading && (
          <>
            {isAuthenticated ? (
              // Authenticated Mobile Menu
              <Stack gap="lg">
                <Link href="/" style={{ textDecoration: 'none' }} onClick={handleLinkClick}>
                  <UnstyledButton style={{ width: '100%' }}>
                    <Text size="lg" c="#666" style={{ padding: '0.5rem 0' }}>
                      Home
                    </Text>
                  </UnstyledButton>
                </Link>
                <Link href="/groups" style={{ textDecoration: 'none' }} onClick={handleLinkClick}>
                  <UnstyledButton style={{ width: '100%' }}>
                    <Text size="lg" c="#666" style={{ padding: '0.5rem 0' }}>
                      Groups
                    </Text>
                  </UnstyledButton>
                </Link>
                <Link href="/invitations" style={{ textDecoration: 'none' }} onClick={handleLinkClick}>
                  <UnstyledButton style={{ width: '100%' }}>
                    <Text size="lg" c="#666" style={{ padding: '0.5rem 0' }}>
                      Invitations
                    </Text>
                  </UnstyledButton>
                </Link>
                <Link href="/preferences" style={{ textDecoration: 'none' }} onClick={handleLinkClick}>
                  <UnstyledButton style={{ width: '100%' }}>
                    <Text size="lg" c="#666" style={{ padding: '0.5rem 0' }}>
                      Preferences
                    </Text>
                  </UnstyledButton>
                </Link>
                <Link href="/matches" style={{ textDecoration: 'none' }} onClick={handleLinkClick}>
                  <UnstyledButton style={{ width: '100%' }}>
                    <Text size="lg" c="#666" style={{ padding: '0.5rem 0' }}>
                      Recommendations
                    </Text>
                  </UnstyledButton>
                </Link>
                <Link href="/account" style={{ textDecoration: 'none' }} onClick={handleLinkClick}>
                  <UnstyledButton style={{ width: '100%' }}>
                    <Text size="lg" c="#666" style={{ padding: '0.5rem 0' }}>
                      Account
                    </Text>
                  </UnstyledButton>
                </Link>
                
                <Divider />
                
                <Button
                  variant="subtle"
                  color="gray"
                  onClick={handleSignout}
                  fullWidth
                >
                  Sign Out
                </Button>
              </Stack>
            ) : (
              // Unauthenticated Mobile Menu
              <Stack gap="md">
                <Link href="/login" style={{ textDecoration: 'none' }} onClick={handleLinkClick}>
                  <Button variant="subtle" color="gray" fullWidth size="lg">
                    Log In
                  </Button>
                </Link>
                <Link href="/signup" style={{ textDecoration: 'none' }} onClick={handleLinkClick}>
                  <Button
                    fullWidth
                    size="lg"
                    style={{
                      backgroundColor: '#20c997',
                    }}
                  >
                    Sign Up
                  </Button>
                </Link>
              </Stack>
            )}
          </>
        )}
      </Drawer>
    </header>
  );
}

