from backend.cache import NoOpCache, RedisCache, cache_key
from backend.observability import start_event


class FakeRedis:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.writes = []
        self.closed = False

    def get(self, key):
        if self.error:
            raise self.error
        return self.value

    def setex(self, key, ttl, value):
        if self.error:
            raise self.error
        self.writes.append((key, ttl, value))

    def close(self):
        self.closed = True


def test_cache_key_is_stable_and_input_sensitive():
    assert cache_key("tool:v1", {"a": 1, "b": 2}) == cache_key(
        "tool:v1", {"b": 2, "a": 1}
    )
    assert cache_key("tool:v1", {"a": 1}) != cache_key("tool:v1", {"a": 2})


def test_redis_cache_records_hit_and_miss():
    event = start_event()
    cache = RedisCache(FakeRedis(value="cached"))  # type: ignore[arg-type]

    assert cache.get("key", tool="stockfish") == "cached"
    assert event.cache_events == [{"tool": "stockfish", "outcome": "hit"}]

    event = start_event()
    cache = RedisCache(FakeRedis())  # type: ignore[arg-type]
    assert cache.get("key", tool="stockfish") is None
    assert event.cache_events == [{"tool": "stockfish", "outcome": "miss"}]


def test_redis_cache_fails_open():
    event = start_event()
    cache = RedisCache(FakeRedis(error=RuntimeError("down")))  # type: ignore[arg-type]

    assert cache.get("key", tool="lichess") is None
    cache.set("key", "value", tool="lichess", ttl_seconds=60)

    assert event.cache_events == [
        {"tool": "lichess", "outcome": "read_error"},
        {"tool": "lichess", "outcome": "write_error"},
    ]


def test_noop_cache_records_disabled():
    event = start_event()
    assert NoOpCache().get("key", tool="stockfish") is None
    assert event.cache_events == [{"tool": "stockfish", "outcome": "disabled"}]
