# Rule34 Recommendation System

A recommendation engine for Rule34 that combines **tag-based filtering** with **CLIP embeddings** to recommend images based on what the user actually likes instead of simply matching tags.

Unlike traditional booru search, this project attempts to recommend images by **visual similarity**, making it possible to discover artists, characters, styles and compositions that use completely different tags.

---

# Why this project exists

Most Rule34 clients recommend images using tags.

Unfortunately, tags have many problems:

* different artists use different tag styles;
* many images are poorly tagged;
* some images have hundreds of unnecessary tags;
* many important visual features are not tagged at all;
* two visually identical images may share only a few tags;
* two images with almost identical tags may look completely different.

Example:

Image A:

```text
1girl
blue_eyes
smile
```

Image B:

```text
solo
female
looking_at_viewer
```

They can depict almost identical characters while sharing almost no tags.

The opposite also happens.

Two images may both contain

```text
2girls
hug
bed
```

while one is anime, another is 3D, another is realistic, another is furry.

Tags simply cannot describe appearance accurately.

---

# Why CLIP

CLIP embeds every image into a vector.

Instead of asking

> "Do these images have the same tags?"

we ask

> "Do these images look similar?"

This allows recommendations such as

* same character with different tags;
* same artist;
* same drawing style;
* same composition;
* similar poses;
* similar facial expressions;
* similar lighting;

without relying entirely on metadata.

---

# Recommendation algorithm

The current pipeline works like this:

```text
All posts
        │
        ▼
Random liked post
        │
        ▼
Fast tag filter
(cheap pre-filter)
        │
        ▼
Top candidates
        │
        ▼
CLIP similarity
        │
        ▼
Penalty for similarity
to disliked posts
        │
        ▼
TOP 20
        │
        ▼
Weighted random choice
```

The first stage is intentionally very cheap.

The expensive CLIP comparison is performed only on a few hundred candidates.

---

# Why tags are still used

Tags are **not** used as the final recommendation signal.

They are only used to reduce the search space.

Instead of comparing CLIP embeddings against tens of thousands of posts, the algorithm first removes obviously unrelated images.

This makes the recommendation much faster.

---

# User learning

The system stores:

* liked posts;
* disliked posts;
* tag statistics;
* viewed posts.

The recommendation score mainly depends on

* CLIP similarity to liked images;
* CLIP similarity to disliked images;
* lightweight tag filtering.

The goal is to gradually move away from tags and rely more on visual similarity.

---

# Requirements

Python **3.11+** is recommended.

Install Git first.

Clone the repository:

```bash
git clone https://github.com/LincolnCox29/rule_34_recommendation_system.git
```

Go inside the project directory:

```bash
cd rule_34_recommendation_system
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Rule34 API

The API requires authentication.

Create a **.env** file in the project root.

Example:

```text
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN

R34_API_KEY=YOUR_RULE34_API_KEY

R34_USER_ID=YOUR_RULE34_USER_ID
```

You must create a Rule34 account and generate an API key.

Without these values the application will not work.

---

# Telegram bot

Create a bot using **BotFather**.

Copy its token into

```text
BOT_TOKEN
```

inside the `.env` file.

---

# Downloading CLIP model

The project uses OpenCLIP.

The first launch downloads the model automatically.

Depending on your Internet connection it may take several minutes.

---

# Running

Run the project:

```bash
python main.py
```

(or whatever your entry file is called).

If everything is configured correctly you should see something similar to

```text
Loading model...
clip device: gpu
Model loaded
Torch: 2.11.0+cu128
CUDA: 12.8
Available: True
GPU: NVIDIA GeForce RTX 2060
```

---

# Troubleshooting

## "Missing authentication"

Your Rule34 API credentials are missing or incorrect.

Check

```text
R34_API_KEY
R34_USER_ID
```

inside `.env`.

---

## "BOT_TOKEN not found"

Make sure

```text
BOT_TOKEN
```

exists inside `.env`.

Restart the application after editing the file.

---

## ModuleNotFoundError

Install dependencies again.

---

## CLIP model downloads every launch

The download probably failed or the cache directory cannot be written.

Delete the incomplete cache and launch again.

---

# Future plans

* Better visual ranking;
* Fine-tuned CLIP model on Rule34 data;
* Multiple recommendation strategies;
* Better diversity;
* Faster nearest-neighbor search;
* Artist/style discovery.

---

# Disclaimer

This project is intended for research and educational purposes.

Please respect the Terms of Service of the services you use.
