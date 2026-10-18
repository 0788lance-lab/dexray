"""Tests for swap parser: BUY/SELL, USDC pair, ATA creation, failed tx, non-swap."""

import pytest

from dexray.solana.parser import (
    parse_swap,
    QUOTE_PRIORITY,
    parse_wallet,
    SolanaParser,
    WSOL,
    USDC,
    USDT,
    LAMPORTS_PER_SOL,
)
from dexray.core import Swap


WALLET = "WalletABC123"
TOKEN_MINT = "TokenMint123456789"
JUPITER_PROGRAM = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
RAYDIUM_PROGRAM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_tx(
    wallet=WALLET,
    pre_sol=1_000_000_000,
    post_sol=500_000_000,
    fee=5000,
    pre_token_balances=None,
    post_token_balances=None,
    err=None,
    block_time=1700000000,
    signature="sig123",
    account_keys=None,
    instructions=None,
    account_keys_as_dicts=False,
) -> dict:
    if account_keys is None:
        if account_keys_as_dicts:
            account_keys = [
                {"pubkey": wallet, "signer": True, "writable": True},
                {"pubkey": "OtherAccount", "signer": False, "writable": True},
            ]
        else:
            account_keys = [wallet, "OtherAccount"]

    if instructions is None:
        instructions = [{"programId": JUPITER_PROGRAM}]

    return {
        "blockTime": block_time,
        "transaction": {
            "signatures": [signature],
            "message": {
                "accountKeys": account_keys,
                "instructions": instructions,
            },
        },
        "meta": {
            "err": err,
            "fee": fee,
            "preBalances": [pre_sol, 2_000_000_000],
            "postBalances": [post_sol, 2_000_000_000],
            "preTokenBalances": pre_token_balances or [],
            "postTokenBalances": post_token_balances or [],
            "innerInstructions": [],
        },
    }


def _token_balance(owner: str, mint: str, amount: float, decimals: int = 6) -> dict:
    return {
        "accountIndex": 1,
        "owner": owner,
        "mint": mint,
        "uiTokenAmount": {
            "uiAmount": amount,
            "uiAmountString": str(amount),
            "decimals": decimals,
            "amount": str(int(amount * (10 ** decimals))),
        },
    }


# ---------------------------------------------------------------------------
# BUY: SOL decreased + token increased
# ---------------------------------------------------------------------------

class TestBuy:
    def test_basic_buy(self):
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            fee=5000,
            post_token_balances=[
                _token_balance(WALLET, TOKEN_MINT, 1000.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap is not None
        assert swap.direction == "BUY"
        assert swap.mint == TOKEN_MINT
        assert swap.token_amount == 1000.0
        assert swap.sol_amount == pytest.approx(0.499995)
        assert swap.source == "JUPITER"

    def test_buy_first_purchase_ata_creation(self):
        """First buy: token only in postTokenBalances (new ATA)."""
        tx = _make_tx(
            pre_sol=2_000_000_000,
            post_sol=1_000_000_000,
            fee=5000,
            pre_token_balances=[],
            post_token_balances=[
                _token_balance(WALLET, TOKEN_MINT, 50000.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap is not None
        assert swap.direction == "BUY"
        assert swap.token_amount == 50000.0

    def test_buy_with_dict_account_keys(self):
        """accountKeys as objects with pubkey field."""
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            fee=5000,
            post_token_balances=[
                _token_balance(WALLET, TOKEN_MINT, 100.0),
            ],
            account_keys_as_dicts=True,
        )
        swap = parse_swap(tx, WALLET)
        assert swap is not None
        assert swap.direction == "BUY"


# ---------------------------------------------------------------------------
# SELL: SOL increased + token decreased
# ---------------------------------------------------------------------------

class TestSell:
    def test_basic_sell(self):
        tx = _make_tx(
            pre_sol=500_000_000,
            post_sol=1_000_000_000,
            fee=5000,
            pre_token_balances=[
                _token_balance(WALLET, TOKEN_MINT, 1000.0),
            ],
            post_token_balances=[
                _token_balance(WALLET, TOKEN_MINT, 0.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap is not None
        assert swap.direction == "SELL"
        assert swap.mint == TOKEN_MINT
        assert swap.token_amount == 1000.0
        assert swap.sol_amount == pytest.approx(0.500005)

    def test_sell_full_close_ata(self):
        """Full sell: token only in preTokenBalances (ATA closed)."""
        tx = _make_tx(
            pre_sol=500_000_000,
            post_sol=1_500_000_000,
            fee=5000,
            pre_token_balances=[
                _token_balance(WALLET, TOKEN_MINT, 2000.0),
            ],
            post_token_balances=[],
        )
        swap = parse_swap(tx, WALLET)
        assert swap is not None
        assert swap.direction == "SELL"
        assert swap.token_amount == 2000.0


# ---------------------------------------------------------------------------
# USDC/USDT pair
# ---------------------------------------------------------------------------

class TestStablecoinPair:
    def test_usdc_buy(self):
        """USDC decreased + token increased = BUY."""
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=1_000_000_000,
            fee=5000,
            pre_token_balances=[
                _token_balance(WALLET, USDC, 500.0),
            ],
            post_token_balances=[
                _token_balance(WALLET, USDC, 400.0),
                _token_balance(WALLET, TOKEN_MINT, 10000.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap is not None
        assert swap.direction == "BUY"
        assert swap.mint == TOKEN_MINT
        assert swap.usdc_amount == pytest.approx(100.0)
        assert swap.sol_amount == 0.0

    def test_usdc_sell(self):
        """Token decreased + USDC increased = SELL."""
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=1_000_000_000,
            fee=5000,
            pre_token_balances=[
                _token_balance(WALLET, TOKEN_MINT, 10000.0),
                _token_balance(WALLET, USDC, 400.0),
            ],
            post_token_balances=[
                _token_balance(WALLET, TOKEN_MINT, 0.0),
                _token_balance(WALLET, USDC, 550.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap is not None
        assert swap.direction == "SELL"
        assert swap.usdc_amount == pytest.approx(150.0)

    def test_usdt_buy(self):
        """USDT pair buy."""
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=1_000_000_000,
            fee=5000,
            pre_token_balances=[
                _token_balance(WALLET, USDT, 1000.0),
            ],
            post_token_balances=[
                _token_balance(WALLET, USDT, 800.0),
                _token_balance(WALLET, TOKEN_MINT, 5000.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap is not None
        assert swap.direction == "BUY"
        assert swap.usdc_amount == pytest.approx(200.0)


# ---------------------------------------------------------------------------
# WSOL handling
# ---------------------------------------------------------------------------

class TestWSOL:
    def test_wsol_folded_into_sol_leg(self):
        """WSOL token balance changes count toward the SOL leg, not as a token."""
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            fee=5000,
            pre_token_balances=[
                _token_balance(WALLET, WSOL, 0.5),
            ],
            post_token_balances=[
                _token_balance(WALLET, WSOL, 0.0),
                _token_balance(WALLET, TOKEN_MINT, 10000.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap is not None
        assert swap.direction == "BUY"
        assert swap.mint == TOKEN_MINT
        assert swap.sol_amount == pytest.approx(0.999995)
        assert swap.quote_mint == WSOL

    def test_sell_into_persistent_wsol_account(self):
        """Proceeds land in a WSOL account that stays open; native SOL unchanged."""
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=1_000_000_000 - 5000,
            fee=5000,
            pre_token_balances=[
                _token_balance(WALLET, WSOL, 0.1, decimals=9),
                _token_balance(WALLET, TOKEN_MINT, 3000.0),
            ],
            post_token_balances=[
                _token_balance(WALLET, WSOL, 0.35, decimals=9),
                _token_balance(WALLET, TOKEN_MINT, 0.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap is not None
        assert swap.direction == "SELL"
        assert swap.sol_amount == pytest.approx(0.25)
        assert swap.token_amount == 3000.0


# ---------------------------------------------------------------------------
# failed / non-swap
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_failed_tx_returns_none(self):
        tx = _make_tx(err={"InstructionError": [0, "Custom"]})
        assert parse_swap(tx, WALLET) is None

    def test_non_swap_transfer_returns_none(self):
        """Only SOL change, no token change => not a swap."""
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            fee=5000,
            pre_token_balances=[],
            post_token_balances=[],
        )
        assert parse_swap(tx, WALLET) is None

    def test_only_token_no_sol_change_returns_none(self):
        """Token transfer without SOL or stablecoin counterpart."""
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=1_000_000_000,
            fee=5000,
            pre_token_balances=[],
            post_token_balances=[
                _token_balance(WALLET, TOKEN_MINT, 100.0),
            ],
        )
        assert parse_swap(tx, WALLET) is None

    def test_wallet_not_in_tx_returns_none(self):
        tx = _make_tx()
        assert parse_swap(tx, "UNKNOWN_WALLET") is None

    def test_null_ui_amount_fallback(self):
        """uiAmount is null, should fallback to uiAmountString."""
        bal = _token_balance(WALLET, TOKEN_MINT, 500.0)
        bal["uiTokenAmount"]["uiAmount"] = None
        bal["uiTokenAmount"]["uiAmountString"] = "500.0"

        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            fee=5000,
            post_token_balances=[bal],
        )
        swap = parse_swap(tx, WALLET)
        assert swap is not None
        assert swap.token_amount == 500.0

    def test_other_wallet_tokens_ignored(self):
        """Tokens owned by other wallets should not be counted."""
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            fee=5000,
            post_token_balances=[
                _token_balance("SomeOtherWallet", TOKEN_MINT, 1000.0),
            ],
        )
        assert parse_swap(tx, WALLET) is None


# ---------------------------------------------------------------------------
# DEX identification
# ---------------------------------------------------------------------------

class TestDexIdentification:
    def test_jupiter(self):
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 100.0)],
            instructions=[{"programId": JUPITER_PROGRAM}],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.source == "JUPITER"
        assert swap.program == JUPITER_PROGRAM

    def test_raydium(self):
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 100.0)],
            instructions=[{"programId": RAYDIUM_PROGRAM}],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.source == "RAYDIUM"

    def test_unknown_dex(self):
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 100.0)],
            instructions=[{"programId": "UnknownProgram123"}],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.source == "UNKNOWN"

    def test_dex_from_inner_instructions(self):
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 100.0)],
            instructions=[{"programId": "SomeRouterProgram"}],
        )
        tx["meta"]["innerInstructions"] = [
            {
                "index": 0,
                "instructions": [
                    {"programId": RAYDIUM_PROGRAM},
                ],
            }
        ]
        swap = parse_swap(tx, WALLET)
        assert swap.source == "RAYDIUM"


# ---------------------------------------------------------------------------
# metadata / output fields
# ---------------------------------------------------------------------------

class TestOutputFields:
    def test_timestamp(self):
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            block_time=1695849600,
            post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 100.0)],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.timestamp == 1695849600

    def test_signature(self):
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            signature="abc123def",
            post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 100.0)],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.signature == "abc123def"

    def test_to_dict(self):
        tx = _make_tx(
            pre_sol=1_000_000_000,
            post_sol=500_000_000,
            post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 100.0)],
        )
        swap = parse_swap(tx, WALLET)
        d = swap.to_dict()
        assert isinstance(d, dict)
        assert d["direction"] == "BUY"
        assert d["mint"] == TOKEN_MINT


# ---------------------------------------------------------------------------
# SolanaParser wrapper
# ---------------------------------------------------------------------------

class TestSolanaParser:
    def test_parse_swap_by_sig(self):
        class MockRPC:
            def get_transaction(self, sig):
                return _make_tx(
                    pre_sol=1_000_000_000,
                    post_sol=500_000_000,
                    post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 100.0)],
                )

        parser = SolanaParser(MockRPC())
        swap = parser.parse_swap_by_sig("sig1", WALLET)
        assert swap is not None
        assert swap.direction == "BUY"

    def test_parse_swap_by_sig_not_found(self):
        class MockRPC:
            def get_transaction(self, sig):
                return None

        parser = SolanaParser(MockRPC())
        assert parser.parse_swap_by_sig("sig1", WALLET) is None

    def test_parse_wallet(self):
        class MockRPC:
            def get_signatures(self, addr, limit=1000):
                return [{"signature": "s1"}, {"signature": "s2"}]

            def batch_get_transactions(self, sigs, batch_size=10):
                return [
                    _make_tx(
                        pre_sol=1_000_000_000,
                        post_sol=500_000_000,
                        post_token_balances=[
                            _token_balance(WALLET, TOKEN_MINT, 100.0)
                        ],
                    ),
                    None,  # one tx not found
                ]

        parser = SolanaParser(MockRPC())
        swaps = parser.parse_wallet(WALLET, limit=10)
        assert len(swaps) == 1
        assert swaps[0].direction == "BUY"

    def test_resolver_populates_symbol(self):
        class MockRPC:
            def get_transaction(self, sig):
                return _make_tx(
                    pre_sol=1_000_000_000,
                    post_sol=500_000_000,
                    post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 100.0)],
                )

        class MockResolver:
            def resolve(self, mint):
                return "BONK" if mint == TOKEN_MINT else mint

        parser = SolanaParser(MockRPC(), resolver=MockResolver())
        swap = parser.parse_swap_by_sig("sig1", WALLET)
        assert swap.symbol == "BONK"

    def test_no_resolver_symbol_empty(self):
        class MockRPC:
            def get_transaction(self, sig):
                return _make_tx(
                    pre_sol=1_000_000_000,
                    post_sol=500_000_000,
                    post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 100.0)],
                )

        parser = SolanaParser(MockRPC())
        swap = parser.parse_swap_by_sig("sig1", WALLET)
        assert swap.symbol == ""


# ---------------------------------------------------------------------------
# quote asset (quote_mint / quote_amount)
# ---------------------------------------------------------------------------

OTHER_MINT = "OtherTokenMint987654321"
RELAYER = "RelayerFeePayer111"


class TestQuote:
    def test_sol_quote(self):
        tx = _make_tx(
            pre_sol=1_000_000_000, post_sol=500_000_000, fee=5000,
            post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 1000.0)],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.quote_mint == WSOL
        assert swap.quote_amount == swap.sol_amount == pytest.approx(0.499995)
        assert swap.usdc_amount == 0.0

    def test_usdc_quote(self):
        tx = _make_tx(
            pre_sol=1_000_000_000, post_sol=1_000_000_000 - 5000, fee=5000,
            pre_token_balances=[_token_balance(WALLET, USDC, 500.0)],
            post_token_balances=[
                _token_balance(WALLET, USDC, 400.0),
                _token_balance(WALLET, TOKEN_MINT, 1000.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.quote_mint == USDC
        assert swap.quote_amount == 100.0
        assert swap.sol_amount == 0.0

    def test_usdt_quote_is_not_reported_as_usdc_mint(self):
        tx = _make_tx(
            pre_sol=1_000_000_000, post_sol=1_000_000_000 - 5000, fee=5000,
            pre_token_balances=[_token_balance(WALLET, USDT, 500.0)],
            post_token_balances=[
                _token_balance(WALLET, USDT, 300.0),
                _token_balance(WALLET, TOKEN_MINT, 1000.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.quote_mint == USDT
        assert swap.quote_amount == 200.0

    def test_amounts_from_raw_integers(self):
        """uiAmount floats carry noise; amounts come from raw integer amounts."""
        pre = _token_balance(WALLET, USDC, 0.0)
        post = _token_balance(WALLET, USDC, 0.0)
        pre["uiTokenAmount"].update(amount="1000000000", uiAmount=1000.0000000001)
        post["uiTokenAmount"].update(amount="993504657", uiAmount=993.5046569999)
        tx = _make_tx(
            pre_sol=1_000_000_000, post_sol=1_000_000_000 - 5000, fee=5000,
            pre_token_balances=[pre],
            post_token_balances=[post, _token_balance(WALLET, TOKEN_MINT, 10.0)],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.quote_amount == 6.495343

    def test_token_accounts_of_same_mint_are_summed(self):
        tx = _make_tx(
            pre_sol=1_000_000_000, post_sol=500_000_000, fee=5000,
            pre_token_balances=[_token_balance(WALLET, TOKEN_MINT, 100.0)],
            post_token_balances=[
                _token_balance(WALLET, TOKEN_MINT, 100.0),
                _token_balance(WALLET, TOKEN_MINT, 250.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.token_amount == 250.0

    def test_token_to_token(self):
        tx = _make_tx(
            pre_sol=1_000_000_000, post_sol=1_000_000_000 - 5000, fee=5000,
            pre_token_balances=[_token_balance(WALLET, OTHER_MINT, 900.0)],
            post_token_balances=[
                _token_balance(WALLET, OTHER_MINT, 0.0),
                _token_balance(WALLET, TOKEN_MINT, 42.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.direction == "BUY"
        assert swap.mint == TOKEN_MINT
        assert swap.quote_mint == OTHER_MINT
        assert swap.quote_amount == 900.0
        assert swap.sol_amount == 0.0

    def test_token_to_token_with_ata_rent(self):
        """SOL spent on a new ATA does not turn a token swap into a SOL buy."""
        tx = _make_tx(
            pre_sol=1_000_000_000, post_sol=1_000_000_000 - 5000 - 2_039_280, fee=5000,
            pre_token_balances=[_token_balance(WALLET, OTHER_MINT, 900.0)],
            post_token_balances=[
                _token_balance(WALLET, OTHER_MINT, 0.0),
                _token_balance(WALLET, TOKEN_MINT, 42.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.quote_mint == OTHER_MINT

    def test_large_sol_outflow_is_not_token_to_token(self):
        """Token out + LP token in + lots of SOL out looks like adding liquidity."""
        tx = _make_tx(
            pre_sol=5_000_000_000, post_sol=3_000_000_000, fee=5000,
            pre_token_balances=[_token_balance(WALLET, OTHER_MINT, 900.0)],
            post_token_balances=[
                _token_balance(WALLET, OTHER_MINT, 0.0),
                _token_balance(WALLET, TOKEN_MINT, 42.0),
            ],
        )
        swap = parse_swap(tx, WALLET)
        assert swap is None or swap.quote_mint != OTHER_MINT

    def test_sol_to_usdc(self):
        tx = _make_tx(
            pre_sol=1_000_000_000, post_sol=950_000_000, fee=5000,
            pre_token_balances=[_token_balance(WALLET, USDC, 1.0)],
            post_token_balances=[_token_balance(WALLET, USDC, 11.0)],
        )
        swap = parse_swap(tx, WALLET)
        assert swap.direction == "SELL"
        assert swap.mint == WSOL
        assert swap.token_amount == pytest.approx(0.049995)
        assert swap.quote_mint == USDC
        assert swap.quote_amount == 10.0

    def test_usdc_received_with_rent_is_not_a_swap(self):
        tx = _make_tx(
            pre_sol=1_000_000_000, post_sol=1_000_000_000 - 5000 - 2_039_280, fee=5000,
            post_token_balances=[_token_balance(WALLET, USDC, 50.0)],
        )
        assert parse_swap(tx, WALLET) is None

    def test_custom_quote_priority(self):
        tx = _make_tx(
            pre_sol=1_000_000_000, post_sol=1_000_000_000 - 5000, fee=5000,
            pre_token_balances=[_token_balance(WALLET, OTHER_MINT, 900.0)],
            post_token_balances=[
                _token_balance(WALLET, OTHER_MINT, 0.0),
                _token_balance(WALLET, TOKEN_MINT, 42.0),
            ],
        )
        swap = parse_swap(tx, WALLET, quote_mints=(OTHER_MINT,) + QUOTE_PRIORITY)
        assert swap.direction == "BUY"
        assert swap.quote_mint == OTHER_MINT
        swap = parse_swap(tx, WALLET, quote_mints=(TOKEN_MINT,) + QUOTE_PRIORITY)
        assert swap.direction == "SELL"
        assert swap.mint == OTHER_MINT


# ---------------------------------------------------------------------------
# trader / fee payer
# ---------------------------------------------------------------------------

def _relayer_tx(trader_pre_sol, trader_post_sol, fee=11534, extra_signer=None):
    """Relayer pays the fee; the trader co-signs and buys TOKEN_MINT."""
    tx = _make_tx(
        fee=fee,
        account_keys=[
            {"pubkey": RELAYER, "signer": True, "writable": True},
            {"pubkey": WALLET, "signer": True, "writable": True},
        ] + ([{"pubkey": extra_signer, "signer": True, "writable": True}] if extra_signer else []),
        post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 6254.070163)],
    )
    tx["meta"]["preBalances"] = [5_000_000_000, trader_pre_sol, 0]
    tx["meta"]["postBalances"] = [5_000_000_000 - fee, trader_post_sol, 0]
    return tx


class TestTraderAttribution:
    def test_fee_not_added_back_when_relayer_pays(self):
        swap = parse_swap(_relayer_tx(1_000_000_000, 592_000_000), WALLET)
        assert swap.sol_amount == 0.408
        assert swap.trader == WALLET
        assert swap.fee_payer == RELAYER

    def test_self_paid_fee_payer_is_trader(self):
        tx = _make_tx(post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 1.0)])
        swap = parse_swap(tx, WALLET)
        assert swap.trader == swap.fee_payer == WALLET

    def test_infer_trader_relayer(self):
        swap = parse_swap(_relayer_tx(1_000_000_000, 592_000_000))
        assert swap.trader == WALLET
        assert swap.fee_payer == RELAYER

    def test_infer_trader_ignores_non_owner_signers(self):
        """Extra signers that own no token accounts (e.g. a new mint keypair) are skipped."""
        swap = parse_swap(_relayer_tx(1_000_000_000, 592_000_000, extra_signer="MintKeypair"))
        assert swap.trader == WALLET

    def test_infer_trader_self_paid(self):
        tx = _make_tx(
            account_keys_as_dicts=True,
            post_token_balances=[_token_balance(WALLET, TOKEN_MINT, 1.0)],
        )
        assert parse_swap(tx).trader == WALLET

    def test_to_dict_has_new_fields(self):
        d = parse_swap(_relayer_tx(1_000_000_000, 592_000_000), WALLET).to_dict()
        assert d["quote_mint"] == WSOL
        assert d["quote_amount"] == 0.408
        assert d["trader"] == WALLET
        assert d["fee_payer"] == RELAYER
