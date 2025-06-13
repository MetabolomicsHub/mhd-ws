import asyncio


def run_coroutine(coroutine):
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            result = asyncio.ensure_future(coroutine)
        else:
            result = loop.run_until_complete(coroutine)
    except RuntimeError:
        result = asyncio.run(coroutine)
    return result
