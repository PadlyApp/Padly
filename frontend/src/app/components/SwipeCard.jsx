'use client';

import { useRef, useState, useEffect } from 'react';
import { Text, Badge, Box, Group, Button } from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';
import { ImageWithFallback } from './ImageWithFallback';

const SWIPE_THRESHOLD = 100;

export function SwipeCard({ listing, onSwipe, isTop, stackOffset, onExpand }) {
  const [dragging, setDragging] = useState(false);
  const [offsetX, setOffsetX] = useState(0);
  const [leaving, setLeaving] = useState(null); // 'left' | 'right' | null
  const startXRef = useRef(0);

  useEffect(() => {
    if (!dragging) return;

    const onMove = (e) => {
      const clientX = e.clientX ?? e.touches?.[0]?.clientX;
      if (clientX == null) return;
      setOffsetX(clientX - startXRef.current);
    };

    const onUp = () => {
      setDragging(false);
      if (offsetX > SWIPE_THRESHOLD) {
        triggerLeave('right');
      } else if (offsetX < -SWIPE_THRESHOLD) {
        triggerLeave('left');
      } else {
        setOffsetX(0);
      }
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    window.addEventListener('touchmove', onMove, { passive: true });
    window.addEventListener('touchend', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      window.removeEventListener('touchmove', onMove);
      window.removeEventListener('touchend', onUp);
    };
  }, [dragging, offsetX]);

  const triggerLeave = (direction) => {
    setLeaving(direction);
    setTimeout(() => onSwipe(direction, listing), 350);
  };

  const handlePointerDown = (e) => {
    if (!isTop || leaving) return;
    e.preventDefault();
    startXRef.current = e.clientX ?? e.touches?.[0]?.clientX;
    setDragging(true);
  };

  // Transform & transition
  let transform, transition;
  if (leaving === 'right') {
    transform = 'translateX(130%) rotate(22deg)';
    transition = 'transform 0.35s ease';
  } else if (leaving === 'left') {
    transform = 'translateX(-130%) rotate(-22deg)';
    transition = 'transform 0.35s ease';
  } else if (dragging) {
    transform = `translateX(${offsetX}px) rotate(${offsetX * 0.06}deg)`;
    transition = 'none';
  } else {
    transform = `translateY(${stackOffset * 10}px) scale(${1 - stackOffset * 0.04})`;
    transition = 'transform 0.3s ease';
  }

  const likeOpacity = leaving === 'right' ? 1 : Math.max(0, Math.min(offsetX / SWIPE_THRESHOLD, 1));
  const nopeOpacity = leaving === 'left'  ? 1 : Math.max(0, Math.min(-offsetX / SWIPE_THRESHOLD, 1));

  const images = (() => {
    const imgs = listing.images;
    if (Array.isArray(imgs)) return imgs;
    if (typeof imgs === 'string') { try { return JSON.parse(imgs); } catch { return []; } }
    return [];
  })();
  const image =
    images[0] ||
    'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800';

  return (
    <Box
      onMouseDown={handlePointerDown}
      onTouchStart={handlePointerDown}
      style={{
        position: 'absolute',
        inset: 0,
        transform,
        transition,
        cursor: isTop ? (dragging ? 'grabbing' : 'grab') : 'default',
        userSelect: 'none',
        borderRadius: '20px',
        overflow: 'hidden',
        boxShadow: '0 12px 40px rgba(0,0,0,0.12)',
        backgroundColor: '#fff',
        zIndex: isTop ? 10 : 10 - stackOffset,
      }}
    >
      {/* Full-card colour overlay */}
      <Box style={{
        position: 'absolute', inset: 0, zIndex: 20, pointerEvents: 'none',
        borderRadius: '20px',
        backgroundColor: likeOpacity > 0 ? `rgba(32, 201, 151, ${likeOpacity * 0.35})` : `rgba(255, 107, 107, ${nopeOpacity * 0.35})`,
        transition: leaving ? 'background-color 0.1s ease' : 'none',
      }} />

      {/* Image */}
      <Box style={{ position: 'relative', height: '58%', overflow: 'hidden', backgroundColor: '#f0f0f0' }}>
        <ImageWithFallback
          src={image}
          alt={listing.title || 'Listing'}
          draggable={false}
          style={{ width: '100%', height: '100%', objectFit: 'cover', pointerEvents: 'none' }}
        />

        {/* Match badge */}
        {listing.match_percent && (
          <Badge
            variant="filled"
            color="teal"
            size="md"
            radius="sm"
            style={{ position: 'absolute', top: 14, right: 14, fontWeight: 700 }}
          >
            {listing.match_percent} match
          </Badge>
        )}

        {/* LIKE stamp */}
        <Box style={{
          position: 'absolute', top: 20, left: 20,
          border: '3px solid #20c997', borderRadius: '8px',
          padding: '2px 10px', opacity: likeOpacity,
          transform: 'rotate(-12deg)', pointerEvents: 'none',
        }}>
          <Text fw={800} size="lg" style={{ color: '#20c997', letterSpacing: 3 }}>LIKE</Text>
        </Box>

        {/* NOPE stamp */}
        <Box style={{
          position: 'absolute', top: 20, right: 20,
          border: '3px solid #ff6b6b', borderRadius: '8px',
          padding: '2px 10px', opacity: nopeOpacity,
          transform: 'rotate(12deg)', pointerEvents: 'none',
        }}>
          <Text fw={800} size="lg" style={{ color: '#ff6b6b', letterSpacing: 3 }}>NOPE</Text>
        </Box>
      </Box>

      {/* Info */}
      <Box style={{
        padding: '1.25rem 1.5rem',
        height: '42%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
      }}>
        <Box>
          <Text fw={600} size="lg" lineClamp={1} style={{ color: '#111', marginBottom: 4 }}>
            {listing.title || 'Listing'}
          </Text>
          {listing.city && (
            <Text size="sm" c="dimmed" style={{ marginBottom: 8 }}>
              {listing.city}
            </Text>
          )}
          <Text size="sm" c="dimmed">
            {[
              listing.number_of_bedrooms != null && (listing.number_of_bedrooms === 0 ? 'Studio' : `${listing.number_of_bedrooms} bed`),
              listing.number_of_bathrooms != null && `${listing.number_of_bathrooms} bath`,
              listing.area_sqft && `${listing.area_sqft} sqft`,
              listing.furnished && 'Furnished',
            ].filter(Boolean).join(' · ')}
          </Text>
        </Box>

        {listing.amenities && typeof listing.amenities === 'object' && (
          <Group gap="xs" mt={6}>
            {Object.entries(listing.amenities)
              .filter(([, v]) => v)
              .slice(0, 2)
              .map(([key]) => (
                <Badge key={key} variant="light" size="xs">{key}</Badge>
              ))}
          </Group>
        )}

        {listing.price_per_month != null && (
          <Text fw={700} size="xl" c="teal.6">
            ${Number(listing.price_per_month).toLocaleString()}/mo
          </Text>
        )}

        <Box style={{ display: 'flex', justifyContent: 'center', marginTop: 8 }}>
          <Button
            size="xs"
            variant="subtle"
            color="gray"
            leftSection={<IconInfoCircle size={14} />}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => { e.stopPropagation(); onExpand && onExpand(listing); }}
            style={{ fontSize: 12, color: '#868e96' }}
          >
            View details
          </Button>
        </Box>
      </Box>
    </Box>
  );
}
