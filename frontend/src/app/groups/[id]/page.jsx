'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { 
  Container, 
  Title, 
  Text, 
  Button, 
  Stack, 
  Card, 
  Badge,
  Group,
  Avatar,
  Divider,
  Modal,
  TextInput,
  ActionIcon,
  Menu,
  Alert,
  Grid,
  Paper,
  Tabs,
  Loader,
  Center
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { 
  IconArrowLeft, 
  IconUsers, 
  IconMail,
  IconUserPlus,
  IconDoorExit,
  IconEdit,
  IconTrash,
  IconDotsVertical,
  IconCheck,
  IconX,
  IconMapPin,
  IconCurrencyDollar,
  IconCalendar,
  IconBuildingCommunity,
  IconAlertCircle,
  IconHome
} from '@tabler/icons-react';
import { useAuth } from '../../contexts/AuthContext';
import { Navigation } from '../../components/Navigation';

export default function GroupDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { user, token } = useAuth();
  const groupId = params.id;

  const [group, setGroup] = useState(null);
  const [members, setMembers] = useState([]);
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviting, setInviting] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    if (groupId) {
      fetchGroupData();
    }
  }, [groupId]);

  const fetchGroupData = async () => {
    setLoading(true);
    try {
      // Fetch group details with members
      const groupResponse = await fetch(
        `http://localhost:8000/api/roommate-groups/${groupId}?include_members=true`,
        {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        }
      );
      const groupData = await groupResponse.json();

      if (groupResponse.ok && groupData.status === 'success') {
        setGroup(groupData.data);
        setMembers(groupData.data.members || []);
      }

      // Fetch matches
      const matchesResponse = await fetch(
        `http://localhost:8000/api/roommate-groups/${groupId}/matches`,
        {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        }
      );
      const matchesData = await matchesResponse.json();

      if (matchesResponse.ok && matchesData.status === 'success') {
        setMatches(matchesData.data || []);
      }
    } catch (error) {
      console.error('Error fetching group data:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to load group details',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleInvite = async () => {
    if (!inviteEmail) {
      notifications.show({
        title: 'Missing Email',
        message: 'Please enter an email address',
        color: 'orange',
      });
      return;
    }

    setInviting(true);
    try {
      const response = await fetch(
        `http://localhost:8000/api/roommate-groups/${groupId}/invite`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ email: inviteEmail })
        }
      );

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Invitation Sent',
          message: `Invitation sent to ${inviteEmail}`,
          color: 'green',
          icon: <IconCheck />,
        });
        setInviteModalOpen(false);
        setInviteEmail('');
        fetchGroupData(); // Refresh to show pending invitation
      } else {
        throw new Error(data.detail || 'Failed to send invitation');
      }
    } catch (error) {
      console.error('Error sending invitation:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to send invitation',
        color: 'red',
      });
    } finally {
      setInviting(false);
    }
  };

  const handleLeaveGroup = async () => {
    if (!confirm('Are you sure you want to leave this group?')) return;

    try {
      const response = await fetch(
        `http://localhost:8000/api/roommate-groups/${groupId}/leave`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Left Group',
          message: 'You have left the group',
          color: 'green',
        });
        router.push('/groups');
      } else {
        throw new Error(data.detail || 'Failed to leave group');
      }
    } catch (error) {
      console.error('Error leaving group:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to leave group',
        color: 'red',
      });
    }
  };

  const handleDeleteGroup = async () => {
    if (!confirm('Are you sure you want to delete this group? This action cannot be undone.')) return;

    try {
      const response = await fetch(
        `http://localhost:8000/api/roommate-groups/${groupId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Group Deleted',
          message: 'The group has been deleted',
          color: 'green',
        });
        router.push('/groups');
      } else {
        throw new Error(data.detail || 'Failed to delete group');
      }
    } catch (error) {
      console.error('Error deleting group:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to delete group',
        color: 'red',
      });
    }
  };

  const handleRemoveMember = async (memberId) => {
    if (!confirm('Are you sure you want to remove this member?')) return;

    try {
      const response = await fetch(
        `http://localhost:8000/api/roommate-groups/${groupId}/members/${memberId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Member Removed',
          message: 'Member has been removed from the group',
          color: 'green',
        });
        fetchGroupData();
      } else {
        throw new Error(data.detail || 'Failed to remove member');
      }
    } catch (error) {
      console.error('Error removing member:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to remove member',
        color: 'red',
      });
    }
  };

  if (loading) {
    return (
      <>
        <Navigation />
        <Center h="80vh">
          <Loader size="lg" />
        </Center>
      </>
    );
  }

  if (!group) {
    return (
      <>
        <Navigation />
        <Container size="md" py="xl">
          <Alert icon={<IconAlertCircle />} title="Group Not Found" color="red">
            The group you're looking for doesn't exist or has been deleted.
          </Alert>
          <Button mt="md" onClick={() => router.push('/groups')}>
            Back to Groups
          </Button>
        </Container>
      </>
    );
  }

  const isCreator = user && group.created_by === user.id;
  const isMember = user && members.some(m => m.user_id === user.id);
  const statusColor = {
    active: 'blue',
    matched: 'green',
    inactive: 'gray'
  }[group.status] || 'gray';

  return (
    <>
      <Navigation />
      <Container size="xl" py="xl">
        <Stack gap="xl">
          {/* Header */}
          <Group justify="space-between">
          <Group>
            <Button
              variant="subtle"
              leftSection={<IconArrowLeft size={16} />}
              onClick={() => router.back()}
            >
              Back
            </Button>
          </Group>

          {isMember && (
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <ActionIcon variant="subtle" size="lg">
                  <IconDotsVertical size={20} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                {isCreator && (
                  <>
                    <Menu.Item
                      leftSection={<IconEdit size={16} />}
                      onClick={() => router.push(`/groups/${groupId}/edit`)}
                    >
                      Edit Group
                    </Menu.Item>
                    <Menu.Item
                      leftSection={<IconTrash size={16} />}
                      color="red"
                      onClick={handleDeleteGroup}
                    >
                      Delete Group
                    </Menu.Item>
                  </>
                )}
                {!isCreator && (
                  <Menu.Item
                    leftSection={<IconDoorExit size={16} />}
                    color="red"
                    onClick={handleLeaveGroup}
                  >
                    Leave Group
                  </Menu.Item>
                )}
              </Menu.Dropdown>
            </Menu>
          )}
        </Group>

        {/* Group Header */}
        <Card withBorder p="xl">
          <Stack gap="md">
            <Group justify="space-between" align="flex-start">
              <div>
                <Group gap="xs" mb="xs">
                  <Title order={1}>{group.group_name}</Title>
                  <Badge color={statusColor} size="lg">
                    {group.status}
                  </Badge>
                </Group>
                {group.description && (
                  <Text c="dimmed" mt="xs">{group.description}</Text>
                )}
              </div>

              {isMember && (
                <Button
                  leftSection={<IconUserPlus size={18} />}
                  onClick={() => setInviteModalOpen(true)}
                >
                  Invite Members
                </Button>
              )}
            </Group>

            <Divider />

            <Grid>
              <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
                <Group gap="xs">
                  <IconMapPin size={18} />
                  <div>
                    <Text size="xs" c="dimmed">Target City</Text>
                    <Text fw={500}>{group.target_city}</Text>
                  </div>
                </Group>
              </Grid.Col>

              <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
                <Group gap="xs">
                  <IconCurrencyDollar size={18} />
                  <div>
                    <Text size="xs" c="dimmed">Budget (per person)</Text>
                    <Text fw={500}>
                      {group.budget_per_person_min && group.budget_per_person_max
                        ? `$${group.budget_per_person_min} - $${group.budget_per_person_max}`
                        : 'Not set'}
                    </Text>
                  </div>
                </Group>
              </Grid.Col>

              <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
                <Group gap="xs">
                  <IconCalendar size={18} />
                  <div>
                    <Text size="xs" c="dimmed">Move-in Date</Text>
                    <Text fw={500}>
                      {group.target_move_in_date 
                        ? new Date(group.target_move_in_date).toLocaleDateString()
                        : 'Flexible'}
                    </Text>
                  </div>
                </Group>
              </Grid.Col>

              <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
                <Group gap="xs">
                  <IconUsers size={18} />
                  <div>
                    <Text size="xs" c="dimmed">Group Size</Text>
                    <Text fw={500}>
                      {members.length}/{group.target_group_size || '?'}
                    </Text>
                  </div>
                </Group>
              </Grid.Col>
            </Grid>
          </Stack>
        </Card>

        {/* Tabs */}
        <Tabs value={activeTab} onChange={setActiveTab}>
          <Tabs.List>
            <Tabs.Tab value="overview" leftSection={<IconUsers size={16} />}>
              Members
            </Tabs.Tab>
            <Tabs.Tab value="matches" leftSection={<IconHome size={16} />}>
              Matches ({matches.length})
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="overview" pt="xl">
            <Card withBorder>
              <Stack gap="md">
                <Group justify="space-between">
                  <Title order={3}>Group Members</Title>
                  <Badge size="lg">{members.length} members</Badge>
                </Group>

                <Divider />

                {members.length === 0 ? (
                  <Text c="dimmed" ta="center" py="xl">
                    No members yet
                  </Text>
                ) : (
                  <Stack gap="sm">
                    {members.map((member) => (
                      <Paper key={member.user_id} p="md" withBorder>
                        <Group justify="space-between">
                          <Group>
                            <Avatar size="md" radius="xl">
                              {member.users?.full_name?.charAt(0) || 'U'}
                            </Avatar>
                            <div>
                              <Text fw={500}>
                                {member.users?.full_name || 'Unknown User'}
                              </Text>
                              <Group gap="xs">
                                <Text size="sm" c="dimmed">
                                  {member.users?.email}
                                </Text>
                                {member.user_id === group.created_by && (
                                  <Badge size="sm" variant="light">Creator</Badge>
                                )}
                                {member.role === 'pending' && (
                                  <Badge size="sm" color="orange">Pending</Badge>
                                )}
                              </Group>
                            </div>
                          </Group>

                          {isCreator && member.user_id !== group.created_by && (
                            <ActionIcon
                              color="red"
                              variant="subtle"
                              onClick={() => handleRemoveMember(member.user_id)}
                            >
                              <IconX size={18} />
                            </ActionIcon>
                          )}
                        </Group>
                      </Paper>
                    ))}
                  </Stack>
                )}
              </Stack>
            </Card>
          </Tabs.Panel>

          <Tabs.Panel value="matches" pt="xl">
            {matches.length === 0 ? (
              <Card withBorder>
                <Stack align="center" py="xl">
                  <IconBuildingCommunity size={48} stroke={1.5} color="gray" />
                  <Text c="dimmed">No matches found yet</Text>
                  <Text size="sm" c="dimmed" ta="center">
                    Matches will appear here once the matching algorithm runs
                  </Text>
                </Stack>
              </Card>
            ) : (
              <Stack gap="md">
                {matches.map((match) => (
                  <Card key={match.id} withBorder p="lg" style={{ cursor: 'pointer' }}
                    onClick={() => router.push(`/listings/${match.listing_id}`)}>
                    <Stack gap="md">
                      <Group justify="space-between">
                        <div>
                          <Title order={4}>{match.listing?.title || 'Listing'}</Title>
                          <Group gap="xs" mt="xs">
                            <IconMapPin size={16} />
                            <Text size="sm" c="dimmed">
                              {match.listing?.address}, {match.listing?.city}
                            </Text>
                          </Group>
                        </div>
                        <Badge color={match.is_stable ? 'green' : 'orange'} size="lg">
                          {match.is_stable ? 'Stable Match' : 'Unstable'}
                        </Badge>
                      </Group>

                      <Grid>
                        <Grid.Col span={6}>
                          <Paper p="sm" withBorder bg="blue.0">
                            <Text size="xs" c="dimmed">Price</Text>
                            <Text fw={600} size="lg">
                              ${match.listing?.price_per_month}/month
                            </Text>
                          </Paper>
                        </Grid.Col>
                        <Grid.Col span={6}>
                          <Paper p="sm" withBorder bg="blue.0">
                            <Text size="xs" c="dimmed">Bedrooms</Text>
                            <Text fw={600} size="lg">
                              {match.listing?.number_of_bedrooms} bed
                            </Text>
                          </Paper>
                        </Grid.Col>
                      </Grid>

                      <Group gap="xl">
                        <div>
                          <Text size="xs" c="dimmed">Your Group Rank</Text>
                          <Text fw={600}>#{match.group_rank}</Text>
                        </div>
                        <div>
                          <Text size="xs" c="dimmed">Listing Rank</Text>
                          <Text fw={600}>#{match.listing_rank}</Text>
                        </div>
                        <div>
                          <Text size="xs" c="dimmed">Group Score</Text>
                          <Text fw={600}>{match.group_score?.toFixed(2)}</Text>
                        </div>
                        <div>
                          <Text size="xs" c="dimmed">Listing Score</Text>
                          <Text fw={600}>{match.listing_score?.toFixed(2)}</Text>
                        </div>
                      </Group>

                      {match.listing?.available_from && (
                        <Group gap="xs">
                          <IconCalendar size={16} />
                          <Text size="sm">
                            Available from: {new Date(match.listing.available_from).toLocaleDateString()}
                          </Text>
                        </Group>
                      )}
                    </Stack>
                  </Card>
                ))}
              </Stack>
            )}
          </Tabs.Panel>
        </Tabs>
      </Stack>

      {/* Invite Modal */}
      <Modal
        opened={inviteModalOpen}
        onClose={() => setInviteModalOpen(false)}
        title="Invite Member"
      >
        <Stack gap="md">
          <TextInput
            label="Email Address"
            placeholder="friend@example.com"
            leftSection={<IconMail size={16} />}
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleInvite()}
          />
          <Button
            onClick={handleInvite}
            loading={inviting}
            fullWidth
          >
            Send Invitation
          </Button>
        </Stack>
      </Modal>
    </Container>
    </>
  );
}
