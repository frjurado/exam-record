I'm giving you the list of bugs I found in the wizard here, in order to be more structured about them.


## Composer Section

### Local Search

1. (FUTURE) As discussed in the design, I understood that search here would be "smart", meaning: if I start typing "Bethoven" with a typo, it should still find "Beethoven". Not urgent, we'll leave it like this for now.


### Wikidata Search

1. If I type, then "Search Global Database", then delete & type again, either the composer list or "Not found" are displayed ahead of time. It's also weird when you type, click on search, then continue typing and you see a mismatch between the composer list and the composer you're typing. I don't really know what the behavior should be.

2. Is the list shown limited somehow to N items? For example: if I type "Johann", only J.S. Bach appears; if I type "Johann Christian", though, his son emerges!

3. Still some very obvious names ("Palestrina") don't show up in the list.

4. If I type the name of a composer who is on the database: should "Search Global Database" really show me the same exact composer? It seems to lead to DB duplicates.

5. (RETHINK) The Search Global/Use unverified workflow should be more subtle. (Should "Use unverified" be disabled at first? Should "Search global" be disabled if no results found? Etc.)


### Unverified Composer

-

## Work Section

### Local Search

1. (RETHINK) Search seems to be just on local DB. Can it start with more pre-populated works?


### Lazy Builder

1. Some fields should be mandatory (maybe "Genre"?).

2. Should "Genre" be a dropdown with "Other" option? Or, again, to have some autocomplete based on a common genre list?

3. "Key" should be a dropdown + major/minor (+ doesn't apply, for the rare atonal work?)

4. "Opus number" should be just "Catalog number", to include the options of BWV, KV, Hob., etc.

5. The "Number" field should be forced to be an actual number.

6. Better order: (line one) Genre, Title or nickname, (line two) Catalog number, Work number, (line three) Key

7. Once shown, if I un-type in local search above, the lazy builder form shouldn't disappear.

8. (QUESTION) Shouldn't this lazy builder be actively looking for works in OpenOus??
   > **ANSWER:** You are correct.
   > 1. **Verified Composers**: If we have a valid OpenOpus Composer ID (which we do if selected from DB/Wikidata), we **can and should** search OpenOpus.
   > 2. **Current State**: The current code (`wizard.html`) hardcodes `source=local`.
   > **Decision**: We will implement "Real-time OpenOpus Search" in Phase 5.3 or 5.4.
   >    - *Logic*: If `selectedComposer.wikidata_id` exists -> Search OpenOpus. Else -> Search Local.


## Scope section

1. (QUESTION) Again, the ideal situation is that, if work is verified (see item #8 above), movement information is automatically fetched from OpenOpus & displayed somehow for selection. In this case, also, if no movement applies (ex: a Nocturne), that option could be disabled.
   > **ANSWER:** OpenOpus data is often "flat" (just a title string) and lacks structured movement metadata.
   > **Decision:** We will adopt your **Scope UI Proposal**:
   >    - [ ] **Whole Work** OR **Movement** radio buttons.
   >    - [ ] If Movement: **Number** (Selector) + **Name** (Text) + **Excerpt** (Toggle).
   >    - [ ] If Excerpt: **Bars/Details** (Text).
   

## Submission

1. Have to clean up behavior after submission. For example, if I have to send email to get a magic link, if I close the modal I'm back on the form, ready to resubmit???

2. After I click on magic link, I'm redirected to the contribution form (empty) for some seconds, then redirected to the event page. To see the form in a normal state at that point is just weird. (I'd rather see a confirmation message for a sec if that's necessary, then be redirected to the event page.) The situation is similar when I'm logged in, though in this case I see the form with the data I just submitted (just composer, as it's on initial state).
