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
  IconSparkles,
} from '@tabler/icons-react';

const NEXT_STEPS = [
  {
    icon: IconSettings,
    color: 'teal',
    label: 'Set Preferences',
    desc: 'Budget, city, move-in date',
    path: '/account?tab=preferences',
  },
  {
    icon: IconSwipe,
    color: 'orange',
    label: 'Keep Swiping',
    desc: 'Train your recommendations',
    path: '/discover',
  },
  {
    icon: IconSparkles,
    color: 'green',
    label: 'View Recommendations',
    desc: 'See your top listing matches',
    path: '/matches',
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
                padding: '0.875rem 0.5rem',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                whiteSpace: 'normal',
                wordBreak: 'break-word',
              }}
              styles={{
                inner: {
                  flexDirection: 'column',
                  gap: 6,
                  width: '100%',
                },
                label: {
                  flexDirection: 'column',
                  gap: 4,
                  width: '100%',
                  overflow: 'visible',
                },
              }}
            >
              <step.icon size={22} />
              <Text size="xs" fw={600} ta="center" style={{ lineHeight: 1.3, width: '100%' }}>
                {step.label}
              </Text>
              <Text size="xs" c="dimmed" ta="center" style={{ lineHeight: 1.3, width: '100%', whiteSpace: 'normal' }}>
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
