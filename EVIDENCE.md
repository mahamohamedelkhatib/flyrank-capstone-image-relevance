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
