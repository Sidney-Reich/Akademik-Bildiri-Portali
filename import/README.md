# DBLP import (T3, Sidney)

`dblp_import.py` will load a subset of the DBLP XML dump into the `staging` schema,
clean it, replace real names, and copy it into `core` (person, publication, publication_author).
Downloaded files go into `import/data/` (ignored by Git).
