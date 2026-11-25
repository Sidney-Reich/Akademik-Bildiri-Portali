-- 005 (T2): Reviewer assignments
-- Report 4.1 - ReviewAssignment


CREATE TABLE core.review_assignment (
    assignment_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    submission_id BIGINT NOT NULL
        REFERENCES core.submission(submission_id),

    reviewer_id BIGINT NOT NULL
        REFERENCES core.person(person_id),

    round INTEGER NOT NULL DEFAULT 1
        CHECK (round > 0),

    is_additional BOOLEAN NOT NULL DEFAULT FALSE,

    reason TEXT,

    assigned_by BIGINT NOT NULL
        REFERENCES core.person(person_id),

    status TEXT NOT NULL DEFAULT 'ASSIGNED',

    UNIQUE (
        submission_id,
        reviewer_id,
        round
    )
);
