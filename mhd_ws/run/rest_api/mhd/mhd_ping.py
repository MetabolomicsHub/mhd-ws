from mhd_ws.application.decorators.async_task import async_task


@async_task(app_name="mhd", queue="submission")
def ping_connection(
    data: str = "ping",
    **kwargs,
) -> str:
    if data == "ping":
        return "pong"
    return data
