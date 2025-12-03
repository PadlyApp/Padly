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
  Badge,
  Group,
  Loader,
  Center,
  Alert,
  Paper,
  Divider
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { 
  IconCheck, 
  IconX, 
  IconInbox,
  IconMapPin,
  IconUsers,
  IconCurrencyDollar,
  IconCalendar,
  IconAlertCircle
} from '@tabler/icons-react';
import { useAuth } from '../contexts/AuthContext';
import { Navigation } from '../components/Navigation';

export default function InvitationsPage() {
  const router = useRouter();
  const { user, authState, isLoading: authLoading } = useAuth();
  const [invitations, setInvitations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState(null);

  useEffect(() => {
    if (user && authState) {
      fetchInvitations();
    }
  }, [user, authState]);

  const fetchInvitations = async () => {
    try {
      setLoading(true);
      
      const headers = {};
      if (authState?.accessToken) {
        headers['Authorization'] = `Bearer ${authState.accessToken}`;
      }

      // Fetch group memberships with status='pending'
      const response = await fetch(
        'http://localhost:8000/api/roommate-groups?my_groups=true',
        { headers }
      );
      
      const data = await response.json();
      
      if (data.status === 'success') {
        // Filter to only show pending invitations
        // This will be more efficient once we have a dedicated endpoint
        const allGroups = data.data;
        
        // For now, we'll need to check each group's member status
        // In a real implementation, you'd want a dedicated /invitations endpoint
        const pendingInvites = [];
        
        for (const group of allGroups) {
          const memberResponse = await fetch(
            `http://localhost:8000/api/roommate-groups/${group.id}/members`,
            { headers }
          );
          const memberData = await memberResponse.json();
          
          if (memberData.status === 'success') {
            const myMembership = memberData.data.find(m => m.user_id === user.id);
            if (myMembership && myMembership.status === 'pending') {
              pendingInvites.push({
                ...group,
                membership: myMembership
              });
            }
          }
        }
        
        setInvitations(pendingInvites);
      }
    } catch (error) {
      console.error('Error fetching invitations:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to load invitations',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async (groupId) => {
    setProcessingId(groupId);
    try {
      const response = await fetch(
        `http://localhost:8000/api/roommate-groups/${groupId}/join`,
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
          title: 'Success!',
          message: 'You have joined the group',
          color: 'green',
          icon: <IconCheck />,
        });
        fetchInvitations(); // Refresh list
      } else {
        throw new Error(data.detail || 'Failed to accept invitation');
      }
    } catch (error) {
      console.error('Error accepting invitation:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to accept invitation',
        color: 'red',
      });
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (groupId) => {
    setProcessingId(groupId);
    try {
      const response = await fetch(
        `http://localhost:8000/api/roommate-groups/${groupId}/reject`,
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
          title: 'Invitation Rejected',
          message: 'You have rejected the invitation',
          color: 'orange',
        });
        fetchInvitations(); // Refresh list
      } else {
        throw new Error(data.detail || 'Failed to reject invitation');
      }
    } catch (error) {
      console.error('Error rejecting invitation:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to reject invitation',
        color: 'red',
      });
    } finally {
      setProcessingId(null);
    }
  };

  if (authLoading || loading) {
    return (
      <>
        <Navigation />
        <Center h="80vh">
          <Loader size="lg" />
        </Center>
      </>
    );
  }

  if (!user) {
    return (
      <>
        <Navigation />
        <Container size="md" py="xl">
          <Alert icon={<IconAlertCircle />} title="Authentication Required" color="orange">
            Please log in to view your invitations.
          </Alert>
          <Button mt="md" onClick={() => router.push('/login')}>
            Log In
          </Button>
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
          <div>
            <Title order={1}>Group Invitations</Title>
            <Text c="dimmed" mt="xs">
              Review and respond to your pending group invitations
            </Text>
          </div>

          {/* Invitations List */}
          {invitations.length === 0 ? (
            <Card withBorder p="xl">
              <Stack align="center" py="xl">
                <IconInbox size={64} stroke={1.5} color="gray" />
                <Title order={3} c="dimmed">No Pending Invitations</Title>
                <Text c="dimmed" ta="center">
                  You don't have any pending group invitations at the moment.
                </Text>
                <Button
                  mt="md"
                  onClick={() => router.push('/groups')}
                >
                  Browse Groups
                </Button>
              </Stack>
            </Card>
          ) : (
            <Stack gap="md">
              {invitations.map((invitation) => (
                <Card key={invitation.id} withBorder p="lg">
                  <Stack gap="md">
                    <Group justify="space-between" align="flex-start">
                      <div style={{ flex: 1 }}>
                        <Group gap="sm" mb="xs">
                          <Title order={3}>{invitation.group_name}</Title>
                          <Badge color="blue">Pending</Badge>
                        </Group>
                        {invitation.description && (
                          <Text c="dimmed" mb="md">{invitation.description}</Text>
                        )}
                      </div>
                    </Group>

                    <Divider />

                    {/* Group Details */}
                    <Group grow>
                      <Paper p="sm" withBorder>
                        <Group gap="xs">
                          <IconMapPin size={16} />
                          <div>
                            <Text size="xs" c="dimmed">City</Text>
                            <Text size="sm" fw={500}>{invitation.target_city}</Text>
                          </div>
                        </Group>
                      </Paper>

                      <Paper p="sm" withBorder>
                        <Group gap="xs">
                          <IconUsers size={16} />
                          <div>
                            <Text size="xs" c="dimmed">Group Size</Text>
                            <Text size="sm" fw={500}>{invitation.target_group_size} people</Text>
                          </div>
                        </Group>
                      </Paper>

                      {invitation.budget_per_person_min && invitation.budget_per_person_max && (
                        <Paper p="sm" withBorder>
                          <Group gap="xs">
                            <IconCurrencyDollar size={16} />
                            <div>
                              <Text size="xs" c="dimmed">Budget</Text>
                              <Text size="sm" fw={500}>
                                ${invitation.budget_per_person_min} - ${invitation.budget_per_person_max}
                              </Text>
                            </div>
                          </Group>
                        </Paper>
                      )}

                      {invitation.target_move_in_date && (
                        <Paper p="sm" withBorder>
                          <Group gap="xs">
                            <IconCalendar size={16} />
                            <div>
                              <Text size="xs" c="dimmed">Move-in</Text>
                              <Text size="sm" fw={500}>
                                {new Date(invitation.target_move_in_date).toLocaleDateString()}
                              </Text>
                            </div>
                          </Group>
                        </Paper>
                      )}
                    </Group>

                    {/* Action Buttons */}
                    <Group gap="sm" mt="md">
                      <Button
                        leftSection={<IconCheck size={18} />}
                        onClick={() => handleAccept(invitation.id)}
                        loading={processingId === invitation.id}
                        color="green"
                        flex={1}
                      >
                        Accept Invitation
                      </Button>
                      <Button
                        leftSection={<IconX size={18} />}
                        onClick={() => handleReject(invitation.id)}
                        loading={processingId === invitation.id}
                        variant="outline"
                        color="red"
                        flex={1}
                      >
                        Decline
                      </Button>
                    </Group>
                  </Stack>
                </Card>
              ))}
            </Stack>
          )}
        </Stack>
      </Container>
    </>
  );
}
