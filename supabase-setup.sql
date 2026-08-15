-- ============================================================================
--  G-Daze Runner — Supabase setup
--  RIT Dubai Graphic Design Club
--
--  RUN THIS ONCE, BEFORE deploying the matching front-end changes:
--    Supabase dashboard -> SQL Editor -> New query -> paste -> Run.
--  It is safe to re-run.
--
--  FIRST, decide who the admins are and edit the list in PART 5 below.
--
--  Then, for each of them:
--    Authentication -> Users -> "Add user" -> "Create new user"
--      Email:    <same address you put in PART 5>
--      Password: <pick a new one — the old one is in this repo's git history>
--      Tick "Auto Confirm User"
--
--  Also turn OFF public signup, so nobody can create their own account:
--    Authentication -> Sign In / Providers -> Email -> untick "Allow new users
--    to sign up".
--
--  What this fixes
--  ---------------
--  1. The anon key is committed in this repo and is visible to anyone who
--     opens the page, and it could read the players table directly — every
--     name, email and mobile number. Signup and score saving now go through
--     two functions instead, and the table itself is closed to the public.
--  2. The game_locked switch could be flipped by anyone, logged in or not.
--     It now requires a signed-in admin.
--  3. Any score could be written straight into players from the browser
--     console. Scores now go through submit_score(), which only ever raises
--     a personal best and records every run.
--  4. There was no way to ask "who was top scorer today?" — highest_score is
--     an all-time max and updated_at is a display string with no year. The
--     new scores table logs every run with a real timestamp.
-- ============================================================================


-- ----------------------------------------------------------------------------
--  Helper — the "15th August, 7:34pm" string the players table already uses.
--  Kept so the dashboard looks exactly as it did. Dubai time, not UTC.
-- ----------------------------------------------------------------------------
create or replace function public.gd_display_time()
returns text
language sql
stable
as $$
    select to_char(now() at time zone 'Asia/Dubai', 'FMDDth FMMonth, FMHH12:MI')
        || to_char(now() at time zone 'Asia/Dubai', 'am');
$$;


-- ----------------------------------------------------------------------------
--  PART 1 — Per-run score log
--
--  One row per game over, with a real timestamp. This is what makes a daily
--  winner answerable, and it doubles as an audit trail if a score looks off.
-- ----------------------------------------------------------------------------
create table if not exists public.scores (
    id        bigint generated always as identity primary key,
    player_id bigint      not null references public.players (id) on delete cascade,
    score     integer     not null check (score >= 0 and score <= 99999),
    played_at timestamptz not null default now()
);

create index if not exists scores_played_at_idx on public.scores (played_at desc);
create index if not exists scores_player_id_idx on public.scores (player_id);

-- No policies are added below, so with RLS on, the public gets nothing.
-- Writes happen inside submit_score(); reads happen in the dashboard.
alter table public.scores enable row level security;


-- ----------------------------------------------------------------------------
--  PART 2 — Signup
--
--  Replaces the browser's direct select-then-insert on players.
--  security definer: runs as the owner, so it can touch players even though
--  the public no longer can.
--
--  Identity is email + mobile, NOT name. Previously all three had to match,
--  so a student who typed "Ali" one round and "ali" the next got a second
--  row and a split score — which matters when there's a prize attached.
-- ----------------------------------------------------------------------------
create or replace function public.register_player(
    p_name   text,
    p_email  text,
    p_mobile text
)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
    v_id bigint;
begin
    p_name   := btrim(p_name);
    p_email  := lower(btrim(p_email));
    p_mobile := btrim(p_mobile);

    -- Same rules the landing page enforces, applied again here, because
    -- client-side validation is only a convenience.
    if p_name = '' or length(p_name) > 60 then
        raise exception 'invalid name';
    end if;
    if p_mobile !~ '^05\d{8}$' then
        raise exception 'invalid mobile';
    end if;
    if p_email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then
        raise exception 'invalid email';
    end if;

    select id into v_id
      from players
     where lower(email) = p_email
       and mobile = p_mobile
     limit 1;

    if v_id is null then
        insert into players (name, email, mobile, highest_score, updated_at)
        values (p_name, p_email, p_mobile, 0, gd_display_time())
        returning id into v_id;
    end if;

    return v_id;
end;
$$;


-- ----------------------------------------------------------------------------
--  PART 3 — Score submission
--
--  Logs the run, then raises highest_score only if the new score beats it.
--  A score can never be lowered, and never set to an arbitrary value.
--  Returns {"is_best": bool, "best": int} so the game-over overlay can show
--  the same two messages it always did.
-- ----------------------------------------------------------------------------
create or replace function public.submit_score(
    p_player_id bigint,
    p_score     integer
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_prev integer;
    v_new  boolean := false;
begin
    if p_score is null or p_score < 0 or p_score > 99999 then
        raise exception 'invalid score';
    end if;

    select highest_score into v_prev
      from players
     where id = p_player_id
       for update;

    if v_prev is null then
        raise exception 'unknown player';
    end if;

    insert into scores (player_id, score) values (p_player_id, p_score);

    if p_score > v_prev then
        update players
           set highest_score = p_score,
               updated_at    = gd_display_time()
         where id = p_player_id;
        v_new := true;
    end if;

    return jsonb_build_object('is_best', v_new, 'best', greatest(v_prev, p_score));
end;
$$;


-- ----------------------------------------------------------------------------
--  PART 4 — Close the players table to the public
--
--  The leaderboard view keeps working: a normal view runs as its owner, so it
--  still reads players and still exposes only name + highest_score.
--
--  The one exception is if that view was created WITH (security_invoker = true),
--  in which case it runs as the caller and will start returning nothing once
--  RLS is on. If the leaderboard goes empty after running this file, that is
--  the cause, and this turns it back off:
--      alter view public.leaderboard set (security_invoker = false);
-- ----------------------------------------------------------------------------
alter table public.players enable row level security;

revoke all on public.players from anon;
revoke all on public.scores  from anon;

grant select on public.leaderboard to anon;

grant execute on function public.register_player(text, text, text) to anon;
grant execute on function public.submit_score(bigint, integer)     to anon;


-- ----------------------------------------------------------------------------
--  PART 5 — Who counts as an admin
--
--  >>> EDIT THE LIST BELOW BEFORE RUNNING THIS FILE. <<<
--
--  Being signed in is NOT enough on its own — Supabase projects accept public
--  email signups by default, so "any logged-in user" would have meant anyone
--  who registered themselves an account. Only the addresses listed here can
--  touch the lock switch.
--
--  km2495@rit.edu is what the old control page had hardcoded; it is not a
--  recommendation. Put whoever actually runs the booth here, one row each.
--  Each address also needs a matching user under Authentication -> Users.
-- ----------------------------------------------------------------------------
create table if not exists public.admins (
    email text primary key
);

insert into public.admins (email) values
    ('km2495@rit.edu')
    -- , ('your.email@rit.edu')
on conflict (email) do nothing;

-- Nobody reads or writes this from the browser; manage it in the dashboard.
alter table public.admins enable row level security;
revoke all on public.admins from anon, authenticated;

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
          from admins
         where lower(email) = lower(coalesce(auth.jwt() ->> 'email', ''))
    );
$$;


-- ----------------------------------------------------------------------------
--  PART 6 — The lock switch is admin-only
--
--  Everyone needs to read game_locked (the landing page and the game-over
--  screen both check it). Only a listed admin may change it.
-- ----------------------------------------------------------------------------
alter table public.settings enable row level security;

drop policy if exists "anyone can read the lock flag"   on public.settings;
drop policy if exists "admins can change the lock flag" on public.settings;

create policy "anyone can read the lock flag"
    on public.settings for select
    to anon, authenticated
    using (true);

create policy "admins can change the lock flag"
    on public.settings for update
    to authenticated
    using (public.is_admin())
    with check (public.is_admin());


-- ============================================================================
--  Useful queries
-- ============================================================================

-- Today's winner (Dubai time) — this is the one the AED 100 banner promises.
--
--   select p.name, p.email, p.mobile, max(s.score) as best
--     from scores s
--     join players p on p.id = s.player_id
--    where s.played_at >= date_trunc('day', now() at time zone 'Asia/Dubai')
--                         at time zone 'Asia/Dubai'
--    group by p.id, p.name, p.email, p.mobile
--    order by best desc
--    limit 5;

-- Every run by one player, newest first — for checking a suspicious score.
--
--   select s.score, s.played_at
--     from scores s join players p on p.id = s.player_id
--    where p.email = 'someone@rit.edu'
--    order by s.played_at desc;
