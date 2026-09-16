# courtlistener Data Dictionary

Source: [CourtListener bulk data](https://www.courtlistener.com/help/api/bulk-data/) (Free Law Project), exports of 2024-05-06, 2025-01-31.
Column names and types are CourtListener's own (bulk schema.sql); see its API docs for field meanings.
`v_judge_positions` joins positions to judges and courts.

## judges

One row per person in CourtListener's judge database (federal and state judges, plus some other public figures): names, birth/death, gender, religion, FJC judge id (fjc_id joins fjc-judges.judges.jid)

Rows: 16,190

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 1 |  |
| date_created | TIMESTAMP | 0.0% | 2016-04-20 11:15:47.527089 |  |
| date_modified | TIMESTAMP | 0.0% | 2016-04-25 23:03:21.302131 |  |
| date_completed | TIMESTAMP | 91.7% | 2020-12-23 15:27:18 |  |
| fjc_id | INTEGER | 77.1% | 1 | Federal Judicial Center judge id (the directory's jid, not nid); joins fjc-judges.judges.jid for 3,710 of 3,711 judges |
| slug | VARCHAR | 0.0% | a-andrew-hauk |  |
| name_first | VARCHAR | 0.0% | "Bob" |  |
| name_middle | VARCHAR | 17.7% |   |  |
| name_last | VARCHAR | 0.0% | Aaron |  |
| name_suffix | VARCHAR | 93.9% | 2 |  |
| date_dob | DATE | 54.5% | 1697-09-17 |  |
| date_granularity_dob | VARCHAR | 54.5% | %Y |  |
| date_dod | DATE | 72.5% | 0031-01-01 |  |
| date_granularity_dod | VARCHAR | 72.5% | %Y |  |
| dob_city | VARCHAR | 73.2% | (Belmont), Philadelphia |  |
| dob_state | VARCHAR | 73.9% | AK |  |
| dob_country | VARCHAR | 0.0% | Antigua and Barbuda |  |
| dod_city | VARCHAR | 90.7% | (Belmont), Philadelphia |  |
| dod_state | VARCHAR | 90.8% | AK |  |
| dod_country | VARCHAR | 0.0% | United States |  |
| gender | VARCHAR | 30.7% | f |  |
| religion | VARCHAR | 97.4% | Baptist |  |
| ftm_total_received | DOUBLE | 97.5% | 0.0 |  |
| ftm_eid | VARCHAR | 97.5% | 10238635 |  |
| has_photo | BOOLEAN | 0.0% | false |  |
| is_alias_of_id | INTEGER | 97.6% | 10290 |  |

## positions

One row per position held: judgeships (court_id joins courts), clerkships, offices and other jobs, with nomination, confirmation, start and termination dates, appointer, predecessor and how the seat was obtained

Rows: 51,289

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 1 |  |
| date_created | TIMESTAMP | 0.0% | 2016-04-20 11:15:47.565552 |  |
| date_modified | TIMESTAMP | 0.0% | 2016-04-20 11:15:47.565585 |  |
| position_type | VARCHAR | 41.4% | act-jud |  |
| job_title | VARCHAR | 58.6% | &nbsp-1799 |  |
| sector | INTEGER | 86.8% | 1 |  |
| organization_name | VARCHAR | 74.2% | "Gun Parts" Specialty Court |  |
| location_city | VARCHAR | 79.5% | Abbeville |  |
| location_state | VARCHAR | 75.2% | AK |  |
| date_nominated | DATE | 91.7% | 1789-09-24 |  |
| date_elected | DATE | 96.6% | 1980-11-04 |  |
| date_recess_appointment | DATE | 99.4% | 1789-11-18 |  |
| date_referred_to_judicial_committee | DATE | 92.4% | 1826-05-08 |  |
| date_judicial_committee_action | DATE | 92.2% | 1826-05-22 |  |
| judicial_committee_action | VARCHAR | 100.0% | rep_w_rec |  |
| date_hearing | DATE | 98.3% | 1983-02-23 |  |
| date_confirmation | DATE | 91.8% | 1789-09-25 |  |
| date_start | DATE | 1.7% | 0217-08-11 |  |
| date_granularity_start | VARCHAR | 1.7% | %Y |  |
| date_termination | DATE | 17.2% | 0022-01-01 |  |
| termination_reason | VARCHAR | 80.0% | abolished |  |
| date_granularity_termination | VARCHAR | 17.1% | %Y |  |
| date_retirement | DATE | 96.8% | 1919-10-06 |  |
| nomination_process | VARCHAR | 100.0% | fed_senate |  |
| vote_type | VARCHAR | 91.5% | s |  |
| voice_vote | BOOLEAN | 91.5% | false |  |
| votes_yes | INTEGER | 98.6% | 10 |  |
| votes_no | INTEGER | 98.6% | 0 |  |
| votes_yes_percent | DOUBLE | 100.0% | 100.0 |  |
| votes_no_percent | DOUBLE | 100.0% | 0.0 |  |
| how_selected | VARCHAR | 78.0% | a_gov |  |
| has_inferred_values | BOOLEAN | 0.0% | false |  |
| appointer_id | INTEGER | 83.1% | 1 |  |
| court_id | VARCHAR | 56.8% | akb | CourtListener court code; joins courts.id |
| person_id | INTEGER | 0.0% | 1 | CourtListener person id; joins judges.id |
| predecessor_id | INTEGER | 99.7% | 1003 |  |
| school_id | INTEGER | 99.6% | 1261 | Joins schools.id |
| supervisor_id | INTEGER | 99.7% | 1015 |  |

## educations

One row per degree (school_id joins schools)

Rows: 12,777

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 1 |  |
| date_created | TIMESTAMP | 0.0% | 2016-04-20 11:15:52.780039 |  |
| date_modified | TIMESTAMP | 0.0% | 2016-04-20 11:15:52.780075 |  |
| degree_level | VARCHAR | 2.1% | aa |  |
| degree_detail | VARCHAR | 64.8% | 1959 |  |
| degree_year | INTEGER | 38.1% | 0 |  |
| person_id | INTEGER | 0.2% | 100 | CourtListener person id; joins judges.id |
| school_id | INTEGER | 0.0% | 1 | Joins schools.id |

## schools

Law schools and universities

Rows: 6,011

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 1 |  |
| date_created | TIMESTAMP | 0.0% | 2010-06-07 20:00:00 |  |
| date_modified | TIMESTAMP | 0.0% | 2010-06-07 20:00:00 |  |
| name | VARCHAR | 0.0% | 85721 |  |
| ein | INTEGER | 41.3% | -1 |  |
| is_alias_of_id | INTEGER | 60.4% | 1 |  |

## political_affiliations

One row per recorded party affiliation with its source and dates

Rows: 8,486

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 1 |  |
| date_created | TIMESTAMP | 0.0% | 2016-04-20 11:15:47.555057 |  |
| date_modified | TIMESTAMP | 0.0% | 2016-04-20 11:15:47.555097 |  |
| political_party | VARCHAR | 0.0% | d |  |
| source | VARCHAR | 14.1% | a |  |
| date_start | DATE | 51.5% | 1798-04-11 |  |
| date_granularity_start | VARCHAR | 51.5% | %Y |  |
| date_end | DATE | 99.2% | 1806-02-21 |  |
| date_granularity_end | VARCHAR | 99.2% | %Y |  |
| person_id | INTEGER | 0.0% | 1 | CourtListener person id; joins judges.id |

## judge_races

Person-to-race links (race_id decoded in the race column)

Rows: 6,542

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 1 |  |
| person_id | INTEGER | 0.0% | 1 | CourtListener person id; joins judges.id |
| race_id | INTEGER | 0.0% | 1 | CourtListener race code id; decoded in judge_races.race |
| race | VARCHAR | 0.0% | American Indian or Alaska Native |  |

## courts

Every court CourtListener tracks (federal, state, tribal, special), with jurisdiction, PACER and FJC ids, dates and parent court

Rows: 3,353

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | VARCHAR | 0.0% | acca |  |
| pacer_court_id | INTEGER | 93.9% | 1 |  |
| pacer_has_rss_feed | BOOLEAN | 93.8% | false |  |
| pacer_rss_entry_types | VARCHAR | 94.6% | adr,answer,appeal,appeal-cr,charge-cr,cmp,cvbevent-cr,detention-cr,discov,dis... |  |
| date_last_pacer_contact | TIMESTAMP | 100.0% |  |  |
| fjc_court_id | VARCHAR | 94.0% | 0 |  |
| date_modified | TIMESTAMP | 0.0% | 2013-08-14 12:46:30 |  |
| in_use | BOOLEAN | 0.0% | false |  |
| has_opinion_scraper | BOOLEAN | 0.0% | false |  |
| has_oral_argument_scraper | BOOLEAN | 0.0% | false |  |
| position | DOUBLE | 0.0% | 1.0 |  |
| citation_string | VARCHAR | 39.2% | 10th |  |
| short_name | VARCHAR | 0.0% | Accomack County Circuit Court |  |
| full_name | VARCHAR | 0.0% |  United States Court of Berlin |  |
| url | VARCHAR | 68.7% | http://access.tarrantcounty.com/en/civil-courts/district-courts/141st-distric... |  |
| start_date | DATE | 87.1% | 1200-01-01 |  |
| end_date | DATE | 88.0% | 1688-12-31 |  |
| jurisdiction | VARCHAR | 0.0% | C |  |
| notes | VARCHAR | 55.4% | "One of three Commissions established over the years to alleviate case load o... |  |
| parent_court_id | VARCHAR | 15.9% | ag |  |

## courthouses

Courthouse addresses per court

Rows: 3,352

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 1 |  |
| court_seat | BOOLEAN | 0.0% | false |  |
| building_name | VARCHAR | 100.0% |  |  |
| address1 | VARCHAR | 100.0% |  |  |
| address2 | VARCHAR | 100.0% |  |  |
| city | VARCHAR | 99.9% | Baltimore |  |
| county | VARCHAR | 100.0% |  |  |
| state | VARCHAR | 0.0% | AK |  |
| zip_code | VARCHAR | 100.0% |  |  |
| country_code | VARCHAR | 0.0% | GB |  |
| court_id | VARCHAR | 0.0% | acca | CourtListener court code; joins courts.id |

## originating_court_information

Lower-court information for appellate dockets (judges, dates, docket numbers)

Rows: 38,926

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 1 |  |
| date_created | TIMESTAMP | 0.0% | 2018-06-27 14:36:09.761192 |  |
| date_modified | TIMESTAMP | 0.0% | 2018-06-27 15:34:15.944139 |  |
| docket_number | VARCHAR | 6.8% | 0 |  |
| assigned_to_str | VARCHAR | 45.5% | A. Kathleen Tomlinson |  |
| ordering_judge_str | VARCHAR | 94.2% | Adam B. Abelson U. S. |  |
| court_reporter | VARCHAR | 64.5% | ALMD Court Reporter TBA |  |
| date_disposed | DATE | 92.3% | 1986-09-11 |  |
| date_filed | DATE | 15.2% | 1951-01-25 |  |
| date_judgment | DATE | 47.5% | 1971-08-08 |  |
| date_judgment_eod | DATE | 70.5% | 1985-06-26 |  |
| date_filed_noa | DATE | 22.7% | 1984-07-10 |  |
| date_received_coa | DATE | 47.2% | 1988-03-25 |  |
| assigned_to_id | INTEGER | 58.7% | 1001 |  |
| ordering_judge_id | INTEGER | 96.8% | 10045 |  |

## financial_disclosures

One row per federal judicial financial disclosure report (person_id joins judges): year, report type, amendment flag, page count and the original PDF's storage path

Rows: 32,336

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 100 |  |
| date_created | TIMESTAMP | 0.0% | 2020-12-31 18:38:18.589831 |  |
| date_modified | TIMESTAMP | 0.0% | 2020-12-31 18:39:42.984256 |  |
| year | INTEGER | 0.0% | 1987 |  |
| download_filepath | VARCHAR | 0.0% | https://com-courtlistener-storage.s3-us-west-2.amazonaws.com/financial-disclo... |  |
| filepath | VARCHAR | 0.0% | us/federal/judicial/financial-disclosures/1/george-washington-disclosure.1990... |  |
| thumbnail | VARCHAR | 1.4% | us/federal/judicial/financial-disclosures/1/george-washington-disclosure.1990... |  |
| thumbnail_status | INTEGER | 0.0% | 0 |  |
| page_count | INTEGER | 0.0% | 1 |  |
| sha1 | VARCHAR | 0.0% | 00004c2e3612245602c21535b194cbeead350835 |  |
| report_type | INTEGER | 0.0% | -1 |  |
| is_amended | BOOLEAN | 0.0% | false |  |
| addendum_content_raw | VARCHAR | 41.4% | 
  
              
 
 
 
 (*)  Fidelity combined and merged the funds from Mu... |  |
| addendum_redacted | BOOLEAN | 0.0% | false |  |
| has_been_extracted | BOOLEAN | 0.0% | false |  |
| person_id | INTEGER | 0.0% | 1000 | CourtListener person id; joins judges.id |

## disclosure_agreements

Agreements reported on a disclosure (financial_disclosure_id joins financial_disclosures)

Rows: 10,007

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 100 |  |
| date_created | TIMESTAMP | 0.0% | 2021-01-03 18:24:29.424173 |  |
| date_modified | TIMESTAMP | 0.0% | 2021-01-03 18:24:29.424195 |  |
| date_raw | VARCHAR | 6.6% | "997 |  |
| parties_and_terms | VARCHAR | 0.4% |   |  |
| redacted | BOOLEAN | 0.0% | false |  |
| financial_disclosure_id | INTEGER | 0.0% | 10002 | Joins financial_disclosures.id |

## disclosure_debts

Liabilities reported on a disclosure, with value code

Rows: 18,775

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 100 |  |
| date_created | TIMESTAMP | 0.0% | 2021-01-03 18:46:56.633116 |  |
| date_modified | TIMESTAMP | 0.0% | 2021-01-03 18:46:56.633134 |  |
| creditor_name | VARCHAR | 0.2% | "LAS CRUCES NM (SEE NOTE IN PART VIII) |  |
| description | VARCHAR | 0.4% |   |  |
| value_code | VARCHAR | 8.9% |   |  |
| redacted | BOOLEAN | 0.0% | false |  |
| financial_disclosure_id | INTEGER | 0.0% | 10001 | Joins financial_disclosures.id |

## disclosure_gifts

Gifts reported on a disclosure

Rows: 2,025

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 1004 |  |
| date_created | TIMESTAMP | 0.0% | 2021-01-03 19:43:37.644169 |  |
| date_modified | TIMESTAMP | 0.0% | 2021-01-03 19:43:37.644221 |  |
| source | VARCHAR | 2.9% | & Mrs. David Spurr |  |
| description | VARCHAR | 5.0% | "7 Shares Walmart |  |
| value | VARCHAR | 21.6% |   |  |
| redacted | BOOLEAN | 0.0% | false |  |
| financial_disclosure_id | INTEGER | 0.0% | 10015 | Joins financial_disclosures.id |

## disclosure_non_investment_income

Non-investment income (teaching, book royalties ...) reported on a disclosure

Rows: 15,302

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 10 |  |
| date_created | TIMESTAMP | 0.0% | 2021-01-03 18:21:55.443288 |  |
| date_modified | TIMESTAMP | 0.0% | 2021-01-03 18:21:55.443308 |  |
| date_raw | VARCHAR | 4.3% | "1 |  |
| source_type | VARCHAR | 1.9% |   |  |
| income_amount | VARCHAR | 1.3% |  (Teaching Income) |  |
| redacted | BOOLEAN | 0.0% | false |  |
| financial_disclosure_id | INTEGER | 0.0% | 10000 | Joins financial_disclosures.id |

## disclosure_positions

Outside positions reported on a disclosure

Rows: 37,050

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 10001 |  |
| date_created | TIMESTAMP | 0.0% | 2021-01-03 18:20:23.431978 |  |
| date_modified | TIMESTAMP | 0.0% | 2021-01-03 18:20:23.432 |  |
| position | VARCHAR | 0.6% | !' 3o0arc of Trustees |  |
| organization_name | VARCHAR | 2.1% |   |  |
| redacted | BOOLEAN | 0.0% | false |  |
| financial_disclosure_id | INTEGER | 0.0% | 10000 | Joins financial_disclosures.id |

## disclosure_reimbursements

Travel reimbursements reported on a disclosure

Rows: 33,472

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 1 |  |
| date_created | TIMESTAMP | 0.0% | 2021-01-03 18:21:55.439456 |  |
| date_modified | TIMESTAMP | 0.0% | 2021-01-03 18:21:55.439473 |  |
| source | VARCHAR | 3.8% |  EE   |  |
| date_raw | VARCHAR | 24.0% |  6/17-6/21/2019 |  |
| location | VARCHAR | 25.1% |  Boca Raton, FL Fed |  |
| purpose | VARCHAR | 17.7% |  Business Travel |  |
| items_paid_or_provided | VARCHAR | 7.8% |   |  |
| redacted | BOOLEAN | 0.0% | false |  |
| financial_disclosure_id | INTEGER | 0.0% | 1000 | Joins financial_disclosures.id |

## disclosure_spousal_income

Spousal income reported on a disclosure

Rows: 20,174

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 10002 |  |
| date_created | TIMESTAMP | 0.0% | 2021-01-03 18:20:23.436326 |  |
| date_modified | TIMESTAMP | 0.0% | 2021-01-03 18:20:23.436341 |  |
| source_type | VARCHAR | 0.9% |   |  |
| date_raw | VARCHAR | 2.0% | "Aiil.Compuier Sves.A Scisco Svws:-ems |  |
| redacted | BOOLEAN | 0.0% | false |  |
| financial_disclosure_id | INTEGER | 0.0% | 10000 | Joins financial_disclosures.id |

## oral_arguments

Oral-argument audio metadata (case name, docket, court, date, duration); the 2024-05-06 export

Rows: 89,468

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 1 |  |
| date_created | TIMESTAMP | 0.0% | 2014-10-30 21:58:26.541148 |  |
| date_modified | TIMESTAMP | 0.0% | 2015-05-06 23:12:13.363952 |  |
| source | VARCHAR | 0.0% | C |  |
| case_name_short | VARCHAR | 59.2% | $1 |  |
| case_name | VARCHAR | 0.0% | "Richard ""Bud"" Steen v. Robert Murray" |  |
| case_name_full | VARCHAR | 100.0% | Friends of Animals v. Dan Ashe, In his official capacity as Director U.S. Fis... |  |
| judges | VARCHAR | 58.4% | A. Marvin Quattlebaum Jr., Allison J. Rushing, Rossie David Alston Jr. |  |
| sha1 | VARCHAR | 0.0% | 0000a23423bb52207fb0e99cc239f069bd170050 |  |
| download_url | VARCHAR | 0.0% | http://8cc-www.ca8.uscourts.gov/OAaudio/2013/12/123207.MP3 |  |
| local_path_mp3 | VARCHAR | 0.2% | mp3/1969/12/31/billy_test_cl.mp3 |  |
| local_path_original_file | VARCHAR | 0.0% | MP3/2014/05/13/occidental_fire__casualty_co._v._adam_soczynski.MP3 |  |
| filepath_ia | VARCHAR | 1.8% | https://archive.org/download/gov.uscourts.ca1./gov.uscourts.ca1..2015-01-09.mp3 |  |
| ia_upload_failure_count | INTEGER | 98.4% | 1 |  |
| duration | INTEGER | 0.2% | 0 |  |
| processing_complete | BOOLEAN | 0.0% | false |  |
| date_blocked | DATE | 89.5% | 2015-10-11 |  |
| blocked | BOOLEAN | 0.0% | false |  |
| stt_status | INTEGER | 0.0% | 0 |  |
| stt_google_response | VARCHAR | 100.0% |  |  |
| docket_id | INTEGER | 0.0% | 1003286 |  |

## opinion_cluster_panel

Judge-to-opinion-cluster panel links (person_id joins judges; cluster ids refer to CourtListener opinion clusters, not included here)

Rows: 831,965

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 10 |  |
| opinioncluster_id | INTEGER | 0.0% | 10 |  |
| person_id | INTEGER | 0.0% | 100 | CourtListener person id; joins judges.id |

## opinion_joined_by

Judge-to-opinion 'joined by' links (person_id joins judges; opinion ids refer to CourtListener opinions, not included here)

Rows: 1,028

| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| id | INTEGER | 0.0% | 10 |  |
| opinion_id | INTEGER | 0.0% | 3221819 |  |
| person_id | INTEGER | 0.0% | 1352 | CourtListener person id; joins judges.id |

## v_judge_positions


| Column | Type | Nulls | Example | Join |
|--------|------|-------|---------|------|
| person_id | INTEGER | 0.0% | 1 | CourtListener person id; joins judges.id |
| name_first | VARCHAR | 0.0% | A |  |
| name_middle | VARCHAR | 15.6% |   |  |
| name_last | VARCHAR | 0.0% | Aaron |  |
| name_suffix | VARCHAR | 92.1% | 2 |  |
| date_dob | DATE | 33.0% | 1697-09-17 |  |
| gender | VARCHAR | 13.8% | f |  |
| fjc_id | INTEGER | 52.4% | 1 | Federal Judicial Center judge id (the directory's jid, not nid); joins fjc-judges.judges.jid for 3,710 of 3,711 judges |
| position_id | INTEGER | 0.0% | 1 | Joins positions.id |
| position_type | VARCHAR | 41.4% | act-jud |  |
| job_title | VARCHAR | 58.6% | &nbsp-1799 |  |
| court_id | VARCHAR | 56.8% | akb | CourtListener court code; joins courts.id |
| court_name | VARCHAR | 56.8% | Alabama Court of Appeals |  |
| court_jurisdiction | VARCHAR | 56.8% | F |  |
| appointer_id | INTEGER | 83.1% | 1 |  |
| how_selected | VARCHAR | 78.0% | a_gov |  |
| date_nominated | DATE | 91.7% | 1789-09-24 |  |
| date_confirmation | DATE | 91.8% | 1789-09-25 |  |
| date_start | DATE | 1.7% | 0217-08-11 |  |
| date_termination | DATE | 17.2% | 0022-01-01 |  |
| termination_reason | VARCHAR | 80.0% | abolished |  |
