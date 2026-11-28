-- BR-27: a revised version must arrive before the revision deadline.
-- BR-28: every version keeps its own file and hash; old versions never change.

CREATE FUNCTION core.fn_t1_version_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_sub  core.submission%ROWTYPE;
    v_at   timestamptz := core.fn_t1_request_time();
    v_due  timestamptz;
    v_next integer;
BEGIN
    SELECT * INTO v_sub FROM core.submission
    WHERE submission_id = NEW.submission_id FOR NO KEY UPDATE;
    IF NOT FOUND THEN
        RETURN NEW;  -- the foreign key refuses it
    END IF;

    SELECT coalesce(max(version_no), 0) + 1 INTO v_next
    FROM core.submission_version WHERE submission_id = NEW.submission_id;
    IF NEW.version_no <> v_next THEN
        RAISE EXCEPTION 'next version of submission % is %, not %',
            NEW.submission_id, v_next, NEW.version_no
            USING ERRCODE = 'check_violation', CONSTRAINT = 'br28_version_order';
    END IF;

    IF v_sub.status = 'SUBMITTED' THEN                  -- first upload or replacement
        IF NOT core.fn_t1_submission_open(v_sub.track_id, v_at) THEN
            RAISE EXCEPTION 'the submission deadline has passed'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'br04_deadline';
        END IF;
    ELSIF v_sub.status = 'REVISION_REQUESTED' THEN      -- revised version
        v_due := core.fn_t1_due_at(v_sub.track_id, 'REVISION');
        IF v_due IS NULL OR v_at > v_due THEN
            RAISE EXCEPTION 'the revision deadline has passed or is not set'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'br27_revision_deadline';
        END IF;
    ELSIF v_sub.status = 'ACCEPTED' THEN                -- final (camera-ready) version
        v_due := core.fn_t1_due_at(v_sub.track_id, 'CAMERA_READY');
        IF v_at > v_due THEN                            -- no deadline set: allowed
            RAISE EXCEPTION 'the final version deadline has passed'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'br27_camera_ready_deadline';
        END IF;
    ELSE
        RAISE EXCEPTION 'no version can be uploaded while the status is %', v_sub.status
            USING ERRCODE = 'check_violation', CONSTRAINT = 'br28_upload_status';
    END IF;

    NEW.uploaded_at := v_at;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_t1_version_insert
    BEFORE INSERT ON core.submission_version
    FOR EACH ROW EXECUTE FUNCTION core.fn_t1_version_insert();

CREATE FUNCTION core.fn_t1_version_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'submission versions cannot be changed or deleted'
        USING ERRCODE = 'check_violation', CONSTRAINT = 'br28_immutable';
END $$;

CREATE TRIGGER trg_t1_version_immutable
    BEFORE UPDATE OR DELETE ON core.submission_version
    FOR EACH ROW EXECUTE FUNCTION core.fn_t1_version_immutable();

CREATE TRIGGER trg_t1_version_no_truncate
    BEFORE TRUNCATE ON core.submission_version
    FOR EACH STATEMENT EXECUTE FUNCTION core.fn_t1_version_immutable();
