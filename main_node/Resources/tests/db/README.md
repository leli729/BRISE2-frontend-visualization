# Filling Test Database
* Stop the test database if it is running: it publishes the same port as the BRISE database.
* Start a local docker-compose configuration:
`./brise.sh up -m docker-compose` from the root folder.
* Clean the BRISE database (`./brise.sh clean_database`): the dump below holds every experiment in it.
* Run benchmark [`fill_db`](../../../../benchmark/benchmark_runner.py) scenario. It runs every product configuration of [`fill_db/`](fill_db/README.md) with both default configuration handlers and both sampling strategies.
    * The benchmark skips experiments it already has a dump of in `benchmark/results/serialized`; move the old dumps away first.
    * Results of the runs are stored within the main BRISE database.
* Run script [`dump_db.py`](dump_db.py) to create bson-representations of the collections.
* Use [`restore_db()`](../../../tools/restore_db.py) function to populate the test database from bson-dumps.
