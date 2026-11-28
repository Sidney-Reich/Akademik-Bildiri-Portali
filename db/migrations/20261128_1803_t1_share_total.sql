-- BR-03: the contribution shares of a submission add up to exactly 100.
-- Authors are inserted one by one, so the check runs at commit.
CREATE FUNCTION core.fn_t1_check_shares() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_ids   bigint[];
    v_id    bigint;
    v_total numeric;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_ids := ARRAY[NEW.submission_id];
    ELSIF TG_OP = 'DELETE' THEN
        v_ids := ARRAY[OLD.submission_id];
    ELSE
        v_ids := ARRAY[OLD.submission_id, NEW.submission_id];
    END IF;

    FOREACH v_id IN ARRAY v_ids LOOP
        -- two transactions changing the same author list wait for each other
        PERFORM 1 FROM core.submission WHERE submission_id = v_id FOR NO KEY UPDATE;
        IF FOUND THEN
            SELECT coalesce(sum(contribution_share), 0) INTO v_total
            FROM core.authorship WHERE submission_id = v_id;
            IF v_total <> 100 THEN
                RAISE EXCEPTION 'submission %: shares total %; must be 100', v_id, v_total
                    USING ERRCODE = 'check_violation', CONSTRAINT = 'br03_share_total';
            END IF;
        END IF;
    END LOOP;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER trg_t1_share_total
    AFTER INSERT OR UPDATE OR DELETE ON core.authorship
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION core.fn_t1_check_shares();
