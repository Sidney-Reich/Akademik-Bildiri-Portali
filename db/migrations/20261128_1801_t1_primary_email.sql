-- BR-10: a person may have several emails; exactly one of them is primary.

-- at most one primary email per person
CREATE UNIQUE INDEX idx_t1_one_primary_email
    ON core.person_email (person_id) WHERE is_primary;

-- at least one: checked at commit. A person without any email is allowed only
-- while there is no account (no password), e.g. authors imported from DBLP.
CREATE FUNCTION core.fn_t1_check_primary_email() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_ids bigint[];
    v_id  bigint;
BEGIN
    IF TG_TABLE_NAME = 'person' THEN
        v_ids := ARRAY[NEW.person_id];
    ELSIF TG_OP = 'INSERT' THEN
        v_ids := ARRAY[NEW.person_id];
    ELSIF TG_OP = 'DELETE' THEN
        v_ids := ARRAY[OLD.person_id];
    ELSE
        v_ids := ARRAY[OLD.person_id, NEW.person_id];
    END IF;

    FOREACH v_id IN ARRAY v_ids LOOP
        -- one change at a time per person
        PERFORM 1 FROM core.person WHERE person_id = v_id FOR NO KEY UPDATE;
        IF EXISTS (SELECT 1 FROM core.person p
                   WHERE p.person_id = v_id
                     AND (p.password_hash IS NOT NULL
                          OR EXISTS (SELECT 1 FROM core.person_email e WHERE e.person_id = v_id))
                     AND NOT EXISTS (SELECT 1 FROM core.person_email e
                                     WHERE e.person_id = v_id AND e.is_primary)) THEN
            RAISE EXCEPTION 'person % must have a primary email', v_id
                USING ERRCODE = 'check_violation', CONSTRAINT = 'br10_primary_email';
        END IF;
    END LOOP;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER trg_t1_person_primary_email
    AFTER INSERT OR UPDATE OF password_hash ON core.person
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION core.fn_t1_check_primary_email();

CREATE CONSTRAINT TRIGGER trg_t1_email_primary_email
    AFTER INSERT OR UPDATE OR DELETE ON core.person_email
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION core.fn_t1_check_primary_email();
