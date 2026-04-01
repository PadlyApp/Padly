'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Container,
  Title,
  Text,
  Button,
  Stack,
  Card,
  Group,
  Badge,
  TextInput,
  Select,
  Loader,
  Grid,
  ActionIcon,
  Tabs,
  Box,
  Skeleton,
  ThemeIcon,
  Avatar,
  Switch,
  Alert,
  Center,
  Collapse,
  Divider,
  Progress,
  SegmentedControl,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconPlus, IconSearch, IconUsers, IconMapPin, IconCalendar, IconCurrencyDollar, IconCheck, IconUserPlus, IconSparkles, IconStar, IconInbox, IconChevronDown, IconChevronUp, IconAlertCircle, IconHome, IconUserSearch } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useAuth } from '../contexts/AuthContext';
import { Navigation } from '../components/Navigation';
import { InvitationsPanel } from '../components/InvitationsPanel';
import { api } from '../../../lib/api';

// --- People tab helpers (copied from roommates/page.jsx) ---

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

function SuggestionCard({ item, myId, useMlRanking, onExpress, expressing, expressedSet }) {
  const [opened, { toggle }] = useDisclosure(false);
  const profile = item.profile || {};
  const scores = item.scores || {};
  const uid = item.user_id;
  const hardFilterMode = !useMlRanking || scores.behavior_confidence === 'hard_filter';
  const pct = Math.round((scores.final ?? 0) * 100);
  const sent = expressedSet.has(uid);

  return (
    <Card withBorder padding="lg" radius="lg" shadow="sm">
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
        {hardFilterMode ? (
          <Badge color="teal" variant="light">
            Hard-pass
          </Badge>
        ) : (
          <Stack gap={4} align="flex-end">
            <Text fw={700} size="xl" c="teal">
              {pct}%
            </Text>
            <Text size="xs" c="dimmed">
              match
            </Text>
            <Progress value={pct} size="xs" color="teal" radius="xl" w={60} mt={4} />
          </Stack>
        )}
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

      {!hardFilterMode && (
        <>
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
              <Text size="sm">
                Taste embedding:{' '}
                {scores.embedding != null ? `${Math.round(scores.embedding * 100)}%` : '—'}
              </Text>
              <Text size="xs" c="dimmed">
                Behavior confidence: {scores.behavior_confidence || '—'}
              </Text>
            </Stack>
          </Collapse>
        </>
      )}

      <Divider my="md" />

      <Button
        fullWidth
        color="teal"
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
    <Card withBorder padding="md" radius="lg">
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
              color="teal"
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

// --- End People tab helpers ---

export default function GroupsPage() {
  return (
    <Suspense fallback={<><Navigation /><Stack align="center" py="xl"><Loader size="lg" /></Stack></>}>
      <GroupsPageContent />
    </Suspense>
  );
}

function GroupsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, authState, isLoading: authLoading } = useAuth();
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchCity, setSearchCity] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const tabFromUrl = searchParams.get('tab');
  const myTabFromUrl = searchParams.get('myTab');
  const peopleTabFromUrl = searchParams.get('peopleTab');
  const [activeTab, setActiveTab] = useState(
    tabFromUrl === 'invitations'
      ? 'my-groups'
      : tabFromUrl === 'people'
        ? 'people'
        : tabFromUrl === 'my-groups'
          ? 'my-groups'
          : 'all'
  );
  const [myGroupsTab, setMyGroupsTab] = useState(
    tabFromUrl === 'invitations' || myTabFromUrl === 'invitations' ? 'invitations' : 'groups'
  );
  const [peopleTab, setPeopleTab] = useState(
    peopleTabFromUrl === 'inbox' ? 'inbox' : 'suggested'
  );
  const [userGroupIds, setUserGroupIds] = useState(new Set()); // Non-solo groups user is in (for "My Group" badge)
  const [userInAnyGroup, setUserInAnyGroup] = useState(false); // True if user is in ANY group (including solo)
  const [pendingRequestIds, setPendingRequestIds] = useState(new Set()); // Groups where user has pending join request
  const [joiningGroupId, setJoiningGroupId] = useState(null);
  const [recommendedGroupIds, setRecommendedGroupIds] = useState(new Set());

  // --- People tab state ---
  const queryClient = useQueryClient();
  const [useMlRanking, setUseMlRanking] = useState(true);
  const [expressedIds, setExpressedIds] = useState(() => new Set());
  const [funnelBanner, setFunnelBanner] = useState(null);
  const [respondingId, setRespondingId] = useState(null);
  const myId = user?.profile?.id;

  useEffect(() => {
    if (activeTab === 'people' || (activeTab === 'my-groups' && myGroupsTab === 'invitations')) return;
    fetchGroups();
    if (authState?.accessToken) {
      fetchUserMemberships();
      fetchRecommendedIds();
    }
  }, [statusFilter, activeTab, myGroupsTab, authState]);

  // --- People tab queries ---
  const token = authState?.accessToken;

  const suggestionsQuery = useQuery({
    queryKey: ['roommateSuggestions', token, useMlRanking],
    queryFn: () => api.getRoommateSuggestions(token, { limit: 20, mode: useMlRanking ? 'ml' : 'hard_filter' }),
    enabled: !!token && activeTab === 'people',
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
      await Promise.all([...ids].map(async (uid) => {
        try {
          const r = await api.getUserWithAuth(uid, token);
          profiles[uid] = r.data || r;
        } catch { profiles[uid] = { id: uid, full_name: 'User' }; }
      }));
      return { ...raw, profiles };
    },
    enabled: !!token && activeTab === 'people',
  });

  const expressMutation = useMutation({
    mutationFn: (toUserId) => api.expressRoommateInterest(token, toUserId),
    onSuccess: (data, toUserId) => {
      setExpressedIds((prev) => new Set(prev).add(toUserId));
      queryClient.invalidateQueries({ queryKey: ['roommateIntroInbox'] });
      if (data.funnel?.group_id) {
        setFunnelBanner(data.funnel);
        notifications.show({ title: "You're matched", message: 'Open your group to continue.', color: 'teal' });
      } else {
        notifications.show({ title: 'Interest sent', message: "They'll see this in their inbox.", color: 'teal' });
      }
    },
    onError: (e) => notifications.show({ title: 'Could not send', message: e.message, color: 'red' }),
  });

  const respondMutation = useMutation({
    mutationFn: ({ introId, action }) => api.respondToRoommateIntro(token, introId, action),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['roommateIntroInbox'] });
      if (data.funnel?.group_id) {
        setFunnelBanner(data.funnel);
        notifications.show({ title: 'Accepted', message: 'Continue in your roommate group.', color: 'teal' });
      } else {
        notifications.show({ title: 'Updated', message: 'Intro status saved.', color: 'teal' });
      }
    },
    onError: (e) => notifications.show({ title: 'Action failed', message: e.message, color: 'red' }),
    onSettled: () => setRespondingId(null),
  });

  const handleRespond = (introId, action) => {
    setRespondingId(introId);
    respondMutation.mutate({ introId, action });
  };

  const suggestions = suggestionsQuery.data?.suggestions || [];
  const prefsError = suggestionsQuery.isError && (suggestionsQuery.error?.message || '').toLowerCase().includes('target_city');

  // --- End People tab queries ---

  const fetchRecommendedIds = async () => {
    if (!authState?.accessToken) return;
    try {
      const city = searchCity || 'San Francisco';
      const response = await fetch(
        `http://localhost:8000/api/matches/groups?city=${encodeURIComponent(city)}&min_score=30&limit=50`,
        { headers: { 'Authorization': `Bearer ${authState.accessToken}` } }
      );
      const data = await response.json();
      if (response.ok && data.status === 'success') {
        setRecommendedGroupIds(new Set(data.groups.map(g => g.group_id || g.id)));
      }
    } catch {
      // best-effort — flags are optional
    }
  };

  const fetchUserMemberships = async () => {
    if (!authState?.accessToken) return;

    try {
      // Fetch user's pending join requests
      const pendingResponse = await fetch(
        'http://localhost:8000/api/roommate-groups/my-pending-requests',
        {
          headers: {
            'Authorization': `Bearer ${authState.accessToken}`
          }
        }
      );
      const pendingData = await pendingResponse.json();

      if (pendingResponse.ok && pendingData.status === 'success') {
        const pendingIds = new Set(pendingData.data.map(r => r.group_id));
        setPendingRequestIds(pendingIds);
      }

      // Fetch user's accepted memberships
      const response = await fetch(
        'http://localhost:8000/api/roommate-groups?my_groups=true',
        {
          headers: {
            'Authorization': `Bearer ${authState.accessToken}`
          }
        }
      );
      const data = await response.json();

      if (data.status === 'success') {
        // Check if user is in ANY group (including solo) - blocks joining other groups
        const allGroups = data.data || [];
        setUserInAnyGroup(allGroups.length > 0);

        // Filter out solo groups for the "My Group" badge display
        const nonSoloGroups = allGroups.filter(g => g.is_solo !== true);
        const memberGroupIds = new Set(nonSoloGroups.map(g => g.id));

        console.log('User memberships:', {
          allGroups: allGroups.map(g => ({ id: g.id, name: g.group_name, is_solo: g.is_solo })),
          nonSoloGroups: nonSoloGroups.map(g => ({ id: g.id, name: g.group_name })),
          userInAnyGroup: allGroups.length > 0
        });

        setUserGroupIds(memberGroupIds);
      }
    } catch (error) {
      console.error('Error fetching user memberships:', error);
    }
  };

  const fetchGroups = async () => {
    try {
      setLoading(true);
      let url = `http://localhost:8000/api/roommate-groups?status=${statusFilter}`;

      if (activeTab === 'my-groups' && user) {
        url += '&my_groups=true';
      }

      if (searchCity) {
        url += `&city=${encodeURIComponent(searchCity)}`;
      }

      // Get token from authState
      const headers = {};
      if (authState?.accessToken) {
        headers['Authorization'] = `Bearer ${authState.accessToken}`;
      }

      console.log('Fetching groups:', { url, hasToken: !!authState?.accessToken, activeTab, user: user?.id });

      const response = await fetch(url, { headers });
      const data = await response.json();

      console.log('Groups response:', { status: data.status, count: data.count, groupsLength: data.data?.length });

      if (data.status === 'success') {
        // For "All Groups" tab, filter out solo groups (they're personal)
        // For "My Groups" tab, show all groups including solo
        const filteredGroups = activeTab === 'all'
          ? data.data.filter(g => g.is_solo !== true)
          : data.data;
        setGroups(filteredGroups);
      }
    } catch (error) {
      console.error('Error fetching groups:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    fetchGroups();
    if (authState?.accessToken) fetchRecommendedIds();
  };

  const handleJoinGroup = async (groupId, e) => {
    e.stopPropagation();

    if (!authState?.accessToken) {
      notifications.show({
        title: 'Authentication Required',
        message: 'Please log in to join a group',
        color: 'orange',
      });
      router.push('/login');
      return;
    }

    setJoiningGroupId(groupId);

    try {
      const response = await fetch(
        `http://localhost:8000/api/roommate-groups/${groupId}/request-join`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${authState.accessToken}`
          }
        }
      );

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        // Add to pending requests
        setPendingRequestIds(prev => new Set([...prev, groupId]));

        notifications.show({
          title: 'Join Request Sent!',
          message: 'Check My Group > Invitations to accept and join the group',
          color: 'green',
          icon: <IconCheck />,
        });
        // Don't refresh immediately - user needs to accept the invitation first
      } else {
        throw new Error(data.detail || 'Failed to send join request');
      }
    } catch (error) {
      console.error('Error joining group:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to send join request',
        color: 'red',
      });
    } finally {
      setJoiningGroupId(null);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'green';
      case 'inactive': return 'gray';
      case 'matched': return 'blue';
      default: return 'gray';
    }
  };

  if (authLoading) {
    return (
      <>
        <Navigation />
        <Container size="lg" py="xl">
          <Stack align="center" gap="md" style={{ minHeight: '400px', justifyContent: 'center' }}>
            <Loader size="lg" />
            <Text>Loading...</Text>
          </Stack>
        </Container>
      </>
    );
  }

  return (
    <>
      <Navigation />
      <Container size="lg" py="xl">
        <Stack gap="xl">
        {/* Header */}
        <Group justify="space-between" align="flex-start" data-tour="groups-header">
          <Group gap="sm" align="flex-start" mb="xs">
            <Box style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(32,201,151,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 4, flexShrink: 0 }}>
              <IconUsers size={22} color="#20c997" />
            </Box>
            <div>
              <Title order={1}>Roommate Groups</Title>
              <Text c="dimmed" mt={4}>Find or create groups to search for housing together</Text>
            </div>
          </Group>
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => router.push('/groups/create')}
            size="md"
          >
            Create Group
          </Button>
        </Group>

        {/* Tabs */}
        <Tabs value={activeTab} onChange={setActiveTab} data-tour="groups-tabs">
          <Tabs.List>
            <Tabs.Tab value="all" leftSection={<IconUsers size={16} />}>
              All Groups
            </Tabs.Tab>
            {authState?.accessToken && (
              <Tabs.Tab value="my-groups" leftSection={<IconUsers size={16} />}>
                My Group
              </Tabs.Tab>
            )}
            {authState?.accessToken && (
              <Tabs.Tab value="people" leftSection={<IconUserSearch size={16} />}>
                People
              </Tabs.Tab>
            )}
          </Tabs.List>
        </Tabs>

        {/* Tab Content */}
        {activeTab === 'people' ? (
          <Stack gap="lg">
            {funnelBanner?.group_id && (
              <Alert icon={<IconHome size={18} />} title="Next step" color="teal" variant="light">
                <Text size="sm" mb="sm">
                  {funnelBanner.next_step === 'join_group'
                    ? 'Accept your invite and join the roommate group to continue.'
                    : 'Open your roommate group to coordinate with your match.'}
                </Text>
                <Button component={Link} href={`/groups/${funnelBanner.group_id}`} size="sm" color="teal">
                  Go to group
                </Button>
              </Alert>
            )}

            <Card withBorder={false} style={{ backgroundColor: '#f8f9fa' }}>
              <Group justify="flex-end" align="center" wrap="wrap">
                <SegmentedControl
                  value={peopleTab}
                  onChange={setPeopleTab}
                  data={[
                    { label: 'Suggested', value: 'suggested' },
                    { label: 'Inbox', value: 'inbox' },
                  ]}
                  color="teal"
                />
              </Group>
            </Card>

            {peopleTab === 'suggested' ? (
              <Stack gap="md">
                <Card padding="md" radius="lg" style={{ backgroundColor: '#f8f9fa' }}>
                  <Group justify="space-between" align="center" wrap="wrap">
                    <div>
                      <Text size="sm" fw={500}>Ranking mode</Text>
                      <Text size="xs" c="dimmed">Toggle between ML ranking and hard constraints.</Text>
                    </div>
                    <Switch checked={useMlRanking} onChange={(e) => setUseMlRanking(e.currentTarget.checked)} color="teal" onLabel="ML" offLabel="Hard" />
                  </Group>
                </Card>

                {suggestionsQuery.isLoading && <Center py="xl"><Loader color="teal" /></Center>}

                {prefsError && (
                  <Alert icon={<IconAlertCircle size={18} />} color="orange" title="Set your city">
                    <Text size="sm" mb="md">{suggestionsQuery.error.message}</Text>
                    <Button component={Link} href="/account?tab=preferences" variant="light" color="teal">Open preferences</Button>
                  </Alert>
                )}

                {suggestionsQuery.isError && !prefsError && (
                  <Alert color="red" title="Could not load suggestions">{suggestionsQuery.error.message}</Alert>
                )}

                {!suggestionsQuery.isLoading && !suggestionsQuery.isError && suggestions.length === 0 && (
                  <Alert color="gray" title="No matches yet">
                    <Text size="sm">
                      {useMlRanking ? 'No strong ranked matches right now. Swipe on ' : 'No users meet your hard constraints. Swipe on '}
                      <Text component={Link} href="/discover" c="teal" inherit span fw={500}>Discover</Text>
                      {useMlRanking ? ' to improve your taste signal.' : ' to improve data coverage.'}
                    </Text>
                  </Alert>
                )}

                {suggestions.map((item) => (
                  <SuggestionCard
                    key={item.user_id}
                    item={item}
                    myId={myId}
                    useMlRanking={useMlRanking}
                    onExpress={(uid) => expressMutation.mutate(uid)}
                    expressing={expressMutation.isPending && expressMutation.variables === item.user_id}
                    expressedSet={expressedIds}
                  />
                ))}
              </Stack>
            ) : (
              <>
                {inboxQuery.isLoading && <Center py="xl"><Loader color="teal" /></Center>}
                {inboxQuery.isError && <Alert color="red">{inboxQuery.error.message}</Alert>}
                {!inboxQuery.isLoading && !inboxQuery.isError && (
                  <Stack gap="xl">
                    <div>
                      <Text fw={600} mb="sm">Incoming</Text>
                      {(inboxQuery.data?.incoming || []).length === 0 ? (
                        <Text size="sm" c="dimmed">No incoming requests.</Text>
                      ) : (
                        <Stack gap="sm">
                          {(inboxQuery.data.incoming || []).map((row) => (
                            <IntroRow key={row.id} row={row} direction="incoming" profiles={inboxQuery.data.profiles || {}} onRespond={handleRespond} respondingId={respondingId} />
                          ))}
                        </Stack>
                      )}
                    </div>
                    <Divider />
                    <div>
                      <Text fw={600} mb="sm">Outgoing</Text>
                      {(inboxQuery.data?.outgoing || []).length === 0 ? (
                        <Text size="sm" c="dimmed">You haven't sent interest to anyone yet.</Text>
                      ) : (
                        <Stack gap="sm">
                          {(inboxQuery.data.outgoing || []).map((row) => (
                            <IntroRow key={row.id} row={row} direction="outgoing" profiles={inboxQuery.data.profiles || {}} onRespond={handleRespond} respondingId={respondingId} />
                          ))}
                        </Stack>
                      )}
                    </div>
                  </Stack>
                )}
              </>
            )}
          </Stack>
        ) : activeTab === 'my-groups' ? (
          <Stack gap="md">
            <Card withBorder={false} style={{ backgroundColor: '#f8f9fa' }}>
              <Group justify="flex-end" align="center" wrap="wrap">
                <SegmentedControl
                  value={myGroupsTab}
                  onChange={setMyGroupsTab}
                  data={[
                    { label: 'Group', value: 'groups' },
                    { label: 'Invitations', value: 'invitations' },
                  ]}
                  color="teal"
                />
              </Group>
            </Card>

            {myGroupsTab === 'invitations' && (
              <InvitationsPanel user={user} authState={authState} />
            )}
            {myGroupsTab === 'groups' && (
              <>
                {/* Search and Filters */}
                <Card withBorder={false} style={{ backgroundColor: '#f8f9fa' }} data-tour="groups-search">
                  <Group gap="md">
                    <TextInput
                      placeholder="Search by city..."
                      leftSection={<IconSearch size={16} />}
                      value={searchCity}
                      onChange={(e) => setSearchCity(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                      style={{ flex: 1 }}
                    />
                    <Select
                      placeholder="Status"
                      data={[
                        { value: 'active', label: 'Active' },
                        { value: 'inactive', label: 'Inactive' },
                        { value: 'matched', label: 'Matched' }
                      ]}
                      value={statusFilter}
                      onChange={setStatusFilter}
                      style={{ width: 150 }}
                    />
                    <Button onClick={handleSearch}>Search</Button>
                  </Group>
                </Card>

                {/* Groups Grid */}
                <div data-tour="groups-list">
                  {loading ? (
                    <Grid>
                      {[1,2,3,4,5,6].map(i => (
                        <Grid.Col key={i} span={{ base: 12, sm: 6, md: 4 }}>
                          <Card radius="lg" shadow="sm" style={{ height: 220 }}>
                            <Stack gap="md">
                              <Skeleton height={20} width="60%" />
                              <Skeleton height={14} width="40%" />
                              <Skeleton height={14} width="80%" />
                              <Box style={{ flex: 1 }} />
                              <Skeleton height={36} />
                            </Stack>
                          </Card>
                        </Grid.Col>
                      ))}
                    </Grid>
                  ) : groups.length === 0 ? (
                    <Card withBorder p="xl">
                      <Stack align="center" gap="md" py="xl">
                        <ThemeIcon size={64} variant="light" color="teal"><IconUsers size={32} /></ThemeIcon>
                        <Title order={3}>No groups found</Title>
                        <Text c="dimmed" ta="center">
                          {"You haven't joined any groups yet. Create one or browse all groups to join."}
                        </Text>
                      </Stack>
                    </Card>
                  ) : (
                    <Grid>
                      {groups.map((group) => (
                        <Grid.Col key={group.id} span={{ base: 12, sm: 6, md: 4 }}>
                          <Card
                            className="card-lift"
                            padding="lg"
                            radius="lg"
                            shadow="sm"
                            style={{
                              height: '100%',
                              cursor: 'pointer',
                            }}
                            onClick={() => router.push(`/groups/${group.id}`)}
                          >
                            <Stack gap="md" style={{ height: '100%' }}>
                              {/* Header */}
                              <Group justify="space-between">
                                <Group gap="xs">
                                  <Badge color={getStatusColor(group.status)} variant="light">
                                    {group.status}
                                  </Badge>
                                  {/* My Group badge for groups user is a member of */}
                                  {userGroupIds.has(group.id) && (
                                    <Badge color="blue" variant="filled">
                                      My Group
                                    </Badge>
                                  )}
                                  {group.is_solo === true && (
                                    <Badge color="grape" variant="light">
                                      Solo
                                    </Badge>
                                  )}
                                  {recommendedGroupIds.has(group.id) && (
                                    <Badge color="teal" variant="light" leftSection={<IconSparkles size={12} />}>
                                      Recommended
                                    </Badge>
                                  )}
                                </Group>
                                <Group gap={4}>
                                  <IconUsers size={16} color="gray" />
                                  <Text size="sm" c="dimmed">
                                    {group.target_group_size}
                                  </Text>
                                </Group>
                              </Group>

                              {/* Title */}
                              <Title order={4} lineClamp={2}>
                                {group.group_name}
                              </Title>

                              {/* Description */}
                              <Text size="sm" c="dimmed" lineClamp={2} style={{ flex: 1 }}>
                                {group.description || 'No description provided'}
                              </Text>

                              {/* Details */}
                              <Stack gap="xs">
                                <Group gap="xs">
                                  <IconMapPin size={16} color="gray" />
                                  <Text size="sm">{group.target_city}</Text>
                                </Group>

                                {group.budget_per_person_min && group.budget_per_person_max && (
                                  <Group gap="xs">
                                    <IconCurrencyDollar size={16} color="gray" />
                                    <Text size="sm">
                                      ${group.budget_per_person_min} - ${group.budget_per_person_max}
                                    </Text>
                                  </Group>
                                )}

                                {group.target_move_in_date && (
                                  <Group gap="xs">
                                    <IconCalendar size={16} color="gray" />
                                    <Text size="sm">
                                      {new Date(group.target_move_in_date).toLocaleDateString()}
                                    </Text>
                                  </Group>
                                )}
                              </Stack>

                              {/* Full Group Indicator - only show if we have valid data */}
                              {group.target_group_size && (group.current_member_count || 0) >= group.target_group_size && (
                                <Badge color="red" variant="filled" size="lg" fullWidth>
                                  Group is Full
                                </Badge>
                              )}

                              {/* Pending Request Indicator */}
                              {pendingRequestIds.has(group.id) && (
                                <Badge color="blue" variant="light" size="lg" fullWidth>
                                  ✓ Request Sent
                                </Badge>
                              )}

                              {/* Footer */}
                              <Group gap="xs" mt="auto">
                                {/* Show Join button only if: user is logged in, no pending request, not in this group, group not full, and user not in ANY group (including solo) */}
                                {!pendingRequestIds.has(group.id) && !userGroupIds.has(group.id) && authState?.accessToken && (!group.target_group_size || (group.current_member_count || 0) < group.target_group_size) && !userInAnyGroup ? (
                                  <>
                                    <Button
                                      variant="filled"
                                      color="green"
                                      flex={1}
                                      leftSection={<IconUserPlus size={16} />}
                                      onClick={(e) => handleJoinGroup(group.id, e)}
                                      loading={joiningGroupId === group.id}
                                    >
                                      Join
                                    </Button>
                                    <Button
                                      variant="light"
                                      flex={1}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        router.push(`/groups/${group.id}`);
                                      }}
                                    >
                                      View
                                    </Button>
                                  </>
                                ) : (
                                  <Button
                                    variant="light"
                                    fullWidth
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      router.push(`/groups/${group.id}`);
                                    }}
                                  >
                                    View Details
                                  </Button>
                                )}
                              </Group>
                            </Stack>
                          </Card>
                        </Grid.Col>
                      ))}
                    </Grid>
                  )}
                </div>
              </>
            )}
          </Stack>
        ) : (
        <>
        {/* Search and Filters */}
        <Card withBorder={false} style={{ backgroundColor: '#f8f9fa' }} data-tour="groups-search">
          <Group gap="md">
            <TextInput
              placeholder="Search by city..."
              leftSection={<IconSearch size={16} />}
              value={searchCity}
              onChange={(e) => setSearchCity(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              style={{ flex: 1 }}
            />
            <Select
              placeholder="Status"
              data={[
                { value: 'active', label: 'Active' },
                { value: 'inactive', label: 'Inactive' },
                { value: 'matched', label: 'Matched' }
              ]}
              value={statusFilter}
              onChange={setStatusFilter}
              style={{ width: 150 }}
            />
            <Button onClick={handleSearch}>Search</Button>
          </Group>
        </Card>

        {/* Groups Grid */}
        <div data-tour="groups-list">
        {loading ? (
          <Grid>
            {[1,2,3,4,5,6].map(i => (
              <Grid.Col key={i} span={{ base: 12, sm: 6, md: 4 }}>
                <Card radius="lg" shadow="sm" style={{ height: 220 }}>
                  <Stack gap="md">
                    <Skeleton height={20} width="60%" />
                    <Skeleton height={14} width="40%" />
                    <Skeleton height={14} width="80%" />
                    <Box style={{ flex: 1 }} />
                    <Skeleton height={36} />
                  </Stack>
                </Card>
              </Grid.Col>
            ))}
          </Grid>
        ) : groups.length === 0 ? (
          <Card withBorder p="xl">
            <Stack align="center" gap="md" py="xl">
              <ThemeIcon size={64} variant="light" color="teal"><IconUsers size={32} /></ThemeIcon>
              <Title order={3}>No groups found</Title>
              <Text c="dimmed" ta="center">
                {activeTab === 'my-groups'
                  ? "You haven't joined any groups yet. Create one or browse all groups to join."
                  : "No groups match your search criteria. Try adjusting your filters."}
              </Text>
              {activeTab === 'all' && (
                <Button onClick={() => router.push('/groups/create')} mt="md">
                  Create Your First Group
                </Button>
              )}
            </Stack>
          </Card>
        ) : (
          <Grid>
            {groups.map((group) => (
              <Grid.Col key={group.id} span={{ base: 12, sm: 6, md: 4 }}>
                <Card
                  className="card-lift"
                  padding="lg"
                  radius="lg"
                  shadow="sm"
                  style={{
                    height: '100%',
                    cursor: 'pointer',
                  }}
                  onClick={() => router.push(`/groups/${group.id}`)}
                >
                  <Stack gap="md" style={{ height: '100%' }}>
                    {/* Header */}
                    <Group justify="space-between">
                      <Group gap="xs">
                        <Badge color={getStatusColor(group.status)} variant="light">
                          {group.status}
                        </Badge>
                        {/* My Group badge for groups user is a member of */}
                        {userGroupIds.has(group.id) && (
                          <Badge color="blue" variant="filled">
                            My Group
                          </Badge>
                        )}
                        {group.is_solo === true && (
                          <Badge color="grape" variant="light">
                            Solo
                          </Badge>
                        )}
                        {recommendedGroupIds.has(group.id) && (
                          <Badge color="teal" variant="light" leftSection={<IconSparkles size={12} />}>
                            Recommended
                          </Badge>
                        )}
                      </Group>
                      <Group gap={4}>
                        <IconUsers size={16} color="gray" />
                        <Text size="sm" c="dimmed">
                          {group.target_group_size ?? 'Unlimited'}
                        </Text>
                      </Group>
                    </Group>

                    {/* Title */}
                    <Title order={4} lineClamp={2}>
                      {group.group_name}
                    </Title>

                    {/* Description */}
                    <Text size="sm" c="dimmed" lineClamp={2} style={{ flex: 1 }}>
                      {group.description || 'No description provided'}
                    </Text>

                    {/* Details */}
                    <Stack gap="xs">
                      <Group gap="xs">
                        <IconMapPin size={16} color="gray" />
                        <Text size="sm">{group.target_city}</Text>
                      </Group>

                      {group.budget_per_person_min && group.budget_per_person_max && (
                        <Group gap="xs">
                          <IconCurrencyDollar size={16} color="gray" />
                          <Text size="sm">
                            ${group.budget_per_person_min} - ${group.budget_per_person_max}
                          </Text>
                        </Group>
                      )}

                      {group.target_move_in_date && (
                        <Group gap="xs">
                          <IconCalendar size={16} color="gray" />
                          <Text size="sm">
                            {new Date(group.target_move_in_date).toLocaleDateString()}
                          </Text>
                        </Group>
                      )}
                    </Stack>

                    {/* Full Group Indicator - only show if we have valid data */}
                    {group.target_group_size && (group.current_member_count || 0) >= group.target_group_size && (
                      <Badge color="red" variant="filled" size="lg" fullWidth>
                        Group is Full
                      </Badge>
                    )}

                    {/* Pending Request Indicator */}
                    {pendingRequestIds.has(group.id) && (
                      <Badge color="blue" variant="light" size="lg" fullWidth>
                        ✓ Request Sent
                      </Badge>
                    )}

                    {/* Footer */}
                    <Group gap="xs" mt="auto">
                      {/* Show Join button only if: user is logged in, no pending request, not in this group, group not full, and user not in ANY group (including solo) */}
                      {!pendingRequestIds.has(group.id) && !userGroupIds.has(group.id) && authState?.accessToken && (!group.target_group_size || (group.current_member_count || 0) < group.target_group_size) && !userInAnyGroup ? (
                        <>
                          <Button
                            variant="filled"
                            color="green"
                            flex={1}
                            leftSection={<IconUserPlus size={16} />}
                            onClick={(e) => handleJoinGroup(group.id, e)}
                            loading={joiningGroupId === group.id}
                          >
                            Join
                          </Button>
                          <Button
                            variant="light"
                            flex={1}
                            onClick={(e) => {
                              e.stopPropagation();
                              router.push(`/groups/${group.id}`);
                            }}
                          >
                            View
                          </Button>
                        </>
                      ) : (
                        <Button
                          variant="light"
                          fullWidth
                          onClick={(e) => {
                            e.stopPropagation();
                            router.push(`/groups/${group.id}`);
                          }}
                        >
                          View Details
                        </Button>
                      )}
                    </Group>
                  </Stack>
                </Card>
              </Grid.Col>
            ))}
          </Grid>
        )}
        </div>
        </>
        )}
      </Stack>
    </Container>
    </>
  );
}
