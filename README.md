# Yale Museum Keepsake (working title): Final Project

A website for people visiting Yale's museums. While you walk the galleries, you save the art, instruments, fossils and artifacts you like, by tapping ♡ or by **snapping a photo of the wall label**. An AI agent writes a short, true description of each piece using only the museum's own records. Then your favorites become a book you can print and take home.

**Status:** The app runs on the test dataset of 160 objects from 6 museums. The full harvest from Yale's [LUX](https://lux.collections.yale.edu) platform is approved and waiting for LUX to lift a rate-limit block (see "Getting the data").

**Report and slides:** open [`report.html`](report.html) (prints to 13 letter pages) and [`slides.html`](slides.html) (10 slides; arrow keys to move, F for full screen) straight from the folder. Every image is embedded, so each is a single file. To change them, edit `report/report_src.html` or `report/slides_src.html` and run `python3 build.py` in `report/`.

## What's in it

- **Frontend** (`frontend/`, React + Vite + TypeScript). The palette is soft and muted (linen, dusty rose, sage, teal, ochre, plum). Animated art pieces drawn in SVG appear on the pages: a Calder-style mobile, a marble bust in a beret, a dinosaur skeleton, a violin, paintings and a library book.
  - Browse by museum: search, a printable-images filter, and departments. Each museum page opens with an info card: what the museum is, address, admission and **opening hours**, from its own website.
  - An object page for each piece.
  - **My book:** saved objects, reorder, book title and your name.
  - **Print view:** a cover, one page per object and a sources page. Prints as letter pages, or saves as a PDF.
  - **Your own photo:** for a work whose museum image can't be printed, you can use the photo you just scanned, take one, or upload one. It's kept only in your browser (IndexedDB), never sent to the server. It prints marked "Your photo", with a personal-use credit.
- **Backend** (`backend/`, FastAPI):
  - Serves the collection data and images. It refuses any image whose rights don't allow reuse.
  - Runs the description writer.
- **The scanner** (`backend/scanner.py`, three agents). A visitor's photo goes to the **scanner**, which uses four tools: `read_photo` (a **photo-reader** agent with vision that copies the label text), `search_collection`, `write_blurb` (hands off to the description writer) and `add_to_book`. It adds an object only when the label's object number, or both its title and maker, match. Otherwise the visitor chooses from the closest matches.
- **The description writer** (`backend/agent.py`, PydanticAI, OpenAI `gpt-6-luna` through Portkey). One agent with one tool, `get_object_facts`, which reads the museum's record. A checker makes sure every number and name in the text appears in that record. Descriptions are cached, and token use is capped and logged.
- **The data harvester** (`harvest/lux_harvest.py`): pulls museum objects, IIIF images and image rights from LUX.

## Folder structure

```
Final Project/
├── AI_prompts.md              # every prompt, follow-ups and results
├── README.md
├── report.html                # final report (self-contained, images embedded)
├── slides.html                # final slides (reveal.js, self-contained)
├── report/                    # sources for both: report_src.html, slides_src.html, img/, build.py
├── requirements.txt
├── .env.example               # key names only, no values
├── .gitignore
├── backend/
│   ├── main.py                # FastAPI routes: run with `uvicorn main:app --reload --port 8000`
│   ├── catalog.py             # loads the test or full data, search, object details
│   ├── images.py              # image proxy + cache, rights enforced
│   ├── museum_info.json       # each museum's info card (from its own website; sources listed)
│   ├── books.py               # each visitor's book (object IDs) on the server, so add_to_book can add
│   ├── scanner.py             # the scanner + photo-reader agents: photo -> object -> page -> book
│   ├── agent.py               # ┐ the description writer: model, limits, checker, cache, usage log
│   ├── tools.py               # │ all tools: get_object_facts; read_photo, search_collection, write_blurb, add_to_book
│   ├── models.py              # │ data types
│   ├── prompts/               # ┘ blurb.md, scanner.md, photo_reader.md
│   └── tests/                 # test_offline.py + test_scanner.py (scripted model, no key needed),
│                              # run_scan_examples.py + scan_photos/ (real scans for the report)
├── frontend/                  # React + Vite + TypeScript
├── harvest/
│   ├── lux_harvest.py         # LUX harvester: discover, sample, harvest, remap, report
│   └── run_option_a.sh        # the approved full run: wait for LUX, finish samples, harvest option A
├── data/
│   ├── blurb_cache.json       # descriptions already written (reused, no tokens spent)
│   └── lux/
│       ├── units.json         # LUX holding units, departments and counts per museum
│       ├── agents.json        # cache: LUX person/group URI -> name
│       ├── samples/           # TEST DATASET (committed): 20 records per museum, CSV + JSON
│       └── full/              # FULL DATASET (not committed): built by the harvester
└── output/
    ├── harness.md             # how the system works: agent, tools, safety, costs
    ├── usage_log.jsonl        # real token counts for every description request
    ├── sample_book.pdf        # a 7-object book printed from the app
    ├── screenshots/           # full-size app screenshots used in the report and slides
    ├── scan_examples.json     # real scans of the test photos: what was read, each tool step, the outcome
    ├── lux_data_report.md     # LUX: API, counts, coverage, image rights, oddities, harvest options
    ├── lux_report_samples.md  # auto-generated coverage and rights tables for the samples
    └── lux_samples_preview.html
```

## How to run the app

You need Python 3.10+ and Node 20.19+. Run the commands from this `Final Project/` folder unless a step says otherwise.

### 1. Keys

```bash
cp .env.example .env      # then put your PORTKEY_API_KEY in .env (never commit .env)
```

The backend looks for `.env` in this folder first, then in the folder above it. If there's no key, the app still runs, and each page shows the museum's own details instead of an AI description.

### 2. Backend (terminal 1)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

### 3. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

### 4. Use it

Open **http://localhost:5173**.

1. Tap **Scan** and photograph a wall label (or the object), or pick a museum and tap ♡ on anything you like. On a laptop, "Choose a photo" uses a picture file. You can try the labels in `backend/tests/scan_photos/`.
2. Open an object to read its description.
3. Go to **My book**, give the book a title, put the pages in order, and choose **Preview and print my book**.
4. **Print or save as PDF** makes letter-size pages.

### Tests (no key needed)

```bash
cd backend && ../.venv/bin/python -m pytest -q tests
```

## Test data vs. full data

| | Folder | In git? | How to get it |
|---|---|---|---|
| **Test** (default) | `data/lux/samples/` | Yes | Already in the repo |
| **Full** | `data/lux/full/` | No (too large) | Run the harvest (below) |

To switch, set `KEEPSAKE_DATA=data/lux/full` in `.env` and restart the backend. Both folders have the same files and columns.

The app shows the Art Gallery, British Art, the Peabody (including the Babylonian Collection), Musical Instruments, Campus Art and the University Library (including the Lewis Walpole Library). Research collections that aren't public galleries stay in the data but are hidden: the Lens Media Lab, the Elizabethan Club and the Paul Mellon Centre.

## Getting the data from LUX

The harvester needs no API keys. Commands are run from this folder.

```bash
.venv/bin/python harvest/lux_harvest.py discover              # holding units, departments, counts (~2 min)
.venv/bin/python harvest/lux_harvest.py sample --n 20 --resume # 20 records per museum (test data)
.venv/bin/python harvest/lux_harvest.py report data/lux/samples --output output/lux_report_samples.md --html output/lux_samples_preview.html
.venv/bin/python harvest/lux_harvest.py --interval 2 harvest --scope on_view   # full harvest, resumable
.venv/bin/python harvest/lux_harvest.py remap samples          # rebuild outputs from the raw cache, no refetching
```

- `--scope` is `on_view` (what a visitor can see today), `images` or `all`. `--museum yuag ycba` limits the museums, and `--limit 50` is for tests.
- Stop any time with Ctrl-C. Rerunning the same command resumes, from progress saved in `data/lux/full/<museum>/`.
- **The approved run (option A)** is `caffeinate -i harvest/run_option_a.sh`. It waits until LUX answers, checking every 15 minutes, finishes the samples, then harvests everything on view plus Musical Instruments and Campus Art with images, at 1 request every 2 seconds. It logs to `data/lux/full/option_a.log`.
- **How it behaves:**
  - It sends a descriptive User-Agent, at most 1 request per second (2 for the approved run), with backoff on 429, 5xx and network errors.
  - On a CloudFront `403` it pauses 5, 15 and 30 minutes, slowing down each time, then stops cleanly. It never changes its headers to get around a block.
  - It never fills a missing field.
  - `image_usable = yes` only when the image's own rights statement is CC0 or public domain (including *No Copyright – United States*). There is one exception, approved on 2026-10-25. Yale University Library marks its images only with a generic "may be subject to copyright" line, so Library objects made **before 1900** count as public domain under [Yale's Open Access policy](https://guides.library.yale.edu/openaccess). They're labelled "Public domain by date (Yale Open Access policy)" in the data, the app and the book. Explicit copyright claims are never overridden.
  - `relabel data/lux/samples` re-applies these rules to existing files. Add `--fill-from-manifests` to fill a missing date, creator or description from the museum's IIIF image record (IIIF servers only, never LUX).

## Data source

| Museum | Object records | Image + image-rights record (IIIF manifest) | Image files |
|---|---|---|---|
| Art Gallery, British Art, Peabody, Musical Instruments, Campus Art | LUX (`lux.collections.yale.edu`) | `manifests.collections.yale.edu` | `images.collections.yale.edu` |
| University Library, incl. Lewis Walpole | LUX | `collections.library.yale.edu` (Yale Library Digital Collections) | `collections.library.yale.edu` |

Collection data comes from [LUX: Yale Collections Discovery](https://lux.collections.yale.edu), through its public search API. Each museum's info card (`backend/museum_info.json`) is written from that museum's own website, and the source links are kept in the file. Images appear only where the museum marks them public domain or CC0, or for Library objects made before 1900, under Yale's Open Access policy. Each museum's own terms apply. See `output/lux_data_report.md`.
