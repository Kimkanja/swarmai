# Reference materials

These are the original files you supplied (Supabase schema, edge function,
and MQL license includes from your existing setup). They were used to
understand the license-validation contract your EA already expects and are
kept here for reference only — they are not imported or executed by this
Flask application. The new `/api/license/validate` endpoint in this project
follows the same key → account → validation-result shape as
`validate-license.ts`, adapted to Flask/SQLAlchemy.
