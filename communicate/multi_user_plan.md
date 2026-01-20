# Multi-User & Credit System Implementation Plan

## 1. System Architecture Overview

This plan transitions the application from a single-user local tool to a multi-user server application using Supabase for authentication and state management.

### Key Components:
-   **User Management**: Supabase Auth (Email/Password).
-   **Database**: Supabase PostgreSQL (hosting all app data + user credits).
-   **Backend**: FastAPI (Stateless, verifying JWTs).
-   **Task Queue**: Asynchronous background workers for review tasks.

---

## 2. Detailed Implementation Steps

### Phase 1: Database Schema & Supabase Setup
**Objective**: Enable user storage and ownership tracking.

1.  **Supabase Config**:
    -   Use credentials from `.env` (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`).
    -   Configure Supabase Auth.
2.  **User Profile Table**:
    -   Create `public.profiles` table linked to `auth.users`.
    -   Columns: `id` (FK to auth.users), `email`, `credits` (Integer, default 10).
    -   **Trigger**: Create a Postgres trigger to automatically create a `profile` row when a new user signs up via Supabase Auth.
3.  **Resource Ownership Migration**:
    -   Add `owner_id` column to:
        -   `rule_groups`
        -   `rules`
        -   `documents` (uploaded files)
        -   `comparison_documents`
        -   `review_tasks`
        -   `review_results`
    -   **Migration Strategy (Legacy Data)**:
        -   Create a dedicated "Admin" user in Supabase.
        -   Migration Step: `UPDATE tables SET owner_id = 'ADMIN_UUID' WHERE owner_id IS NULL`.
        -   This ensures all pre-existing data is accessible to the Admin.

### Phase 2: Backend Authentication & Authorization
**Objective**: Secure the API and manage credits.

1.  **Auth Middleware**:
    -   Install `supabase` python client.
    -   Create a dependency `get_current_user` that:
        -   Validates the Bearer Token (JWT).
        -   Extracts `user_id`.
        -   Fetches user profile (to check credits).
2.  **Credit Management Logic**:
    -   Endpoint `POST /reviews/start`:
        -   Check if `user.credits > 0`.
        -   Deduct 1 credit in a transaction.
        -   If success -> Access to start task.
        -   If fail -> Return 402 Payment Required.
3.  **Authorization Enforcement**:
    -   Update all CRUD endpoints (`GET`, `PUT`, `DELETE`) to filter by `owner_id`.
    -   Example: `db.query(Document).filter(Document.owner_id == user_id).all()`.

### Phase 3: Async Task Engine
**Objective**: Non-blocking reviews with status tracking.

1.  **Task Model Update**:
    -   Enhance `ReviewTask` model:
        -   `status`: PENDING, PROCESSING, COMPLETED, FAILED.
        -   `start_time`: DateTime.
        -   `end_time`: DateTime.
        -   `progress`: Integer (0-100).
        -   `error`: String.
2.  **Background Processing**:
    -   Use FastAPI `BackgroundTasks` for execution to ensure immediate HTTP response.
    -   **Workflow**:
        1.  User calls `start_review`.
        2.  Backend creates `ReviewTask` (status=PENDING), deducts credit.
        3.  Backend launches async function `process_review(task_id)`.
        4.  Backend returns `task_id` immediately.
    -   **Process_review logic**:
        -   Update status -> PROCESSING. Set `start_time`.
        -   Run LLM analysis.
        -   Update status -> COMPLETED. Set `end_time`.
3.  **Concurrency**:
    -   Since operations are IO-bound (LLM calls), standard AsyncIO allows multiple concurrent tasks per worker.

### Phase 4: Frontend Implementation
**Objective**: User Interface for Auth, Credits, and Tasks.

1.  **Auth Integration**:
    -   Install `@supabase/supabase-js`.
    -   Create `AuthContext` (Login, Signup, Logout, Session).
    -   Protect all routes (redirect to `/login` if no session).
    -   Inject `access_token` into all API calls in `services/api.ts`.
2.  **User Profile Page**:
    -   **Route**: `/profile`
    -   **Features**:
        -   **Display Info**: Show User Email and **Current Credits**.
        -   **Security**: "Change Password" form (uses Supabase `auth.updateUser`).
        -   **Credit History** (Optional for v1): List of tasked performed and credits consumed.
3.  **Task Management UI**:
    -   Create specific `ReviewTaskList` component.
    -   **Columns**: Task Name, Start Time, Duration, Status (Spinner/Check), Actions.
    -   **Real-time Updates**: Implement polling (every 3s) or SSE to refresh the task list status.

---

## 3. Implementation Sequence

1.  **Backend**: Add `owner_id` to models and generate migrations.
2.  **Backend**: Implement Supabase Auth dependency and Credit deduction logic.
3.  **Backend**: Refactor `ReviewService` to be fully async and background-capable.
4.  **Frontend**: Add Login Page + Supabase Client.
5.  **Frontend**: Update API service to send tokens.
6.  **Frontend**: Build the Task List View.
