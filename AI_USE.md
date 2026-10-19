# AI Use Disclosure

## Xuanhua Li

I used ChatGPT as a supporting tool during the integration and testing stages of this project. It helped me review error messages, clarify implementation ideas, and improve the wording and organization of parts of the report. I also used it to suggest possible test cases for the student-facing workflow and AI assistant.

One incorrect suggestion was to pass `city="any"` when searching for events without a city preference. The search tool treated `"any"` as an actual city name, so the query returned no matching events. I identified the issue by reviewing the tool-call arguments and testing the function directly. I fixed it by omitting the optional city argument when no specific city was requested and by normalizing placeholder values such as `"any"` and `"no preference"`.

All AI-generated suggestions were reviewed and tested before being included. The final implementation decisions, integration work, testing, and verification were completed by the project team.

## Trapti Kulshrestha

I used ChatGPT and Claude in the project mainly to help me understand implementation details, debug errors, review integration issues & organize my work. I also used them to explain unfamiliar backend and frontend code, suggest test cases, review FastAPI and React behavior.

One incorrect suggestion was related to the company-side AI Assistant. During development, AI-generated guidance sometimes treated the recruiter-side Assistant as if it were a required final feature. After reviewing the actual Lab 1 rubric and the required AI tools, I realized that the Assistant requirements were clearly centered on the student workflow, such as student preferences, job and event search, and saving jobs or events. I corrected the report and final integration accordingly so that the Assistant remained on the student side, while the company portal focused on recruiter workflows such as jobs, applicants, events, student search, and company profile management.

I also verified AI-generated code suggestions by running backend tests, frontend lint and production builds, and manual browser testing before accepting any changes. When integration issues appeared, such as missing student names or unclear resume errors on the company side, I used the actual API responses and application behavior to confirm the problem before applying fixes.

All AI suggestions were reviewed, tested and adjusted as needed. The final code, integration decisions, debugging, testing, report updates, and verification were completed by us.