'use client';

import { useState } from 'react';
import { Container, Group, Text, UnstyledButton, Button, Burger, Drawer, Stack, Divider, Box } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { IconHome } from '@tabler/icons-react';
import { useAuth } from '../contexts/AuthContext';
import { usePadlyTour } from '../contexts/TourContext';

export function Navigation() {
  const { isAuthenticated, user, signout, isLoading } = useAuth();
  const { isTourPaused, resumeTour } = usePadlyTour();
  const [opened, { open, close }] = useDisclosure(false);
  const pathname = usePathname();
  const isAdmin = user?.profile?.role === 'admin';

  const handleSignout = async () => {
    await signout();
    close();
  };

  const handleLinkClick = () => {
    close();
  };

  const LogoMark = () => (
    <Group gap="xs" align="center" style={{ textDecoration: 'none' }}>
      <Box style={{
        width: 28, height: 28, borderRadius: 8,
        background: '#20c997',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <IconHome size={16} color="white" />
      </Box>
      <Text size="lg" fw={700} style={{ color: '#212529', letterSpacing: '-0.01em' }}>
        Padly
      </Text>
    </Group>
  );

  return (
    <header style={{
      position: 'sticky',
      top: 0,
      zIndex: 100,
      backgroundColor: 'rgba(255,255,255,0.92)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      borderBottom: '1px solid #e9ecef',
    }}>
      <Container size="xl" style={{ padding: '1.25rem 3rem' }}>
        <Group justify="space-between" style={{ height: '50px' }}>
          {/* Logo */}
          <Link href="/" style={{ textDecoration: 'none' }}>
            <LogoMark />
          </Link>

          {/* Desktop Navigation Links */}
          {!isLoading && (
            <>
              {isAuthenticated ? (
                // Authenticated Navigation - Desktop
                <Group gap={40} visibleFrom="md">
                  <Link href="/" style={{ textDecoration: 'none' }}>
                    <UnstyledButton className={`nav-link ${pathname === '/' ? 'active' : ''}`}>
                      Home
                    </UnstyledButton>
                  </Link>
                  <Link href="/groups" style={{ textDecoration: 'none' }} data-tour="nav-groups">
                    <UnstyledButton className={`nav-link ${pathname === '/groups' ? 'active' : ''}`}>
                      Groups
                    </UnstyledButton>
                  </Link>
                  <Link href="/discover" style={{ textDecoration: 'none' }} data-tour="nav-discover">
                    <UnstyledButton className={`nav-link ${pathname === '/discover' ? 'active' : ''}`}>
                      Discover
                    </UnstyledButton>
                  </Link>
                  <Link href="/matches" style={{ textDecoration: 'none' }} data-tour="nav-matches">
                    <UnstyledButton className={`nav-link ${pathname === '/matches' ? 'active' : ''}`}>
                      Recommendations
                    </UnstyledButton>
                  </Link>
                  <Link href="/account" style={{ textDecoration: 'none' }} data-tour="nav-account">
                    <UnstyledButton className={`nav-link ${pathname === '/account' ? 'active' : ''}`}>
                      Account
                    </UnstyledButton>
                  </Link>
                  {isAdmin && (
                    <Link href="/admin/evaluation" style={{ textDecoration: 'none' }}>
                      <UnstyledButton className={`nav-link ${pathname.startsWith('/admin') ? 'active' : ''}`}>
                        Admin
                      </UnstyledButton>
                    </Link>
                  )}
                  {isTourPaused && (
                    <Button
                      variant="light"
                      color="teal"
                      size="xs"
                      onClick={resumeTour}
                      style={{ fontSize: '0.8rem' }}
                    >
                      Resume Tour
                    </Button>
                  )}
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
                    <Button color="teal">
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
        title={<LogoMark />}
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
                <Link href="/discover" style={{ textDecoration: 'none' }} onClick={handleLinkClick}>
                  <UnstyledButton style={{ width: '100%' }}>
                    <Text size="lg" c="#666" style={{ padding: '0.5rem 0' }}>
                      Discover
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
                {isAdmin && (
                  <Link href="/admin/evaluation" style={{ textDecoration: 'none' }} onClick={handleLinkClick}>
                    <UnstyledButton style={{ width: '100%' }}>
                      <Text size="lg" c="#666" style={{ padding: '0.5rem 0' }}>
                        Admin
                      </Text>
                    </UnstyledButton>
                  </Link>
                )}

                <Divider />

                {isTourPaused && (
                  <Button
                    variant="light"
                    color="teal"
                    fullWidth
                    onClick={() => { resumeTour(); close(); }}
                  >
                    Resume Tour
                  </Button>
                )}

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
                    color="teal"
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
