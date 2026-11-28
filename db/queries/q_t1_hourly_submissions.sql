-- T1: how many submissions arrived in each hour of the last 24 hours before the
-- deadline, per track. Hour 1 is the last hour before the deadline.
-- (Submissions accepted in the grace period come after the deadline and are not counted.)
WITH current_deadline AS (
    SELECT DISTINCT ON (track_id) track_id, due_at
    FROM core.track_deadline
    WHERE deadline_type = 'SUBMISSION' AND valid_from <= now()
    ORDER BY track_id, valid_from DESC
)
SELECT d.track_id,
       t.name                                AS track,
       h.hour_before_deadline,
       d.due_at - make_interval(hours => h.hour_before_deadline) AS hour_start,
       count(s.submission_id)                AS submissions
FROM current_deadline d
JOIN core.track t ON t.track_id = d.track_id
CROSS JOIN generate_series(1, 24) AS h(hour_before_deadline)
LEFT JOIN core.submission s
       ON s.track_id = d.track_id
      AND s.created_at >  d.due_at - make_interval(hours => h.hour_before_deadline)
      AND s.created_at <= d.due_at - make_interval(hours => h.hour_before_deadline - 1)
GROUP BY d.track_id, t.name, h.hour_before_deadline, d.due_at
ORDER BY d.track_id, h.hour_before_deadline DESC;
