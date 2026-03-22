'use client';

import { Paper, Text, Title, Button, Group, Badge, Stack, CloseButton } from '@mantine/core';
import { IconArrowRight, IconArrowLeft, IconCheck } from '@tabler/icons-react';

export function TourTooltip({
  title,
  description,
  currentStep,
  totalSteps,
  onNext,
  onPrev,
  onClose,
  isLastStep,
  nextLabel,
  icon,
  hideNext,
}) {
  return (
    <Paper
      shadow="xl"
      radius="lg"
      p="lg"
      style={{
        maxWidth: 340,
        border: '1px solid #e9ecef',
        position: 'relative',
      }}
    >
      <CloseButton
        size="sm"
        style={{ position: 'absolute', top: 12, right: 12 }}
        onClick={onClose}
        aria-label="Skip tour"
      />

      <Stack gap="sm">
        <Group gap="xs" align="center">
          {icon && (
            <Text style={{ fontSize: '1.5rem', lineHeight: 1 }}>{icon}</Text>
          )}
          <Badge
            size="sm"
            variant="light"
            color="teal"
            style={{ fontWeight: 600 }}
          >
            {currentStep + 1} of {totalSteps}
          </Badge>
        </Group>

        <Title order={4} style={{ color: '#111', fontWeight: 600, paddingRight: 24 }}>
          {title}
        </Title>

        <Text size="sm" c="dimmed" style={{ lineHeight: 1.6 }}>
          {description}
        </Text>

        <Group justify="space-between" mt="xs">
          {currentStep > 0 && !hideNext ? (
            <Button
              variant="subtle"
              color="gray"
              size="xs"
              leftSection={<IconArrowLeft size={14} />}
              onClick={onPrev}
            >
              Back
            </Button>
          ) : (
            <Button
              variant="subtle"
              color="gray"
              size="xs"
              onClick={onClose}
            >
              Skip tour
            </Button>
          )}

          {hideNext ? (
            <Badge variant="light" color="orange" size="lg" style={{ fontWeight: 500 }}>
              Try it now ↑
            </Badge>
          ) : (
            <Button
              size="xs"
              color="teal"
              rightSection={isLastStep ? <IconCheck size={14} /> : <IconArrowRight size={14} />}
              onClick={onNext}
            >
              {nextLabel || (isLastStep ? 'Finish' : 'Next')}
            </Button>
          )}
        </Group>
      </Stack>
    </Paper>
  );
}
