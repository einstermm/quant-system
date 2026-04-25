from decimal import Decimal
from unittest import TestCase

from packages.core.enums import OrderSide, OrderType, RiskDecisionStatus
from packages.core.models import AccountSnapshot, OrderRequest, PortfolioPosition
from packages.execution.order_intent import OrderIntent
from packages.risk.account_limits import AccountRiskLimits
from packages.risk.kill_switch import KillSwitch
from packages.risk.risk_engine import RiskEngine


class RiskEngineTest(TestCase):
    def setUp(self) -> None:
        self.limits = AccountRiskLimits(
            max_order_notional=Decimal("1000"),
            max_symbol_notional=Decimal("2000"),
            max_gross_notional=Decimal("5000"),
            max_daily_loss=Decimal("250"),
            max_drawdown_pct=Decimal("0.10"),
        )
        self.account = AccountSnapshot("main", Decimal("10000"), Decimal("10000"))

    def make_intent(
        self,
        *,
        quantity: Decimal = Decimal("1"),
        estimated_price: Decimal = Decimal("100"),
    ) -> OrderIntent:
        request = OrderRequest(
            client_order_id="order-1",
            strategy_id="test_strategy",
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=quantity,
        )
        return OrderIntent("intent-1", "main", request, estimated_price)

    def test_approves_order_inside_limits(self) -> None:
        engine = RiskEngine(self.limits)

        decision = engine.evaluate_order_intent(self.make_intent(), self.account)

        self.assertEqual(RiskDecisionStatus.APPROVED, decision.status)

    def test_rejects_when_kill_switch_active(self) -> None:
        kill_switch = KillSwitch(active=True, reason="manual stop")
        engine = RiskEngine(self.limits, kill_switch)

        decision = engine.evaluate_order_intent(self.make_intent(), self.account)

        self.assertEqual(RiskDecisionStatus.REJECTED, decision.status)
        self.assertEqual("manual stop", decision.reason)

    def test_rejects_order_notional_above_limit(self) -> None:
        engine = RiskEngine(self.limits)

        decision = engine.evaluate_order_intent(
            self.make_intent(quantity=Decimal("11"), estimated_price=Decimal("100")),
            self.account,
        )

        self.assertEqual(RiskDecisionStatus.REJECTED, decision.status)
        self.assertIn("order notional", decision.reason)

    def test_rejects_projected_symbol_exposure_above_limit(self) -> None:
        engine = RiskEngine(self.limits)
        account = AccountSnapshot(
            "main",
            Decimal("10000"),
            Decimal("10000"),
            positions=(
                PortfolioPosition(
                    "BTC-USDT",
                    Decimal("15"),
                    Decimal("100"),
                    Decimal("100"),
                ),
            ),
        )

        decision = engine.evaluate_order_intent(
            self.make_intent(quantity=Decimal("6"), estimated_price=Decimal("100")),
            account,
        )

        self.assertEqual(RiskDecisionStatus.REJECTED, decision.status)
        self.assertIn("symbol exposure", decision.reason)
