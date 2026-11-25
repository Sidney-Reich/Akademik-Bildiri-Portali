-- 002 (T2): Conference setup and management
-- Report 4.1 - Conference, policies, members,
-- tracks, deadlines and declared conflicts.


-- 1. CONFERENCE
CREATE TABLE core.conference (
    conference_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    name TEXT NOT NULL,
    year INTEGER NOT NULL CHECK (year > 0),

    created_by BIGINT NOT NULL
        REFERENCES core.person(person_id)
);


-- 2. CONFERENCE POLICY
CREATE TABLE core.conference_policy (
    conference_id BIGINT NOT NULL
        REFERENCES core.conference(conference_id),

    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    k INTEGER NOT NULL DEFAULT 3 CHECK (k > 0),
    l INTEGER NOT NULL DEFAULT 5 CHECK (l > 0),
    n INTEGER NOT NULL DEFAULT 3 CHECK (n >= 0),

    max_revision_rounds INTEGER NOT NULL DEFAULT 1
        CHECK (max_revision_rounds BETWEEN 0 AND 1),

    changed_by BIGINT NOT NULL
        REFERENCES core.person(person_id),

    PRIMARY KEY (conference_id, valid_from)
);


-- 3. CONFERENCE MEMBER
CREATE TABLE core.conference_member (
    conference_id BIGINT NOT NULL
        REFERENCES core.conference(conference_id),

    person_id BIGINT NOT NULL
        REFERENCES core.person(person_id),

    role TEXT NOT NULL
        CHECK (role IN ('CHAIR', 'REVIEWER')),

    invitation_status TEXT NOT NULL DEFAULT 'INVITED'
        CHECK (
            invitation_status IN (
                'INVITED',
                'ACCEPTED',
                'DECLINED'
            )
        ),

    invite_token_hash TEXT UNIQUE,
    token_expires_at TIMESTAMPTZ,

    invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at TIMESTAMPTZ,

    personal_max_load INTEGER
        CHECK (personal_max_load > 0),

    PRIMARY KEY (conference_id, person_id)
);


-- 4. TRACK
CREATE TABLE core.track (
    track_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    conference_id BIGINT NOT NULL
        REFERENCES core.conference(conference_id),

    name TEXT NOT NULL
);


-- 5. TRACK DEADLINE
CREATE TABLE core.track_deadline (
    track_id BIGINT NOT NULL
        REFERENCES core.track(track_id),

    deadline_type TEXT NOT NULL,

    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    due_at TIMESTAMPTZ NOT NULL,

    changed_by BIGINT NOT NULL
        REFERENCES core.person(person_id),

    PRIMARY KEY (
        track_id,
        deadline_type,
        valid_from
    )
);


-- 6. DECLARED CONFLICT
CREATE TABLE core.declared_conflict (
    person_a BIGINT NOT NULL
        REFERENCES core.person(person_id),

    person_b BIGINT NOT NULL
        REFERENCES core.person(person_id),

    reason TEXT NOT NULL,

    declared_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (person_a, person_b),

    CHECK (person_a <> person_b)
);
