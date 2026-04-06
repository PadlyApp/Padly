'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Container,
  Group,
  Loader,
  Progress,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import {
  IconAlertCircle,
  IconChartBar,
  IconDownload,
  IconRefresh,
  IconShieldLock,
} from '@tabler/icons-react';
import { Navigation } from '../../components/Navigation';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import { useAuth } from '../../contexts/AuthContext';

const DAY_OPTIONS = [
  { value: '7', label: 'Last 7 days' },
  { value: '14', label: 'Last 14 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
];

const SURFACE_OPTIONS = [
  { value: 'all', label: 'All surfaces' },
  { value: 'matches', label: 'Matches' },
  { value: 'discover', label: 'Discover' },
];

const USER_MODE_OPTIONS = [
  { value: 'all_sessions', label: 'All sessions' },
  { value: 'latest_per_user', label: 'Latest per user' },
];

const FEEDBACK_LABEL_COPY = {
  not_useful: 'Not useful',
  somewhat_useful: 'Somewhat useful',
  very_useful: 'Very useful',
};

const REASON_LABEL_COPY = {
  too_expensive: 'Too expensive',
  wrong_location: 'Wrong location',
  not_my_style: 'Not my style',
  too_few_good_options: 'Too few good options',
  other: 'Other',
};

function formatPercent(value) {
  const numeric = Number(value || 0);
  return `${numeric.toFixed(1)}%`;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function formatDuration(ms) {
  const value = Number(ms || 0);
  if (!value) return '0s';
  if (value >= 60000) {
    return `${(value / 60000).toFixed(1)}m`;
  }
  return `${Math.round(value / 1000)}s`;
}

function MetricCard({ label, value, hint }) {
  return (
    <Card withBorder radius="lg" padding="lg">
      <Text size="sm" c="dimmed">{label}</Text>
      <Title order={3} mt={6}>{value}</Title>
      {hint ? <Text size="sm" c="dimmed" mt={6}>{hint}</Text> : null}
    </Card>
  );
}

function BarList({ rows, emptyLabel, labelResolver = (label) => label }) {
  if (!rows?.length) {
    return <Text c="dimmed">{emptyLabel}</Text>;
  }

  return (
    <Stack gap="sm">
      {rows.map((row) => (
        <Box key={row.label}>
          <Group justify="space-between" mb={6}>
            <Text size="sm" fw={500}>{labelResolver(row.label)}</Text>
            <Text size="sm" c="dimmed">
              {formatNumber(row.count)} · {formatPercent(row.pct)}
            </Text>
          </Group>
          <Progress value={Math.min(Number(row.pct || 0), 100)} color="teal" radius="xl" />
        </Box>
      ))}
    </Stack>
  );
}

function TrendRows({ rows }) {
  if (!rows?.length) {
    return <Text c="dimmed">No trend data yet.</Text>;
  }

  return (
    <Table striped highlightOnHover withTableBorder>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Date</Table.Th>
          <Table.Th>Sessions</Table.Th>
          <Table.Th>Feedback</Table.Th>
          <Table.Th>Very useful</Table.Th>
          <Table.Th>Not useful</Table.Th>
          <Table.Th>Avg dwell</Table.Th>
          <Table.Th>Avg interested</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.slice(-14).reverse().map((row) => (
          <Table.Tr key={row.date}>
            <Table.Td>{row.date}</Table.Td>
            <Table.Td>{formatNumber(row.total_sessions)}</Table.Td>
            <Table.Td>{formatNumber(row.feedback_count)}</Table.Td>
            <Table.Td>{formatNumber(row.very_useful_count)}</Table.Td>
            <Table.Td>{formatNumber(row.not_useful_count)}</Table.Td>
            <Table.Td>{formatDuration(row.avg_surface_dwell_ms)}</Table.Td>
            <Table.Td>{Number(row.avg_interested || row.avg_saves || 0).toFixed(2)}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function ComparisonTable({ rows, labelKey, labelTitle }) {
  if (!rows?.length) {
    return <Text c="dimmed">No comparison data yet.</Text>;
  }

  return (
    <Table striped highlightOnHover withTableBorder>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>{labelTitle}</Table.Th>
          <Table.Th>Sessions</Table.Th>
          <Table.Th>Feedback rate</Table.Th>
          <Table.Th>Very useful rate</Table.Th>
          <Table.Th>Avg opens</Table.Th>
          <Table.Th>Avg interested</Table.Th>
          <Table.Th>Interested rate</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.map((row) => (
          <Table.Tr key={row[labelKey]}>
            <Table.Td>
              <Badge variant="light" color={row[labelKey] === 'two_tower' ? 'teal' : 'gray'}>
                {row[labelKey]}
              </Badge>
            </Table.Td>
            <Table.Td>{formatNumber(row.total_sessions)}</Table.Td>
            <Table.Td>{formatPercent(row.feedback_rate)}</Table.Td>
            <Table.Td>{formatPercent(row.very_useful_rate)}</Table.Td>
            <Table.Td>{Number(row.avg_detail_opens || 0).toFixed(2)}</Table.Td>
            <Table.Td>{Number(row.avg_interested || row.avg_saves || 0).toFixed(2)}</Table.Td>
            <Table.Td>{formatPercent(row.interested_rate || row.save_rate)}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function PositionTable({ rows }) {
  if (!rows?.length) {
    return <Text c="dimmed">No position-aware engagement data yet.</Text>;
  }

  return (
    <Table striped highlightOnHover withTableBorder>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Rank position</Table.Th>
          <Table.Th>Detail opens</Table.Th>
          <Table.Th>Interested</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.slice(0, 10).map((row) => (
          <Table.Tr key={row.position}>
            <Table.Td>#{row.position + 1}</Table.Td>
            <Table.Td>{formatNumber(row.detail_open_count)}</Table.Td>
            <Table.Td>{formatNumber(row.interested_count || row.save_count)}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

export default function AdminEvaluationPage() {
  return (
    <ProtectedRoute>
      <AdminEvaluationPageContent />
    </ProtectedRoute>
  );
}

function AdminEvaluationPageContent() {
  const { user, isLoading, getValidToken } = useAuth();
  const isAdmin = user?.profile?.role === 'admin';
  const [days, setDays] = useState('30');
  const [surface, setSurface] = useState('matches');
  const [variant, setVariant] = useState('all');
  const [userMode, setUserMode] = useState('all_sessions');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(null);
  const [error, setError] = useState(null);

  const variantOptions = useMemo(() => {
    const dynamicOptions = (data?.variant_comparison || []).map((row) => ({
      value: row.variant,
      label: row.variant,
    }));

    return [{ value: 'all', label: 'All variants' }, ...dynamicOptions];
  }, [data?.variant_comparison]);

  const fetchSummary = useCallback(async () => {
    if (!isAdmin) return;

    setLoading(true);
    setError(null);

    try {
      const token = await getValidToken();
      if (!token) {
        throw new Error('Authentication required');
      }

      const params = new URLSearchParams({
        days,
        surface,
        variant,
        user_mode: userMode,
      });

      const response = await fetch(`/api/admin/evaluation?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: 'no-store',
      });

      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || 'Failed to load evaluation dashboard');
      }

      setData(payload?.data || null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Failed to load evaluation dashboard');
    } finally {
      setLoading(false);
    }
  }, [days, surface, userMode, variant, getValidToken, isAdmin]);

  useEffect(() => {
    if (!isLoading && isAdmin) {
      fetchSummary();
    }
  }, [fetchSummary, isAdmin, isLoading]);

  const overview = data?.overview;
  const usefulnessRows = (data?.usefulness_distribution || []).map((row) => ({
    ...row,
    label: FEEDBACK_LABEL_COPY[row.label] || row.label,
  }));
  const reasonRows = (data?.negative_reasons || []).map((row) => ({
    ...row,
    label: REASON_LABEL_COPY[row.label] || row.label,
  }));

  const exportSummary = useCallback(async (format) => {
    if (!isAdmin) return;

    setExporting(format);
    try {
      const token = await getValidToken();
      if (!token) {
        throw new Error('Authentication required');
      }

      const params = new URLSearchParams({
        days,
        surface,
        variant,
        user_mode: userMode,
        format,
      });

      const response = await fetch(`/api/admin/evaluation/export?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: 'no-store',
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || 'Failed to export evaluation summary');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = format === 'csv' ? 'evaluation-summary.csv' : 'evaluation-summary.json';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : 'Failed to export evaluation summary');
    } finally {
      setExporting(null);
    }
  }, [days, getValidToken, isAdmin, surface, userMode, variant]);

  return (
    <>
      <Navigation />
      <Container size="xl" py="xl">
        <Stack gap="xl">
          <Group justify="space-between" align="flex-end">
            <div>
              <Group gap="xs" mb={8}>
                <Badge variant="light" color="teal">Phase 4</Badge>
                <Badge variant="light" color="gray">Admin only</Badge>
              </Group>
              <Title order={1}>Model Evaluation</Title>
              <Text c="dimmed" mt={6}>
                Review session quality, explicit usefulness, passive engagement, and ranker performance.
              </Text>
              <Text size="sm" c="dimmed" mt={4}>
                Counting mode: {data?.filters?.user_mode === 'latest_per_user' ? 'latest session per user' : 'all eligible sessions'}
              </Text>
            </div>

            <Group>
              <Select
                label="Window"
                data={DAY_OPTIONS}
                value={days}
                onChange={(value) => setDays(value || '30')}
                w={150}
              />
              <Select
                label="Surface"
                data={SURFACE_OPTIONS}
                value={surface}
                onChange={(value) => setSurface(value || 'matches')}
                w={160}
              />
              <Select
                label="Variant"
                data={variantOptions}
                value={variant}
                onChange={(value) => setVariant(value || 'all')}
                w={170}
              />
              <Select
                label="Counting"
                data={USER_MODE_OPTIONS}
                value={userMode}
                onChange={(value) => setUserMode(value || 'all_sessions')}
                w={180}
              />
              <Button
                leftSection={<IconRefresh size={16} />}
                onClick={fetchSummary}
                loading={loading}
                mt={24}
              >
                Refresh
              </Button>
              <Button
                leftSection={<IconDownload size={16} />}
                variant="light"
                onClick={() => exportSummary('csv')}
                loading={exporting === 'csv'}
                mt={24}
              >
                Export CSV
              </Button>
              <Button
                leftSection={<IconDownload size={16} />}
                variant="subtle"
                onClick={() => exportSummary('json')}
                loading={exporting === 'json'}
                mt={24}
              >
                Export JSON
              </Button>
            </Group>
          </Group>

          {!isLoading && !isAdmin ? (
            <Alert color="red" icon={<IconShieldLock size={18} />} radius="lg">
              This page is restricted to users whose `users.role` is set to `admin`.
            </Alert>
          ) : null}

          {error ? (
            <Alert color="red" icon={<IconAlertCircle size={18} />} radius="lg">
              {error}
            </Alert>
          ) : null}

          {loading && !data ? (
            <Center py={80}>
              <Loader size="lg" />
            </Center>
          ) : null}

          {data && isAdmin ? (
            <>
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
                <MetricCard
                  label="Sessions"
                  value={formatNumber(overview?.total_sessions)}
                  hint={`${formatNumber(overview?.unique_users)} unique users`}
                />
                <MetricCard
                  label="Feedback rate"
                  value={formatPercent(overview?.feedback_rate)}
                  hint={`${formatNumber(overview?.feedback_count)} feedback responses`}
                />
                <MetricCard
                  label="Very useful rate"
                  value={formatPercent(overview?.very_useful_rate)}
                  hint="Share of explicit responses marked very useful"
                />
                <MetricCard
                  label="Interested rate"
                  value={formatPercent(overview?.interested_rate || overview?.save_rate)}
                  hint={`${Number(overview?.avg_interested || overview?.avg_saves || 0).toFixed(2)} interested per session`}
                />
              </SimpleGrid>

              <SimpleGrid cols={{ base: 1, lg: 2 }}>
                <Card withBorder radius="lg" padding="lg">
                  <Group justify="space-between" mb="md">
                    <Title order={3}>Usefulness</Title>
                    <IconChartBar size={18} />
                  </Group>
                  <BarList
                    rows={usefulnessRows}
                    emptyLabel="No explicit feedback yet."
                  />
                </Card>

                <Card withBorder radius="lg" padding="lg">
                  <Group justify="space-between" mb="md">
                    <Title order={3}>Negative Reasons</Title>
                    <Badge variant="light" color="gray">Optional follow-up</Badge>
                  </Group>
                  <BarList
                    rows={reasonRows}
                    emptyLabel="No negative reason selections yet."
                  />
                </Card>
              </SimpleGrid>

              <SimpleGrid cols={{ base: 1, md: 2, lg: 4 }}>
                <MetricCard
                  label="Avg recommendation count"
                  value={Number(overview?.avg_recommendation_count || 0).toFixed(2)}
                  hint="Listings shown per session"
                />
                <MetricCard
                  label="Avg detail opens"
                  value={Number(overview?.avg_detail_opens || 0).toFixed(2)}
                  hint={`${formatPercent(overview?.detail_open_rate)} open rate`}
                />
                <MetricCard
                  label="Surface dwell"
                  value={formatDuration(overview?.avg_surface_dwell_ms)}
                  hint="Average time on the recommendation surface"
                />
                <MetricCard
                  label="Detail dwell"
                  value={formatDuration(overview?.avg_detail_dwell_ms)}
                  hint={`${formatDuration(overview?.avg_detail_view_dwell_ms)} avg detail-view event`}
                />
              </SimpleGrid>

              <Card withBorder radius="lg" padding="lg">
                <Group justify="space-between" mb="md">
                  <Title order={3}>Variant Comparison</Title>
                  <Text c="dimmed" size="sm">
                    Compare the two-tower ranker against fallback or baseline variants.
                  </Text>
                </Group>
                <ComparisonTable rows={data?.variant_comparison || []} labelKey="variant" labelTitle="Variant" />
              </Card>

              <SimpleGrid cols={{ base: 1, lg: 2 }}>
                <Card withBorder radius="lg" padding="lg">
                  <Group justify="space-between" mb="md">
                    <Title order={3}>Model Versions</Title>
                    <Text c="dimmed" size="sm">
                      Compare performance by deployed model version.
                    </Text>
                  </Group>
                  <ComparisonTable rows={data?.model_version_comparison || []} labelKey="model_version" labelTitle="Model version" />
                </Card>

                <Card withBorder radius="lg" padding="lg">
                  <Group justify="space-between" mb="md">
                    <Title order={3}>User History Buckets</Title>
                    <Text c="dimmed" size="sm">
                      Separate first-time users from returning and experienced users.
                    </Text>
                  </Group>
                  <ComparisonTable rows={data?.user_history_buckets || []} labelKey="bucket" labelTitle="Bucket" />
                </Card>
              </SimpleGrid>

              <SimpleGrid cols={{ base: 1, lg: 2 }}>
                <Card withBorder radius="lg" padding="lg">
                  <Group justify="space-between" mb="md">
                    <Title order={3}>Event Breakdown</Title>
                    <Badge variant="light" color="teal">Passive metrics</Badge>
                  </Group>
                  <SimpleGrid cols={2}>
                    <MetricCard label="Detail opens" value={formatNumber(data?.event_breakdown?.detail_open)} />
                    <MetricCard label="Detail views" value={formatNumber(data?.event_breakdown?.detail_view)} />
                    <MetricCard label="Interested" value={formatNumber(data?.event_breakdown?.interested || data?.event_breakdown?.save)} />
                    <MetricCard label="Uninterested" value={formatNumber(data?.event_breakdown?.not_interested || data?.event_breakdown?.unsave)} />
                  </SimpleGrid>
                </Card>

                <Card withBorder radius="lg" padding="lg">
                  <Group justify="space-between" mb="md">
                    <Title order={3}>Top Positions</Title>
                    <Text size="sm" c="dimmed">Where ranked listings actually earned attention</Text>
                  </Group>
                  <PositionTable rows={data?.position_breakdown || []} />
                </Card>
              </SimpleGrid>

              <Card withBorder radius="lg" padding="lg">
                <Group justify="space-between" mb="md">
                  <Title order={3}>Daily Trend</Title>
                  <Text size="sm" c="dimmed">
                    Rolling visibility into recommendation quality over time
                  </Text>
                </Group>
                <TrendRows rows={data?.daily_trends || []} />
              </Card>

              <Card withBorder radius="lg" padding="lg">
                <Group justify="space-between" mb="md">
                  <Title order={3}>Research Notes</Title>
                  <Badge variant="light" color="gray">Phase 6</Badge>
                </Group>
                <Stack gap="xs">
                  <Text size="sm" c="dimmed">
                    Sample size: {formatNumber(data?.research_notes?.sample_size_sessions)} sessions, {formatNumber(data?.research_notes?.sample_size_feedback)} feedback submissions.
                  </Text>
                  <Text size="sm" c="dimmed">
                    Counting mode: {data?.research_notes?.counting_mode || 'all_sessions'}.
                  </Text>
                  <Text size="sm" c="dimmed">
                    Exposure bias: {data?.research_notes?.exposure_bias_note}
                  </Text>
                  <Text size="sm" c="dimmed">
                    Repeat users: {data?.research_notes?.repeat_user_note}
                  </Text>
                </Stack>
              </Card>
            </>
          ) : null}
        </Stack>
      </Container>
    </>
  );
}
