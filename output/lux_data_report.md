# LUX data report: Step 1 (samples, before the full harvest)

_Checked against LUX on 2026-10-24. Detailed tables: `output/lux_report_samples.md`. Script: `harvest/lux_harvest.py`._

## 1. How the LUX API works

| What | How |
|---|---|
| Search | `GET https://lux.collections.yale.edu/api/search/item?q=<JSON>&page=N&pageLength=100`. Returns an `OrderedCollectionPage` of record URIs only (`orderedItems[].id`), with a `next` link. |
| Count | `GET /api/search-estimate/item?q=<JSON>` returns `totalItems`. |
| Paging | `pageLength` is capped at **100**, so asking for 500 or 1,000 still returns 100. Deep paging works: page 2,236 of the Art Gallery returned results in 0.2 s. |
| Full record | `GET https://lux.collections.yale.edu/data/object/<uuid>` returns Linked Art JSON-LD (one request per object). |
| Facets | `GET /api/facets/item?q=<JSON>&name=responsibleUnits` (holding units) or `name=responsibleCollections` (departments). |
| Museum filter | LUX's item search has no "held by" field. The *Responsible Units* facet filters with `{"memberOf":{"curatedBy":{"OR":[{"memberOf":{"id":UNIT}},{"id":UNIT}]}}}`, meaning objects in a collection curated by the unit or one of its departments. A single department is `{"memberOf":{"id":SET}}`. Every query also adds `{"recordType":"HumanMadeObject"}` to keep physical objects only. |
| Images | `{"hasDigitalImage":1}`. Rights and the full-size image are in the object's **IIIF v3 manifest**, which is a second request. |
| On view | LUX has **no on-view field**. The harvester phrase-searches `"on view"` / `"on exhibit"`, excludes `"not on view"` / `"not on exhibit"`, then re-checks each record's access statement. |

### Where each field lives in a record

| Our field | Linked Art path (LUX record unless noted) |
|---|---|
| LUX URI / LUX page | `id` / the same with `/data/` → `/view/` |
| Accession number | `identified_by[type=Identifier]` classified *Accession Number* (Art Gallery, British Art, Musical Instruments, Campus Art), *YPM External Catalog Number* (Peabody), or *Call Number* (Library, Elizabethan Club) |
| Title | `identified_by[type=Name]` classified *Primary Title* (Art Gallery) or *Primary* (British Art), else *Primary Name*, else `_label` |
| Creators + URIs | `produced_by.carried_out_by[]` and `produced_by.part[].carried_out_by[]` (`id`, `_label`). The role comes from `part.classified_as` (Artist, Maker, …). Peabody specimens have no creator. Collectors come from `encountered_by[].carried_out_by[]`. |
| Date | `produced_by.timespan.identified_by[0].content` (display text). Earliest and latest year come from `begin_of_the_begin` and `end_of_the_end`. Specimens use the `encountered_by` timespan instead (`date_kind = collected`). |
| Type / classification | `classified_as[]`. Labels whose own `classified_as` is *Type of Work* or *Type of Object* go to `object_type`, the rest to `classification`. |
| Medium, dimensions, description, credit line, culture, period, on view | `referred_to_by[]` statements, named by their `classified_as` label. Names vary by museum: *Medium* vs *Material Statement*, *Dimensions* vs *Dimension Statement*, *Credit Line* vs *Creditline*, *Access statement* vs *Access Statement*. Structured data is in `made_of[]` and `dimension[]`. |
| Holding museum / department | Holding museum is the unit we queried. Department is `member_of[]._label`. |
| Museum web page, IIIF manifest | `subject_of[].digitally_carried_by[].access_point[].id` |
| Thumbnail | `representation[].digitally_shown_by[].access_point[].id`. Wikidata copies are skipped. |
| Image URL, size | Manifest: `items[0].items[0].items[0].body.id`, plus the IIIF Image service, width and height |
| Image rights | Manifest. See section 4. |
| Alt text | Manifest `metadata` *Alternative Text* (Art Gallery only, and rich) |

## 2. Bulk downloads

| Source | What exists | Use it? |
|---|---|---|
| LUX | No data dump. The [project-lux GitHub](https://github.com/project-lux) has code only, plus `luxport` (exports IIIF manifests and images as ZIPs) and `luxy` (a Python wrapper). | No. The API is the only bulk route. |
| Yale Center for British Art | Live OAI-PMH with LIDO XML at `harvester-bl.britishart.yale.edu/oaicatmuseum/OAIHandler` ([data sharing page](https://britishart.yale.edu/collections-data-sharing)) | Not simpler: it's a different schema, and it still has no image rights per image. |
| Yale Peabody Museum | 10 Darwin Core datasets on GBIF (publisher `2e167bb0-…`) | Natural-history fields only, with no IIIF or rights per image. Not simpler. |
| Yale University Art Gallery | No bulk export found | |

**Decision:** use the LUX API for every museum. It's one schema, one script, and it includes IIIF manifests and per-image rights, which none of the bulk options do.

## 3. Holding units and counts

LUX doesn't list museums. It has **9 holding units**, from its *Responsible Units* facet, with 60 departments between them. The Babylonian Collection belongs to the **Peabody**, the Lewis Walpole Library to the **University Library**, and Dura-Europos and Gerasa to the **Art Gallery**. LUX lists no separate "Babylonian" or "Walpole" unit, so the harvester treats those two as extra museums by department.

| Museum (slug) | Physical objects | With an image | On view* | What it is |
|---|---:|---:|---:|---|
| Yale University Art Gallery (`yuag`) | 223,609 | 195,901 | 4,104 | Art museum. 43% of its objects are coins (Numismatics). |
| Yale Peabody Museum (`peabody`) | 2,311,647 | 742,355 | 2,111 | Natural history and anthropology, mostly specimen drawers |
| Yale Center for British Art (`ycba`) | 134,343 | 48,775 | 589 | Art museum. Also holds a reference library and archives. |
| Yale University Library (`yale_library`) | 12,007,256 | 89,196 | 180 | Books and archives. On-view items are exhibition pieces (Beinecke etc.). |
| Babylonian Collection (`babylonian_collection`) | 40,319 | 27,353 | 176 | Cuneiform tablets and seals (part of the Peabody) |
| Lewis Walpole Library (`lewis_walpole_library`) | 69,350 | 22,991 | 51 | 18th-century British prints and books (part of the Library) |
| Paul Mellon Centre, London (`paul_mellon_centre`) | 58,376 | 0 | 12 | Research library and archive. No images. |
| Lens Media Lab (`lens_media_lab`) | 7,249 | 7,240 | 0 | Photographic-paper samples for conservation research |
| Collection of Musical Instruments (`musical_instruments`) | 979 | 791 | 0 | Instruments. Every sampled record says "Not on view." |
| Elizabethan Club (`elizabethan_club`) | 452 | 75 | 0 | A members' club library (Shakespeare folios) |
| Yale Campus Art (`campus_art`) | 188 | 187 | 1 | Portraits and sculpture around campus |

\*On view is LUX's text match on the access statement (see section 1), checked against the real statement for each record during the harvest.

**Sample:** 20 records per museum, 220 in total, spread across each museum's list of objects with images (Paul Mellon Centre has none, so its 20 come from all objects). Files are in `data/lux/samples/`: one CSV and one JSON per museum, plus `all_museums.*`. Browse them with thumbnails and rights badges in `output/lux_samples_preview.html`.

**Field coverage in the sample** (full table: `output/lux_report_samples.md`):

- **Art Gallery, British Art, Campus Art:** the richest records. Title, date, type, dimensions, credit line and image run 85–100%, makers 75–100%, and medium 90–100%.
- **Musical Instruments:** has no medium field, but 90% have a written description.
- **Peabody and Babylonian:** a title, catalogue number, department and image, but almost never a maker or date. Babylonian tablets give their period in the title ("Ur III", "Neo-Babylonian").
- **Library, Walpole and Elizabethan:** the creator sits on a linked *work* record (section 5).
- **Descriptions:** the museum's own description is rare, 11% overall. Musical Instruments is the exception at 90%. The van Gogh record checked by hand had only a one-line Wikidata summary ("painting by Vincent van Gogh") plus a rich *Alternative Text* in its manifest. Blurbs will have to be written from the other fields.

## 4. Image rights

**119 of the 220 sampled images (54%) are usable**: 91 that the museum marks CC0 or public domain, plus 28 Library objects made before 1900 (see the exception below). The rest are flagged with a reason in `image_flag_reason`.

| Museum | Usable | What the rights statements say |
|---|---:|---|
| Peabody, Babylonian | 40/40 | Manifest licence is **CC0**, with "Open Access; see museum policies" (see section 5) |
| British Art | 18/20 | Image is **CC0** ("No Copyright … (CC0 1.0)"). 2 are *Copyright Undetermined*. |
| Art Gallery | 15/20 | 15 *No Copyright – United States*. Flagged: 3 *Copyright Undetermined*, 1 *In Copyright*, 1 *Not Assigned*. |
| Musical Instruments | 13/20 | 13 *No Copyright – United States*, 7 *Not Assigned* |
| Campus Art | 5/20 | Mostly *Not Assigned* (20th-century portraits) |
| Library, Walpole | 28/40 | Generic "may be subject to the copyright law…", or no statement. The 28 were made before 1900 and are used under Yale's Open Access policy (below). The 12 still flagged date from 1900 onward, are undated, or carry an explicit copyright claim. |
| Elizabethan Club | 0/20 | Same generic Library line. Not shown in the app: it's a members' club, not a public gallery. |
| Lens Media Lab | 0/20 | CC BY 2.0 on the manifest, but its own note says the licence covers the data and "restrictions may apply" to images |
| Paul Mellon Centre | 0/20 | No images |

**Library exception (approved 2026-10-25):**
- Yale University Library never marks images public domain. Its manifests carry a generic "may be subject to the copyright law…" line, and LUX's own "Can I re-use it?" panel shows only "Under Certain Circumstances" for these records.
- Yale's [Open Access policy](https://guides.library.yale.edu/openaccess) says images of public-domain works in Yale's museum, library and archive collections "may be used by anyone for any purpose".
- So **Library objects made before 1900** count as public domain, in category *Public domain by date (Yale Open Access policy)*, with the reason in `image_rights_note`.
- Explicit claims ("Copyright is retained by …") are never overridden.
- In the sample this makes 28 of 40 Library and Lewis Walpole images printable. The dates for 20 first-pass Walpole records came from the Library's IIIF image records ("publish'd … June 1773"), not from LUX.

**What still can't print (checked 2026-10-25):** 41 of the 160 works the app shows. All 41 rights records were re-fetched from Yale's image servers and are unchanged. They are 20th-century works the museums mark "Not Assigned", "Copyright Undetermined" or in copyright: Campus Art portraits from 1935–2006, instruments from 1934 on, an August Sander photograph, a 1927 etching, and Library archives from 1900 on. None was made before 1900. Only the museums can clear them.

**How rights are read:** most specific first. The image's own *Image Use Rights* (canvas metadata) comes first. Then the manifest's *Rights* metadata. The manifest-level `rights` licence counts only if the manifest doesn't say it covers metadata only. One rule needs your OK: *No Copyright – United States* (rightsstatements.org NoC-US) is counted as public domain. That's what it means, but only in the US. The Art Gallery and Musical Instruments use it for nearly all their public-domain works, so treating it as not usable would flag most of the Art Gallery.

## 5. Anything odd

1. **The manifest's CC0 is not the image licence.** Art Gallery, British Art and Lens Media Lab manifests carry CC0 or CC BY at the top. Their own note says it covers the *data*, and that "rights restrictions may apply to … images." The real image rights are on each image. A naive harvester would mark every Art Gallery image CC0.
2. **Peabody's CC0 is only at manifest level.** Peabody and Babylonian manifests say CC0 plus "Open Access; see museum policies." There's no image-level statement. The Peabody's [terms of use](http://peabody.yale.edu/about-us/terms-use) say it keeps all rights unless stated otherwise, asks for a courtesy copy for scholarly redistribution, and wants written permission for commercial use. We mark these usable because the per-item statement says CC0, and the site should still credit "Yale Peabody Museum" with the catalogue number. The report counts these separately.
3. **Library images carry no public-domain statement**, even 1700s prints and 1623 Shakespeare folios. The Library's manifests use one generic "may be subject to copyright" line. Resolved 2026-10-25: Library objects made before 1900 now count as public domain under Yale's Open Access policy (section 4). The Elizabethan Club folios stay hidden, because the club isn't a public gallery.
4. **There's no on-view field**, and `"on view"` also matches "Not on view," so the harvester excludes that phrase and re-checks every record. The Art Gallery's statement includes the floor and gallery ("On view, 2nd floor, European Art"), which is great for visitors. The Peabody says "on exhibit." The Musical Instruments collection marks every sampled object "Not on view."
5. **Labels differ by museum** for the same field. Titles are *Primary Title* (Art Gallery) or *Primary* (British Art), and British Art also tags a print's series as *Primary Name*. Medium is *Medium* or *Material Statement*. Dimensions are *Dimensions* or *Dimension Statement*. Credit is *Credit Line* or *Creditline*. The mapping handles each.
6. **Names aren't always in the object record.** Peabody records label every collector just "Collector," and the real name (e.g. John Bell Hatcher) is only on the person's own record. Art Gallery labels read "Artist: Vincent van Gogh (Dutch, active France, 1853–1890)." The harvester keeps that label as `creators` and looks up each person once, cached in `data/lux/agents.json`, to fill `creator_names` and `collectors`.
7. **Library items keep their creator on a linked work.** For prints and books, the object record has no creator or date. Both live on the linked *visual item* or *text* (`shows` / `carries` → `created_by`). The harvester follows that link only when the object names no creator, and sets `creator_source = linked work`.
8. **Placeholder dates.** Undated objects sometimes carry the year range 0001–0001 ("n.d."). The harvester blanks those years. Other "undated" objects come with a real estimated range (e.g. 1775–1848), and those years are kept.
9. **Archive items have no accession number.** Dura-Europos and Gerasa photos and plans carry only system-assigned numbers (e.g. "DA4973"). These go to `other_identifiers`, and `accession_number` stays empty.
10. **Cultural sensitivity.** The Peabody's Anthropology collection (304,788 objects) may include sacred objects or human remains covered by NAGPRA. We should decide whether the app shows these.
11. **Big manifests.** Library and Elizabethan books carry one image per page, up to 932. The harvester uses the first image (often the cover) and records `image_count`.
12. **Rate limiting.** After roughly 1,000 requests in an hour, nearly all at 1 per second plus a few manual checks, LUX's CloudFront began answering **HTTP 403 to every request from this address**. It was still blocked 75 minutes later. The image and manifest servers were not affected. The harvester now pauses 5, 15 and 30 minutes and slows down on a 403, then stops cleanly. Nine museums' samples are on the first version of the mapping until LUX lets us back in (section 2 of `lux_report_samples.md`).

## 6. Full harvest: options (needs your approval)

Each object costs 2 requests (the record and its IIIF manifest). Library items cost a third, for the linked work, and each new artist or collector costs one name lookup. At 1 request per second that averages about **2.2 s per object**.

| Option | What it covers | Objects | Time at 1 req/s |
|---|---|---:|---:|
| **A (recommended)** | Everything LUX marks **on view** at the Art Gallery, British Art, Peabody, Library (Beinecke etc.), Babylonian and Lewis Walpole. Adds **all objects with images** at Musical Instruments and Campus Art, which have no on-view flags. | ~8,200 | **~5 hours** |
| B | Every object **with an image** at the Art Gallery, British Art, Musical Instruments and Campus Art | ~245,700 | ~6 days |
| C | Every object with an image in every unit | ~1,084,500 | ~4 weeks |
| D | Everything in LUX | ~14.8 million | ~1 year |

**Why A:** a visitor can only save what is in front of them, and that's what's on view. Option A is small enough to refresh every month as galleries rotate. Anything else a visitor wants can be fetched live from LUX when they save it, at 2 requests per object. That's an app decision for a later step.

**Status (2026-10-25):** option A **approved**, to run at 1 request every 2 seconds after the samples are finished. LUX was still answering 403 at 12:38 on Oct 25, about 18 hours after the block began. `harvest/run_option_a.sh` is running. It checks LUX every 15 minutes, starts the moment LUX answers, and logs to `data/lux/full/option_a.log`.

**Rate:** LUX blocked us at about 1 request per second (section 5, item 12). For the full run I suggest **1 request every 2 seconds**, which takes option A to about **10 hours**. It can run overnight, and it resumes if LUX blocks us again.

**Commands for A** (once LUX answers again):

```bash
.venv/bin/python harvest/lux_harvest.py --interval 2 harvest --scope on_view --museum yuag ycba peabody yale_library paul_mellon_centre babylonian_collection lewis_walpole_library
.venv/bin/python harvest/lux_harvest.py --interval 2 harvest --scope images --museum musical_instruments campus_art
```

Lens Media Lab (photographic-paper samples) and the Elizabethan Club (a members' rare-book library) aren't public galleries and have nothing on view, so A leaves them out.
