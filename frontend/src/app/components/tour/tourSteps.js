export const NAV_TOUR_STEPS = [
  {
    selector: '[data-tour="nav-discover"]',
    icon: '🔍',
    title: 'Discover',
    description:
      'Swipe through listing cards! Every swipe teaches our algorithm what you\'re looking for.',
  },
  {
    selector: '[data-tour="nav-matches"]',
    icon: '💚',
    title: 'Recommendations',
    description:
      'Your top listing matches ranked by compatibility score. The more you swipe, the smarter these get.',
  },
  {
    selector: '[data-tour="nav-account"]',
    icon: '👤',
    title: 'Account',
    description:
      'Your profile and housing preferences live here. ' +
      'A complete profile and well-set preferences drive better matches.',
    nextLabel: 'Set preferences →',
  },
];

export const PREFERENCES_TOUR_STEPS = [
  {
    selector: '[data-tour="prefs-hard"]',
    icon: '🔒',
    title: 'Hard Constraints',
    description:
      'These are your must-haves — city, budget, move-in date, lease type. ' +
      'Listings that don\'t match these are filtered out completely.',
  },
  {
    selector: '[data-tour="prefs-soft"]',
    icon: '✨',
    title: 'Soft Preferences',
    description:
      'These influence ranking but won\'t exclude listings. ' +
      'Neighborhoods, lifestyle, amenities — the more you fill in, the better your matches.',
  },
  {
    selector: '[data-tour="prefs-save"]',
    icon: '💾',
    title: 'Save When Ready',
    description:
      'Fill out what you can now and hit Save. You can always come back and update these later.',
    nextLabel: 'Got it',
    waitForAction: 'prefs-save',
  },
];

export const DISCOVER_TOUR_STEPS = [
  {
    selector: '[data-tour="discover-card"]',
    icon: '🏠',
    title: 'Listing Cards',
    description:
      'Each card shows a listing with its photo, price, location, and details. ' +
      'Let\'s try swiping on a couple!',
  },
  {
    selector: '[data-tour="discover-pass-btn"]',
    icon: '👈',
    title: 'Try Passing',
    description:
      'Tap the X button to pass on this listing. ' +
      'This tells us it\'s not your style.',
    waitForAction: 'swipe-pass',
    hideNext: true,
  },
  {
    selector: '[data-tour="discover-like-btn"]',
    icon: '💚',
    title: 'Now Like One!',
    description:
      'Tap the heart to like this listing. ' +
      'Liked listings show up in your Recommendations with match scores.',
    waitForAction: 'swipe-like',
    hideNext: true,
  },
  {
    selector: '[data-tour="discover-card"]',
    icon: '🎉',
    title: 'You\'ve Got the Hang of It!',
    description:
      'You passed on one and liked another — that\'s all it takes. ' +
      'Now let\'s look at your personalized recommendations.',
    nextLabel: 'See recommendations →',
  },
];

export const MATCHES_TOUR_STEPS = [
  {
    selector: '[data-tour="matches-content"]',
    icon: '💚',
    title: 'Your Recommendations',
    description:
      'Listings you\'ve liked appear here with compatibility scores. ' +
      'The more you swipe on Discover, the smarter these recommendations become.',
    nextLabel: 'Finish tour',
  },
];
