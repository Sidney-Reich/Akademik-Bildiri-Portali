# Test Results

One row per test. These rows go into the final report.
Result is Pass or Fail; if Fail, note what you fixed and run it again.

| Member  | Test           | Rule  | Case                  | Expected          | Actual                           | Result | Date   |
| ------- | -------------- | ----- | --------------------- | ----------------- | -------------------------------- | ------ | ------ |
| Example | Shares 60 + 30 | BR-03 | Two authors, total 90 | Refused at commit | Refused: "total 90; must be 100" | Pass   | 27 Nov |
| Eyup | No track / unknown track | BR-01 | track_id empty or 999999 | Refused | Refused: NOT NULL; foreign key submission_track_id_fkey | Pass | 28 Nov |
| Eyup | Corresponding author | BR-02 | Not one of the authors | Refused at commit | Refused: fk_t1_corresponding_author | Pass | 28 Nov |
| Eyup | Shares 60 + 30 | BR-03 | Two authors, total 90 | Refused at commit | Refused: "total 90.00; must be 100" | Pass | 28 Nov |
| Eyup | Share 0 | BR-03 | Shares 100 and 0 | Refused | Refused: authorship_contribution_share_check | Pass | 28 Nov |
| Eyup | Shares 60 + 40 | BR-03 | Two authors, total 100 | Accepted | Accepted | Pass | 28 Nov |
| Eyup | Late submission | BR-04 | Deadline passed, then extended | Refused, then accepted | Refused (br04_deadline); accepted after new deadline row | Pass | 28 Nov |
| Eyup | Grace period | BR-04 | 10 min grace, 5 and 15 min late | Accepted / refused | Accepted / refused | Pass | 28 Nov |
| Eyup | Same request x3 | BR-05 | One request key, three times (also at once, via API) | One submission | One submission; API answers 201, 200, 200 | Pass | 28 Nov |
| Eyup | Crash while submitting | BR-06 | Connection killed before commit | Nothing saved | No submission, authors or file | Pass | 28 Nov |
| Eyup | Same PDF twice | BR-07 | Same hash, same conference (also at the same moment) | Refused | Refused: br07_unique_pdf; other conference accepted | Pass | 28 Nov |
| Eyup | Author added late | BR-08 | Insert author after deadline | Refused and recorded | 0 rows changed, warning, audit record (stand-in audit_log until T4's 007) | Pass | 28 Nov |
| Eyup | Renamed .docx | BR-09 | Zip file named paper.pdf | Refused | Refused: "Dosya bir PDF değil." | Pass | 28 Nov |
| Eyup | Too large PDF | BR-09 | Above max_pdf_mb | Refused | Refused: HTTP 413 | Pass | 28 Nov |
| Eyup | PDF metadata | BR-09 | Author name in Info and XMP | Removed | Not found in stored file | Pass | 28 Nov |
| Eyup | Second primary email | BR-10 | Two primary emails | Refused | Refused: idx_t1_one_primary_email | Pass | 28 Nov |
| Eyup | Used email | BR-10 | Email of another person | Refused | Refused: person_email_pkey | Pass | 28 Nov |
| Eyup | Duplicate ORCID | BR-11 | Same ORCID twice | Refused | Refused: person_orcid_key | Pass | 28 Nov |
| Eyup | Late revised version | BR-27 | Revision deadline passed or missing | Refused | Refused: br27_revision_deadline | Pass | 28 Nov |
| Eyup | Change old version | BR-28 | UPDATE / DELETE / TRUNCATE | Refused | Refused: br28_immutable | Pass | 28 Nov |
