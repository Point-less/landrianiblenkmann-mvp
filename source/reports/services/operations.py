from decimal import Decimal
from typing import List

from django.db.models import F

from opportunities.models import Operation
from utils.services import BaseService


class ClosedOperationsFinancialReportQuery(BaseService):
    """Return financial/tax report rows for closed operations (both sides)."""

    def run(self) -> List[dict]:
        operations = (
            Operation.objects.filter(state=Operation.State.CLOSED)
            .select_related(
                "currency",
                "provider_opportunity__source_intention__owner",
                "provider_opportunity__source_intention__property",
                "provider_opportunity__source_intention__agent",
                "seeker_opportunity__source_intention__contact",
                "seeker_opportunity__source_intention__agent",
            )
        )

        rows: List[dict] = []
        for op in operations:
            provider_opp = op.provider_opportunity
            seeker_opp = op.seeker_opportunity

            close_date = op.occurred_at.date() if op.occurred_at else None
            deal_value = op.offered_amount or op.initial_offered_amount
            deed_value = op.declared_deed_value

            seller_contact = provider_opp.owner
            gross = provider_opp.gross_commission_pct or Decimal("0")
            split = provider_opp.agent.commission_split or Decimal("0")
            agent_revenue = (deal_value or Decimal("0")) * gross * split if deal_value is not None else None
            agency_revenue = (deal_value or Decimal("0")) * gross * (Decimal("1") - split) if deal_value is not None else None
            rows.append(
                {
                    "close_date": close_date,
                    "client_name": f"{seller_contact.first_name} {seller_contact.last_name}".strip() or seller_contact.email,
                    "client_tax_id": seller_contact.tax_id,
                    "client_tax_condition": seller_contact.get_tax_condition_display() if hasattr(seller_contact, "get_tax_condition_display") else "",
                    "client_address": seller_contact.full_address,
                    "property_address": provider_opp.property.full_address,
                    "agent": provider_opp.agent,
                    "role": "Seller",
                    "deal_value": deal_value,
                    "deed_value": deed_value,
                    "gross_commission_pct": provider_opp.gross_commission_pct,
                    "agent_split": provider_opp.agent.commission_split,
                    "agent_revenue": agent_revenue,
                    "agency_revenue": agency_revenue,
                }
            )

            buyer_contact = seeker_opp.contact
            gross = seeker_opp.gross_commission_pct or Decimal("0")
            split = seeker_opp.agent.commission_split or Decimal("0")
            agent_revenue = (deal_value or Decimal("0")) * gross * split if deal_value is not None else None
            agency_revenue = (deal_value or Decimal("0")) * gross * (Decimal("1") - split) if deal_value is not None else None
            rows.append(
                {
                    "close_date": close_date,
                    "client_name": f"{buyer_contact.first_name} {buyer_contact.last_name}".strip() or buyer_contact.email,
                    "client_tax_id": buyer_contact.tax_id,
                    "client_tax_condition": buyer_contact.get_tax_condition_display() if hasattr(buyer_contact, "get_tax_condition_display") else "",
                    "client_address": buyer_contact.full_address,
                    "property_address": provider_opp.property.full_address,
                    "agent": seeker_opp.agent,
                    "role": "Buyer",
                    "deal_value": deal_value,
                    "deed_value": deed_value,
                    "gross_commission_pct": seeker_opp.gross_commission_pct,
                    "agent_split": seeker_opp.agent.commission_split,
                    "agent_revenue": agent_revenue,
                    "agency_revenue": agency_revenue,
                }
            )

        return rows
