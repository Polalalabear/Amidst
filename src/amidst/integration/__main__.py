"""Inspect contracts or run a loopback-only mock JSON API."""

import argparse
from pathlib import Path
from wsgiref.simple_server import make_server

from amidst.integration.api import IntegrationApplication, api_contract
from amidst.integration.contracts import RecordQuery
from amidst.integration.wiring import build_mock_service, build_replay_service


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path)
    source.add_argument("--benchmark-output", type=Path)
    parser.add_argument("--contract", action="store_true", help="print versioned JSON schemas")
    parser.add_argument("--serve", action="store_true", help="serve mock API on 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.contract:
        print(api_contract().model_dump_json(indent=2))
        return
    service = (build_mock_service(args.config) if args.config is not None
               else build_replay_service(args.benchmark_output))
    if args.serve:
        with make_server("127.0.0.1", args.port, IntegrationApplication(service)) as server:
            print(f"MOCK_INTEGRATION_ONLY: http://127.0.0.1:{server.server_port}", flush=True)
            server.serve_forever()
    else:
        snapshot = service.repository.snapshot()
        times = [time for item in snapshot.observations
                 for time in (item.observation.start_time, item.observation.end_time)]
        query = RecordQuery(time_range=(min(times, default=0), max(times, default=0)))
        print(service.events(query).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
