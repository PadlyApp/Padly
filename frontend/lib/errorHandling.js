function detailToMessage(detail) {
  if (typeof detail === 'string' && detail.trim()) return detail.trim();
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') return item.msg || JSON.stringify(item);
        return '';
      })
      .filter(Boolean)
      .join(', ');
  }
  return '';
}

export function createAppError(message, options = {}) {
  const error = new Error(message);
  error.name = 'AppError';
  if (options.status != null) error.status = options.status;
  if (options.code) error.code = options.code;
  if (options.payload != null) error.payload = options.payload;
  if (options.rawMessage) error.rawMessage = options.rawMessage;
  if (options.isNetworkError) error.isNetworkError = true;
  return error;
}

export function parseApiErrorPayload(payload, fallbackMessage = 'Request failed') {
  if (!payload || typeof payload !== 'object') {
    return fallbackMessage;
  }

  const detailMessage = detailToMessage(payload.detail);
  if (detailMessage) return detailMessage;

  if (typeof payload.message === 'string' && payload.message.trim()) {
    return payload.message.trim();
  }

  if (typeof payload.error === 'string' && payload.error.trim()) {
    return payload.error.trim();
  }

  return fallbackMessage;
}

async function safeReadJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function parseApiErrorResponse(response, fallbackMessage = 'Request failed') {
  const payload = await safeReadJson(response);
  const messageFromPayload = parseApiErrorPayload(payload, '');
  const message =
    messageFromPayload ||
    (typeof response.statusText === 'string' && response.statusText.trim()
      ? response.statusText.trim()
      : fallbackMessage);

  return {
    status: response.status,
    message,
    payload,
  };
}

export function isNetworkError(error) {
  if (!error) return false;
  if (error.isNetworkError) return true;
  return error instanceof TypeError && /fetch|network|internet|failed/i.test(String(error.message || ''));
}

export function getErrorMessage(error, fallbackMessage = 'Something went wrong') {
  if (!error) return fallbackMessage;
  if (typeof error === 'string') return error;
  if (typeof error.message === 'string' && error.message.trim()) return error.message.trim();
  return fallbackMessage;
}

export function normalizeAuthErrorMessage(error, { flow = 'signin' } = {}) {
  const status = error?.status;
  const baseMessage = getErrorMessage(error, '');
  const raw = String(error?.rawMessage || baseMessage).toLowerCase();

  if (error?.code === 'EMAIL_CONFIRMATION_REQUIRED') {
    return baseMessage || 'Account created. Please check your email to confirm your account.';
  }

  if (isNetworkError(error)) {
    return "Can't reach the server right now. Check your connection and try again.";
  }

  if (
    status === 401 ||
    raw.includes('invalid email or password') ||
    raw.includes('invalid login credentials')
  ) {
    return 'Incorrect email or password. Please try again.';
  }

  if (status === 409 || raw.includes('already exists') || raw.includes('already registered')) {
    return 'An account with this email already exists. Try signing in instead.';
  }

  if (
    status === 422 ||
    raw.includes('invalid email') ||
    raw.includes('email format') ||
    raw.includes('password')
  ) {
    return flow === 'signup'
      ? 'Please check your email and password format, then try again.'
      : 'Please check your login details and try again.';
  }

  if (status >= 500) {
    return 'Something went wrong on our side. Please try again in a moment.';
  }

  if (flow === 'signup') {
    return baseMessage || 'Unable to create your account right now. Please try again.';
  }
  return baseMessage || 'Unable to sign you in right now. Please try again.';
}

export function normalizeRecommendationsError(error) {
  if (isNetworkError(error)) {
    return "We couldn't load recommendations right now. Check your internet connection and try again.";
  }

  const status = error?.status;
  if (status >= 500) {
    return "We're having trouble loading listings right now. Please try again in a moment.";
  }

  return getErrorMessage(error, 'Unable to load recommendations right now.');
}

export function hasCompleteCorePreferences(prefs) {
  return Boolean(prefs?.target_country && prefs?.target_state_province && prefs?.target_city);
}
