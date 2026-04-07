'use client';

import {
  Modal,
  Title,
  Text,
  Button,
  Stack,
  Group,
  ThemeIcon,
  Box,
} from '@mantine/core';
import {
  IconSettings,
  IconUsers,
  IconHome,
  IconSwipe,
  IconArrowRight,
} from '@tabler/icons-react';

const STEPS = [
  {
    icon: IconSettings,
    color: 'teal',
    title: 'Set your preferences',
    desc: 'Tell us your budget, target city, move-in date, and lifestyle — so we only show what fits.',
  },
  {
    icon: IconUsers,
    color: 'blue',
    title: 'Discover compatible people',
    desc: 'Explore listings and compare fit signals to find people and places that match your lifestyle.',
  },
  {
    icon: IconHome,
    color: 'violet',
    title: 'Get matched to listings',
    desc: 'Receive personalized listing recommendations ranked by compatibility.',
  },
  {
    icon: IconSwipe,
    color: 'orange',
    title: 'Swipe to refine',
    desc: 'Like or pass on listings — every swipe makes your future recommendations smarter.',
  },
];

export function WelcomeModal({ opened, onStart, onSkip }) {
  return (
    <Modal
      opened={opened}
      onClose={onSkip}
      size="lg"
      radius="lg"
      centered
      withCloseButton={false}
      overlayProps={{ backgroundOpacity: 0.4, blur: 3 }}
      styles={{
        body: { padding: '2rem' },
      }}
    >
      <Stack gap="xl" align="center">
        <Box ta="center">
          <Text style={{ fontSize: '2.5rem', lineHeight: 1 }} mb="sm">
            🏠
          </Text>
          <Title order={2} style={{ color: '#111', fontWeight: 700 }}>
            Welcome to Padly!
          </Title>
          <Text size="md" c="dimmed" mt="xs" maw={420} mx="auto">
            Find housing and compatible roommates in four simple steps.
            Let us show you around.
          </Text>
        </Box>

        <Stack gap="md" style={{ width: '100%' }}>
          {STEPS.map((step, i) => (
            <Group
              key={i}
              gap="md"
              align="flex-start"
              style={{
                padding: '0.875rem 1rem',
                borderRadius: '12px',
                backgroundColor: '#f8f9fa',
              }}
            >
              <ThemeIcon
                size={40}
                radius="xl"
                variant="light"
                color={step.color}
                style={{ flexShrink: 0 }}
              >
                <step.icon size={20} />
              </ThemeIcon>
              <Box style={{ flex: 1 }}>
                <Text fw={600} size="sm" style={{ color: '#111' }}>
                  {step.title}
                </Text>
                <Text size="xs" c="dimmed" mt={2}>
                  {step.desc}
                </Text>
              </Box>
            </Group>
          ))}
        </Stack>

        <Group justify="center" gap="md" style={{ width: '100%' }}>
          <Button
            variant="subtle"
            color="gray"
            onClick={onSkip}
          >
            Skip tour
          </Button>
          <Button
            size="md"
            color="teal"
            rightSection={<IconArrowRight size={18} />}
            onClick={onStart}
            style={{ minWidth: 160 }}
          >
            Show me around
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
