-- BR-04: a submission is accepted only before the track's current deadline plus
-- the chair's grace period, judged by the time the request reached the server.
-- BR-01: and it stays in that one track.
--
-- core.track_deadline.deadline_type values used by T1:
--   'SUBMISSION', 'REVISION', 'CAMERA_READY'

-- The backend sets app.request_received_at (SET LOCAL) to the arrival time of
-- the request; without it, the start of the transaction counts. A value in the
-- future or older than 15 minutes is not believed.
CREATE FUNCTION core.fn_t1_request_time() RETURNS timestamptz
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_at timestamptz := nullif(current_setting('app.request_received_at', true), '')::timestamptz;
BEGIN
    IF v_at IS NULL THEN
        RETURN now();
    END IF;
    IF v_at > now() OR v_at < now() - interval '15 minutes' THEN
        RAISE EXCEPTION 'request time % is not believable', v_at
            USING ERRCODE = 'check_violation', CONSTRAINT = 'br04_request_time';
    END IF;
    RETURN v_at;
END $$;

-- the current deadline = the newest row (extensions are new rows, never updates)
CREATE FUNCTION core.fn_t1_due_at(p_track bigint, p_type text) RETURNS timestamptz
LANGUAGE sql STABLE AS $$
    SELECT due_at FROM core.track_deadline
    WHERE track_id = p_track AND deadline_type = p_type AND valid_from <= now()
    ORDER BY valid_from DESC
    LIMIT 1
$$;

CREATE FUNCTION core.fn_t1_grace(p_track bigint) RETURNS interval
LANGUAGE sql STABLE AS $$
    SELECT make_interval(mins => coalesce((
        SELECT p.grace_minutes
        FROM core.track t
        JOIN core.conference_policy p ON p.conference_id = t.conference_id
        WHERE t.track_id = p_track AND p.valid_from <= now()
        ORDER BY p.valid_from DESC
        LIMIT 1), 0))
$$;

-- a track without a submission deadline is closed
CREATE FUNCTION core.fn_t1_submission_open(p_track bigint, p_at timestamptz) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT coalesce(p_at <= core.fn_t1_due_at(p_track, 'SUBMISSION') + core.fn_t1_grace(p_track),
                    false)
$$;

CREATE FUNCTION core.fn_t1_submission_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status <> 'SUBMITTED' THEN
        RAISE EXCEPTION 'a new submission starts as SUBMITTED, not %', NEW.status
            USING ERRCODE = 'check_violation', CONSTRAINT = 'br23_initial_status';
    END IF;
    NEW.created_at := core.fn_t1_request_time();
    -- an unknown track is left to the foreign key (BR-01)
    IF EXISTS (SELECT 1 FROM core.track WHERE track_id = NEW.track_id)
       AND NOT core.fn_t1_submission_open(NEW.track_id, NEW.created_at) THEN
        RAISE EXCEPTION 'the submission deadline of track % has passed or is not set', NEW.track_id
            USING ERRCODE = 'check_violation', CONSTRAINT = 'br04_deadline';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_t1_submission_deadline
    BEFORE INSERT ON core.submission
    FOR EACH ROW EXECUTE FUNCTION core.fn_t1_submission_insert();

CREATE FUNCTION core.fn_t1_submission_fixed() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'track, request key and request time of a submission cannot change'
        USING ERRCODE = 'check_violation', CONSTRAINT = 'br01_fixed_columns';
END $$;

CREATE TRIGGER trg_t1_submission_fixed
    BEFORE UPDATE ON core.submission
    FOR EACH ROW
    WHEN (OLD.track_id IS DISTINCT FROM NEW.track_id
          OR OLD.idempotency_key IS DISTINCT FROM NEW.idempotency_key
          OR OLD.created_at IS DISTINCT FROM NEW.created_at)
    EXECUTE FUNCTION core.fn_t1_submission_fixed();
