import { Skeleton, Box, Card, Grid, Stack, Group, Divider } from '@mantine/core';

/**
 * Skeleton for a listing card in the recommendations/matches grid.
 * Mirrors the Card layout in matches/page.jsx.
 */
export function SkeletonListingCard() {
  return (
    <Card
      shadow="sm"
      radius="lg"
      style={{
        overflow: 'hidden',
        border: '1px solid #e9ecef',
        backgroundColor: '#fff',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Image area — 66% aspect ratio, same as real cards */}
      <Card.Section>
        <Box style={{ position: 'relative', paddingBottom: '66%', overflow: 'hidden', backgroundColor: '#f0f0f0' }}>
          <Skeleton
            style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}
            radius={0}
          />
        </Box>
      </Card.Section>

      <Stack gap="xs" style={{ padding: '1.25rem', flex: 1 }}>
        {/* Title */}
        <Skeleton height={18} width="72%" radius="sm" />
        {/* Location */}
        <Skeleton height={13} width="52%" radius="sm" />
        {/* Bed/bath/sqft details */}
        <Skeleton height={13} width="42%" radius="sm" />
        {/* Badges row */}
        <Group gap="xs">
          <Skeleton height={22} width={72} radius="xl" />
          <Skeleton height={22} width={60} radius="xl" />
        </Group>
        {/* Price */}
        <Skeleton height={26} width="35%" radius="sm" style={{ marginTop: 'auto', paddingTop: '0.5rem' }} />
        {/* Action buttons */}
        <Stack gap="xs" mt="xs">
          <Skeleton height={34} radius="md" />
          <Skeleton height={34} radius="md" />
        </Stack>
      </Stack>
    </Card>
  );
}

/**
 * Skeleton for the full listing detail page (/listings/[id]).
 * Mirrors the two-column Grid layout.
 */
export function SkeletonListingDetail() {
  return (
    <Grid gutter="xl">
      {/* Left column — images */}
      <Grid.Col span={{ base: 12, md: 7 }}>
        <Stack gap="sm">
          {/* Hero image */}
          <Skeleton height={500} radius="lg" />
          {/* Thumbnail strip */}
          <Group gap="xs" wrap="nowrap">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} height={60} width={80} radius="sm" style={{ flexShrink: 0 }} />
            ))}
          </Group>
        </Stack>
      </Grid.Col>

      {/* Right column — info */}
      <Grid.Col span={{ base: 12, md: 5 }}>
        <Stack gap="lg">
          {/* Title */}
          <Stack gap={6}>
            <Skeleton height={34} width="80%" radius="sm" />
            <Skeleton height={14} width="55%" radius="sm" />
          </Stack>

          {/* Price */}
          <Skeleton height={28} width="38%" radius="sm" />

          {/* Bed / bath / sqft badges */}
          <Group gap="md">
            <Skeleton height={28} width={80} radius="xl" />
            <Skeleton height={28} width={72} radius="xl" />
            <Skeleton height={28} width={96} radius="xl" />
          </Group>

          {/* Description heading + lines */}
          <Stack gap="xs">
            <Skeleton height={20} width="30%" radius="sm" />
            <Skeleton height={14} radius="sm" />
            <Skeleton height={14} radius="sm" />
            <Skeleton height={14} width="85%" radius="sm" />
            <Skeleton height={14} width="60%" radius="sm" />
          </Stack>

          {/* Details section */}
          <Stack gap="xs">
            <Skeleton height={20} width="20%" radius="sm" />
            {[0, 1, 2, 3, 4].map((i) => (
              <Group key={i} justify="space-between">
                <Skeleton height={14} width="40%" radius="sm" />
                <Skeleton height={14} width="28%" radius="sm" />
              </Group>
            ))}
          </Stack>

          {/* Action buttons */}
          <Stack gap="sm" mt="md">
            <Skeleton height={44} radius="md" />
            <Skeleton height={44} radius="md" />
          </Stack>
        </Stack>
      </Grid.Col>
    </Grid>
  );
}

/**
 * Skeleton for the swipe card in the Discover page.
 * Matches the 400×520 footprint of the real SwipeCard stack.
 */
export function SkeletonSwipeCard() {
  return (
    // width: 100% forces the Stack to fill its flex parent so the inner
    // maxWidth: 400 boxes actually reach their full intended width.
    <Stack align="center" gap="xl" style={{ width: '100%' }}>
      {/* Progress bar — mirrors the real progress box above the card */}
      <Box style={{ width: '100%', maxWidth: 400 }}>
        <Group justify="space-between" mb={6}>
          <Skeleton height={12} width={80} radius="sm" />
          <Skeleton height={12} width={80} radius="sm" />
        </Group>
        <Skeleton height={6} radius="xl" />
      </Box>

      {/* Card — 400×520, same as <Box data-tour="discover-card"> */}
      <Box
        style={{
          width: '100%',
          maxWidth: 400,
          height: 520,
          borderRadius: 20,
          overflow: 'hidden',
          boxShadow: '0 12px 40px rgba(0,0,0,0.12)',
          backgroundColor: '#fff',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Image area: real card uses height 58% of 520 = 302px */}
        <Skeleton height={302} radius={0} style={{ flexShrink: 0 }} />

        {/* Info area: remaining 218px, mirroring SwipeCard's info section */}
        <Box
          style={{
            padding: '1.25rem 1.5rem',
            height: 218,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <Stack gap={6}>
            {/* Title */}
            <Skeleton height={20} width="70%" radius="sm" />
            {/* City */}
            <Skeleton height={14} width="45%" radius="sm" />
            {/* Bed · bath · sqft */}
            <Skeleton height={14} width="55%" radius="sm" />
          </Stack>

          {/* Amenity badge pills */}
          <Group gap="xs">
            <Skeleton height={20} width={70} radius="xl" />
            <Skeleton height={20} width={58} radius="xl" />
          </Group>

          {/* Price */}
          <Skeleton height={24} width="38%" radius="sm" />

          {/* "View details" button */}
          <Box style={{ display: 'flex', justifyContent: 'center' }}>
            <Skeleton height={26} width={100} radius="sm" />
          </Box>
        </Box>
      </Box>

      {/* Pass / Like action buttons */}
      <Group gap={48} justify="center">
        <Skeleton height={64} width={64} radius="xl" />
        <Skeleton height={64} width={64} radius="xl" />
      </Group>
    </Stack>
  );
}

/**
 * Skeleton for the ProfilePanel inside /account.
 * Mirrors: gradient header card → form card (inputs + selects) → save button row.
 */
export function SkeletonAccountProfile() {
  return (
    <Stack gap="xl">
      {/* Profile header card */}
      <Card
        style={{
          background: 'linear-gradient(120deg, #e6fcf5 0%, #ffffff 100%)',
          border: '1px solid #e9ecef',
        }}
      >
        <Group gap="xl" align="center" wrap="wrap">
          {/* Avatar circle */}
          <Skeleton height={80} width={80} radius="xl" style={{ flexShrink: 0 }} />
          <Stack gap={6} style={{ flex: 1 }}>
            {/* Full name */}
            <Skeleton height={22} width="45%" radius="sm" />
            {/* Email */}
            <Skeleton height={14} width="60%" radius="sm" />
            {/* Verification badge */}
            <Skeleton height={22} width={110} radius="xl" />
          </Stack>
        </Group>
      </Card>

      {/* Form card */}
      <Card withBorder padding="xl" radius="md">
        <Stack gap="lg">
          {/* "Profile Information" heading */}
          <Skeleton height={22} width="35%" radius="sm" />

          {/* Email field (disabled) */}
          <Stack gap={6}>
            <Skeleton height={13} width={40} radius="sm" />
            <Skeleton height={36} radius="sm" />
          </Stack>

          {/* Full Name field */}
          <Stack gap={6}>
            <Skeleton height={13} width={70} radius="sm" />
            <Skeleton height={36} radius="sm" />
          </Stack>

          {/* Bio textarea */}
          <Stack gap={6}>
            <Skeleton height={13} width={28} radius="sm" />
            <Skeleton height={80} radius="sm" />
          </Stack>

          <Divider label="Work & Education" labelPosition="center" />

          {/* Company select */}
          <Stack gap={6}>
            <Skeleton height={13} width={56} radius="sm" />
            <Skeleton height={36} radius="sm" />
          </Stack>

          {/* School select */}
          <Stack gap={6}>
            <Skeleton height={13} width={46} radius="sm" />
            <Skeleton height={36} radius="sm" />
          </Stack>

          {/* Role/Title select */}
          <Stack gap={6}>
            <Skeleton height={13} width={84} radius="sm" />
            <Skeleton height={36} radius="sm" />
          </Stack>
        </Stack>
      </Card>

      {/* Save button row */}
      <Group justify="flex-end">
        <Skeleton height={42} width={140} radius="sm" />
      </Group>
    </Stack>
  );
}
