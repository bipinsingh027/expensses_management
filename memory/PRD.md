# Site Expense Manager — Product Record

## Original problem statement
Build a responsive web application for a 3–10 employee construction/business company to replace manual Excel processing of monthly UPI/bank statements. Version 1 uses manual CSV/XLSX uploads only; it must support secure roles, transaction classification, duplicate flagging, dashboards, reporting, documents, and mobile use.

## Architecture decisions
- React frontend with React Router, Axios, Recharts, and a responsive CSS system.
- FastAPI backend with MongoDB through the existing `MONGO_URL` and `DB_NAME` environment values.
- JWT email/password authentication in an httpOnly cookie, with admin and employee roles.
- Statement uploads are preserved under the backend uploads directory; CSV/XLSX parsing uses pandas.
- Transactions use string UUIDs in application responses to avoid BSON serialization issues.

## User personas
- Admin: manages the company structure, imports statements, reviews classifications, and monitors spend.
- Employee: signs in, uploads their own statement, and can view the records attached to their uploads.

## Core requirements (static)
Authentication, employees, sites, categories, statement uploads, transaction import, description-based classification, duplicate detection, manual review, dashboard, reports/exports, documents, month closing, authorization, and mobile-friendly use.

## What's been implemented
- 2026-08-17: JWT login/logout/me, seeded admin and employee accounts, protected API routes.
- 2026-08-17: Sample sites, categories, transactions, dashboard totals, site chart, category breakdown, and recent activity.
- 2026-08-17: CSV/XLSX statement import with original preservation, column detection, totals, classification status, and duplicate flags.
- 2026-08-17: Responsive dashboard shell, transaction search, upload form, sites/categories view, mobile navigation, and accessible test IDs.

## Prioritized backlog
- P0: Add manual transaction classification controls and editable keyword rules.
- P1: Add receipt/document upload and authenticated document preview.
- P1: Add monthly/site/employee/category reports with Excel and PDF export.
- P1: Add month closing and immutable closed-month protections.
- P2: Add richer filters, employee management UI, and statement column-mapping presets.

## Next tasks
1. Build transaction detail drawer with site/category correction.
2. Add classification rule management and review queue actions.
3. Add report pages and export endpoints.
4. Add private transaction documents and month closing.