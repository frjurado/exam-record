I'm giving you the list of bugs I found in the wizard here, in order to be more structured about them.


## Composer Section

### Local Search

1. Where's the local search searching? I could only find Bach & Beethoven. As I understood, we should have seeded the database with a list of composers from OpenOpus, then cache this whole list to the client, is that correct? But there's no Mozart there... 
    (Solved)
2. As discussed in the design, I understood that search here would be "smart", meaning: if I start typing "Bethoven" with a typo, it should still find "Beethoven".
    (Comment) We leave it like this for now, that's ok.
3. If I click on "Back to composer", the search field should be cleared.
    (Solved)

### Wikidata Search

1. When you click on "Search Global Database", it generates a list of options from Wikidata. But, if I don't choose & start typing again on the composer field, the list remains unupdated until I click on "Search Global Database" again, which is confusing.
    (Solved)
2. If Wikidata returns no results, the UI should display a message like "No results found" instead of giving no feedback.
    (Solved)
3. The crucial one: is there a way to filter Wikidata results to only show composers? The list is sometimes huge & filled with non-composer results, as well as with the same name multiple times.
    (Solved) This works like magic now, and the comment-like description ("Austrian composer ...") is also a plus.
4. A new issue here seems that (a) some very common names don't appear ("Schumann"), and (b) sometimes a very obvious search finds unexpected results ("Mozart" returns both the actual composer & some "Camargo Guarnieri" from Brazil...)
    (Solved)

### Unverified Composer

1. The text shown on the link is always 'Add "" (Unverified)': I understand that the intention was to display the name of the composer we're trying to add.
    (Solved)

### Addition to database

1. If I add a new composer, either from Wikidata or unverified, I understand that it should appear in future searches (cause it's in the database now, right?). If this happens on composer selection, it definitely isn't doing so. If it happens on submission, I'm not sure it does either (as I describe elsewhere in this document, I'm only sometimes getting to submit).
    (Issue) I don't think I can really test this, as I can't submit because of the authentication issue below.


## Work Section

### Local Search

1. As with composers, I'm not sure where this search is querying, neither where it should. The docs mention OpenOpus, but I'm pretty sure it's not being used.
    (Solved?) I'm assuming it's checking just the DB for now.
2. At some point, I've had works clearly not filtered by composer. So I could select Beethoven, the it would offer me a Brandenburg Concerto as an option, which is clearly not his work. I've tried to reproduce it but I couldn't. Is it possible that the list is cached somewhere and I'm hitting an old version of it?
    (Solved)
3. If works can be matched by nickname (ex: Moonlight), the result should display the nickname as well (ex: "Piano Sonata No. 14 in C# Minor (Moonlight)"). 
    (Solved)
4. If I un-type the work's name, the work list should disappear. 
    (Solved)

### Lazy Builder

1. The form should include Genre (mandatory), Key, Number and Opus fields, as stated in the design (better order: Genre, Opus, Number, Key).
    (Solved)
2. If I restart the process, the fields should be cleared.
    (Solved)
3. The docs state: "As the user fills these fields, the system runs a **Live Search** in the background". That's obviously not happening. One question arises: where does that search happen? If OpenOpus was already used, it doesn't make much sense here. Maybe it should be DB first, then OpenOpus? 
    (Issue) This isn't happening yet.

## Scope section

1. Again, the ideal situation is that, if work is verified, movement information is automatically fetched from OpenOpus & displayed somehow for selection. In this case, also, if no movement applies (ex: a Nocturne), that option could be disabled.
    (New)

## Submission

1. I'm not allowed to submit. I'm told Error: Not authenticated. 
    (Issue) This problem is still here. Obviously, I haven't authenticated (that's not set up yet, as far as I know), so maybe it shouldn't require authentication yet?
2. The message "Error: not authenticated" isn't cleared if I go back to work/composer.
    (New)
