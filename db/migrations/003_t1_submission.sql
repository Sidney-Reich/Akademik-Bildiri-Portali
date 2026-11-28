-- 003 (T1, Eyup): submissions, their file versions, authors -- Report 4.1

CREATE TABLE core.submission (
    submission_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- BR-01: exactly one track (and through it one conference)
    track_id        bigint NOT NULL REFERENCES core.track (track_id),
    title           text NOT NULL CHECK (btrim(title) <> ''),
    abstract        text NOT NULL CHECK (btrim(abstract) <> ''),
    -- state machine of Report 2.5 (allowed changes: status_transition, T4)
    status          text NOT NULL DEFAULT 'SUBMITTED'
                    CHECK (status IN ('SUBMITTED', 'UNDER_REVIEW', 'ACCEPTED', 'REJECTED',
                                      'REVISION_REQUESTED', 'REVISED', 'WITHDRAWN',
                                      'CAMERA_READY')),
    -- BR-05: a repeated request can never create a second submission
    idempotency_key uuid NOT NULL UNIQUE,
    corresponding_author_id bigint NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()  -- time the request reached the server
);

CREATE TABLE core.submission_version (
    submission_id bigint NOT NULL REFERENCES core.submission (submission_id),
    version_no    integer NOT NULL CHECK (version_no > 0),
    file_path     text NOT NULL,
    file_hash     char(64) NOT NULL CHECK (file_hash ~ '^[0-9a-f]{64}$'),  -- SHA-256
    uploaded_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (submission_id, version_no)
);

CREATE TABLE core.authorship (
    submission_id      bigint NOT NULL REFERENCES core.submission (submission_id),
    person_id          bigint NOT NULL REFERENCES core.person (person_id),
    author_order       integer NOT NULL CHECK (author_order > 0),
    -- BR-03: each share is greater than 0 (the sum is checked by a trigger)
    contribution_share numeric(5, 2) NOT NULL
                       CHECK (contribution_share > 0 AND contribution_share <= 100),
    institution_id     bigint REFERENCES core.institution (institution_id),
    PRIMARY KEY (submission_id, person_id),
    UNIQUE (submission_id, author_order) DEFERRABLE INITIALLY DEFERRED
);

-- BR-02: the corresponding author is one of the authors. Checked at commit,
-- because the submission and its authors are inserted in one transaction.
ALTER TABLE core.submission
    ADD CONSTRAINT fk_t1_corresponding_author
    FOREIGN KEY (submission_id, corresponding_author_id)
    REFERENCES core.authorship (submission_id, person_id)
    DEFERRABLE INITIALLY DEFERRED;
