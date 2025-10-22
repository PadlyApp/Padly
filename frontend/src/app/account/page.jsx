'use client';

import { Container, Title, Text, Stack, Box } from '@mantine/core';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';

export default function AccountPage() {
  return (
    <ProtectedRoute>
      <AccountPageContent />
    </ProtectedRoute>
  );
}

function AccountPageContent() {
  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <Navigation />
      
      <Container size="md" style={{ padding: '4rem 2rem' }}>
        <Stack gap="xl">
          <Stack align="center" gap="lg">
            <Title 
              order={1} 
              style={{ 
                fontSize: '2.5rem', 
                fontWeight: 500,
                color: '#111',
                textAlign: 'center'
              }}
            >
              Your Account
            </Title>
            <Text 
              size="lg" 
              c="dimmed" 
              style={{ 
                maxWidth: '42rem', 
                textAlign: 'center',
                color: '#666'
              }}
            >
              Manage your profile and settings
            </Text>
          </Stack>

          {/* Placeholder for account details */}
          <Box 
            style={{ 
              padding: '3rem', 
              borderRadius: '1rem', 
              border: '1px solid #f1f1f1',
              textAlign: 'center'
            }}
          >
            <Text size="lg" c="dimmed">
              Account management coming soon...
            </Text>
          </Box>
        </Stack>
      </Container>
    </Box>
  );
}

