import hashlib
from typing import Any, Dict, List, Tuple, Union


def compute_leaf_hash(event_data: Union[bytes, str]) -> bytes:
    """Compute leaf hash with second-preimage defense domain separation prefix: SHA-256(0x00 || event_data)."""
    if isinstance(event_data, str):
        try:
            data_bytes = bytes.fromhex(event_data.strip())
        except ValueError:
            data_bytes = event_data.encode("utf-8")
    else:
        data_bytes = event_data

    return hashlib.sha256(b"\x00" + data_bytes).digest()


def _hash_internal_node(left: bytes, right: bytes) -> bytes:
    """Compute interior tree node hash with domain separation prefix: SHA-256(0x01 || left || right)."""
    return hashlib.sha256(b"\x01" + left + right).digest()


def build_merkle_tree(leaf_hashes: List[bytes]) -> Tuple[bytes, List[List[bytes]]]:
    """Construct a deterministic Merkle Tree over a list of leaf hashes.

    Handles odd-length levels by duplicating the last node deterministically.

    Returns:
        Tuple of (root_hash_32_bytes, tree_levels) where tree_levels[0] is the leaves.
    """
    if not leaf_hashes:
        empty_root = hashlib.sha256(b"\x00").digest()
        return empty_root, [[empty_root]]

    levels: List[List[bytes]] = [list(leaf_hashes)]
    current = levels[0]

    while len(current) > 1:
        next_level: List[bytes] = []
        for i in range(0, len(current), 2):
            left = current[i]
            right = current[i + 1] if i + 1 < len(current) else current[i]
            parent = _hash_internal_node(left, right)
            next_level.append(parent)
        levels.append(next_level)
        current = next_level

    return levels[-1][0], levels


def generate_merkle_proof(
    leaf_index: int,
    tree_levels: List[List[bytes]],
) -> List[Dict[str, str]]:
    """Generate an audit inclusion proof path for a given leaf index.

    Returns:
        List of proof steps formatted as: [{"position": "left" | "right", "hash_hex": str}]
    """
    if not tree_levels or leaf_index < 0 or leaf_index >= len(tree_levels[0]):
        return []

    proof: List[Dict[str, str]] = []
    idx = leaf_index

    # Traverse from bottom leaves up to the level below the root
    for level_idx in range(len(tree_levels) - 1):
        current_level = tree_levels[level_idx]
        if idx % 2 == 0:
            # Current node is on the left -> sibling is on the right
            sibling = current_level[idx + 1] if idx + 1 < len(current_level) else current_level[idx]
            proof.append({"position": "right", "hash_hex": sibling.hex()})
        else:
            # Current node is on the right -> sibling is on the left
            sibling = current_level[idx - 1]
            proof.append({"position": "left", "hash_hex": sibling.hex()})

        idx = idx // 2

    return proof


def verify_merkle_proof(
    leaf_hash: bytes,
    proof: List[Dict[str, str]],
    expected_root: bytes,
) -> bool:
    """Verify that recalculating hashes up the tree from leaf_hash using proof reproduces expected_root."""
    try:
        curr = leaf_hash
        for step in proof:
            pos = step.get("position", "").strip().lower()
            sibling_hex = step.get("hash_hex", "").strip()
            sibling = bytes.fromhex(sibling_hex)

            if pos == "right":
                curr = _hash_internal_node(curr, sibling)
            elif pos == "left":
                curr = _hash_internal_node(sibling, curr)
            else:
                return False

        return curr == expected_root
    except Exception:
        return False
