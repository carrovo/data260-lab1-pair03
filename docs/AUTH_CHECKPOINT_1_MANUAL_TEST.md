# Authentication Checkpoint 1 Manual Test Checklist

Run the FastAPI backend on port 9030 and the Vite frontend on port 5173.
Complete these checks in a browser without displaying or logging the full JWT.

## Logged-out behavior

- Open `/jobs` with local storage cleared. Confirm job search still loads and filters jobs.
- Confirm the header shows `Login` and `Sign Up`, and does not show a student name or `Logout`.
- Open `/login`, enter an incorrect password, and confirm the page shows `Incorrect email or password.` without navigating away.

## Signup and session creation

- Open `/signup` and submit a new student. Confirm the browser redirects to `/jobs` and displays a success message with the student's name.
- Confirm the header shows the student's name and `Logout` after the redirect.
- Confirm local storage contains the `student_access_token` key. Do not copy, display, or log its value.
- Try the same email again after logging out. Confirm the duplicate-email message is displayed.
- Submit a password longer than 72 UTF-8 bytes, such as 19 lock emoji. Confirm the backend validation message is displayed.

## Login, restoration, and logout

- Log out, then log in with the new student's credentials. Confirm the loading state, redirect, named success message on `/jobs`, and authenticated header.
- Refresh the browser. Confirm the session is restored through `/auth/me` and the authenticated header remains visible.
- While logged in, open `/login` or `/signup` directly. Confirm the app redirects to `/jobs`.
- Replace `student_access_token` in local storage with an invalid value and refresh. Confirm the token is removed and the logged-out navigation returns.
- Log in again, select `Logout`, and confirm the token, student name, and authenticated session are cleared.
