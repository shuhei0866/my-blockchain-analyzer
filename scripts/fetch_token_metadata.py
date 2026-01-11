#!/usr/bin/env python3
"""Fetch token metadata from on-chain (Metaplex)"""
import asyncio
import json
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solana.rpc.commitment import Confirmed


async def get_token_metadata(mint_address: str, rpc_url: str = "https://api.mainnet-beta.solana.com"):
    """
    Get token metadata from Metaplex Token Metadata program

    Args:
        mint_address: Token mint address
        rpc_url: RPC endpoint URL

    Returns:
        Dict with symbol and name or None
    """
    try:
        async with AsyncClient(rpc_url) as client:
            mint_pubkey = Pubkey.from_string(mint_address)

            # Get Metaplex metadata account PDA
            METADATA_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")

            # Find metadata account address
            seeds = [
                b"metadata",
                bytes(METADATA_PROGRAM_ID),
                bytes(mint_pubkey)
            ]

            metadata_account, _ = Pubkey.find_program_address(seeds, METADATA_PROGRAM_ID)

            # Fetch account info
            response = await client.get_account_info(metadata_account, commitment=Confirmed)

            if response.value is None:
                return None

            # Parse metadata (simplified - actual parsing is more complex)
            data = response.value.data

            # This is a simplified parser - full implementation needs proper deserialization
            # For now, let's try to extract basic info
            try:
                # Skip header bytes and read name/symbol
                # Note: This is a rough approximation and may not work for all tokens
                data_str = bytes(data).decode('utf-8', errors='ignore')
                return {
                    'address': mint_address,
                    'symbol': 'UNKNOWN',
                    'name': 'Unknown Token',
                    'raw_data': data_str[:200]
                }
            except Exception as e:
                print(f"Error parsing metadata for {mint_address}: {e}")
                return None

    except Exception as e:
        print(f"Error fetching metadata for {mint_address}: {e}")
        return None


async def fetch_all_metadata(balance_file: str = "data/balance.json",
                             output_file: str = "data/token_metadata_onchain.json"):
    """Fetch metadata for all tokens in balance file"""
    print(f"\n{'='*70}")
    print("  Fetching Token Metadata from On-Chain")
    print(f"{'='*70}\n")

    # Load balance data
    with open(balance_file, 'r') as f:
        data = json.load(f)

    balances = data['current_balances']

    # Get non-zero tokens
    mints = [mint for mint, balance in balances.items()
             if float(balance.get('ui_amount', 0) or 0) > 0 and mint != 'SOL']

    print(f"Fetching metadata for {len(mints)} tokens...\n")

    metadata_list = []

    for i, mint in enumerate(mints, 1):
        print(f"[{i}/{len(mints)}] {mint[:16]}...")
        metadata = await get_token_metadata(mint)
        if metadata:
            metadata_list.append(metadata)
            await asyncio.sleep(0.2)  # Rate limiting

    # Save to file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(metadata_list, f, indent=2)

    print(f"\n✓ Saved {len(metadata_list)} metadata entries to {output_file}")


if __name__ == '__main__':
    asyncio.run(fetch_all_metadata())
