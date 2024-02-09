"""
Goal:
- generate a payment script for a validator to distribute boosted validator rewards
- Set how much to distribute, then it will generate %s to give.

dymd tx sign payment.json --from test --node=https://m-dymension.rpc.utsa.tech:443
dymd tx sign broadcast ...
"""

import json
from datetime import date
from typing import Tuple

import httpx

BASE_DENOM = "adym"
TOKEN_TO_DISTRIBUTE = 50.0  # 50DYM

PAYMENT_FROM_ADDRESS = "dym1udkeke6hfeahv85fghaajkpgtgzpvza79g6jxy"
VALIDATOR_ADDR = "dymvaloper1ut9fa4c5wg6ld4yn7e4w6vwg4h6upad68snnx5"  # Oni Validator
REST_API = "https://m-dymension.api.utsa.tech:443"  # cosmos.directory

COIN_DECIMAL = 18  # 10**18, use 6 for standard cosmos
DELEGATOR_LIMIT = 100_000  # Don't need to touch unless you max out somehow

FEE_AMOUNT = 160000000000000000  # base of BASE_DENOM
GAS = 8_000_000

WALLET_BLACKLIST = []

# ---------------------


class StakingDelegation:
    # cosmos/staking/v1beta1/validators/{VALIDATOR_ADDR}/delegations endpoint
    # {
    # 'delegation': {
    #   'delegator_address': 'dym1qz9056lh5vla5t03z0vjzzvpjj028ys9saly4t',
    #   'validator_address': 'dymvaloper1ut9fa4c5wg6ld4yn7e4w6vwg4h6upad68snnx5',
    #   'shares': '3700000000000000000.000000000000000000'}, 'balance': {'denom': 'adym', 'amount': '3700000000000000000'}
    def __init__(
        self,
        delegator_address: str,
        validator_address: str,
        shares: float,
        denom: str,
        amount: float,
    ):
        self.delegator_address = delegator_address
        self.validator_address = validator_address
        self.shares = float(shares)
        self.denom = denom
        self.amount = float(amount)


def get_all_delegations() -> Tuple[int, list[StakingDelegation]]:
    # https://github.com/cosmos/cosmos-sdk/blob/v0.46.16/proto/cosmos/staking/v1beta1/query.proto
    url = (
        REST_API
        + f"/cosmos/staking/v1beta1/validators/{VALIDATOR_ADDR}/delegations?pagination.limit={DELEGATOR_LIMIT}"
    )

    total_shares = 0

    all_delegations = []
    res = httpx.get(url)
    for d in res.json()["delegation_responses"]:

        delegator = delegator_address = d["delegation"]["delegator_address"]
        if delegator in WALLET_BLACKLIST:
            print(f"Blacklist: {delegator}")
            continue

        amount = float(d["balance"]["amount"])
        total_shares += amount

        all_delegations.append(
            StakingDelegation(
                delegator,
                validator_address=d["delegation"]["validator_address"],
                shares=d["delegation"]["shares"],
                denom=d["balance"]["denom"],
                amount=d["balance"]["amount"],
            )
        )

    return total_shares, all_delegations


total_shares, delegations = get_all_delegations()
print(f"TOKEN_TO_DISTRIBUTE: {TOKEN_TO_DISTRIBUTE}")  # in adym
print(f"Total shares: {total_shares}")  # in adym
print(f"Total delegators: {len(delegations)}")


MSG_FORMAT = {
    "body": {
        "messages": [],
        "memo": "",
        "timeout_height": "0",
        "extension_options": [],
        "non_critical_extension_options": [],
    },
    "auth_info": {
        "signer_infos": [],
        "fee": {
            "amount": [{"amount": f"{FEE_AMOUNT}", "denom": "adym"}],
            "gas_limit": f"{GAS}",
            "payer": "",
            "granter": "",
        },
        "tip": None,
    },
    "signatures": [],
}

total = 0
adym_total = 0
for d in delegations:
    percentage = d.amount / total_shares
    receives = percentage * TOKEN_TO_DISTRIBUTE  # DYM receive, mul * 10**18
    print(f"{d.delegator_address} will receive {receives} DYM")

    adym = receives * (10**COIN_DECIMAL)

    total += receives
    adym_total += adym

    MSG_FORMAT["body"]["messages"].append(
        {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": f"{PAYMENT_FROM_ADDRESS}",
            "to_address": f"{d.delegator_address}",
            "amount": [{"denom": BASE_DENOM, "amount": f"{int(adym):.0f}"}],
        }
    )

print(f"Total DYM to distribute: {total}")

print(
    f"{total} ({adym_total} {BASE_DENOM}) will be distributed to {len(delegations)} delegators"
)

print("Sign and broadcast the Tx, make sure to edit the amount of gas")

today = date.today()

with open(f"payment-{today}.json", "w") as file:
    json.dump(MSG_FORMAT, file, indent=4)
