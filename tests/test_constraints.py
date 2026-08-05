"""Schema constraints datamodel-code-generator drops and postprocess_models.py restores.

Every case here passed validation before the post-processing step existed, in
violation of the schema. They are regression guards: an import-only smoke test
would not catch losing them again, because the models keep importing fine.
"""

import pydantic
import pytest

from bcp_sdk.models.schemas.shopping.types.available_payment_instrument import (
    AvailablePaymentInstrument,
)
from bcp_sdk.models.schemas.shopping.types.context import Context
from bcp_sdk.models.schemas.shopping.types.description import Description
from bcp_sdk.models.schemas.shopping.types.totals import Totals
from bcp_sdk.models.schemas.shopping.types.totals_create_request import (
    TotalsCreateRequest,
)

SUBTOTAL = {"type": "subtotal", "display_text": "Subtotal", "amount": 1000}
TOTAL = {"type": "total", "display_text": "Total", "amount": 1000}
TAX = {"type": "tax", "display_text": "ICMS", "amount": 180}


class TestTotalsContains:
    """totals.json: exactly one subtotal and exactly one total entry."""

    def test_accepts_exactly_one_subtotal_and_total(self) -> None:
        totals = Totals.model_validate([SUBTOTAL, TAX, TOTAL])
        assert len(totals.root) == 3

    def test_rejects_empty_array(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            Totals.model_validate([])

    def test_rejects_missing_total(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            Totals.model_validate([SUBTOTAL])

    def test_rejects_duplicate_subtotal(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            Totals.model_validate([SUBTOTAL, SUBTOTAL, TOTAL])


class TestTotalsRequestVariant:
    """The request variant's root is a union, so the bound applies to the list arm only."""

    def test_rejects_empty_array(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            TotalsCreateRequest.model_validate([])

    def test_accepts_the_object_arm_untouched(self) -> None:
        # contains only constrains arrays; an object payload is out of scope and
        # must not be rejected with an array error message.
        request = TotalsCreateRequest.model_validate({"ucp_request": "x"})
        assert not isinstance(request.root, list)


class TestMinProperties:
    """description.json: at least one format must be provided."""

    def test_rejects_empty_object(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            Description.model_validate({})

    @pytest.mark.parametrize("field", ["plain", "html", "markdown"])
    def test_accepts_any_single_format(self, field: str) -> None:
        assert Description.model_validate({field: "conteudo"})

    def test_rejects_empty_free_form_object(self) -> None:
        # This one the generator already handles natively, as Field(min_length=1)
        # on the dict field. Guarded here so a flag change cannot drop it.
        with pytest.raises(pydantic.ValidationError):
            AvailablePaymentInstrument.model_validate({"type": "card", "constraints": {}})


class TestUniqueItems:
    """context.json: eligibility claims must not repeat."""

    def test_accepts_distinct_claims(self) -> None:
        context = Context.model_validate(
            {"eligibility": ["com.example.loyalty_gold", "org.school.student"]}
        )
        assert len(context.eligibility) == 2

    def test_rejects_duplicate_claims(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            Context.model_validate(
                {"eligibility": ["com.example.loyalty_gold", "com.example.loyalty_gold"]}
            )
