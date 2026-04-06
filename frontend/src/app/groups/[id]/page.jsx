'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
  Center,
  Tooltip,
  ScrollArea,
  ThemeIcon,
  Progress,
  Skeleton
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
  IconHome,
  IconSearch,
  IconSparkles,
  IconMoon,
  IconVolume,
  IconSmokingNo,
  IconDog,
  IconFriends,
  IconInbox,
  IconHeart,
  IconBookmark
} from '@tabler/icons-react';
import { useAuth } from '../../contexts/AuthContext';
import { Navigation } from '../../components/Navigation';

export default function GroupDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { user, getValidToken, authState } = useAuth();
  const groupId = params.id;

  const [group, setGroup] = useState(null);
  const [members, setMembers] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviting, setInviting] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [inviteTab, setInviteTab] = useState('compatible');
  const [compatibleUsers, setCompatibleUsers] = useState([]);
  const [loadingCompatible, setLoadingCompatible] = useState(false);
  const [invitingUserId, setInvitingUserId] = useState(null);
  const [joinRequests, setJoinRequests] = useState([]);
  const [loadingRequests, setLoadingRequests] = useState(false);
  const [processingRequestId, setProcessingRequestId] = useState(null);
  const [memberSavedListings, setMemberSavedListings] = useState([]);
  const [loadingLiked, setLoadingLiked] = useState(false);

  useEffect(() => {
    if (groupId) {
      fetchGroupData();
    }
  }, [groupId]);

  // Fetch current user info if not available from context
  useEffect(() => {
    const fetchCurrentUser = async () => {
      if (!currentUser && authState?.accessToken) {
        try {
          const response = await fetch(`${API_BASE}/api/auth/me`, {
            headers: {
              'Authorization': `Bearer ${authState.accessToken}`
            }
          });
          const data = await response.json();
          if (response.ok && data.user) {
            // Merge auth info with profile data
            const profile = data.user.profile || {};
            setCurrentUser({ 
              ...profile, 
              email: data.user.email, 
              auth_id: data.user.id,
              id: profile.id || data.user.id
            });
          }
        } catch (error) {
          console.error('Error fetching current user:', error);
        }
      }
    };
    fetchCurrentUser();
  }, [authState, currentUser]);

  // Fetch join requests initially when group data is loaded (for badge count)
  useEffect(() => {
    if (group && (user || currentUser) && authState?.accessToken) {
      fetchJoinRequests();
    }
  }, [group, user, currentUser, authState]);

  const fetchGroupData = async () => {
    setLoading(true);
    try {
      const validToken = await getValidToken();
      const headers = validToken ? { 'Authorization': `Bearer ${validToken}` } : {};
      
      // Fetch group details with members
      const groupResponse = await fetch(
        `${API_BASE}/api/roommate-groups/${groupId}?include_members=true`,
        { headers }
      );
      const groupData = await groupResponse.json();

      if (groupResponse.ok && groupData.status === 'success') {
        setGroup(groupData.data);
        setMembers(groupData.data.members || []);
      }

      // Fetch group->listing feed (rule-based ranking).
      let listingsFeed = [];
      try {
        const fallbackResponse = await fetch(
          `${API_BASE}/api/roommate-groups/${groupId}/ranked-listings?limit=50`,
          { headers }
        );
        const fallbackData = await fallbackResponse.json();
        if (fallbackResponse.ok && fallbackData.status === 'success') {
          listingsFeed = fallbackData.ranked_listings || [];
        }
      } catch {
        // Listing feed is non-critical; group overview still loads.
      }

      setMatches(listingsFeed);
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

  const fetchMemberSavedListings = async () => {
    setLoadingLiked(true);
    try {
      const validToken = await getValidToken();
      const response = await fetch(
        `${API_BASE}/api/interactions/swipes/groups/${groupId}/liked?action=group_save`,
        { headers: { Authorization: `Bearer ${validToken}` } }
      );
      const data = await response.json();
      if (response.ok && data.status === 'success') {
        setMemberSavedListings(data.data || []);
      }
    } catch (error) {
      console.error('Error fetching member saved listings:', error);
    } finally {
      setLoadingLiked(false);
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
      const validToken = await getValidToken();
      const response = await fetch(
        `${API_BASE}/api/roommate-groups/${groupId}/invite`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${validToken}`
          },
          body: JSON.stringify({ user_email: inviteEmail })
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

  const fetchCompatibleUsers = async () => {
    setLoadingCompatible(true);
    try {
      const validToken = await getValidToken();
      if (!validToken) {
        throw new Error('Please log in to view compatible users');
      }
      const response = await fetch(
        `${API_BASE}/api/roommate-groups/${groupId}/compatible-users`,
        {
          headers: { 'Authorization': `Bearer ${validToken}` }
        }
      );
      const data = await response.json();

      if (response.ok && data.status === 'success') {
        setCompatibleUsers(data.users || []);
      } else {
        throw new Error(data.detail || 'Failed to load compatible users');
      }
    } catch (error) {
      console.error('Error fetching compatible users:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to load compatible users',
        color: 'red',
      });
    } finally {
      setLoadingCompatible(false);
    }
  };

  const handleInviteUser = async (userId, userEmail) => {
    setInvitingUserId(userId);
    try {
      const validToken = await getValidToken();
      const response = await fetch(
        `${API_BASE}/api/roommate-groups/${groupId}/invite`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${validToken}`
          },
          body: JSON.stringify({ user_email: userEmail })
        }
      );

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Invitation Sent',
          message: `Invitation sent to ${userEmail}`,
          color: 'green',
          icon: <IconCheck />,
        });
        // Remove user from compatible list
        setCompatibleUsers(prev => prev.filter(u => u.id !== userId));
        fetchGroupData();
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
      setInvitingUserId(null);
    }
  };

  // Fetch compatible users when invite modal opens
  useEffect(() => {
    if (inviteModalOpen && inviteTab === 'compatible') {
      fetchCompatibleUsers();
    }
  }, [inviteModalOpen, inviteTab]);

  // Fetch join requests for group creators
  const fetchJoinRequests = async () => {
    setLoadingRequests(true);
    try {
      const validToken = await getValidToken();
      if (!validToken) {
        throw new Error('Please log in to view join requests');
      }
      const response = await fetch(
        `${API_BASE}/api/roommate-groups/${groupId}/pending-requests`,
        {
          headers: { 'Authorization': `Bearer ${validToken}` }
        }
      );
      const data = await response.json();

      if (response.ok && data.status === 'success') {
        setJoinRequests(data.requests || []);
      } else {
        // Not an error if user is not creator - just no requests
        if (response.status !== 403) {
          throw new Error(data.detail || 'Failed to load join requests');
        }
      }
    } catch (error) {
      console.error('Error fetching join requests:', error);
      // Don't show error notification for 403 (not creator)
    } finally {
      setLoadingRequests(false);
    }
  };

  // Fetch join requests when viewing as creator
  useEffect(() => {
    if (group && user && activeTab === 'requests') {
      fetchJoinRequests();
    }
  }, [group, user, activeTab]);

  const handleAcceptRequest = async (userId, userName) => {
    setProcessingRequestId(userId);
    try {
      const validToken = await getValidToken();
      const response = await fetch(
        `${API_BASE}/api/roommate-groups/${groupId}/accept-request/${userId}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${validToken}`
          }
        }
      );

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Request Accepted!',
          message: `${userName || 'User'} is now a member of your group`,
          color: 'green',
          icon: <IconCheck />,
        });
        fetchJoinRequests();
        fetchGroupData();
      } else {
        throw new Error(data.detail || 'Failed to accept request');
      }
    } catch (error) {
      console.error('Error accepting request:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to accept request',
        color: 'red',
      });
    } finally {
      setProcessingRequestId(null);
    }
  };

  const handleRejectRequest = async (userId, userName) => {
    setProcessingRequestId(userId);
    try {
      const validToken = await getValidToken();
      const response = await fetch(
        `${API_BASE}/api/roommate-groups/${groupId}/reject-request/${userId}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${validToken}`
          }
        }
      );

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Request Rejected',
          message: `Join request from ${userName || 'user'} has been declined`,
          color: 'orange',
        });
        fetchJoinRequests();
      } else {
        throw new Error(data.detail || 'Failed to reject request');
      }
    } catch (error) {
      console.error('Error rejecting request:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to reject request',
        color: 'red',
      });
    } finally {
      setProcessingRequestId(null);
    }
  };

  const handleLeaveGroup = async () => {
    const acceptedMembers = members.filter(m => m.status === 'accepted');
    const otherMembers = acceptedMembers.filter(m => m.user_email !== user?.email);
    
    let confirmMessage = 'Are you sure you want to leave this group?';
    if (isCreator) {
      if (otherMembers.length > 0) {
        confirmMessage = 'Are you sure you want to leave this group? Ownership will be transferred to another member.';
      } else {
        confirmMessage = 'Are you sure you want to leave this group? Since you are the only member, the group will be deleted.';
      }
    }
    
    if (!confirm(confirmMessage)) return;

    try {
      const validToken = await getValidToken();
      const response = await fetch(
        `${API_BASE}/api/roommate-groups/${groupId}/leave`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${validToken}`
          }
        }
      );

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Left Group',
          message: data.message || 'You have left the group',
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
      const validToken = await getValidToken();
      const response = await fetch(
        `${API_BASE}/api/roommate-groups/${groupId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${validToken}`
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
      const validToken = await getValidToken();
      const response = await fetch(
        `${API_BASE}/api/roommate-groups/${groupId}/members/${memberId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${validToken}`
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

  // Use currentUser if user from context is null
  const activeUser = user || currentUser;
  
  // Compare by email since user.id is auth_id but members have app's user_id
  // Check if current user is creator by finding the creator member
  const creatorMember = members.find(m => m.is_creator);
  const isCreator = activeUser && creatorMember && creatorMember.user_email === activeUser.email;
  
  // Check membership by email or user_id (auth_id)
  const isMember = activeUser && members.some(m => 
    (m.user_email === activeUser.email || m.user_id === activeUser.id) && m.status === 'accepted'
  );
  
  // Debug logging
  console.log('User check:', { 
    fullUser: activeUser,
    userEmail: activeUser?.email, 
    userId: activeUser?.id,
    members: members.map(m => ({ email: m.user_email, id: m.user_id, status: m.status })),
    isMember,
    isCreator 
  });
  
  // Only count accepted members for display
  const acceptedMembers = members.filter(m => m.status === 'accepted');
  const acceptedMemberCount = acceptedMembers.length;
  
  // Check if group is full (only if we have a valid target size)
  const isGroupFull = group.target_group_size != null && acceptedMemberCount >= group.target_group_size;

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
                  <Menu.Item
                    leftSection={<IconEdit size={16} />}
                    onClick={() => router.push(`/groups/${groupId}/edit`)}
                  >
                    Edit Group
                  </Menu.Item>
                )}
                <Menu.Item
                  leftSection={<IconDoorExit size={16} />}
                  color="red"
                  onClick={handleLeaveGroup}
                >
                  Leave Group
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          )}
        </Group>

        {/* Full Group Banner */}
        {isGroupFull && (
          <Alert 
            icon={<IconAlertCircle size={18} />} 
            title="This group is full" 
            color="red"
            variant="filled"
          >
            This group has reached its maximum capacity of {group.target_group_size} members and is no longer accepting new members.
          </Alert>
        )}

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
                  variant="gradient"
                  gradient={{ from: 'blue', to: 'cyan' }}
                >
                  Find & Invite Members
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
                    <Text size="xs" c="dimmed">Members</Text>
                    <Text fw={500}>
                      {group.target_group_size != null
                        ? `${acceptedMemberCount} of ${group.target_group_size}`
                        : `${acceptedMemberCount}`}
                    </Text>
                    {group.target_group_size != null && (
                      <Text size="xs" c={isGroupFull ? 'red' : 'dimmed'}>
                        {isGroupFull ? 'Group full' : `${group.target_group_size - acceptedMemberCount} spot${group.target_group_size - acceptedMemberCount === 1 ? '' : 's'} open`}
                      </Text>
                    )}
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
            <Tabs.Tab
              value="interests"
              leftSection={<IconBookmark size={16} />}
              onClick={() => { if (!loadingLiked) fetchMemberSavedListings(); }}
            >
              Saved Listings
            </Tabs.Tab>
            {isCreator && (
              <Tabs.Tab 
                value="requests" 
                leftSection={<IconUserPlus size={16} />}
                rightSection={
                  joinRequests.length > 0 ? (
                    <Badge size="xs" color="red" variant="filled" circle>
                      {joinRequests.length}
                    </Badge>
                  ) : null
                }
              >
                Join Requests
              </Tabs.Tab>
            )}
          </Tabs.List>

          <Tabs.Panel value="overview" pt="xl">
            <Card withBorder>
              <Stack gap="md">
                <Group justify="space-between">
                  <Title order={3}>Group Members</Title>
                  <Badge size="lg">{acceptedMemberCount} members</Badge>
                </Group>

                <Divider />

                {acceptedMemberCount === 0 ? (
                  <Text c="dimmed" ta="center" py="xl">
                    No members yet
                  </Text>
                ) : (
                  <Stack gap="sm">
                    {acceptedMembers.map((member) => (
                      <Paper key={member.user_id} p="md" withBorder>
                        <Group justify="space-between">
                          <Group>
                            <Avatar size="md" radius="xl">
                              {member.user_name?.charAt(0) || 'U'}
                            </Avatar>
                            <div>
                              <Text fw={500}>
                                {member.user_name || 'Unknown User'}
                              </Text>
                              <Group gap="xs">
                                <Text size="sm" c="dimmed">
                                  {member.user_email}
                                </Text>
                                {member.is_creator && (
                                  <Badge size="sm" variant="light">Creator</Badge>
                                )}
                                {member.status === 'pending' && (
                                  <Badge size="sm" color="orange">Pending</Badge>
                                )}
                              </Group>
                            </div>
                          </Group>

                          {isCreator && !member.is_creator && (
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

          {/* Join Requests Tab (Creator Only) */}
          {isCreator && (
            <Tabs.Panel value="requests" pt="xl">
              <Card withBorder>
                <Stack gap="md">
                  <Group justify="space-between">
                    <div>
                      <Title order={3}>Join Requests</Title>
                      <Text size="sm" c="dimmed">
                        People who want to join your group
                      </Text>
                    </div>
                    <Button 
                      variant="light" 
                      size="sm"
                      leftSection={<IconSearch size={16} />}
                      onClick={fetchJoinRequests}
                      loading={loadingRequests}
                    >
                      Refresh
                    </Button>
                  </Group>

                  <Divider />

                  {loadingRequests ? (
                    <Stack gap="sm">
                      {[1, 2, 3].map(i => (
                        <Skeleton key={i} height={100} radius="md" />
                      ))}
                    </Stack>
                  ) : joinRequests.length === 0 ? (
                    <Stack align="center" py="xl">
                      <ThemeIcon size="xl" variant="light" color="gray">
                        <IconInbox size={24} />
                      </ThemeIcon>
                      <Text c="dimmed" ta="center">
                        No pending join requests
                      </Text>
                      <Text size="sm" c="dimmed" ta="center">
                        When someone requests to join your group, they'll appear here.
                      </Text>
                    </Stack>
                  ) : (
                    <Stack gap="md">
                      {joinRequests.map((request) => (
                        <Paper key={request.user_id} p="md" withBorder>
                          <Stack gap="md">
                            <Group justify="space-between" wrap="nowrap">
                              <Group wrap="nowrap">
                                <Avatar size="lg" radius="xl" color="blue">
                                  {request.full_name?.charAt(0) || request.email?.charAt(0) || 'U'}
                                </Avatar>
                                <div>
                                  <Group gap="xs">
                                    <Text fw={600}>{request.full_name || 'Unknown User'}</Text>
                                    {request.verification_status === 'admin_verified' && (
                                      <Badge size="sm" color="green" variant="light">Verified</Badge>
                                    )}
                                    {request.verification_status === 'email_verified' && (
                                      <Badge size="sm" color="blue" variant="light">Email Verified</Badge>
                                    )}
                                  </Group>
                                  <Text size="sm" c="dimmed">{request.email}</Text>
                                  {request.company_name && (
                                    <Text size="xs" c="dimmed">Works at {request.company_name}</Text>
                                  )}
                                  {request.school_name && (
                                    <Text size="xs" c="dimmed">Studies at {request.school_name}</Text>
                                  )}
                                </div>
                              </Group>

                              <Badge 
                                size="lg"
                                color={
                                  request.compatibility?.score >= 80 ? 'green' : 
                                  request.compatibility?.score >= 60 ? 'teal' :
                                  request.compatibility?.score >= 40 ? 'yellow' : 'orange'
                                }
                                variant="light"
                              >
                                {Math.round(request.compatibility?.score || 0)}% Match
                              </Badge>
                            </Group>

                            {/* User Preferences */}
                            {request.user_preferences && (
                              <Paper p="sm" withBorder bg="gray.0">
                                <Group gap="lg" wrap="wrap">
                                  {request.user_preferences.target_city && (
                                    <Group gap="xs">
                                      <IconMapPin size={14} />
                                      <Text size="sm">{request.user_preferences.target_city}</Text>
                                    </Group>
                                  )}
                                  {(request.user_preferences.budget_min || request.user_preferences.budget_max) && (
                                    <Group gap="xs">
                                      <IconCurrencyDollar size={14} />
                                      <Text size="sm">
                                        ${request.user_preferences.budget_min || 0} - ${request.user_preferences.budget_max || '∞'}
                                      </Text>
                                    </Group>
                                  )}
                                  {request.user_preferences.move_in_date && (
                                    <Group gap="xs">
                                      <IconCalendar size={14} />
                                      <Text size="sm">
                                        {new Date(request.user_preferences.move_in_date).toLocaleDateString()}
                                      </Text>
                                    </Group>
                                  )}
                                </Group>
                              </Paper>
                            )}

                            {/* Compatibility Reasons */}
                            {request.compatibility?.reasons && request.compatibility.reasons.length > 0 && (
                              <Group gap="xs" wrap="wrap">
                                {request.compatibility.reasons.slice(0, 4).map((reason, idx) => (
                                  <Badge key={idx} size="sm" variant="outline" color="gray">
                                    {reason}
                                  </Badge>
                                ))}
                              </Group>
                            )}

                            <Text size="xs" c="dimmed">
                              Requested {request.requested_at ? new Date(request.requested_at).toLocaleDateString() : 'recently'}
                            </Text>

                            {/* Action Buttons */}
                            <Group gap="sm">
                              <Button
                                leftSection={<IconCheck size={16} />}
                                color="green"
                                flex={1}
                                onClick={() => handleAcceptRequest(request.user_id, request.full_name)}
                                loading={processingRequestId === request.user_id}
                              >
                                Accept
                              </Button>
                              <Button
                                leftSection={<IconX size={16} />}
                                variant="outline"
                                color="red"
                                flex={1}
                                onClick={() => handleRejectRequest(request.user_id, request.full_name)}
                                loading={processingRequestId === request.user_id}
                              >
                                Decline
                              </Button>
                            </Group>
                          </Stack>
                        </Paper>
                      ))}
                    </Stack>
                  )}
                </Stack>
              </Card>
            </Tabs.Panel>
          )}

          {/* Saved Listings Tab */}
          <Tabs.Panel value="interests" pt="xl">
            <Stack gap="md">
              <Group justify="space-between">
                <div>
                  <Title order={3}>Saved Listings</Title>
                  <Text size="sm" c="dimmed">Listings your group members bookmarked for the group</Text>
                </div>
                <Button variant="light" size="sm" onClick={fetchMemberSavedListings} loading={loadingLiked}>
                  Refresh
                </Button>
              </Group>

              {loadingLiked ? (
                <Stack gap="sm">
                  {[1, 2, 3].map(i => <Skeleton key={i} height={100} radius="md" />)}
                </Stack>
              ) : memberSavedListings.length === 0 ? (
                <Card withBorder>
                  <Stack align="center" py="xl">
                    <ThemeIcon size="xl" variant="light" color="teal">
                      <IconBookmark size={24} />
                    </ThemeIcon>
                    <Text c="dimmed" ta="center">No saved listings yet</Text>
                    <Text size="sm" c="dimmed" ta="center">
                      When group members save listings from Recommendations, they'll appear here.
                    </Text>
                  </Stack>
                </Card>
              ) : (
                <Stack gap="md">
                  {memberSavedListings.map((listing) => (
                    <Card
                      key={listing.id}
                      withBorder
                      p="lg"
                      style={{ cursor: 'pointer' }}
                      onClick={() => router.push(`/listings/${listing.id}`)}
                    >
                      <Group justify="space-between" align="flex-start">
                        <div style={{ flex: 1 }}>
                          <Title order={4}>
                            {listing.title?.includes('|')
                              ? listing.title.split('|')[0].trim().toLowerCase().replace(/\b\w/g, c => c.toUpperCase())
                              : (listing.title || 'Listing')}
                          </Title>
                          <Group gap="xs" mt={4}>
                            <IconMapPin size={14} />
                            <Text size="sm" c="dimmed">
                              {listing.title?.includes('|')
                                ? listing.title.split('|')[1].trim()
                                : (listing.city || 'Location unavailable')}
                            </Text>
                          </Group>
                          <Group gap="xl" mt="sm">
                            {listing.price_per_month && (
                              <div>
                                <Text size="xs" c="dimmed">Price</Text>
                                <Text fw={600}>${Number(listing.price_per_month).toLocaleString()}/mo</Text>
                              </div>
                            )}
                            {listing.number_of_bedrooms != null && (
                              <div>
                                <Text size="xs" c="dimmed">Beds</Text>
                                <Text fw={600}>{listing.number_of_bedrooms === 0 ? 'Studio' : listing.number_of_bedrooms}</Text>
                              </div>
                            )}
                            {listing.number_of_bathrooms != null && (
                              <div>
                                <Text size="xs" c="dimmed">Baths</Text>
                                <Text fw={600}>{listing.number_of_bathrooms}</Text>
                              </div>
                            )}
                          </Group>
                        </div>
                        <Stack gap={4} align="flex-end">
                          <Text size="xs" c="dimmed">Saved by</Text>
                          {(listing.liked_by || []).map((name) => (
                            <Badge key={name} size="sm" variant="light" color="teal">{name}</Badge>
                          ))}
                        </Stack>
                      </Group>
                    </Card>
                  ))}
                </Stack>
              )}
            </Stack>
          </Tabs.Panel>
        </Tabs>
      </Stack>

      {/* Invite Modal */}
      <Modal
        opened={inviteModalOpen}
        onClose={() => {
          setInviteModalOpen(false);
          setInviteEmail('');
          setInviteTab('compatible');
        }}
        title={
          <Group gap="xs">
            <IconUserPlus size={20} />
            <Text fw={600}>Invite Members</Text>
          </Group>
        }
        size="lg"
      >
        <Tabs value={inviteTab} onChange={setInviteTab}>
          <Tabs.List mb="md">
            <Tabs.Tab value="compatible" leftSection={<IconSparkles size={16} />}>
              Compatible Users
            </Tabs.Tab>
            <Tabs.Tab value="email" leftSection={<IconMail size={16} />}>
              Invite by Email
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="compatible">
            <Stack gap="md">
              <Text size="sm" c="dimmed">
                These users match your group's hard constraints (city, budget, move-in date).
                Hover over each user to see their preferences.
              </Text>

              {loadingCompatible ? (
                <Stack gap="sm">
                  {[1, 2, 3].map(i => (
                    <Skeleton key={i} height={80} radius="md" />
                  ))}
                </Stack>
              ) : compatibleUsers.length === 0 ? (
                <Paper p="xl" withBorder>
                  <Stack align="center" gap="sm">
                    <ThemeIcon size="xl" variant="light" color="gray">
                      <IconSearch size={24} />
                    </ThemeIcon>
                    <Text c="dimmed" ta="center">
                      No compatible users found at this time.
                    </Text>
                    <Text size="sm" c="dimmed" ta="center">
                      Try adjusting your group's preferences or check back later.
                    </Text>
                  </Stack>
                </Paper>
              ) : (
                <ScrollArea.Autosize mah={400}>
                  <Stack gap="sm">
                    {compatibleUsers.map((user) => (
                      <Tooltip
                        key={user.id}
                        position="right"
                        withArrow
                        multiline
                        w={300}
                        label={
                          <Stack gap="xs" p="xs">
                            <Text size="sm" fw={600}>Preferences</Text>
                            <Divider />
                            
                            <Group gap="xs">
                              <IconMapPin size={14} />
                              <Text size="xs">City: {user.preferences?.target_city || 'Any'}</Text>
                            </Group>
                            
                            <Group gap="xs">
                              <IconCurrencyDollar size={14} />
                              <Text size="xs">
                                Budget: ${user.preferences?.budget_min || 0} - ${user.preferences?.budget_max || '∞'}
                              </Text>
                            </Group>
                            
                            <Group gap="xs">
                              <IconCalendar size={14} />
                              <Text size="xs">
                                Move-in: {user.preferences?.move_in_date 
                                  ? new Date(user.preferences.move_in_date).toLocaleDateString()
                                  : 'Flexible'}
                              </Text>
                            </Group>

                            {user.preferences?.lifestyle_preferences && Object.keys(user.preferences.lifestyle_preferences).length > 0 && (
                              <>
                                <Divider label="Lifestyle" labelPosition="center" />
                                
                                {user.preferences.lifestyle_preferences.sleep_time && (
                                  <Group gap="xs">
                                    <IconMoon size={14} />
                                    <Text size="xs">
                                      Sleep: {user.preferences.lifestyle_preferences.sleep_time}
                                    </Text>
                                  </Group>
                                )}
                                
                                {user.preferences.lifestyle_preferences.noise_level && (
                                  <Group gap="xs">
                                    <IconVolume size={14} />
                                    <Text size="xs">
                                      Noise: {user.preferences.lifestyle_preferences.noise_level}
                                    </Text>
                                  </Group>
                                )}
                                
                                {user.preferences.lifestyle_preferences.smoking !== undefined && (
                                  <Group gap="xs">
                                    <IconSmokingNo size={14} />
                                    <Text size="xs">
                                      Smoking: {user.preferences.lifestyle_preferences.smoking ? 'Yes' : 'No'}
                                    </Text>
                                  </Group>
                                )}
                                
                                {user.preferences.lifestyle_preferences.pets !== undefined && (
                                  <Group gap="xs">
                                    <IconDog size={14} />
                                    <Text size="xs">
                                      Pets: {user.preferences.lifestyle_preferences.pets ? 'Yes' : 'No'}
                                    </Text>
                                  </Group>
                                )}
                                
                                {user.preferences.lifestyle_preferences.guests && (
                                  <Group gap="xs">
                                    <IconFriends size={14} />
                                    <Text size="xs">
                                      Guests: {user.preferences.lifestyle_preferences.guests}
                                    </Text>
                                  </Group>
                                )}
                              </>
                            )}

                            <Divider />
                            <Group gap="xs">
                              <Text size="xs" c="dimmed">Compatibility Score:</Text>
                              <Progress 
                                value={user.compatibility_score} 
                                size="sm" 
                                color={user.compatibility_score >= 80 ? 'green' : user.compatibility_score >= 50 ? 'yellow' : 'red'}
                                style={{ flex: 1 }}
                              />
                              <Text size="xs" fw={500}>{Math.round(user.compatibility_score)}%</Text>
                            </Group>
                          </Stack>
                        }
                      >
                        <Paper p="md" withBorder style={{ cursor: 'pointer' }}>
                          <Group justify="space-between">
                            <Group>
                              <Avatar size="md" radius="xl" color="blue">
                                {user.full_name?.charAt(0) || user.email?.charAt(0) || 'U'}
                              </Avatar>
                              <div>
                                <Text fw={500}>{user.full_name || 'User'}</Text>
                                <Text size="sm" c="dimmed">{user.email}</Text>
                              </div>
                            </Group>
                            <Group gap="sm">
                              <Badge 
                                color={user.compatibility_score >= 80 ? 'green' : user.compatibility_score >= 50 ? 'yellow' : 'orange'}
                                variant="light"
                              >
                                {Math.round(user.compatibility_score)}% match
                              </Badge>
                              <Button
                                size="xs"
                                leftSection={<IconUserPlus size={14} />}
                                loading={invitingUserId === user.id}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleInviteUser(user.id, user.email);
                                }}
                              >
                                Invite
                              </Button>
                            </Group>
                          </Group>
                        </Paper>
                      </Tooltip>
                    ))}
                  </Stack>
                </ScrollArea.Autosize>
              )}

              <Button 
                variant="light" 
                leftSection={<IconSearch size={16} />}
                onClick={fetchCompatibleUsers}
                loading={loadingCompatible}
              >
                Refresh List
              </Button>
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="email">
            <Stack gap="md">
              <Text size="sm" c="dimmed">
                Enter the email address of someone you'd like to invite to your group.
              </Text>
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
                leftSection={<IconUserPlus size={16} />}
              >
                Send Invitation
              </Button>
            </Stack>
          </Tabs.Panel>
        </Tabs>
      </Modal>
    </Container>
    </>
  );
}
