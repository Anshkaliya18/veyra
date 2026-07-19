# Database Design

## users

  Field           Type
  --------------- -----------
  id              UUID
  name            VARCHAR
  email           VARCHAR
  password_hash   TEXT
  created_at      TIMESTAMP

## documents

  Field            Type
  ---------------- -----------
  id               UUID
  user_id          UUID
  title            TEXT
  category         TEXT
  file_path        TEXT
  extracted_text   TEXT
  upload_date      TIMESTAMP

## skills

id, user_id, skill_name, confidence

## certifications

id, user_id, title, issuer, issue_date

## projects

id, user_id, title, description, technologies

## internships

id, user_id, company, role, duration

## achievements

id, user_id, title, description

## relationships

id, source_id, source_type, relation, target_id, target_type

## search_history

id, user_id, query, searched_at

## Entity Relationships

User ├── Documents ├── Skills ├── Projects ├── Certifications ├──
Internships └── Achievements

Relationships connect every entity together.
