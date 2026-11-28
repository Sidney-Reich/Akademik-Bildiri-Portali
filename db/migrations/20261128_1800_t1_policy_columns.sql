-- T1: policy values that BR-04 and BR-09 need.
-- Changes a T2 table (core.conference_policy): to be reviewed by Kadir.
ALTER TABLE core.conference_policy
    ADD COLUMN grace_minutes integer NOT NULL DEFAULT 0  CHECK (grace_minutes >= 0),  -- BR-04
    ADD COLUMN max_pdf_mb    integer NOT NULL DEFAULT 10 CHECK (max_pdf_mb > 0);      -- BR-09
