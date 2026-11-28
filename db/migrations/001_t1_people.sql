-- 001 (T1, Eyup): people, their emails, institutions -- Report 4.1

CREATE TABLE core.person (
    person_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name     text NOT NULL CHECK (btrim(full_name) <> ''),
    -- BR-11: optional, but unique when given
    orcid         char(19) UNIQUE
                  CHECK (orcid ~ '^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$'),
    password_hash text,   -- empty until the account is activated
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- BR-10: every email belongs to exactly one person.
-- Stored in lower case, so the primary key also catches "A@x.edu" / "a@x.edu".
CREATE TABLE core.person_email (
    email      text PRIMARY KEY
               CHECK (email = lower(email) AND email ~ '^[^@[:space:]]+@[^@[:space:]]+$'),
    person_id  bigint NOT NULL REFERENCES core.person (person_id),
    is_primary boolean NOT NULL DEFAULT false
);

CREATE TABLE core.institution (
    institution_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name           text NOT NULL CHECK (btrim(name) <> ''),
    country        text
);
