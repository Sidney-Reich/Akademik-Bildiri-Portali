# Migrations

Every change to the database is a numbered SQL file in this folder.
`python manage.py migrate` applies the new ones in name order, each file in one
transaction (all of it is applied, or none of it), and records it in
`public.schema_migrations`.

## Rules

1. **A merged file is never edited.** A change goes into a new file.
2. **No `BEGIN` / `COMMIT` inside a file**: `migrate` already wraps each file in a transaction.
3. **Everything lives in the `core` schema**: write `core.person`, not `person`.
4. **Names start with your task:** `trg_t1_…`, `fn_t2_…`, `v_t3_…`, `idx_t4_…`, `pol_t3_…`.

## Step 1: table files (25–26 November)

Each member writes their own table files, in this order (tables point to each other):

| File                             | Member | Tables                                                                                     |
| -------------------------------- | ------ | ------------------------------------------------------------------------------------------ |
| `000_schemas.sql`                | shared | creates the `core` and `staging` schemas (already done)                                    |
| `001_t1_people.sql`              | Eyup   | person, person_email, institution                                                          |
| `002_t2_conference.sql`          | Kadir  | conference, conference_policy, conference_member, track, track_deadline, declared_conflict |
| `003_t1_submission.sql`          | Eyup   | submission, submission_version, authorship                                                 |
| `004_t3_topics_publications.sql` | Sidney | topic, reviewer_topic, submission_topic, publication, publication_author, criterion        |
| `005_t2_assignment.sql`          | Kadir  | review_assignment                                                                          |
| `006_t3_review.sql`              | Sidney | review, review_score                                                                       |
| `007_t4_decision_audit.sql`      | Selim  | status_transition, decision, notification, audit_log                                       |

A table file contains only `CREATE TABLE` with primary keys, foreign keys,
`NOT NULL`, `UNIQUE`, `DEFAULT` and simple `CHECK`s. Column names are the ones in
Report 4.1, in snake_case (`PersonEmail` → `core.person_email`).

It is merged only when the schema test passes:

```
python manage.py reset
python manage.py test test_schema.py
```

Template:

```sql
-- 001 (T1, Eyup): people, their emails, institutions -- Report 4.1
CREATE TABLE core.person (
    person_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name  text NOT NULL,
    orcid      char(19) UNIQUE,
    ...
);
```

## Step 2: business rules (from 27 November)

One rule = one new file, named with the date, time and task:

```
20261127_1430_t1_share_total.sql
20261128_0900_t2_conflict_trigger.sql
```

These names sort after `007_…`, so rules are always applied after the tables.
