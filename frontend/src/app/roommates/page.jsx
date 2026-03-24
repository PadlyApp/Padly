'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Container,
  Title,
  Text,
  Stack,
  Tabs,
  Card,
  Group,
  Badge,
  Button,
  Avatar,
  Switch,
  Alert,
  Loader,
  Center,
  Collapse,
  Divider,
  Box,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconUsers,
  IconChevronDown,
  IconChevronUp,
  IconAlertCircle,
  IconHome,
} from '@tabler/icons-react';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../../../lib/api';

function displayName(profile) {
  if (!profile) return 'Member';
  return profile.full_name || profile.fullName || 'Member';
}

function initials(name) {
  if (!name || typeof name !== 'string') return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function SuggestionCard({ item, myId, blendEmbedding, onExpress, expressing, expressedSet }) {
  const [opened, { toggle }] = useDisclosure(false);
  const profile = item.profile || {};
  const scores = item.scores || {};
  const uid = item.user_id;
  const pct = Math.round((scores.final ?? 0) * 100);
  const sent = expressedSet.has(uid);

  return (
    <Card withBorder padding="lg" radius="md" shadow="sm">
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Group gap="md" wrap="nowrap">
          <Avatar src={profile.profile_picture_url} radius="xl" size="lg" color="teal">
            {initials(displayName(profile))}
          </Avatar>
          <div>
            <Text fw={600} size="md">
              {displayName(profile)}
            </Text>
            <Group gap="xs" mt={4}>
              {profile.verification_status && (
                <Badge size="xs" variant="light" color="teal">
                  {String(profile.verification_status).replace(/_/g, ' ')}
                </Badge>
              )}
            </Group>
            {(profile.company_name || profile.school_name) && (
              <Text size="sm" c="dimmed" mt={4}>
                {[profile.company_name, profile.school_name].filter(Boolean).join(' · ')}
              </Text>
            )}
          </div>
        </Group>
        <Stack gap={4} align="flex-end">
          <Text fw={700} size="xl" c="teal">
            {pct}%
          </Text>
          <Text size="xs" c="dimmed">
            match
          </Text>
        </Stack>
      </Group>

      {Array.isArray(item.reasons) && item.reasons.length > 0 && (
        <Stack gap={6} mt="md">
          {item.reasons.slice(0, 4).map((r) => (
            <Text key={r} size="sm" c="dimmed">
              {r}
            </Text>
          ))}
        </Stack>
      )}

      <Button
        variant="subtle"
        size="xs"
        mt="sm"
        px={0}
        rightSection={opened ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
        onClick={toggle}
      >
        Score details
      </Button>
      <Collapse in={opened}>
        <Stack gap={6} mt="xs">
          <Text size="sm">
            Lifestyle: {scores.lifestyle != null ? `${Math.round(scores.lifestyle * 100)}%` : '—'}
          </Text>
          <Text size="sm">
            Behavior:{' '}
            {scores.behavior != null ? `${Math.round(scores.behavior * 100)}%` : '— (cold start)'}
          </Text>
          {blendEmbedding && (
            <Text size="sm">
              Taste embedding:{' '}
              {scores.embedding != null ? `${Math.round(scores.embedding * 100)}%` : '—'}
            </Text>
          )}
          <Text size="xs" c="dimmed">
            Behavior confidence: {scores.behavior_confidence || '—'}
          </Text>
        </Stack>
      </Collapse>

      <Divider my="md" />

      <Button
        fullWidth
        style={{ backgroundColor: '#20c997' }}
        disabled={!uid || uid === myId || sent || expressing}
        loading={expressing}
        onClick={() => onExpress(uid)}
      >
        {sent ? 'Interest sent' : 'Express interest'}
      </Button>
    </Card>
  );
}

function IntroRow({ row, direction, profiles, onRespond, respondingId }) {
  const otherId = direction === 'incoming' ? row.from_user_id : row.to_user_id;
  const other = profiles[otherId] || {};
  const status = (row.status || '').toLowerCase();
  const isPendingIncoming = direction === 'incoming' && status === 'pending';

  return (
    <Card withBorder padding="md" radius="md">
      <Group justify="space-between" align="center" wrap="wrap">
        <Group gap="md">
          <Avatar radius="xl" color="gray">
            {initials(displayName(other))}
          </Avatar>
          <div>
            <Text fw={500}>{displayName(other)}</Text>
            <Text size="xs" c="dimmed">
              {direction === 'incoming' ? 'Wants to connect' : 'You reached out'} · {status}
            </Text>
          </div>
        </Group>
        {isPendingIncoming && (
          <Group gap="sm">
            <Button
              size="sm"
              variant="light"
              color="red"
              loading={respondingId === row.id}
              onClick={() => onRespond(row.id, 'decline')}
            >
              Decline
            </Button>
            <Button
              size="sm"
              style={{ backgroundColor: '#20c997' }}
              loading={respondingId === row.id}
              onClick={() => onRespond(row.id, 'accept')}
            >
              Accept
            </Button>
          </Group>
        )}
        {direction === 'outgoing' && status === 'pending' && (
          <Badge color="gray" variant="light">
            Waiting for them
          </Badge>
        )}
        {row.result_group_id && (
          <Button component={Link} href={`/groups/${row.result_group_id}`} size="sm" variant="light">
            View group
          </Button>
        )}
      </Group>
    </Card>
  );
}

function RoommatesContent() {
  const { user, authState } = useAuth();
  const token = authState?.accessToken;
  const myId = user?.profile?.id;
  const queryClient = useQueryClient();
  const [blendEmbedding, setBlendEmbedding] = useState(false);
  const [expressedIds, setExpressedIds] = useState(() => new Set());
  const [funnelBanner, setFunnelBanner] = useState(null);
  const [respondingId, setRespondingId] = useState(null);

  const suggestionsQuery = useQuery({
    queryKey: ['roommateSuggestions', token, blendEmbedding],
    queryFn: () => api.getRoommateSuggestions(token, { limit: 20, blendEmbedding }),
    enabled: !!token,
  });

  const inboxQuery = useQuery({
    queryKey: ['roommateIntroInbox', token],
    queryFn: async () => {
      const raw = await api.getRoommateIntroInbox(token);
      const ids = new Set();
      for (const row of [...(raw.incoming || []), ...(raw.outgoing || [])]) {
        if (row.from_user_id) ids.add(row.from_user_id);
        if (row.to_user_id) ids.add(row.to_user_id);
      }
      const profiles = {};
      await Promise.all(
        [...ids].map(async (uid) => {
          try {
            const r = await api.getUserWithAuth(uid, token);
            profiles[uid] = r.data || r;
          } catch {
            profiles[uid] = { id: uid, full_name: 'User' };
          }
        })
      );
      return { ...raw, profiles };
    },
    enabled: !!token,
  });

  const expressMutation = useMutation({
    mutationFn: (toUserId) => api.expressRoommateInterest(token, toUserId),
    onSuccess: (data, toUserId) => {
      setExpressedIds((prev) => new Set(prev).add(toUserId));
      queryClient.invalidateQueries({ queryKey: ['roommateIntroInbox'] });
      if (data.funnel?.group_id) {
        setFunnelBanner(data.funnel);
        notifications.show({
          title: 'You’re matched',
          message: 'Open your group to continue.',
          color: 'teal',
        });
      } else {
        notifications.show({
          title: 'Interest sent',
          message: 'They’ll see this in their inbox.',
          color: 'teal',
        });
      }
    },
    onError: (e) =>
      notifications.show({ title: 'Could not send', message: e.message, color: 'red' }),
  });

  const respondMutation = useMutation({
    mutationFn: ({ introId, action }) => api.respondToRoommateIntro(token, introId, action),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['roommateIntroInbox'] });
      if (data.funnel?.group_id) {
        setFunnelBanner(data.funnel);
        notifications.show({
          title: 'Accepted',
          message: 'Continue in your roommate group.',
          color: 'teal',
        });
      } else {
        notifications.show({ title: 'Updated', message: 'Intro status saved.', color: 'teal' });
      }
    },
    onError: (e) =>
      notifications.show({ title: 'Action failed', message: e.message, color: 'red' }),
    onSettled: () => setRespondingId(null),
  });

  const handleRespond = (introId, action) => {
    setRespondingId(introId);
    respondMutation.mutate({ introId, action });
  };

  const suggestions = suggestionsQuery.data?.suggestions || [];
  const prefsError =
    suggestionsQuery.isError &&
    (suggestionsQuery.error?.message || '').toLowerCase().includes('target_city');

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#fafafa' }}>
      <Navigation />
      <Container size="sm" py="xl">
        <Stack gap="lg">
          <Group gap="sm" align="center">
            <ThemeIconPlaceholder />
            <div>
              <Title order={2}>Roommates</Title>
              <Text size="sm" c="dimmed">
                People in your city ranked by lifestyle and listing taste—then mutual opt-in.
              </Text>
            </div>
          </Group>

          {funnelBanner?.group_id && (
            <Alert
              icon={<IconHome size={18} />}
              title="Next step"
              color="teal"
              variant="light"
            >
              <Text size="sm" mb="sm">
                {funnelBanner.next_step === 'join_group'
                  ? 'Accept your invite and join the roommate group to continue.'
                  : 'Open your roommate group to coordinate with your match.'}
              </Text>
              <Button
                component={Link}
                href={`/groups/${funnelBanner.group_id}`}
                size="sm"
                style={{ backgroundColor: '#20c997' }}
              >
                Go to group
              </Button>
            </Alert>
          )}

          <Tabs defaultValue="suggested" keepMounted={false}>
            <Tabs.List grow>
              <Tabs.Tab value="suggested" leftSection={<IconUsers size={16} />}>
                Suggested
              </Tabs.Tab>
              <Tabs.Tab value="inbox">Inbox</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="suggested" pt="lg">
              <Stack gap="md">
                <Card withBorder padding="md" radius="md">
                  <Group justify="space-between" align="center" wrap="wrap">
                    <div>
                      <Text size="sm" fw={500}>
                        Taste embedding (beta)
                      </Text>
                      <Text size="xs" c="dimmed">
                        Blend neural listing taste into lifestyle when the model is available.
                      </Text>
                    </div>
                    <Switch
                      checked={blendEmbedding}
                      onChange={(e) => setBlendEmbedding(e.currentTarget.checked)}
                      color="teal"
                    />
                  </Group>
                </Card>

                {suggestionsQuery.isLoading && (
                  <Center py="xl">
                    <Loader color="teal" />
                  </Center>
                )}

                {prefsError && (
                  <Alert icon={<IconAlertCircle size={18} />} color="orange" title="Set your city">
                    <Text size="sm" mb="md">
                      {suggestionsQuery.error.message}
                    </Text>
                    <Button component={Link} href="/account?tab=preferences" variant="light" color="teal">
                      Open preferences
                    </Button>
                  </Alert>
                )}

                {suggestionsQuery.isError && !prefsError && (
                  <Alert color="red" title="Could not load suggestions">
                    {suggestionsQuery.error.message}
                  </Alert>
                )}

                {!suggestionsQuery.isLoading &&
                  !suggestionsQuery.isError &&
                  suggestions.length === 0 && (
                    <Alert color="gray" title="No matches yet">
                      <Text size="sm" mb="sm">
                        We didn’t find other members in your city with overlapping preferences. Try
                        inviting friends, or swipe on{' '}
                        <Text component={Link} href="/discover" c="teal" inherit span fw={500}>
                          Discover
                        </Text>{' '}
                        so your taste signal improves.
                      </Text>
                    </Alert>
                  )}

                {suggestions.map((item) => (
                  <SuggestionCard
                    key={item.user_id}
                    item={item}
                    myId={myId}
                    blendEmbedding={blendEmbedding}
                    onExpress={(uid) => expressMutation.mutate(uid)}
                    expressing={expressMutation.isPending && expressMutation.variables === item.user_id}
                    expressedSet={expressedIds}
                  />
                ))}
              </Stack>
            </Tabs.Panel>

            <Tabs.Panel value="inbox" pt="lg">
              {inboxQuery.isLoading && (
                <Center py="xl">
                  <Loader color="teal" />
                </Center>
              )}
              {inboxQuery.isError && (
                <Alert color="red">{inboxQuery.error.message}</Alert>
              )}
              {!inboxQuery.isLoading && !inboxQuery.isError && (
                <Stack gap="xl">
                  <div>
                    <Text fw={600} mb="sm">
                      Incoming
                    </Text>
                    {(inboxQuery.data?.incoming || []).length === 0 ? (
                      <Text size="sm" c="dimmed">
                        No incoming requests.
                      </Text>
                    ) : (
                      <Stack gap="sm">
                        {(inboxQuery.data.incoming || []).map((row) => (
                          <IntroRow
                            key={row.id}
                            row={row}
                            direction="incoming"
                            profiles={inboxQuery.data.profiles || {}}
                            onRespond={handleRespond}
                            respondingId={respondingId}
                          />
                        ))}
                      </Stack>
                    )}
                  </div>
                  <Divider />
                  <div>
                    <Text fw={600} mb="sm">
                      Outgoing
                    </Text>
                    {(inboxQuery.data?.outgoing || []).length === 0 ? (
                      <Text size="sm" c="dimmed">
                        You haven’t sent interest to anyone yet.
                      </Text>
                    ) : (
                      <Stack gap="sm">
                        {(inboxQuery.data.outgoing || []).map((row) => (
                          <IntroRow
                            key={row.id}
                            row={row}
                            direction="outgoing"
                            profiles={inboxQuery.data.profiles || {}}
                            onRespond={handleRespond}
                            respondingId={respondingId}
                          />
                        ))}
                      </Stack>
                    )}
                  </div>
                </Stack>
              )}
            </Tabs.Panel>
          </Tabs>
        </Stack>
      </Container>
    </Box>
  );
}

/** Avoid importing ThemeIcon if unused — small inline for header icon */
function ThemeIconPlaceholder() {
  return (
    <Box
      style={{
        width: 40,
        height: 40,
        borderRadius: 8,
        background: 'rgba(32,201,151,0.15)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <IconUsers size={22} color="#20c997" />
    </Box>
  );
}

export default function RoommatesPage() {
  return (
    <ProtectedRoute>
      <RoommatesContent />
    </ProtectedRoute>
  );
}
