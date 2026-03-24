'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useTour } from '@reactour/tour';
import { usePadlyTour } from '../../contexts/TourContext';
import { TourTooltip } from './TourTooltip';
import { WelcomeModal } from './WelcomeModal';
import { CompletionModal } from './CompletionModal';
import {
  NAV_TOUR_STEPS,
  PREFERENCES_TOUR_STEPS,
  DISCOVER_TOUR_STEPS,
  GROUPS_TOUR_STEPS,
  MATCHES_TOUR_STEPS,
} from './tourSteps';

function waitForSelector(selector, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    const interval = 150;
    const stabilityChecks = 2;
    let elapsed = 0;
    let consecutiveHits = 0;

    const poll = setInterval(() => {
      elapsed += interval;
      const found = document.querySelector(selector);
      if (found) {
        consecutiveHits++;
        if (consecutiveHits >= stabilityChecks) {
          clearInterval(poll);
          resolve(found);
        }
      } else {
        consecutiveHits = 0;
        if (elapsed >= timeoutMs) {
          clearInterval(poll);
          reject(new Error(`Tour target "${selector}" not found after ${timeoutMs}ms`));
        }
      }
    }, interval);
  });
}

function buildReactourSteps(stepDefs, { onNext, onPrev, onClose, totalSteps }) {
  return stepDefs.map((def, i) => ({
    selector: def.selector,
    content: () => (
      <TourTooltip
        title={def.title}
        description={def.description}
        icon={def.icon}
        currentStep={i}
        totalSteps={totalSteps}
        isLastStep={i === totalSteps - 1}
        nextLabel={def.nextLabel}
        hideNext={!!def.hideNext}
        onNext={() => onNext(i)}
        onPrev={() => onPrev(i)}
        onClose={onClose}
      />
    ),
    position: def.position || 'bottom',
    disableInteraction: !def.hideNext,
  }));
}

export function AppTour() {
  const pathname = usePathname();
  const router = useRouter();
  const { tourPhase, isTourActive, isReady, setTourPhase, pauseTour, endTour } = usePadlyTour();
  const { setIsOpen, setSteps, setCurrentStep, isOpen } = useTour();
  const [showWelcome, setShowWelcome] = useState(false);
  const [showCompletion, setShowCompletion] = useState(false);
  const phaseInitRef = useRef(null);

  // X button pauses so user can resume later via nav
  const closeTour = useCallback(() => {
    setIsOpen(false);
    setShowWelcome(false);
    setShowCompletion(false);
    pauseTour(tourPhase);
  }, [setIsOpen, pauseTour, tourPhase]);

  // ── Welcome phase ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!isReady || !isTourActive) return;
    if (tourPhase === 'welcome' && pathname === '/') {
      setShowWelcome(true);
    }
  }, [isReady, isTourActive, tourPhase, pathname]);

  // ── Nav phase ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isReady || tourPhase !== 'nav' || pathname !== '/') return;
    if (phaseInitRef.current === 'nav') return;
    phaseInitRef.current = 'nav';
    let cancelled = false;

    waitForSelector(NAV_TOUR_STEPS[0].selector).then(() => {
      if (cancelled) return;
      const onNext = (i) => {
        if (i === NAV_TOUR_STEPS.length - 1) {
          setIsOpen(false);
          setTourPhase('preferences');
          router.push('/account?tab=preferences');
        } else {
          setCurrentStep(i + 1);
        }
      };
      const onPrev = (i) => {
        if (i > 0) setCurrentStep(i - 1);
      };

      setSteps(buildReactourSteps(NAV_TOUR_STEPS, {
        onNext, onPrev, onClose: closeTour,
        totalSteps: NAV_TOUR_STEPS.length,
      }));
      setCurrentStep(0);
      setIsOpen(true);
    }).catch(() => {});

    return () => { cancelled = true; };
  }, [isReady, tourPhase, pathname, setSteps, setCurrentStep, setIsOpen, setTourPhase, router, closeTour]);

  // ── Preferences phase ─────────────────────────────────────────────────
  useEffect(() => {
    if (!isReady || tourPhase !== 'preferences' || pathname !== '/account') return;
    if (phaseInitRef.current === 'preferences') return;
    phaseInitRef.current = 'preferences';
    let cancelled = false;

    waitForSelector(PREFERENCES_TOUR_STEPS[0].selector).then(() => {
      if (cancelled) return;
      const onNext = (i) => {
        if (i === PREFERENCES_TOUR_STEPS.length - 1) {
          setIsOpen(false);
        } else {
          setCurrentStep(i + 1);
        }
      };
      const onPrev = (i) => {
        if (i > 0) setCurrentStep(i - 1);
      };

      setSteps(buildReactourSteps(PREFERENCES_TOUR_STEPS, {
        onNext, onPrev, onClose: closeTour,
        totalSteps: PREFERENCES_TOUR_STEPS.length,
      }));
      setCurrentStep(0);
      setIsOpen(true);
    }).catch(() => {});

    return () => { cancelled = true; };
  }, [isReady, tourPhase, pathname, setSteps, setCurrentStep, setIsOpen, closeTour]);

  // Listen for preferences save event → advance to discover
  useEffect(() => {
    if (tourPhase !== 'preferences') return;

    const handler = () => {
      setIsOpen(false);
      setTimeout(() => {
        setTourPhase('discover');
        router.push('/discover');
      }, 600);
    };

    window.addEventListener('padly-tour-prefs-saved', handler);
    return () => window.removeEventListener('padly-tour-prefs-saved', handler);
  }, [tourPhase, setIsOpen, setTourPhase, router]);

  // ── Discover phase (guided swipes) ────────────────────────────────────
  const discoverStepRef = useRef(0);

  useEffect(() => {
    if (!isReady || tourPhase !== 'discover' || pathname !== '/discover') return;
    if (phaseInitRef.current === 'discover') return;
    phaseInitRef.current = 'discover';
    discoverStepRef.current = 0;
    let cancelled = false;

    waitForSelector(DISCOVER_TOUR_STEPS[0].selector).then(() => {
      if (cancelled) return;
      const onNext = (i) => {
        if (i === DISCOVER_TOUR_STEPS.length - 1) {
          setIsOpen(false);
          setTourPhase('groups');
          router.push('/groups');
        } else {
          setCurrentStep(i + 1);
          discoverStepRef.current = i + 1;
        }
      };
      const onPrev = (i) => {
        if (i > 0) {
          setCurrentStep(i - 1);
          discoverStepRef.current = i - 1;
        }
      };

      setSteps(buildReactourSteps(DISCOVER_TOUR_STEPS, {
        onNext, onPrev, onClose: closeTour,
        totalSteps: DISCOVER_TOUR_STEPS.length,
      }));
      setCurrentStep(0);
      setIsOpen(true);
    }).catch(() => {});

    return () => { cancelled = true; };
  }, [isReady, tourPhase, pathname, setSteps, setCurrentStep, setIsOpen, setTourPhase, router, closeTour]);

  // Listen for swipe events to auto-advance guided swipe steps
  useEffect(() => {
    if (tourPhase !== 'discover') return;

    const handler = (e) => {
      const { direction } = e.detail || {};
      const step = discoverStepRef.current;

      // Step 1 = "Try passing" — advance on any pass (left)
      if (step === 1 && direction === 'left') {
        const nextIdx = 2;
        discoverStepRef.current = nextIdx;
        setCurrentStep(nextIdx);
      }
      // Step 2 = "Now like one" — advance on any like (right)
      else if (step === 2 && direction === 'right') {
        const nextIdx = 3;
        discoverStepRef.current = nextIdx;
        setCurrentStep(nextIdx);
      }
    };

    window.addEventListener('padly-tour-swipe', handler);
    return () => window.removeEventListener('padly-tour-swipe', handler);
  }, [tourPhase, setCurrentStep]);

  // ── Groups phase ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!isReady || tourPhase !== 'groups' || pathname !== '/groups') return;
    if (phaseInitRef.current === 'groups') return;
    phaseInitRef.current = 'groups';
    let cancelled = false;

    waitForSelector(GROUPS_TOUR_STEPS[0].selector).then(() => {
      if (cancelled) return;
      const onNext = (i) => {
        if (i === GROUPS_TOUR_STEPS.length - 1) {
          setIsOpen(false);
          setTourPhase('matches');
          router.push('/matches');
        } else {
          setCurrentStep(i + 1);
        }
      };
      const onPrev = (i) => {
        if (i > 0) setCurrentStep(i - 1);
      };

      setSteps(buildReactourSteps(GROUPS_TOUR_STEPS, {
        onNext, onPrev, onClose: closeTour,
        totalSteps: GROUPS_TOUR_STEPS.length,
      }));
      setCurrentStep(0);
      setIsOpen(true);
    }).catch(() => {});

    return () => { cancelled = true; };
  }, [isReady, tourPhase, pathname, setSteps, setCurrentStep, setIsOpen, setTourPhase, router, closeTour]);

  // ── Matches phase ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!isReady || tourPhase !== 'matches' || pathname !== '/matches') return;
    if (phaseInitRef.current === 'matches') return;
    phaseInitRef.current = 'matches';
    let cancelled = false;

    waitForSelector(MATCHES_TOUR_STEPS[0].selector).then(() => {
      if (cancelled) return;
      const onNext = () => {
        setIsOpen(false);
        setTourPhase('finishing');
      };

      setSteps(buildReactourSteps(MATCHES_TOUR_STEPS, {
        onNext, onPrev: () => {}, onClose: closeTour,
        totalSteps: MATCHES_TOUR_STEPS.length,
      }));
      setCurrentStep(0);
      setIsOpen(true);
    }).catch(() => {});

    return () => { cancelled = true; };
  }, [isReady, tourPhase, pathname, setSteps, setCurrentStep, setIsOpen, setTourPhase, closeTour]);

  // ── Finishing phase ───────────────────────────────────────────────────
  useEffect(() => {
    if (!isReady || tourPhase !== 'finishing') return;
    setShowCompletion(true);
  }, [isReady, tourPhase]);

  // ── Reset phaseInitRef on phase change or when tour becomes active ────
  useEffect(() => {
    if (tourPhase !== phaseInitRef.current) {
      phaseInitRef.current = null;
    }
  }, [tourPhase]);

  useEffect(() => {
    if (isTourActive) {
      phaseInitRef.current = null;
    }
  }, [isTourActive]);

  // ── Modal handlers ────────────────────────────────────────────────────
  const handleWelcomeStart = useCallback(() => {
    setShowWelcome(false);
    setTourPhase('nav');
  }, [setTourPhase]);

  const handleWelcomeSkip = useCallback(() => {
    setShowWelcome(false);
    endTour(); // deliberate skip from welcome = fully dismiss
  }, [endTour]);

  const handleCompletionClose = useCallback(() => {
    setShowCompletion(false);
    endTour();
  }, [endTour]);

  const handleCompletionGo = useCallback((path) => {
    setShowCompletion(false);
    endTour();
    router.push(path);
  }, [endTour, router]);

  return (
    <>
      <WelcomeModal
        opened={showWelcome}
        onStart={handleWelcomeStart}
        onSkip={handleWelcomeSkip}
      />
      <CompletionModal
        opened={showCompletion}
        onClose={handleCompletionClose}
        onGoTo={handleCompletionGo}
      />
    </>
  );
}
