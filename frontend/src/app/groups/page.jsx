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
import { IconPlus, IconSearch, IconUsers, IconMapPin, IconCalendar, IconCurrencyDollar, IconCheck, IconUserPlus } from '@tabler/icons-react';
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
  const [userGroupIds, setUserGroupIds] = useState(new Set());
  const [joiningGroupId, setJoiningGroupId] = useState(null);

  useEffect(() => {
    fetchGroups();
    if (user && authState) {
      fetchUserMemberships();
    }
  }, [statusFilter, activeTab, user, authState]);

  const fetchUserMemberships = async () => {
    if (!authState?.accessToken) return;
    
    try {
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
        const memberGroupIds = new Set(data.data.map(g => g.id));
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
        setGroups(data.data);
      }
    } catch (error) {
      console.error('Error fetching groups:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    fetchGroups();
  };

  const handleJoinGroup = async (groupId, e) => {
    e.stopPropagation();
    
    if (!user || !authState?.accessToken) {
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
        <Group justify="space-between" align="flex-start">
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
        <Tabs value={activeTab} onChange={setActiveTab}>
          <Tabs.List>
            <Tabs.Tab value="all" leftSection={<IconUsers size={16} />}>
              All Groups
            </Tabs.Tab>
            {user && (
              <Tabs.Tab value="my-groups" leftSection={<IconUsers size={16} />}>
                My Groups
              </Tabs.Tab>
            )}
          </Tabs.List>
        </Tabs>

        {/* Search and Filters */}
        <Card withBorder>
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
        {loading ? (
          <Stack align="center" gap="md" style={{ minHeight: '300px', justifyContent: 'center' }}>
            <Loader size="lg" />
            <Text>Loading groups...</Text>
          </Stack>
        ) : groups.length === 0 ? (
          <Card withBorder p="xl">
            <Stack align="center" gap="md" py="xl">
              <IconUsers size={48} stroke={1.5} color="gray" />
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
                      <Badge color={getStatusColor(group.status)} variant="light">
                        {group.status}
                      </Badge>
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

                    {/* Footer */}
                    <Group gap="xs" mt="auto">
                      {!userGroupIds.has(group.id) && user ? (
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
      </Stack>
    </Container>
    </>
  );
}
