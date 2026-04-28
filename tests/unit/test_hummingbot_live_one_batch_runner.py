from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.adapters.hummingbot.live_one_batch_runner import (
    SCRIPT_CONFIG_NAME,
    SCRIPT_NAME,
    build_live_one_batch_runner_package,
)


class HummingbotLiveOneBatchRunnerTest(TestCase):
    def test_generates_and_installs_runner_when_exchange_state_confirmed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            hummingbot_root = root / "hummingbot"
            package = build_live_one_batch_runner_package(
                candidate_package=_candidate_package(),
                output_dir=root / "runner",
                hummingbot_root=hummingbot_root,
                session_id="unit",
                exchange_state_confirmed=True,
            )

            self.assertEqual("live_one_batch_runner_ready", package.decision)
            self.assertTrue((hummingbot_root / "scripts" / SCRIPT_NAME).exists())
            self.assertTrue((hummingbot_root / "conf" / "scripts" / SCRIPT_CONFIG_NAME).exists())
            self.assertIn("--v2", package.launch_command)

    def test_pending_without_exchange_state_confirmation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = build_live_one_batch_runner_package(
                candidate_package=_candidate_package(),
                output_dir=root / "runner",
                hummingbot_root=root / "hummingbot",
                session_id="unit",
                exchange_state_confirmed=False,
            )

            self.assertEqual("live_one_batch_runner_pending_exchange_state", package.decision)

    def test_blocks_when_existing_event_log_would_be_overwritten(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_log = root / "hummingbot" / "data" / "events.jsonl"
            event_log.parent.mkdir(parents=True)
            event_log.write_text("existing\n", encoding="utf-8")

            package = build_live_one_batch_runner_package(
                candidate_package=_candidate_package(),
                output_dir=root / "runner",
                hummingbot_root=root / "hummingbot",
                session_id="unit",
                exchange_state_confirmed=True,
                event_log_path="/home/hummingbot/data/events.jsonl",
            )

            self.assertEqual("live_one_batch_runner_blocked", package.decision)


def _candidate_package() -> dict[str, object]:
    return {
        "decision": "live_batch_execution_package_ready_pending_exchange_state_check",
        "strategy_id": "crypto_relative_strength_v1",
        "batch_id": "batch-low-funds",
        "connector": "binance",
        "allowed_pairs": ["BTC-USDT", "ETH-USDT"],
        "risk_summary": {
            "max_batch_notional": "50",
        },
        "candidate_orders": [
            {
                "client_order_id": "batch-low-funds-btc_usdt-1",
                "trading_pair": "BTC-USDT",
                "side": "buy",
                "notional_quote": "50",
                "estimated_price": "77371.32",
                "estimated_quantity": "0.0006462342",
                "signal_momentum": "0.03",
                "signal_timestamp": "2026-04-27T20:00:00+00:00",
            }
        ],
    }
