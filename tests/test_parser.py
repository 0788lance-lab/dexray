"""Tests for swap parser: BUY/SELL, USDC pair, ATA creation, failed tx, non-swap."""

import pytest

from dexray.solana.parser import (
    parse_swap,
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
    def test_wsol_in_token_balances_ignored(self):
        """WSOL changes in tokenBalances should not be counted."""
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
