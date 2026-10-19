# AI Use Disclosure

## Xuanhua Li

I used ChatGPT as a supporting tool during the integration and testing stages of this project. It helped me review error messages, clarify implementation ideas, and improve the wording and organization of parts of the report. I also used it to suggest possible test cases for the student-facing workflow and AI assistant.

One incorrect suggestion was to pass `city="any"` when searching for events without a city preference. The search tool treated `"any"` as an actual city name, so the query returned no matching events. I identified the issue by reviewing the tool-call arguments and testing the function directly. I fixed it by omitting the optional city argument when no specific city was requested and by normalizing placeholder values such as `"any"` and `"no preference"`.

All AI-generated suggestions were reviewed and tested before being included. The final implementation decisions, integration work, testing, and verification were completed by the project team.
