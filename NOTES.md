# Folder Structure
```
- examples/
- src/
   - metview/
      - _cli/ - The terminal command interface is defined here
      - _gui/ - The "metview" Qt code
      - _resources/ - Some simple icons
      - _restapi/ - Some simple queries around The Met's REST API
```


### examples/
For the sake of the test, I added GIF / video demonstrations to this folder.
But normally I would upload this elsewhere and just reference the HTTPS URL
directly in any README or documentation.

Similarly, the `examples/` entry in the `.gitignore` would normally be omitted.
Because the folder wouldn't be there.


### src/metview/_cli/cli.py
In `src/metview/_cli/cli.py`, the CLI was written as subcommands for the sake
of future-proofing but in practice there is only one subcommand.


### src/metview/_resources/
Some free icons that were released under an Apache 2.0 license. See the
`src/metview/_resources/README.md` for details.


### src/metview/_restapi/
Normally I would separate the Qt and non-Qt elements of a repository as separate Python
packages, each with their own limited APIs. For the sake of simplificity for this test,
`_restapi` can be considered a separate Python package.


# Design Decisions
Qt has some design issues that make this process challenging. The main issues are:

1. Qt spams calls to a model's `data()` method, and unfortunately that is usually
   where expensive logic in a GUI has to go.
2. Qt cannot invalidate part of a view which means when the user applies
   a filter that needs to call `data()` on the whole row, it can create unexpected
   spikes in latency as Qt tries to re-query the whole viwe at once even if only part of
   the view was loaded.

The way I got around this is to split the Qt models.

1. `art_model.Model` - This is the real, unabridged data. And on the first
  query, if there are a lot of rows, this model would be very slow.
2. `gui._CropProxy` - A filterer that only shows 80 results
  - This proxy is for the sake of this assessment's requirements. In a production
    scenario this proxy would likely be a model that implements chunked `canFetchMore` +
    `fetchMore` implementations.
3. `_MaskedDataProxy` - Responsible for deferring calls to The MET's REST API
  - Since Qt refreshes `data()` super often, every row initially is loaded with a fake
    placeholder using this model. Once the row actually has data, this model then
    notifies views to update (re-sort / re-filter / etc).
  - By doing this, Qt can refresh all it wants and the low latency code will
    not cause stutters for the user.
4. `_ArtworkSortFilterProxy` - Implements any extra sort and filter logic
  - Sorting requires getting an Artwork's title and that query is 90-150ms. This would
    be very slow. But because the other proxies before it limit the amount of data
    coming through, the remaining data to sort is much easier to handle for Qt.

By progressively adding and limiting the model output we achieve a fast response time
even though the database latency and queries would normally be too high.


# Disclaimer
## Git Commits
Normally I squash all or most of my commits and move the commit messages into
a combined git note. But for the sake of this assessment I thought showing the
commits might be nice to show.


## Searching This Repository
I noted anywhere that is performance related with `# PERF:`, if you'd like to
check those sections out.


# Rejected Ideas
At one point I thought "maybe each time I search, I could serialize the text, hasImage,
classification, etc and use that as a query+result as a cache. That way if users
search for something and want to go back, they don't have to pay for the query the
second time". It's a decent idea but without knowing the upper bounds of the database
results, it could be a bad idea. I added caching to `met_get.search_objects` but
that too might be a bad idea for long-running applications. Other queries like
`met_get.get_all_identifiers` don't have this problem because the LRU cache keys are
less likely to produce "similar queries with huge search results".
