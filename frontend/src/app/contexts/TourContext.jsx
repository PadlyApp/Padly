'use client';

import { createContext, useContext, useState, useEffect, useCallback } from 'react';

const TOUR_STORAGE_KEY = 'padly_tour_state';

const TourContext = createContext(undefined);

const TOUR_PHASES = ['welcome', 'nav', 'preferences', 'discover', 'groups', 'matches', 'finishing', 'complete'];

export function PadlyTourProvider({ children }) {
  const [tourPhase, setTourPhaseState] = useState(null);
  const [tourPaused, setTourPaused] = useState(false);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(TOUR_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.phase && parsed.phase !== 'complete') {
          setTourPhaseState(parsed.phase);
          setTourPaused(parsed.paused === true);
        }
      }
    } catch {
      // ignore corrupt storage
    }
    setIsReady(true);
  }, []);

  const setTourPhase = useCallback((phase) => {
    setTourPhaseState(phase);
    setTourPaused(false);
    localStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify({ phase, paused: false }));
  }, []);

  const startTour = useCallback(() => {
    setTourPhaseState('welcome');
    setTourPaused(false);
    localStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify({ phase: 'welcome', paused: false }));
  }, []);

  const pauseTour = useCallback((phase) => {
    setTourPaused(true);
    localStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify({ phase, paused: true }));
  }, []);

  const resumeTour = useCallback(() => {
    setTourPaused(false);
    localStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify({ phase: tourPhase, paused: false }));
  }, [tourPhase]);

  const advancePhase = useCallback(() => {
    setTourPhaseState((prev) => {
      const idx = TOUR_PHASES.indexOf(prev);
      const next = idx >= 0 && idx < TOUR_PHASES.length - 1
        ? TOUR_PHASES[idx + 1]
        : 'complete';
      localStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify({ phase: next, paused: false }));
      return next;
    });
  }, []);

  const endTour = useCallback(() => {
    setTourPhaseState('complete');
    setTourPaused(false);
    localStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify({ phase: 'complete' }));
  }, []);

  const resetTour = useCallback(() => {
    setTourPhaseState(null);
    setTourPaused(false);
    localStorage.removeItem(TOUR_STORAGE_KEY);
  }, []);

  const isTourActive = tourPhase !== null && tourPhase !== 'complete' && !tourPaused;
  const isTourPaused = tourPhase !== null && tourPhase !== 'complete' && tourPaused;

  return (
    <TourContext.Provider value={{
      tourPhase,
      isTourActive,
      isTourPaused,
      isReady,
      startTour,
      pauseTour,
      resumeTour,
      advancePhase,
      setTourPhase,
      endTour,
      resetTour,
    }}>
      {children}
    </TourContext.Provider>
  );
}

export function usePadlyTour() {
  const context = useContext(TourContext);
  if (context === undefined) {
    throw new Error('usePadlyTour must be used within a PadlyTourProvider');
  }
  return context;
}
