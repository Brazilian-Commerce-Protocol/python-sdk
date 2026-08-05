import importlib
import pkgutil

import pydantic
import pytest

import bcp_sdk.models


def _walk_model_modules() -> list[str]:
    """List every generated module under bcp_sdk.models."""
    return [
        name
        for _, name, _ in pkgutil.walk_packages(bcp_sdk.models.__path__, prefix="bcp_sdk.models.")
    ]


def test_generated_tree_is_not_empty() -> None:
    assert len(_walk_model_modules()) > 100


@pytest.mark.parametrize("module_name", _walk_model_modules())
def test_every_generated_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)


def test_checkout_and_profile_are_pydantic_models() -> None:
    from bcp_sdk.models.discovery.profile_schema import BusinessProfile
    from bcp_sdk.models.schemas.shopping.checkout import Checkout

    assert issubclass(Checkout, pydantic.BaseModel)
    assert issubclass(BusinessProfile, pydantic.BaseModel)


def test_amount_validates_and_is_frozen() -> None:
    from bcp_sdk.models.schemas.shopping.types.amount import Amount

    amount = Amount.model_validate(5000)
    assert amount.root == 5000
    with pytest.raises(pydantic.ValidationError):
        Amount.model_validate(-1)
    with pytest.raises(pydantic.ValidationError):
        amount.root = 1
