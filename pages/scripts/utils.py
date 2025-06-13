import itertools

from pages.models import EPD

def chunked(iterable, size=1000):
    it = iter(iterable)
    while True:
        chunk = list(itertools.islice(it, size))
        if not chunk:
            return
        yield chunk


def find_missing_uuids(ids_list, chunk_size=1000):
    """
    Generator yielding uuids in `all_ids` that are not in EPD.UUID.
    """
    for chunk in chunked(ids_list, chunk_size):
        # 1) Build a set of this chunk
        chunk_set = set(chunk)
        # 2) Fetch only those that DO exist in the DB
        existing = set(
            EPD.objects
                   .filter(UUID__in=chunk_set)
                   .values_list('UUID', flat=True)
        )
        # 3) Compute the missing ones in C, then yield them
        for uuid in chunk_set - existing:
            yield uuid