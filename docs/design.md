mkdir -p docs
cat > docs/design.md <<'EOF'
# Design: AI Image Understanding and Content Matching Engine

## Problem
I am building a system that looks at a library of images, understands what is in each one, and matches each blog post to the right image by meaning. For example, a post about red foxes should get a red fox photo, and never a wolf. If no image is good enough, the system should say "no confident match" instead of guessing. The most important thing is avoiding a wrong match.

## Image tags
A vision model (Gemini) looks at each image and returns JSON with these fields:
- subject: the main thing in the picture, like "red fox"
- category: one of a fixed list, like animal, vehicle or food
- attributes: a short list of visual details
- caption: one sentence describing the image
- confidence: a number from 0 to 1

I check every answer against a schema before I save it. If the answer is invalid, I never trust it. I retry, and if it keeps failing I mark the image as failed. If confidence is low (for example a blurry photo), I flag the image instead of guessing.

## Data model
I use Postgres with these tables:
- images: the file, its status, subject, category, caption and confidence
- tags: one row per tag for each image
- image_vectors: the embeddings of each image's text
- posts: the blog posts and what each one is about
- post_vectors: the embeddings of each post
- suggestions: which image was suggested for which post, with its rank, score and reasons
- reviews: whether a person approved or rejected a suggestion
- jobs and job_items: the queue for the background work, with attempts and retries
- ai_calls: a cost log with one row for every AI call

## Matching strategy
1. Turn each image caption and each post into an embedding, which is a list of numbers that captures meaning.
2. For a post, rank all images by cosine similarity, which shows how close two embeddings are.
3. Send each candidate through the mismatch guard. The first candidate that passes becomes the suggestion.

## Mismatch guard
The guard checks each candidate in this order and rejects it with a reason if it fails:
1. The image has a valid tag and its confidence is high enough.
2. The category matches (an animal image for an animal post).
3. The similarity score is above a minimum threshold.
4. The subject matches. A wolf image on a fox post is rejected with "category mismatch: expected red fox, detected gray wolf".

If no candidate passes, the system answers "no confident match" and explains why. I will choose the thresholds using my own labeled eval set, not by guessing.

## API endpoints
- POST /jobs/process: start the background job that tags images and embeds posts
- GET /jobs/{id}: see the job progress
- GET /posts/{id}/images: get ranked image suggestions for a post
- POST /posts/{id}/images/{image_id}/check: test whether one specific image would be accepted
- POST /suggestions/{id}/review: approve or reject a suggestion
- GET /suggestions/{id}: see why an image was selected or refused
- GET /costs: see the cost of every AI call

Bad input returns a clean 400 error, never a 500.

## Layers
I keep the code in three layers: the API routes (HTTP), the logic (pipeline, matching and the guard), and the database code (SQL). The guard is a small separate module that does not touch the database or the internet, so it is easy to test. The AI calls are behind one interface, so I can switch between Gemini and a local model.

## One non-goal
I am not building an image search engine or a frontend. Review happens through API endpoints and a table.
EOF
cat docs/design.md | head -8
