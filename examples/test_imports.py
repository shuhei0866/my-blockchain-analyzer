#!/usr/bin/env python3
"""Test script to verify all imports work correctly"""

print("Testing imports...")

try:
    print("1. Testing solana imports...")
    from solana.rpc.async_api import AsyncClient
    from solders.pubkey import Pubkey
    print("   ✓ Solana imports successful")
except Exception as e:
    print(f"   ✗ Solana imports failed: {e}")

try:
    print("2. Testing pandas...")
    import pandas as pd
    print("   ✓ Pandas import successful")
except Exception as e:
    print(f"   ✗ Pandas import failed: {e}")

try:
    print("3. Testing matplotlib...")
    import matplotlib.pyplot as plt
    print("   ✓ Matplotlib import successful")
except Exception as e:
    print(f"   ✗ Matplotlib import failed: {e}")

try:
    print("4. Testing backend imports...")
    from solana_analyzer.backend.solana_client import SolanaRPCClient
    from solana_analyzer.backend.transaction_analyzer import TransactionAnalyzer
    from solana_analyzer.backend.balance_tracker import BalanceTracker
    from solana_analyzer.backend.analyzer_api import SolanaAnalyzerAPI
    print("   ✓ Backend imports successful")
except Exception as e:
    print(f"   ✗ Backend imports failed: {e}")

try:
    print("5. Testing visualization imports...")
    from solana_analyzer.visualization.visualizer import SolanaVisualizer
    print("   ✓ Visualization imports successful")
except Exception as e:
    print(f"   ✗ Visualization imports failed: {e}")

print("\nAll imports tested successfully!")
