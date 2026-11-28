-- BR-06: submission, authors and file record are saved together. A submission
-- without a file version cannot be committed (Report 4.3, total participation).
-- (Authors are already required by fk_t1_corresponding_author.)
CREATE FUNCTION core.fn_t1_require_version() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM core.submission WHERE submission_id = NEW.submission_id)
       AND NOT EXISTS (SELECT 1 FROM core.submission_version
                       WHERE submission_id = NEW.submission_id) THEN
        RAISE EXCEPTION 'submission % has no file version', NEW.submission_id
            USING ERRCODE = 'check_violation', CONSTRAINT = 'br06_requires_version';
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER trg_t1_require_version
    AFTER INSERT ON core.submission
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION core.fn_t1_require_version();
