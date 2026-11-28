-- BR-07: the same PDF (same hash) cannot be submitted twice to one conference.
-- The conference is two joins away, so a plain UNIQUE cannot express it.
CREATE INDEX idx_t1_version_hash ON core.submission_version (file_hash);

CREATE FUNCTION core.fn_t1_unique_pdf() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_conf bigint;
BEGIN
    SELECT t.conference_id INTO v_conf
    FROM core.submission s JOIN core.track t ON t.track_id = s.track_id
    WHERE s.submission_id = NEW.submission_id;

    -- two uploads of the same file at the same moment: the second one waits
    PERFORM pg_advisory_xact_lock(hashtextextended(v_conf || ':' || NEW.file_hash, 0));

    IF EXISTS (SELECT 1
               FROM core.submission_version v
               JOIN core.submission s ON s.submission_id = v.submission_id
               JOIN core.track t ON t.track_id = s.track_id
               WHERE v.file_hash = NEW.file_hash
                 AND t.conference_id = v_conf
                 AND v.submission_id <> NEW.submission_id) THEN
        RAISE EXCEPTION 'this PDF was already submitted to this conference'
            USING ERRCODE = 'unique_violation', CONSTRAINT = 'br07_unique_pdf';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_t1_unique_pdf
    BEFORE INSERT ON core.submission_version
    FOR EACH ROW EXECUTE FUNCTION core.fn_t1_unique_pdf();
