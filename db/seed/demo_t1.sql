-- Demo data to try the T1 screens (NOT the shared starter data, seed_minimal.sql).
-- Adds one conference with two tracks open for 30 days. Safe to run again.
--   docker compose exec -T db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB' < db/seed/demo_t1.sql
DO $$
DECLARE
    v_chair bigint;
    v_conf  bigint;
    v_track bigint;
    v_name  text;
BEGIN
    IF EXISTS (SELECT 1 FROM core.conference WHERE name = 'Demo Konferansı') THEN
        RAISE NOTICE 'demo data is already there';
        RETURN;
    END IF;
    INSERT INTO core.person (full_name) VALUES ('Demo Başkan') RETURNING person_id INTO v_chair;
    INSERT INTO core.conference (name, year, created_by)
        VALUES ('Demo Konferansı', 2027, v_chair) RETURNING conference_id INTO v_conf;
    INSERT INTO core.conference_policy (conference_id, changed_by) VALUES (v_conf, v_chair);
    FOREACH v_name IN ARRAY ARRAY['Veri Tabanı Sistemleri', 'Yazılım Mühendisliği'] LOOP
        INSERT INTO core.track (conference_id, name) VALUES (v_conf, v_name)
            RETURNING track_id INTO v_track;
        INSERT INTO core.track_deadline (track_id, deadline_type, due_at, changed_by)
            VALUES (v_track, 'SUBMISSION', now() + interval '30 days', v_chair);
    END LOOP;
END $$;
