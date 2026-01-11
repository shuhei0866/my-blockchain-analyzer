#!/usr/bin/env python3
"""Download Jupiter Token List for offline use"""
import requests
import json
from pathlib import Path


def download_token_list(output_file: str = "data/token_list.json"):
    """Download token list from Jupiter"""
    print("\n" + "="*70)
    print("  Downloading Jupiter Token List")
    print("="*70 + "\n")

    urls = [
        "https://tokens.jup.ag/tokens?tags=verified",
        "https://token.jup.ag/all",
        "https://raw.githubusercontent.com/solana-labs/token-list/main/src/tokens/solana.tokenlist.json"
    ]

    tokens = None
    output_path = Path(output_file)

    for url in urls:
        try:
            print(f"Fetching from {url} ...")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            tokens_data = response.json()
            # If it's the GitHub format, the tokens are in a 'tokens' key
            if isinstance(tokens_data, dict) and 'tokens' in tokens_data:
                tokens = tokens_data['tokens']
            else:
                tokens = tokens_data
                
            print(f"✓ Downloaded {len(tokens)} tokens")

            # Save to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(tokens, f, indent=2)

            print(f"✓ Saved to: {output_path}")
            break
        except Exception as e:
            print(f"⚠ Failed to fetch from {url}: {e}")
            continue

    if tokens is None:
        print("❌ All token list sources failed.")
        print("\nTip: Make sure you have internet connection and that the Jupiter API is accessible.")
        return False

    # Show some stats
    try:
        symbols = [t.get('symbol') for t in tokens if t.get('symbol')]
        print(f"\nStats:")
        print(f"  Total tokens: {len(tokens)}")
        print(f"  With symbols: {len(symbols)}")
        print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

        # Show some examples
        print(f"\nSample tokens:")
        for token in tokens[:5]:
            symbol = token.get('symbol', 'N/A')
            name = token.get('name', 'N/A')
            address = token.get('address', 'N/A')
            print(f"  {symbol:10s} - {name[:30]:30s} ({address[:8]}...)")

        print("\n" + "="*70)
        print("✅ Token list downloaded successfully!")
        print("="*70 + "\n")
        return True
    except Exception as e:
        print(f"⚠ Error displaying stats: {e}")
        return True # Still return True because file was saved


if __name__ == '__main__':
    import sys

    output_file = sys.argv[1] if len(sys.argv) > 1 else "data/token_list.json"
    download_token_list(output_file)
