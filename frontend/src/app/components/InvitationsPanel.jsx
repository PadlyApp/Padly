'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Title,
  Text,
  Button,
  Stack,
  Card,
  Badge,
  Group,
  Loader,
  Center,
  Paper,
  Divider,
  SimpleGrid,
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
} from '@tabler/icons-react';
import { apiFetch } from '../../../lib/api';

export function InvitationsPanel({ user, authState, onBrowseGroups }) {
  const router = useRouter();
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

      const response = await apiFetch(`/roommate-groups?my_groups=true`, {}, { token: authState?.accessToken });

      const data = await response.json();

      if (data.status === 'success') {
        const allGroups = data.data;
        const pendingInvites = [];

        for (const group of allGroups) {
          const memberResponse = await apiFetch(
            `/roommate-groups/${group.id}/members`,
            {},
            { token: authState?.accessToken }
          );
          const memberData = await memberResponse.json();

          if (memberData.status === 'success') {
            const myMembership = memberData.data.find(m => m.user_id === user.id);
            if (myMembership && myMembership.status === 'pending') {
              pendingInvites.push({
                ...group,
                membership: myMembership,
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
      const response = await apiFetch(`/roommate-groups/${groupId}/join`, { method: 'POST' }, { token: authState.accessToken });

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Success!',
          message: 'You have joined the group',
          color: 'green',
          icon: <IconCheck />,
        });
        fetchInvitations();
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
      const response = await apiFetch(`/roommate-groups/${groupId}/reject`, { method: 'POST' }, { token: authState.accessToken });

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Invitation Rejected',
          message: 'You have rejected the invitation',
          color: 'orange',
        });
        fetchInvitations();
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

  if (loading) {
    return (
      <Center py="xl" style={{ minHeight: '300px' }}>
        <Loader size="lg" />
      </Center>
    );
  }

  if (invitations.length === 0) {
    return (
      <Card withBorder p="xl">
        <Stack align="center" py="xl">
          <IconInbox size={64} stroke={1.5} color="gray" />
          <Title order={3} c="dimmed">No Pending Invitations</Title>
          <Text c="dimmed" ta="center">
            You don't have any pending group invitations at the moment.
          </Text>
          <Button
            mt="md"
            onClick={() => {
              if (typeof onBrowseGroups === 'function') {
                onBrowseGroups();
                return;
              }
              router.push('/groups');
            }}
          >
            Browse Groups
          </Button>
        </Stack>
      </Card>
    );
  }

  return (
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

            <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
              <Paper p="sm" radius="lg" shadow="xs">
                <Group gap="xs">
                  <IconMapPin size={16} />
                  <div>
                    <Text size="xs" c="dimmed">City</Text>
                    <Text size="sm" fw={500}>{invitation.target_city}</Text>
                  </div>
                </Group>
              </Paper>

              <Paper p="sm" radius="lg" shadow="xs">
                <Group gap="xs">
                  <IconUsers size={16} />
                  <div>
                    <Text size="xs" c="dimmed">Group Size</Text>
                    <Text size="sm" fw={500}>
                      {invitation.target_group_size != null ? `${invitation.target_group_size} people` : 'Unlimited'}
                    </Text>
                  </div>
                </Group>
              </Paper>

              {invitation.budget_per_person_min && invitation.budget_per_person_max && (
                <Paper p="sm" radius="lg" shadow="xs">
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
                <Paper p="sm" radius="lg" shadow="xs">
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
            </SimpleGrid>

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
  );
}
