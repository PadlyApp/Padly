-- Phase 4: pairwise roommate intro / double opt-in before group funnel

BEGIN;

CREATE TABLE IF NOT EXISTS public.roommate_intro_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    to_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
    result_group_id uuid NULL REFERENCES public.roommate_groups(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NULL,
    CONSTRAINT roommate_intro_requests_no_self CHECK (from_user_id <> to_user_id),
    CONSTRAINT roommate_intro_requests_unique_direction UNIQUE (from_user_id, to_user_id)
);

CREATE INDEX IF NOT EXISTS idx_roommate_intro_requests_to_user
    ON public.roommate_intro_requests(to_user_id, status);

CREATE INDEX IF NOT EXISTS idx_roommate_intro_requests_from_user
    ON public.roommate_intro_requests(from_user_id, status);

CREATE INDEX IF NOT EXISTS idx_roommate_intro_requests_result_group
    ON public.roommate_intro_requests(result_group_id)
    WHERE result_group_id IS NOT NULL;

COMMENT ON TABLE public.roommate_intro_requests IS
    'Directed intro/opt-in between users; mutual pending rows trigger group funnel.';

COMMIT;
