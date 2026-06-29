import threading
import time
import json

import rpyc
from rpyc.utils.server import ThreadedServer

from xqshare.server import LoggingProxy, _init_logging, _to_local_builtin


class StrictXtdata:
    def get_market_data(self, field_list, stock_list, period, **kwargs):
        assert type(field_list) is list
        assert type(stock_list) is list
        assert type(period) is str
        assert all(type(item) is str for item in stock_list)
        assert type(kwargs["start_time"]) is str
        assert type(kwargs["end_time"]) is str
        return {
            "field_list": type(field_list).__name__,
            "stock_list": type(stock_list).__name__,
            "period": type(period).__name__,
        }


class ArgLocalizationService(rpyc.Service):
    def exposed_localize(self, value):
        converted = _to_local_builtin(value)
        return type(converted).__module__, type(converted).__name__, converted

    def exposed_call_proxy(self, field_list, stock_list, period, start_time, end_time):
        proxy = LoggingProxy(StrictXtdata(), "xtdata", lambda: "test-client")
        return proxy.get_market_data(
            field_list=field_list,
            stock_list=stock_list,
            period=period,
            start_time=start_time,
            end_time=end_time,
        )


def _connect_service():
    config = {"allow_all_attrs": True, "allow_pickle": True}
    server = ThreadedServer(
        ArgLocalizationService,
        hostname="127.0.0.1",
        port=0,
        protocol_config=config,
    )
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    time.sleep(0.2)
    conn = rpyc.connect("127.0.0.1", server.port, config=config)
    return server, conn


def test_to_local_builtin_converts_rpyc_list():
    server, conn = _connect_service()
    try:
        module, name, value = conn.root.localize(["000002.SZ"])
        assert module == "builtins"
        assert name == "list"
        assert list(value) == ["000002.SZ"]
    finally:
        conn.close()
        server.close()


def test_logging_proxy_passes_local_builtins_to_target():
    _init_logging("WARNING")
    server, conn = _connect_service()
    try:
        result = conn.root.call_proxy([], ["000002.SZ"], "1d", "20260530", "20260629")
        if isinstance(result, dict) and result.get("__xqshare_serialized__") == "json":
            result = json.loads(result["data"])
        assert result == {
            "field_list": "list",
            "stock_list": "list",
            "period": "str",
        }
    finally:
        conn.close()
        server.close()
