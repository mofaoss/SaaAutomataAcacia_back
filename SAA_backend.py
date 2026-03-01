import argparse
import logging
from pathlib import Path

from app.backend.runtime_shims import install_runtime_shims


def parse_args():
    parser = argparse.ArgumentParser(description="SAA backend service (stdlib HTTP + stream)")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host")
    parser.add_argument("--port", type=int, default=17800, help="HTTP bind port")
    parser.add_argument("--config", default=str(Path("AppData") / "config.json"), help="config json path")
    return parser.parse_args()


def main():
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (script_dir / config_path).resolve()

    install_runtime_shims(config_path=config_path)

    from app.backend.application import BackendApplication
    from app.backend.command_bus import build_default_registry
    from app.backend.feature_runner import FeatureTaskRunner
    from app.backend.http_server import LogHub, create_server
    from app.backend.task_runner import DailyTaskRunner

    from app.common.logger import logger

    log_hub = LogHub(history_size=800)
    logger.addHandler(log_hub)
    logger.setLevel(logging.DEBUG)

    runner = DailyTaskRunner()
    feature_runner = FeatureTaskRunner()
    command_registry = build_default_registry(daily_runner=runner, feature_runner=feature_runner)
    app_service = BackendApplication(
        daily_runner=runner,
        feature_runner=feature_runner,
        command_registry=command_registry,
        log_hub=log_hub,
    )
    server = create_server(
        args.host,
        args.port,
        app_service=app_service,
    )

    logger.info(f"SAA backend server started at http://{args.host}:{args.port}")
    logger.info("Endpoints: GET /api/health, GET /api/status, GET /api/logs, GET /api/logs/stream, GET /api/commands, POST /api/commands/{name}")
    logger.info("Compatibility: POST /api/open-game, POST /api/start, POST /api/stop")

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        logger.info("SAA backend server stopping by keyboard interrupt")
    finally:
        app_service.shutdown(reason="server shutting down")
        server.shutdown()
        server.server_close()
        logger.info("SAA backend server stopped")


if __name__ == "__main__":
    main()