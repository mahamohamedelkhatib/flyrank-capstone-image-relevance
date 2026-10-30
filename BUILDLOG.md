# Build log

How I used AI on this capstone, written honestly. I built it over several days (28 to 30 October 2026) with Claude as a step-by-step guide. I wanted to understand every part, so I ran each command myself, read each output, and asked questions when something looked wrong. Claude wrote almost all of the code. I did not write it from scratch.

## Where AI helped

- **Design.** Claude drafted the design document (`docs/design.md`): the tag schema, the guard rules, the database tables and the endpoints.
- **Code.** Claude wrote the modules in `app/` and the SQL migrations, one step at a time, as pastes that I ran and checked.
- **Tests and Docker.** Claude wrote the tests, the Dockerfile and the compose file.
- **Evaluation.** Claude wrote the 13 evaluation posts and the evaluation script. I ran them and read the results.
- **Documents.** Claude drafted the README and the small helper that captured real command output into `EVIDENCE.md`.
- **Inside the product.** The system itself calls Gemini for image tags, post tags, the subject judge and embeddings.

## Where AI was wrong, and what we changed

1. **Model names.** The first model (`gemini-2.5-flash`) returned 404 for my new account, and `gemini-3.8-flash` was overloaded. I switched to `gemini-3.1-flash-lite` in `.env`. Model names are now settings, not code.
2. **Confidence on blurry photos.** Gemini gave a blurry photo a confidence of 0.95, so trusting its own number was wrong. The first fix was a prompt that defines confidence as how clear the main subject is. One blurry photo still scored 0.8, so I added a rule that flags images whose tags say blur. That rule then wrongly flagged a sharp fox photo with a "blurry green background", so tags about the background are now ignored.
3. **Duplicate code.** I ran one patch step twice, which created duplicate functions and imports. Claude wrote a script that removed the duplicates, and I re-ran the tests.
4. **Lost error text.** One image failed with a TypeError, but its error text was erased when the retry succeeded. Every call is now logged with its error in the `ai_calls` table.
5. **Validation errors.** FastAPI answers bad input with 422 by default, and some messages had empty field names. I added handlers that return 400, 404, 409 and 402 with clear messages.
6. **Tests in Docker.** The first clean clone showed that the tests failed inside Docker (the `app` module was not on the path). Fixed in `pytest.ini`.
7. **Problems found while writing `EVIDENCE.md`.** A post with no suitable image returned "no confident match" but no reasons, so Probe 4 was only half met. I fixed `find_match` so the closest candidates come with a reason. The `/costs` route also had SQL inside it, so I moved it into the repository and service. Some of Claude's first evidence sentences were wrong (a grep that pointed at the wrong file, a test filter that matched nothing because the Docker image was old, a search that matched its own label). I corrected each one before committing.

## What I did myself

- Ran every step in my own terminal, read the output, and pushed to GitHub as I went.
- Chose to build it step by step with pastes, so I could learn the system.
- Did my own research while learning, so the project was not only Claude's steps. I read up on the Gemini API documentation, the Pexels license, Docker and Postgres, because I wanted to understand these parts myself.
- Questioned outputs that looked wrong (for example, an ERROR line in a batch that later succeeded).
- Ran a clean-room test from a fresh clone with an empty database, which is how bug 6 was found.

## What I would not trust without checking

- Gemini's confidence number, and the wording of the subject judge, which can change between runs.
- The 1.00 precision: the threshold was tuned on 12 of the 13 posts, so it is optimistic.
- The cost numbers, which are estimates.
- There is no alert when an image fails. Failures are saved and logged, but nobody is notified.
