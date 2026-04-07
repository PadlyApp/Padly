'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function RoommatesPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/discover');
  }, [router]);
  return null;
}
