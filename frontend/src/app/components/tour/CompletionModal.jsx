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
  SimpleGrid,
} from '@mantine/core';
import {
  IconCheck,
  IconSettings,
  IconSwipe,
  IconUsers,
} from '@tabler/icons-react';

const NEXT_STEPS = [
  {
    icon: IconSettings,
    color: 'teal',
    label: 'Set Preferences',
    desc: 'Budget, city, move-in date',
    path: '/preferences',
  },
  {
    icon: IconSwipe,
    color: 'orange',
    label: 'Keep Swiping',
    desc: 'Train your recommendations',
    path: '/discover',
  },
  {
    icon: IconUsers,
    color: 'blue',
    label: 'Find a Group',
    desc: 'Browse roommate groups',
    path: '/groups',
  },
];

export function CompletionModal({ opened, onClose, onGoTo }) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      size="md"
      radius="lg"
      centered
      withCloseButton={false}
      overlayProps={{ backgroundOpacity: 0.4, blur: 3 }}
      styles={{
        body: { padding: '2rem' },
      }}
    >
      <Stack gap="lg" align="center">
        <ThemeIcon size={64} radius="xl" color="teal" variant="light">
          <IconCheck size={32} />
        </ThemeIcon>

        <Box ta="center">
          <Title order={2} style={{ color: '#111', fontWeight: 700 }}>
            You're all set!
          </Title>
          <Text size="md" c="dimmed" mt="xs" maw={380} mx="auto">
            You've seen how Padly works. Here's what to do next — pick
            whichever feels right to start with.
          </Text>
        </Box>

        <SimpleGrid cols={3} spacing="sm" style={{ width: '100%' }}>
          {NEXT_STEPS.map((step) => (
            <Button
              key={step.path}
              variant="light"
              color={step.color}
              onClick={() => onGoTo(step.path)}
              style={{
                height: 'auto',
                padding: '1rem 0.75rem',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
              }}
              styles={{
                inner: {
                  flexDirection: 'column',
                  gap: 6,
                },
                label: {
                  flexDirection: 'column',
                  gap: 4,
                },
              }}
            >
              <step.icon size={22} />
              <Text size="xs" fw={600} ta="center" style={{ lineHeight: 1.3 }}>
                {step.label}
              </Text>
              <Text size="xs" c="dimmed" ta="center" style={{ lineHeight: 1.3 }}>
                {step.desc}
              </Text>
            </Button>
          ))}
        </SimpleGrid>

        <Button
          variant="subtle"
          color="gray"
          size="sm"
          onClick={onClose}
        >
          Stay here and swipe
        </Button>
      </Stack>
    </Modal>
  );
}
