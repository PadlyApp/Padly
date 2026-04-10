'use client';

import { ActionIcon, Group, Text } from '@mantine/core';
import { IconMinus, IconPlus } from '@tabler/icons-react';

/**
 * A +/- counter for bedrooms or bathrooms.
 * A value of `null` renders as "Any" and the decrement button is disabled.
 */
export function RoomCounter({ label, value, onChange }) {
  const decrement = () => onChange(value === null || value <= 1 ? null : value - 1);
  const increment = () => onChange(value === null ? 1 : value + 1);

  return (
    <Group justify="space-between" align="center" py="xs">
      <Text size="sm" fw={500} style={{ minWidth: 100 }}>{label}</Text>
      <Group gap="md" align="center">
        <ActionIcon
          variant="outline"
          radius="xl"
          size="lg"
          onClick={decrement}
          disabled={value === null}
          style={{ borderColor: '#dee2e6', color: '#495057' }}
        >
          <IconMinus size={14} />
        </ActionIcon>
        <Text size="sm" fw={500} style={{ minWidth: 36, textAlign: 'center' }}>
          {value === null ? 'Any' : value}
        </Text>
        <ActionIcon
          variant="outline"
          radius="xl"
          size="lg"
          onClick={increment}
          style={{ borderColor: '#dee2e6', color: '#495057' }}
        >
          <IconPlus size={14} />
        </ActionIcon>
      </Group>
    </Group>
  );
}
