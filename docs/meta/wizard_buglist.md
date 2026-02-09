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


## Work Section

### Local Search

1. OpenOpus search works fine for composers in the DB, but not for those found in Wikidata. Can we pick the id once we find the composer so that works as well?


### Lazy Builder

1. Should "Genre" be a dropdown with "Other" option? Or, again, to have some autocomplete based on a common genre list?

2. "Key" could be further divided into Note/Accidental? It would allow for rare keys (D flat major) without having a huge dropdown list.

3. "Opus number" (now "Opus/BWV/KV") should be renamed to "Catalog number". In that case you should type the catalog (ex: "BWV") and then the number. Maybe: a regex to ensure you type some number? Also: if known composer, we could pre-populate the catalog field with the most common catalog for that composer? (ex: if I select Bach, it should default to BWV).

4. Once shown, if I un-type in local search above, the lazy builder form shouldn't disappear. Maybe, as it is now functioning as a "show the title you're typing", it should be non-editable when you start typing on the "lazy builder".


## Scope section

1. (FUTURE) The ideal situation is that, if work is verified, movement information is automatically fetched from OpenOpus & displayed somehow for selection. In this case, also, if no movement applies (ex: a Nocturne), that option could be disabled.
