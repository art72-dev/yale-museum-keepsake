# LUX samples: 20 records per museum

Generated 2026-10-25 22:56 by `harvest/lux_harvest.py report data/lux/samples`. Counts checked against LUX on 2026-10-24.

## 1. Holding units LUX uses

LUX holds **14,807,311** physical objects (`recordType: HumanMadeObject`). Every object belongs to one of these holding units (LUX's *Responsible Units* facet):

| Holding unit | Physical objects | All record types | Departments / collections |
|---|---:|---:|---|
| Yale University Library | 12,007,256 | 17,406,134 | Offsite Storage (3,844,428); Sterling Memorial Library (2,548,132); Beinecke Library (1,603,878); Manuscripts and Archives (1,001,072); Divinity Library (613,408); Law Library (495,069); Haas Arts Library (477,963); Music Library (463,779); Marx Library (432,345); Cushing/Whitney Medical Library (310,487); Lewis Walpole Library (69,350); Bass Library (68,585); Yale University Library (39,858); Classics Library (20,022); Film Archive (18,332); Oral History of American Music (240); Yale New Haven Hospital Archives (226); Lillian Goldman Law Library (82) |
| Yale Peabody Museum | 2,311,647 | 2,311,647 | Invertebrate Paleontology Collection (571,225); Entomology Collection (451,044); Anthropology Collection (304,788); Botany Collection (215,729); Vertebrate Zoology Collection (Ornithology) (164,737); Invertebrate Zoology Collection (150,641); Paleobotany Collection (98,722); Vertebrate Paleontology Collection (80,116); Vertebrate Zoology Collection (Herpetology) (79,990); Vertebrate Zoology Collection (Ichthyology) (78,515); Mineralogy & Meteoritics Collection (40,521); Babylonian Collection (40,319); Vertebrate Zoology Collection (Mammalogy) (18,989); History of Science & Technology Collection (8,491); Yale Peabody Museum (7,820) |
| Yale University Art Gallery | 223,609 | 223,609 | Numismatics Collection (95,927); Prints and Drawings Collection (36,418); Dura-Europos Collection (20,901); Photography Collection (20,726); Ancient Art Collection (16,822); American Decorative Arts Collection (15,562); Asian Art Collection (8,677); Indo-Pacific Art Collection (4,302); Gerasa Collection (3,443); Yale University Art Gallery (3,309); African Art Collection (2,992); Modern and Contemporary Art Collection (2,622); American Paintings and Sculpture Collection (2,500); Art of the Ancient Americas Collection (2,288); European Art Collection (1,717); Paintings and Sculpture Collection (1) |
| Yale Center for British Art | 134,343 | 135,511 | Prints and Drawings Collection (57,251); Reference Library (39,760); Rare Books and Manuscripts (24,509); Institutional Archives (8,573); Paintings and Sculpture Collection (2,463); Frames Collection (1,787); Modern and Contemporary Art Collection (1) |
| Paul Mellon Centre (UK) | 58,376 | 58,376 | Paul Mellon Centre for Studies in British Art Library (57,057); Paul Mellon Centre for Studies in British Art Archive (1,319) |
| Lens Media Lab | 7,249 | 7,249 | Lens Media Lab Collection (7,249) |
| Yale Morris Steinert Collection of Musical Instruments | 979 | 979 | Morris Steinert Collection of Musical Instruments (979) |
| Elizabethan Club | 452 | 452 | Elizabethan Club Collection (452) |
| Yale Campus Art | 188 | 188 | Campus Art Collection (188) |

## 2. Objects per museum

| Museum | Slug | All objects | With digital image | On view (estimate) | Records in this folder | Mapping |
|---|---|---:|---:|---:|---:|---|
| Yale University Library | `yale_library` | 12,007,256 | 89,196 | 180 | 20 | current |
| Yale Peabody Museum | `peabody` | 2,311,647 | 742,355 | 2,111 | 20 | current |
| Yale University Art Gallery | `yuag` | 223,609 | 195,901 | 4,104 | 20 | first pass* |
| Yale Center for British Art | `ycba` | 134,343 | 48,775 | 589 | 20 | first pass* |
| Paul Mellon Centre (UK) | `paul_mellon_centre` | 58,376 | 0 | 12 | 20 | first pass* |
| Lens Media Lab | `lens_media_lab` | 7,249 | 7,240 | 0 | 20 | first pass* |
| Yale Morris Steinert Collection of Musical Instruments | `musical_instruments` | 979 | 791 | 0 | 20 | first pass* |
| Elizabethan Club | `elizabethan_club` | 452 | 75 | 0 | 20 | first pass* |
| Yale Campus Art | `campus_art` | 188 | 187 | 1 | 20 | first pass* |
| Babylonian Collection, Yale Peabody Museum | `babylonian_collection` | 40,319 | 27,353 | 176 | 20 | first pass* |
| Lewis Walpole Library, Yale University Library | `lewis_walpole_library` | 69,350 | 22,991 | 51 | 20 | current |

\* Fetched with the first version of the field mapping, before resolved creator/collector names, `creator_source`, `other_identifiers` and linked-work lookups for library items were added. Those columns show – below. Rights categories and dates are re-derived for them, so sections 4 and 5 are comparable. `sample --resume` brings them up to date.

## 3. Field coverage (% of records with a value)

| Field | `yale_library` | `peabody` | `yuag` | `ycba` | `paul_mellon_centre` | `lens_media_lab` | `musical_instruments` | `elizabethan_club` | `campus_art` | `babylonian_collection` | `lewis_walpole_library` | All |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| lux_uri | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| accession_number | 100% | 100% | 90% | 100% | 70% | 100% | 100% | 100% | 100% | 100% | 100% | 96% |
| title | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| creators | 20% | 0% | 75% | 100% | 0% | 100% | 100% | 0% | 100% | 0% | 95% | 54% |
| creator_names | 20% | 0% | – | – | – | – | – | – | – | – | 95% | 39% |
| creator_uris | 20% | 0% | 75% | 100% | 0% | 50% | 100% | 0% | 100% | 0% | 0% | 40% |
| collectors | 0% | 20% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 2% |
| date_display | 100% | 15% | 100% | 100% | 0% | 100% | 100% | 0% | 95% | 0% | 100% | 65% |
| date_earliest_year | 95% | 15% | 95% | 100% | 0% | 100% | 85% | 0% | 95% | 0% | 100% | 62% |
| date_latest_year | 95% | 15% | 95% | 100% | 0% | 100% | 85% | 0% | 95% | 0% | 100% | 62% |
| object_type | 100% | 0% | 100% | 100% | 0% | 0% | 100% | 100% | 100% | 0% | 100% | 64% |
| classification | 0% | 100% | 80% | 10% | 0% | 100% | 100% | 0% | 65% | 100% | 0% | 50% |
| medium | 0% | 15% | 90% | 100% | 0% | 0% | 0% | 0% | 95% | 100% | 0% | 36% |
| materials | 0% | 15% | 70% | 75% | 0% | 0% | 0% | 0% | 95% | 100% | 0% | 32% |
| dimensions | 35% | 5% | 90% | 85% | 0% | 0% | 85% | 100% | 100% | 100% | 100% | 64% |
| description | 10% | 0% | 5% | 0% | 0% | 0% | 90% | 0% | 20% | 0% | 0% | 11% |
| credit_line | 0% | 0% | 100% | 100% | 0% | 0% | 80% | 0% | 100% | 0% | 0% | 35% |
| holding_museum | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| department | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| access_statement | 100% | 100% | 100% | 100% | 0% | 0% | 100% | 100% | 100% | 100% | 100% | 82% |
| museum_page_url | 100% | 100% | 95% | 100% | 0% | 0% | 100% | 100% | 0% | 100% | 100% | 72% |
| iiif_manifest_url | 100% | 100% | 100% | 100% | 0% | 100% | 100% | 100% | 100% | 100% | 100% | 91% |
| thumbnail_url | 100% | 100% | 100% | 100% | 0% | 100% | 100% | 100% | 100% | 100% | 100% | 91% |
| image_url | 100% | 100% | 100% | 100% | 0% | 100% | 100% | 100% | 100% | 100% | 100% | 91% |
| alt_text | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
| image_rights_statement | 100% | 100% | 100% | 100% | 0% | 100% | 100% | 100% | 100% | 100% | 85% | 90% |
| lux_url | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |

Empty values across all records: alt_text 220, collectors 216, description 195, materials 149, credit_line 144, medium 140, creator_uris 131, classification 109, creators 102, date_earliest_year 83, date_latest_year 83, dimensions 80, object_type 80, date_display 78, museum_page_url 61, access_statement 40, creator_names 36, image_rights_statement 23, iiif_manifest_url 20, thumbnail_url 20, image_url 20, accession_number 8.

## 4. Image rights

An image is marked **usable** (`image_usable = yes`) only when the rights statement for the image is CC0, public domain, or *No Copyright – United States* (the rightsstatements.org label for works in the US public domain), and the object's own copyright statement doesn't contradict it. Yale University Library objects made before 1900 are also usable under Yale's Open Access policy when the Library's statement is only the generic "may be subject to copyright" line (category *Public domain by date (Yale Open Access policy)*). Everything else is flagged with a reason in `image_flag_reason`.

| Museum | CC0 | Copyright undetermined | In copyright / restricted | Licence covers metadata only | No Copyright - United States | No image | Not assigned | Public domain by date (Yale Open Access policy) | Unclear (may be in copyright) | Usable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `yale_library` | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 8 | 9 | 8/20 |
| `peabody` | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20/20 |
| `yuag` | 0 | 3 | 1 | 0 | 15 | 0 | 1 | 0 | 0 | 15/20 |
| `ycba` | 18 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 18/20 |
| `paul_mellon_centre` | 0 | 0 | 0 | 0 | 0 | 20 | 0 | 0 | 0 | 0/20 |
| `lens_media_lab` | 0 | 0 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0/20 |
| `musical_instruments` | 0 | 0 | 0 | 0 | 13 | 0 | 7 | 0 | 0 | 13/20 |
| `elizabethan_club` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 0/20 |
| `campus_art` | 0 | 0 | 0 | 0 | 5 | 0 | 15 | 0 | 0 | 5/20 |
| `babylonian_collection` | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20/20 |
| `lewis_walpole_library` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 0 | 20/20 |
| **All** | **58** | **5** | **4** | **20** | **33** | **20** | **23** | **28** | **29** | **119/220** |

Exact statements seen (level → text):

- `manifest` × 54: The use of this image may be subject to the copyright law of the United States (Title 17, United States Code) or to site license or other ri
- `manifest` × 40: Open Access; see museum policies at http://hdl.handle.net/10079/8931zqj
- `image` × 33: No Copyright - United States
- `image` × 23: Not Assigned
- `none` × 23: (empty)
- `metadata-only` × 20: Data provided about the Lens Media Lab Collection are public domain. Rights restrictions may apply to collection objects or images of those 
- `image` × 18: No Copyright: You can copy, modify, distribute and perform the work, even for commercial purposes, all without asking permission. (CC0 1.0)
- `image` × 3: Copyright Undetermined
- `image` × 2: Copyright Undetermined: The copyright and related rights status of this Item has been reviewed by the organization that has made the Item av
- `manifest` × 1: Copyright is retained by Henry A. Kissinger for works he has authored and provided during his lifetime to the Yale University Library. After
- `manifest` × 1: Photographs by Robert Giard are used with permission of the copyright holder, Jonathan G. Silin; permission is required to publish Giard pho
- `manifest` × 1: Copyright Beinecke Rare Book & Manuscript Library.
- `image` × 1: In Copyright

Flag reasons: image rights: Unclear (may be in copyright) (29); image rights: Not assigned (23); no IIIF manifest (20); image rights: Licence covers metadata only (20); image rights: Copyright undetermined (5); image rights: In copyright / restricted (4).

## 5. Automatic checks

- Display date says 'Undated' but LUX gives a year range (musical_instruments) × 3
- Display date says 'n.d.' but LUX gives a year range (campus_art)
- Display date says 'n.d.' but LUX gives a year range (yuag)
- Display date says 'undated' but LUX gives a year range (ycba) × 5
- More than 50 images in one manifest, e.g. every page of a book (elizabethan_club) × 8
- More than 50 images in one manifest, e.g. every page of a book (yale_library) × 2
- Object number has no type label in LUX (lens_media_lab) × 20
- Usable on the strength of a manifest-level licence, not an image-level one (babylonian_collection) × 20
- Usable on the strength of a manifest-level licence, not an image-level one (peabody) × 20
- Usable under Yale's Open Access policy, made before 1900 (lewis_walpole_library) × 20
- Usable under Yale's Open Access policy, made before 1900 (yale_library) × 8

