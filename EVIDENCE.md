# Evidence

One proof per requirement. Every output below was captured by running the command on 30 October 2026 against the Docker stack, and it is pasted without editing.

### 1. Schema validation: invalid model output is never trusted

A made-up answer with an unknown category and confidence 7 is rejected by the Pydantic schema. The last lines show where Gemini's answer is checked against this schema.

```
REJECTED: ('category',) Input should be 'animal', 'vehicle', 'food', 'landscape', 'building' or 'other'
REJECTED: ('confidence',) Input should be less than or equal to 1
app/gemini.py:10:from app.schemas import ImageTags
app/gemini.py:59:    tags = ImageTags(**json.loads(raw))
app/jobs.py:1:from app.schemas import ImageTags
app/jobs.py:24:def save_success(conn, image_id: int, tags: ImageTags, flagged: bool) -> None:
app/schemas.py:8:class ImageTags(BaseModel):
app/worker.py:11:from app.schemas import ImageTags
app/worker.py:18:def should_flag(tags: ImageTags) -> bool:
app/worker.py:55:        tags = ImageTags(**json.loads(raw))
```

### 2. Low-confidence images are flagged, not accepted

Three blurry photos are flagged (by low confidence or by blur in their own tags). The second table counts all 42 images by status.

```
   filename    | status  |   subject    | confidence 
---------------+---------+--------------+------------
 blurry-01.jpg | flagged | bokeh lights |        0.2
 blurry-02.jpg | flagged | bokeh lights |        0.2
 blurry-03.jpg | flagged | person       |       0.85
(3 rows)

 status  | count 
---------+-------
 done    |    39
 flagged |     3
(2 rows)

```

### 3. Batch background job with retries

Images are claimed from a queue with FOR UPDATE SKIP LOCKED, retried with a growing wait (next_try_at) up to a maximum number of attempts, and the job is started in the background (HTTP 202). The table shows the images with the most attempts.

```
   filename    | status  | attempts | last_error 
---------------+---------+----------+------------
 blurry-02.jpg | flagged |        2 | 
 blurry-03.jpg | flagged |        2 | 
 deer-04.jpg   | done    |        2 | 
 wolf-01.jpg   | done    |        2 | 
 bear-01.jpg   | done    |        1 | 
(5 rows)

app/jobs.py:3:MAX_ATTEMPTS = 3
app/jobs.py:14:            WHERE status = 'pending' AND next_try_at <= now()
app/jobs.py:17:            FOR UPDATE SKIP LOCKED
app/jobs.py:45:    if attempts >= MAX_ATTEMPTS:
app/jobs.py:56:                next_try_at = now() + make_interval(secs => %s)
{"job_id":3,"status":"running"}
HTTP 202
```

### 4. Vision and embedding costs are tracked per call, with a budget guard

cost_report shows every logged call, and 'tagged images with no logged call: 0' means every tagged image has a cost entry. by_purpose splits vision, text and embedding. The budget guard test is in proof 4b.

```
calls logged:        204 (200 ok, 4 errors)
input tokens:        65390
output tokens:       6398
estimated cost:      $0.013060
average latency:     3477 ms
tagged images with no logged call: 0
[{'purpose': 'embedding', 'calls': 85, 'input_tokens': 2704, 'output_tokens': 0, 'cost_usd': 0.000411}, {'purpose': 'text', 'calls': 71, 'input_tokens': 9488, 'output_tokens': 2281, 'cost_usd': 0.002911}, {'purpose': 'vision', 'calls': 48, 'input_tokens': 53198, 'output_tokens': 4117, 'cost_usd': 0.009738}]
```

### 4b. Budget guard

When the total spent reaches MAX_BUDGET_USD, no new Gemini call is made and the API returns 402. The test sets a tiny budget and checks that the call is refused.

```
app/costs.py:7:from app.errors import BudgetExceeded
app/costs.py:46:    limit = os.environ.get("MAX_BUDGET_USD")
app/costs.py:51:        raise BudgetExceeded(f"budget of ${limit} is reached (spent ${spent:.4f}), no more AI calls")
app/errors.py:13:class BudgetExceeded(Exception):
app/main.py:7:from app.errors import BadInput, BudgetExceeded, Conflict, NotFound
app/main.py:125:@app.exception_handler(BudgetExceeded)
app/main.py:126:async def handle_budget(request: Request, exc: BudgetExceeded):
tests/test_api.py::test_budget_cap_stops_ai_calls PASSED                 [100%]
================= 1 passed, 17 deselected, 1 warning in 0.19s ==================
```

### 5. Embeddings are stored and posts return ranked image suggestions

The first table counts stored vectors (42 images, one per post). Then a fox post is created and the ranked suggestions come back with a score and the guard's decision for each image.

```
 image_vectors | post_vectors 
---------------+--------------
            42 |            1
(1 row)

POST /posts: HTTP 201
{
 "id": 2,
 "title": "Red fox at the forest edge",
 "tags": {
  "subject": "red fox",
  "category": "animal",
  "confidence": 1.0
 }
}
GET /posts/2/images?top=5: HTTP 200
{
 "post": {
  "id": 2,
  "title": "Red fox at the forest edge",
  "subject": "red fox",
  "category": "animal",
  "confidence": 1.0
 },
 "decision": "match",
 "message": "match found",
 "suggestions": [
  {
   "id": 2,
   "rank": 1,
   "filename": "fox-05.jpg",
   "score": 0.9,
   "decision": "accepted",
   "rule": null,
   "reason": "The image features a red fox, which is the exact subject described in the blog post.",
   "review": null
  }
 ],
 "ranking": [
  {
   "rank": 1,
   "filename": "fox-05.jpg",
   "subject": "red fox",
   "category": "animal",
   "status": "done",
   "score": 0.9
  },
  {
   "rank": 2,
   "filename": "fox-01.jpg",
   "subject": "red fox",
   "category": "animal",
   "status": "done",
   "score": 0.883
  },
  {
   "rank": 3,
   "filename": "fox-03.jpg",
   "subject": "red fox",
   "category": "animal",
   "status": "done",
   "score": 0.871
  },
  {
   "rank": 4,
   "filename": "fox-02.jpg",
   "subject": "red fox",
   "category": "animal",
   "status": "done",
   "score": 0.866
  },
  {
   "rank": 5,
   "filename": "fox-04.jpg",
   "subject": "red fox kit",
   "category": "animal",
   "status": "done",
   "score": 0.863
  }
 ]
}
```

### 5b. Full ranking for the fox post

All 42 images ranked for the red fox post (post 2 from proof 5), with their similarity scores. Fox photos come first, and the wolf and dog photos are below them.

```
HTTP 200 | post subject: red fox
 1  fox-05.jpg       0.9
 2  fox-01.jpg       0.883
 3  fox-03.jpg       0.871
 4  fox-02.jpg       0.866
 5  fox-04.jpg       0.863
 6  fox-06.jpg       0.852
 7  deer-05.jpg      0.825
 8  wolf-02.jpg      0.822
 9  deer-04.jpg      0.822
10  deer-02.jpg      0.82
11  wolf-06.jpg      0.82
12  deer-03.jpg      0.813
13  wolf-03.jpg      0.812
14  dog-01.jpg       0.809
15  wolf-01.jpg      0.808
16  wolf-05.jpg      0.807
17  wolf-04.jpg      0.804
18  bear-02.jpg      0.786
19  dog-02.jpg       0.78
20  dog-05.jpg       0.779
21  bear-05.jpg      0.778
22  bear-03.jpg      0.774
23  bear-04.jpg      0.773
24  bear-01.jpg      0.764
25  deer-01.jpg      0.757
26  dog-04.jpg       0.748
27  mountain-01.jpg  0.744
28  blurry-02.jpg    0.74
29  dog-03.jpg       0.74
30  building-03.jpg  0.729
31  mountain-03.jpg  0.728
32  blurry-01.jpg    0.728
33  mountain-02.jpg  0.726
34  car-02.jpg       0.72
35  building-01.jpg  0.718
36  building-02.jpg  0.718
37  food-01.jpg      0.707
38  car-03.jpg       0.706
39  blurry-03.jpg    0.704
40  food-03.jpg      0.7
41  car-01.jpg       0.699
42  food-02.jpg      0.685
```

### 6. Semantic matching: Vulpes vulpes matches the red fox photos

The post never uses the words 'red' or 'fox', only the scientific name. The post is tagged by Gemini and matched by meaning.

```
POST /posts: HTTP 201 {'subject': 'red fox', 'category': 'animal', 'confidence': 1.0}
decision: match | match found
accepted: fox-01.jpg 0.843 | The image clearly depicts a red fox, which is the exact subject of the blog post.
 1  fox-01.jpg       red fox      0.843
 2  fox-05.jpg       red fox      0.828
 3  fox-02.jpg       red fox      0.823
```

### 7. Mismatch guard: the wolf on a fox post is rejected, with an explanation

The check endpoint forces one image onto the red fox post (post 2) and shows the guard's decision without saving anything. wolf-02.jpg is the highest ranked wolf. car-01.jpg shows a different rule.

```
check wolf-02.jpg on the fox post: HTTP 200
{
 "post_id": 2,
 "image": "wolf-02.jpg",
 "similarity": 0.822,
 "accepted": false,
 "rule": "subject_mismatch",
 "reason": "category mismatch: the post is about 'red fox' but the image shows 'gray wolf'. A red fox and a gray wolf are distinct biological species."
}
check car-01.jpg on the fox post: HTTP 200
{
 "post_id": 2,
 "image": "car-01.jpg",
 "similarity": 0.699,
 "accepted": false,
 "rule": "category_mismatch",
 "reason": "category mismatch: post is about animal (red fox), image shows vehicle (London black cab)"
}
```

### 8. No confident match, with reasons

A post about penguins has no suitable image in the corpus. The answer is no_match, and the three closest images are listed, each with the rule that rejected it and a written reason.

```
POST /posts: HTTP 201 {'subject': 'penguins', 'category': 'animal', 'confidence': 1.0}
GET suggestions: HTTP 200
decision: no_match
message: no confident match: no image passed all the guard rules
  bear-03.jpg  score 0.749  rejected  rule=low_similarity
     reason: similarity 0.75 is below 0.78
  fox-02.jpg   score 0.743  rejected  rule=low_similarity
     reason: similarity 0.74 is below 0.78
  deer-01.jpg  score 0.739  rejected  rule=low_similarity
     reason: similarity 0.74 is below 0.78
```

### 9. Database models with indexes

Five migration files create the tables for images, tags, embeddings (image_vectors, post_vectors), posts, suggestions, reviews (approvals and rejections), ai_calls and jobs, and the indexes on them. A fresh Docker database is created from these files by itself.

```
001_init.sql
002_ai_calls.sql
003_vectors_posts.sql
004_text_purpose.sql
005_review.sql
             List of relations
 Schema |     Name      | Type  |  Owner   
--------+---------------+-------+----------
 public | ai_calls      | table | capstone
 public | image_vectors | table | capstone
 public | images        | table | capstone
 public | jobs          | table | capstone
 public | post_vectors  | table | capstone
 public | posts         | table | capstone
 public | reviews       | table | capstone
 public | suggestions   | table | capstone
 public | tags          | table | capstone
(9 rows)

                              List of relations
 Schema |               Name               | Type  |  Owner   |     Table     
--------+----------------------------------+-------+----------+---------------
 public | ai_calls_pkey                    | index | capstone | ai_calls
 public | idx_ai_calls_created             | index | capstone | ai_calls
 public | idx_ai_calls_image               | index | capstone | ai_calls
 public | idx_images_category              | index | capstone | images
 public | idx_images_queue                 | index | capstone | images
 public | idx_reviews_suggestion           | index | capstone | reviews
 public | idx_suggestions_post             | index | capstone | suggestions
 public | idx_tags_tag                     | index | capstone | tags
 public | image_vectors_pkey               | index | capstone | image_vectors
 public | images_filename_key              | index | capstone | images
 public | images_pkey                      | index | capstone | images
 public | jobs_pkey                        | index | capstone | jobs
 public | post_vectors_pkey                | index | capstone | post_vectors
 public | posts_pkey                       | index | capstone | posts
 public | reviews_pkey                     | index | capstone | reviews
 public | suggestions_pkey                 | index | capstone | suggestions
 public | suggestions_post_id_image_id_key | index | capstone | suggestions
 public | tags_image_id_tag_key            | index | capstone | tags
 public | tags_pkey                        | index | capstone | tags
(19 rows)

```

### 10. API validation and the review workflow

Bad input gets a clean 4xx with a message, never a 500. Then a person rejects the suggestion for the Vulpes vulpes post and approves the one for the fox post, and the inspect endpoint shows the reviews and the reason for the decision.

```
missing field: POST /posts -> HTTP 400 {'error': 'invalid input', 'problems': ['body: Field required']}
unknown post: GET /posts/999999/images -> HTTP 404 {'error': 'post 999999 does not exist'}
post id is not a number: GET /posts/abc/images -> HTTP 400 {'error': 'invalid input', 'problems': ['post_id: Input should be a valid integer, unable to parse string as a
invalid verdict: POST /suggestions/2/review -> HTTP 400 {'error': "verdict must be 'approved' or 'rejected'"}
post 3 subject: red fox | its suggestion id: 3
reject -> 201 {'review_id': 2, 'suggestion_id': 3, 'verdict': 'rejected', 'note': 'demo of the reject path'}
approve -> 201 {'review_id': 3, 'suggestion_id': 2, 'verdict': 'approved', 'note': 'demo of the approve path'}
inspect suggestion 2 -> HTTP 200
{'id': 2, 'post_id': 2, 'rank': 1, 'score': 0.9, 'decision': 'accepted', 'rule': None, 'reason': 'The image features a red fox, which is the exact subject described in the blog post.', 'image': {'id': 32, 'filename': 'fox-05.jpg', 'status': 'done', 'subject': 'red fox', 'category': 'animal', 'caption': 'A red fox stands on a green lawn during a sunny day.', 'confidence': 1.0, 'tags': ['bushy tail', 'daylight', 'pointed ears', 'reddish-orange fur', 'standing on grass']}, 'reviews': [{'id': 3, 'verdict': 'approved', 'note': 'demo of the approve path', 'created_at': '2026-10-30T13:54:58.058475+00:00'}]}
```

### 11. Evaluation: top-1 precision matches the README

The evaluation script is run on the 13 labeled posts. The precision it prints, the value saved in eval/results.json and the table row in the README are the same number.

```
OK  post 13: expected fox       got fox-01.jpg

threshold 0.78: 13/13 correct, top-1 precision 1.00
eval/results.json precision: 1.0
105:| Final, 13 posts, fresh clone and empty database | 0.78 | 13 of 13 | 1.00 |
```

### 12. Layered architecture

Routes (main.py) import only the service layer and the error classes. The service imports the repository. The API's SQL lives only in repository.py (connect count: 0 in main.py and service.py). The batch pipeline modules (worker, jobs, vectors, costs) run their own SQL, as the README says.

```
SQL (connect) in the HTTP and logic layers:
app/main.py:0
app/service.py:0
app/repository.py:19

imports:
app/main.py:6:from app import runner, service
app/main.py:7:from app.errors import BadInput, BudgetExceeded, Conflict, NotFound
app/service.py:3:import app.guard as guard
app/service.py:4:from app import repository
app/service.py:5:from app.embed import cosine
app/service.py:6:from app.engine import find_match
app/service.py:7:from app.errors import BadInput, Conflict, NotFound
app/service.py:8:from app.guard import Verdict, check_basic, subject_mismatch_reason
app/service.py:9:from app.judge import judge_subject
app/service.py:10:from app.matching import rank_vector
app/service.py:11:from app.post_tags import PostTags, tag_post
app/service.py:12:from app.vectors import embed_logged
app/repository.py:1:from app.db import connect
app/repository.py:2:from app.post_tags import PostTags
```

### 13. Idempotency

Running the seed again adds and embeds nothing. Unique constraints stop duplicates: one row per filename, one suggestion per post and image, one tag per image.

```
new images added: 0
images embedded: 0
image statuses: {'done': 39, 'flagged': 3}
 table_name  |             conname              
-------------+----------------------------------
 images      | images_filename_key
 tags        | tags_image_id_tag_key
 suggestions | suggestions_post_id_image_id_key
(3 rows)

```

### 14. Secrets are clean

The only tracked env file is .env.example. No tracked file and no commit in the git history contains a Google API key pattern, .env is in .gitignore, the key is sent in a header and never in a URL, and no error text in the AI call log contains a key.

```
tracked files whose name contains .env:
.env.example

tracked files containing a Google API key pattern (names only, expect none):
(end of list)

commits in all history that added or removed a key pattern (expect 0):
       0

.gitignore rules for .env:
153:.env
154:.envrc
222:.env

how the key is sent (code only):
app/gemini.py:28:    key = os.environ["GEMINI_API_KEY"]
app/gemini.py:42:        headers={"x-goog-api-key": key},
app/embed.py:16:    key = os.environ["GEMINI_API_KEY"]
app/embed.py:25:        headers={"x-goog-api-key": key},

AI call log rows whose error text contains a key (expect 0):
0
```

### 15. Required files are present

README, capstone.yaml, EVIDENCE.md, BUILDLOG.md, .env.example and the MIT LICENSE are in the repository root, together with the Dockerfile and docker-compose.yml that start the system.

```
.env.example
BUILDLOG.md
Dockerfile
EVIDENCE.md
LICENSE
README.md
capstone.yaml
docker-compose.yml

--- capstone.yaml
run: docker compose up -d --build
seed: docker compose run --rm api python -m app.seed
test: docker compose run --rm api pytest -q
base_url: http://127.0.0.1:8000
endpoints:
  - GET /costs
  - POST /posts
  - GET /posts/{post_id}/images
  - POST /posts/{post_id}/images/{image_id}/check
  - GET /suggestions/{suggestion_id}
  - POST /suggestions/{suggestion_id}/review
  - POST /jobs/process
  - GET /jobs/{job_id}

--- .env.example (values hidden here)
GEMINI_API_KEY=...
GEMINI_VISION_MODEL=...
GEMINI_EMBED_MODEL=...
DATABASE_URL=...
PRICE_INPUT_PER_M=...
PRICE_OUTPUT_PER_M=...
PRICE_EMBED_PER_M=...
MAX_BUDGET_USD=...

--- LICENSE first line
MIT License
```
