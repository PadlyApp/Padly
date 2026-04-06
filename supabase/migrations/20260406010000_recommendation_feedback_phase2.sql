-- Migration: Recommendation feedback storage for Matches evaluation
-- Purpose: Phase 2 storage for recommendation sessions and explicit user feedback
-- Date: 2026-04-06

BEGIN;

CREATE TABLE IF NOT EXISTS public.recommendation_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    client_session_id text NOT NULL,
    surface text NOT NULL CHECK (surface IN ('matches', 'discover')),
    started_at timestamp with time zone NOT NULL DEFAULT now(),
    ended_at timestamp with time zone NULL,
    recommendation_count_shown integer NOT NULL DEFAULT 0 CHECK (recommendation_count_shown >= 0),
    top_listing_ids_shown uuid[] NOT NULL DEFAULT '{}'::uuid[],
    algorithm_version text NULL,
    model_version text NULL,
    experiment_name text NULL,
    experiment_variant text NULL,
    prompt_presented_at timestamp with time zone NULL,
    prompt_dismissed_at timestamp with time zone NULL,
    feedback_submitted_at timestamp with time zone NULL,
    detail_opens_count integer NOT NULL DEFAULT 0 CHECK (detail_opens_count >= 0),
    saves_count integer NOT NULL DEFAULT 0 CHECK (saves_count >= 0),
    likes_count integer NOT NULL DEFAULT 0 CHECK (likes_count >= 0),
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT recommendation_sessions_actor_client_unique UNIQUE (actor_user_id, client_session_id)
);

CREATE INDEX IF NOT EXISTS idx_recommendation_sessions_user_started_at
ON public.recommendation_sessions(actor_user_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_recommendation_sessions_surface_started_at
ON public.recommendation_sessions(surface, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_recommendation_sessions_variant_started_at
ON public.recommendation_sessions(experiment_variant, started_at DESC)
WHERE experiment_variant IS NOT NULL;

COMMENT ON TABLE public.recommendation_sessions IS 'One recommendation exposure window, such as a Matches page visit.';
COMMENT ON COLUMN public.recommendation_sessions.client_session_id IS 'Client-generated idempotency key for one page/session visit.';
COMMENT ON COLUMN public.recommendation_sessions.top_listing_ids_shown IS 'Ordered list of top listing IDs shown during the recommendation session.';

CREATE TABLE IF NOT EXISTS public.user_recommendation_feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    recommendation_session_id uuid NOT NULL UNIQUE REFERENCES public.recommendation_sessions(id) ON DELETE CASCADE,
    surface text NOT NULL CHECK (surface IN ('matches', 'discover')),
    feedback_label text NOT NULL CHECK (feedback_label IN ('not_useful', 'somewhat_useful', 'very_useful')),
    reason_label text NULL CHECK (reason_label IS NULL OR reason_label IN ('too_expensive', 'wrong_location', 'not_my_style', 'too_few_good_options', 'other')),
    submitted_at timestamp with time zone NOT NULL DEFAULT now(),
    algorithm_version text NULL,
    model_version text NULL,
    experiment_name text NULL,
    experiment_variant text NULL,
    swipes_in_session integer NULL CHECK (swipes_in_session IS NULL OR swipes_in_session >= 0),
    likes_in_session integer NULL CHECK (likes_in_session IS NULL OR likes_in_session >= 0),
    saves_in_session integer NULL CHECK (saves_in_session IS NULL OR saves_in_session >= 0),
    detail_opens_in_session integer NULL CHECK (detail_opens_in_session IS NULL OR detail_opens_in_session >= 0),
    recommendation_count_shown integer NULL CHECK (recommendation_count_shown IS NULL OR recommendation_count_shown >= 0),
    top_listing_ids_shown uuid[] NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_recommendation_feedback_user_submitted_at
ON public.user_recommendation_feedback(actor_user_id, submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_recommendation_feedback_variant_submitted_at
ON public.user_recommendation_feedback(experiment_variant, submitted_at DESC)
WHERE experiment_variant IS NOT NULL;

COMMENT ON TABLE public.user_recommendation_feedback IS 'Explicit session-level usefulness feedback for recommendation evaluation.';

GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE public.recommendation_sessions TO authenticated, service_role;
GRANT SELECT, INSERT ON TABLE public.user_recommendation_feedback TO authenticated, service_role;

ALTER TABLE public.recommendation_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_recommendation_feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "recommendation_sessions_insert_own" ON public.recommendation_sessions;
CREATE POLICY "recommendation_sessions_insert_own"
ON public.recommendation_sessions
FOR INSERT
TO authenticated
WITH CHECK (
    actor_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
);

DROP POLICY IF EXISTS "recommendation_sessions_select_own" ON public.recommendation_sessions;
CREATE POLICY "recommendation_sessions_select_own"
ON public.recommendation_sessions
FOR SELECT
TO authenticated
USING (
    actor_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
);

DROP POLICY IF EXISTS "recommendation_sessions_update_own" ON public.recommendation_sessions;
CREATE POLICY "recommendation_sessions_update_own"
ON public.recommendation_sessions
FOR UPDATE
TO authenticated
USING (
    actor_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
)
WITH CHECK (
    actor_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
);

DROP POLICY IF EXISTS "user_recommendation_feedback_insert_own" ON public.user_recommendation_feedback;
CREATE POLICY "user_recommendation_feedback_insert_own"
ON public.user_recommendation_feedback
FOR INSERT
TO authenticated
WITH CHECK (
    actor_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
);

DROP POLICY IF EXISTS "user_recommendation_feedback_select_own" ON public.user_recommendation_feedback;
CREATE POLICY "user_recommendation_feedback_select_own"
ON public.user_recommendation_feedback
FOR SELECT
TO authenticated
USING (
    actor_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
);

COMMIT;
