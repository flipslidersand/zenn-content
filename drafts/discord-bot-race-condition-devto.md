# Tracking Down a Race Condition in a Distributed Discord Bot

## TL;DR

Running the bot in two places simultaneously (Docker on a home server + local `main.py` for testing) caused a race: both instances tried to create a Thread on the same message, the slower one got a `400 error code 160004`, and the logs filled with WARNING noise. The fix was one conditional — downgrade 160004 from WARNING to INFO.

---

## Symptom

The `error_handler` cog creates Discord Threads on messages in `#errors` to keep issues organized. One day, WARNING logs started appearing periodically:

```
WARNING: failed to create thread: 400 Bad Request (error code: 160004): Cannot create a thread without a message
```

The confusing part: Threads *were* being created. Users saw no issues. Only the logs were noisy.

---

## Initial Hypothesis vs. Reality

My first instinct was an internal race — maybe `thread_handler` and `error_handler` both trying to call `create_thread`. Reading the code carefully:

- `thread_handler.on_thread_create` *observes* the `THREAD_CREATE` gateway event — it does **not** create threads
- `create_thread` is called in exactly one place: `error_handler`

The actual race was **between Bot instances**:

| Instance | Location |
|---|---|
| Production Bot | Docker container on MINIPC |
| Test Bot | Local `main.py` |

Both watching the same `#errors` channel. On the same message, both call `create_thread`. The first wins; the second gets 160004.

Pre-checking `message.thread` doesn't help here — it reads from the local cache, which may not yet reflect the Thread created by the other instance.

---

## The Fix

```python
# Before — every HTTPException logged as WARNING
except discord.HTTPException as exc:
    logger.warning("failed to create thread: %s", exc)

# After — differentiate between benign and real failures
except discord.HTTPException as exc:
    if exc.code == 160004:
        # Benign race: another instance already created the thread.
        # Pre-checking message.thread is cache-dependent and cannot prevent this.
        logger.info(
            "thread already exists for message %d (created by another instance)",
            message.id,
        )
    else:
        logger.warning("failed to create thread: %s", exc)
```

Error code 160004 means the Thread already exists — the goal is achieved. INFO is the right level. All other errors remain WARNING.

---

## Tests Added

```python
@pytest.mark.asyncio
async def test_error_handler_treats_duplicate_thread_as_benign(caplog):
    """160004 → no WARNING, INFO logged"""
    message.create_thread = AsyncMock(
        side_effect=discord.HTTPException(
            MagicMock(status=400), {"code": 160004, "message": "..."}
        )
    )
    with caplog.at_level(logging.INFO):
        await handler.on_message(message)

    assert not any(r.levelno == logging.WARNING for r in caplog.records)
    assert any("another instance" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_error_handler_warns_on_other_http_errors(caplog):
    """non-160004 → WARNING still fires"""
    message.create_thread = AsyncMock(
        side_effect=discord.HTTPException(
            MagicMock(status=403), {"code": 50001, "message": "Missing Access"}
        )
    )
    with caplog.at_level(logging.INFO):
        await handler.on_message(message)

    assert any(
        r.levelno == logging.WARNING and "failed to create thread" in r.getMessage()
        for r in caplog.records
    )
```

61 tests pass after the change.

---

## Takeaways

**1. WARNING ≠ failure**
A WARNING that fires when the outcome is actually correct is lying to you. When an error code signals "already done," use INFO.

**2. Multi-instance on shared resources means races**
Any "check-then-act" pattern (`if not message.thread: create_thread()`) is a TOCTOU race in distributed or async contexts. Cache staleness makes it worse.

**3. Sometimes the minimal fix is the right fix**
The root cause is "two instances watching the same channel" — a valid operational concern. But fixing that would require coordination logic or deployment policy changes. Downgrading one error code is smaller, safer, and correct.

---

*Code: [flipslidersand/dev-nodee-infrastructure](https://github.com/flipslidersand/dev-nodee-infrastructure) — `scripts/discord-bot/cogs/error_handler.py`*
