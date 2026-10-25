"""Merkle tree for the daily price list, matching GearEscrow.leafOf and OpenZeppelin MerkleProof.

leaf = keccak256(keccak256(abi.encode(uint256 netId, uint64 epoch, uint128 bounty)))
Pairs are hashed in sorted order (commutative), so proofs need no left/right flags.
An odd node at the end of a layer is carried up unchanged.

    python -m engine.merkle --fixture   # writes contracts/test/fixtures/merkle.json for the Solidity test
"""
import json
import sys

from eth_abi import encode
from eth_utils import keccak

from engine import config as C


def leaf(net_id: int, epoch: int, bounty_wei: int) -> bytes:
    return keccak(keccak(encode(["uint256", "uint64", "uint128"], [net_id, epoch, bounty_wei])))


def _pair(a: bytes, b: bytes) -> bytes:
    return keccak(a + b) if a < b else keccak(b + a)


class MerkleTree:
    def __init__(self, leaves: list[bytes]):
        assert leaves, "empty tree"
        self.layers = [list(leaves)]
        while len(self.layers[-1]) > 1:
            cur = self.layers[-1]
            nxt = [_pair(cur[i], cur[i + 1]) for i in range(0, len(cur) - 1, 2)]
            if len(cur) % 2:
                nxt.append(cur[-1])
            self.layers.append(nxt)

    @property
    def root(self) -> bytes:
        return self.layers[-1][0]

    def proof(self, index: int) -> list[bytes]:
        out = []
        for layer in self.layers[:-1]:
            sib = index ^ 1
            if sib < len(layer):
                out.append(layer[sib])
            index //= 2
        return out


def verify(proof: list[bytes], root: bytes, lf: bytes) -> bool:
    h = lf
    for p in proof:
        h = _pair(h, p)
    return h == root


def write_fixture():
    rows = [(i, 7, (200 + 37 * i) * 10**18) for i in range(1, 12)]   # 11 leaves: exercises the odd carry
    t = MerkleTree([leaf(*r) for r in rows])
    fx = {"root": "0x" + t.root.hex(),
          "items": [{"netId": r[0], "epoch": r[1], "bounty": str(r[2]),
                     "proof": ["0x" + p.hex() for p in t.proof(i)]} for i, r in enumerate(rows)]}
    out = C.ROOT / "contracts" / "test" / "fixtures" / "merkle.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fx, indent=1))
    assert all(verify(t.proof(i), t.root, leaf(*r)) for i, r in enumerate(rows))
    print(f"wrote {out.relative_to(C.ROOT)} ({len(rows)} leaves, root {fx['root'][:18]}...)")


if __name__ == "__main__":
    if "--fixture" in sys.argv:
        write_fixture()
