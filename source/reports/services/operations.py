from decimal import Decimal
from typing import List


from opportunities.models import Operation
from utils.services import BaseService
from utils.authorization import REPORT_VIEW, OPERATION_VIEW_ALL, get_role_profile, check


class ClosedOperationsFinancialReportQuery(BaseService):
    """Return financial/tax report rows for closed operations (both sides)."""

    required_action = REPORT_VIEW

    def run(self, *, actor=None) -> List[dict]:
        check(actor, REPORT_VIEW)

        operations = Operation.objects.filter(state=Operation.State.CLOSED).select_related(
            "currency",
            "agreement__provider_opportunity__source_intention__owner",
            "agreement__provider_opportunity__source_intention__property",
            "agreement__provider_opportunity__source_intention__agent",
            "agreement__seeker_opportunity__source_intention__contact",
            "agreement__seeker_opportunity__source_intention__agent",
        )

        try:
            check(actor, OPERATION_VIEW_ALL)
        except Exception:
            from django.db.models import Q

            owner = get_role_profile(actor, "agent") if actor else None
            if owner is not None:
                operations = operations.filter(
                    Q(agreement__provider_opportunity__source_intention__agent=owner)
                    | Q(agreement__seeker_opportunity__source_intention__agent=owner)
                )
            else:
                operations = operations.none()

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
                    "client_tax_condition": seller_contact.get_tax_condition_display(),
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
                    "client_tax_condition": buyer_contact.get_tax_condition_display(),
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
