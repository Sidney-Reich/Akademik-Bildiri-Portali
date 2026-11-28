-- BR-08 (and BR-28): after the deadline, and from the moment review starts,
-- the author list and the shares are locked; attempts are refused AND recorded.
--
-- A raised error would roll back the record together with the change. So the
-- trigger skips the change (0 rows affected), writes the record and warns.
-- The record goes into core.audit_log (T4, BR-25); until that table exists
-- only the warning is produced.

CREATE FUNCTION core.fn_t1_authors_locked(p_submission bigint) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT coalesce((
        SELECT status <> 'SUBMITTED'
               OR NOT core.fn_t1_submission_open(track_id, core.fn_t1_request_time())
        FROM core.submission WHERE submission_id = p_submission), false)
$$;

CREATE FUNCTION core.fn_t1_record_attempt(p_submission bigint, p_old jsonb, p_new jsonb)
RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF to_regclass('core.audit_log') IS NOT NULL THEN
        -- %L literals take the column's type, whether T4 chooses text or jsonb
        EXECUTE format(
            'INSERT INTO core.audit_log (actor_id, action, entity_type, entity_id, old_value, new_value)
             VALUES (%L, %L, %L, %L, %L, %L)',
            nullif(current_setting('app.person_id', true), ''),
            'AUTHORSHIP_CHANGE_REFUSED', 'Submission', p_submission, p_old, p_new);
    END IF;
    RAISE WARNING 'author list of submission % is locked; change refused', p_submission;
END $$;

CREATE FUNCTION core.fn_t1_authorship_lock() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_old jsonb;
    v_new jsonb;
    v_id  bigint;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        v_old := to_jsonb(OLD);
        IF core.fn_t1_authors_locked(OLD.submission_id) THEN
            v_id := OLD.submission_id;
        END IF;
    END IF;
    IF TG_OP <> 'DELETE' THEN
        v_new := to_jsonb(NEW);
        IF core.fn_t1_authors_locked(NEW.submission_id) THEN
            v_id := NEW.submission_id;
        END IF;
    END IF;

    IF v_id IS NOT NULL THEN
        PERFORM core.fn_t1_record_attempt(v_id, v_old, v_new);
        RETURN NULL;  -- the row is not changed
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_t1_authorship_lock
    BEFORE INSERT OR UPDATE OR DELETE ON core.authorship
    FOR EACH ROW EXECUTE FUNCTION core.fn_t1_authorship_lock();

-- the corresponding author is part of the author list
CREATE FUNCTION core.fn_t1_corresponding_lock() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF core.fn_t1_authors_locked(OLD.submission_id) THEN
        PERFORM core.fn_t1_record_attempt(
            OLD.submission_id,
            jsonb_build_object('corresponding_author_id', OLD.corresponding_author_id),
            jsonb_build_object('corresponding_author_id', NEW.corresponding_author_id));
        NEW.corresponding_author_id := OLD.corresponding_author_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_t1_corresponding_lock
    BEFORE UPDATE OF corresponding_author_id ON core.submission
    FOR EACH ROW
    WHEN (OLD.corresponding_author_id IS DISTINCT FROM NEW.corresponding_author_id)
    EXECUTE FUNCTION core.fn_t1_corresponding_lock();
