'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { notifications } from '@mantine/notifications';
import { IconCheck } from '@tabler/icons-react';
import { useAuth } from '../../../../app/contexts/AuthContext';
import { apiFetch } from '../../../../../lib/api';

export function useGroupDetailPage() {
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
          const response = await apiFetch(`/auth/me`, {}, { token: authState.accessToken });
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

      // Fetch group details with members
      const groupResponse = await apiFetch(
        `/roommate-groups/${groupId}?include_members=true`,
        {},
        { token: validToken }
      );
      const groupData = await groupResponse.json();

      if (groupResponse.ok && groupData.status === 'success') {
        setGroup(groupData.data);
        setMembers(groupData.data.members || []);
      }

      // Fetch group->listing feed (rule-based ranking).
      let listingsFeed = [];
      try {
        const fallbackResponse = await apiFetch(
          `/roommate-groups/${groupId}/ranked-listings?limit=50`,
          {},
          { token: validToken }
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
      const response = await apiFetch(
        `/interactions/swipes/groups/${groupId}/liked?action=group_save`,
        {},
        { token: validToken }
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
      const response = await apiFetch(
        `/roommate-groups/${groupId}/invite`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_email: inviteEmail }),
        },
        { token: validToken }
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
      const response = await apiFetch(`/roommate-groups/${groupId}/compatible-users`, {}, { token: validToken });
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
      const response = await apiFetch(
        `/roommate-groups/${groupId}/invite`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_email: userEmail }),
        },
        { token: validToken }
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
      const response = await apiFetch(`/roommate-groups/${groupId}/pending-requests`, {}, { token: validToken });
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
      const response = await apiFetch(`/roommate-groups/${groupId}/accept-request/${userId}`, { method: 'POST' }, { token: validToken });

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
      const response = await apiFetch(`/roommate-groups/${groupId}/reject-request/${userId}`, { method: 'POST' }, { token: validToken });

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
      const response = await apiFetch(`/roommate-groups/${groupId}/leave`, { method: 'DELETE' }, { token: validToken });

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
      const response = await apiFetch(`/roommate-groups/${groupId}`, { method: 'DELETE' }, { token: validToken });

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
      const response = await apiFetch(`/roommate-groups/${groupId}/members/${memberId}`, { method: 'DELETE' }, { token: validToken });

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

  return {
    router,
    groupId,
    user,
    currentUser,
    group,
    members,
    matches,
    loading,
    inviteModalOpen,
    setInviteModalOpen,
    inviteEmail,
    setInviteEmail,
    inviting,
    activeTab,
    setActiveTab,
    inviteTab,
    setInviteTab,
    compatibleUsers,
    loadingCompatible,
    invitingUserId,
    joinRequests,
    loadingRequests,
    processingRequestId,
    memberSavedListings,
    loadingLiked,
    fetchGroupData,
    fetchMemberSavedListings,
    handleInvite,
    fetchCompatibleUsers,
    handleInviteUser,
    fetchJoinRequests,
    handleAcceptRequest,
    handleRejectRequest,
    handleLeaveGroup,
    handleDeleteGroup,
    handleRemoveMember,
  };
}
