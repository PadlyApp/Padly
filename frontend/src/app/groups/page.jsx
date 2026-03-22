'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
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
  Tabs
} from '@mantine/core';
import { IconPlus, IconSearch, IconUsers, IconMapPin, IconCalendar, IconCurrencyDollar, IconCheck, IconUserPlus, IconSparkles, IconStar } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useAuth } from '../contexts/AuthContext';
import { Navigation } from '../components/Navigation';

export default function GroupsPage() {
  const router = useRouter();
  const { user, authState, isLoading: authLoading } = useAuth();
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchCity, setSearchCity] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [activeTab, setActiveTab] = useState('all');
  const [userGroupIds, setUserGroupIds] = useState(new Set()); // Non-solo groups user is in (for "My Group" badge)
  const [userInAnyGroup, setUserInAnyGroup] = useState(false); // True if user is in ANY group (including solo)
  const [pendingRequestIds, setPendingRequestIds] = useState(new Set()); // Groups where user has pending join request
  const [joiningGroupId, setJoiningGroupId] = useState(null);
  const [recommendedGroups, setRecommendedGroups] = useState([]);
  const [loadingRecommended, setLoadingRecommended] = useState(false);

  useEffect(() => {
    if (activeTab === 'recommended' && authState?.accessToken) {
      fetchRecommendedGroups();
    } else {
      fetchGroups();
    }
    if (authState?.accessToken) {
      fetchUserMemberships();
    }
  }, [statusFilter, activeTab, authState]);

  const fetchRecommendedGroups = async () => {
    if (!authState?.accessToken) return;
    
    setLoadingRecommended(true);
    try {
      // Use a default city or get from user preferences
      const city = searchCity || 'San Francisco'; // Default city
      const response = await fetch(
        `http://localhost:8000/api/matches/groups?city=${encodeURIComponent(city)}&min_score=30&limit=50`,
        {
          headers: {
            'Authorization': `Bearer ${authState.accessToken}`
          }
        }
      );
      const data = await response.json();
      
      if (response.ok && data.status === 'success') {
        // Add current_member_count for consistency with other views
        const groupsWithCount = data.groups.map(g => ({
          ...g,
          current_member_count: g.current_member_count || 0
        }));
        setRecommendedGroups(groupsWithCount);
      } else {
        console.error('Error fetching recommended groups:', data);
        setRecommendedGroups([]);
      }
    } catch (error) {
      console.error('Error fetching recommended groups:', error);
      setRecommendedGroups([]);
    } finally {
      setLoadingRecommended(false);
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
    if (activeTab === 'recommended') {
      fetchRecommendedGroups();
    } else {
      fetchGroups();
    }
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
          message: 'Check your Invitations page to accept and join the group',
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
          <div>
            <Title order={1}>Roommate Groups</Title>
            <Text c="dimmed" mt="xs">
              Find or create groups to search for housing together
            </Text>
          </div>
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
            {authState?.accessToken && (
              <Tabs.Tab value="recommended" leftSection={<IconSparkles size={16} />}>
                Recommended For You
              </Tabs.Tab>
            )}
            <Tabs.Tab value="all" leftSection={<IconUsers size={16} />}>
              All Groups
            </Tabs.Tab>
            {authState?.accessToken && (
              <Tabs.Tab value="my-groups" leftSection={<IconUsers size={16} />}>
                My Groups
              </Tabs.Tab>
            )}
          </Tabs.List>
        </Tabs>

        {/* Search and Filters */}
        <Card withBorder data-tour="groups-search">
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
        {(activeTab === 'recommended' ? loadingRecommended : loading) ? (
          <Stack align="center" gap="md" style={{ minHeight: '300px', justifyContent: 'center' }}>
            <Loader size="lg" />
            <Text>{activeTab === 'recommended' ? 'Finding compatible groups...' : 'Loading groups...'}</Text>
          </Stack>
        ) : (activeTab === 'recommended' ? recommendedGroups : groups).length === 0 ? (
          <Card withBorder p="xl">
            <Stack align="center" gap="md" py="xl">
              <IconUsers size={48} stroke={1.5} color="gray" />
              <Title order={3}>No groups found</Title>
              <Text c="dimmed" ta="center">
                {activeTab === 'my-groups' 
                  ? "You haven't joined any groups yet. Create one or browse all groups to join."
                  : activeTab === 'recommended'
                  ? "No compatible groups found. Try searching a different city or adjusting your preferences."
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
            {(activeTab === 'recommended' ? recommendedGroups : groups).map((group) => (
              <Grid.Col key={group.id} span={{ base: 12, sm: 6, md: 4 }}>
                <Card
                  withBorder
                  padding="lg"
                  style={{ 
                    height: '100%', 
                    cursor: 'pointer',
                    transition: 'transform 0.2s, box-shadow 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'translateY(-4px)';
                    e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.boxShadow = 'none';
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
                        {/* Compatibility score for recommended groups */}
                        {group.compatibility?.score && (
                          <Badge 
                            color={group.compatibility.score >= 80 ? 'green' : group.compatibility.score >= 60 ? 'teal' : 'yellow'} 
                            variant="filled"
                            leftSection={<IconStar size={12} />}
                          >
                            {Math.round(group.compatibility.score)}% Match
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
      </Stack>
    </Container>
    </>
  );
}
