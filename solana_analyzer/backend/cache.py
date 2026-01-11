"""SQLite-based cache for transaction data"""
import sqlite3
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime


class TransactionCache:
    """SQLite-based cache for Solana transaction data"""

    def __init__(self, db_path: str = "data/solana_cache.db"):
        """
        Initialize transaction cache

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize_db()

    def _initialize_db(self):
        """Initialize database schema"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()

        # Signatures table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                signature TEXT NOT NULL UNIQUE,
                slot INTEGER,
                block_time INTEGER,
                err TEXT,
                memo TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_address_signature
            ON signatures (address, signature)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_block_time
            ON signatures (block_time)
        """)

        # Transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signature TEXT NOT NULL UNIQUE,
                address TEXT NOT NULL,
                slot INTEGER,
                block_time INTEGER,
                transaction_data TEXT NOT NULL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_signature
            ON transactions (signature)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_address_blocktime
            ON transactions (address, block_time)
        """)

        # Address metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS address_metadata (
                address TEXT PRIMARY KEY,
                total_transactions INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_signature TEXT,
                current_balances TEXT
            )
        """)

        self.conn.commit()

    def save_signatures(
        self,
        address: str,
        signatures: List[Dict[str, Any]]
    ):
        """
        Save transaction signatures

        Args:
            address: Solana address
            signatures: List of signature information
        """
        cursor = self.conn.cursor()

        for sig in signatures:
            try:
                # Convert error to string if present
                err_value = None
                if sig.get('err'):
                    try:
                        err_value = json.dumps(sig.get('err'))
                    except (TypeError, ValueError):
                        err_value = str(sig.get('err'))

                cursor.execute("""
                    INSERT OR IGNORE INTO signatures
                    (address, signature, slot, block_time, err, memo)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    address,
                    sig['signature'],
                    sig.get('slot'),
                    sig.get('block_time'),
                    err_value,
                    sig.get('memo')
                ))
            except sqlite3.IntegrityError:
                pass  # Signature already exists

        self.conn.commit()

    def save_transaction(
        self,
        address: str,
        signature: str,
        transaction_data: Dict[str, Any]
    ):
        """
        Save transaction details

        Args:
            address: Solana address
            signature: Transaction signature
            transaction_data: Full transaction data
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO transactions
                (signature, address, slot, block_time, transaction_data)
                VALUES (?, ?, ?, ?, ?)
            """, (
                signature,
                address,
                transaction_data.get('slot'),
                transaction_data.get('block_time'),
                json.dumps(transaction_data)
            ))
            self.conn.commit()
        except Exception as e:
            print(f"Error saving transaction {signature}: {e}")

    def get_cached_signatures(
        self,
        address: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get cached signatures for an address

        Args:
            address: Solana address
            limit: Maximum number of signatures to return

        Returns:
            List of signature dictionaries
        """
        cursor = self.conn.cursor()

        query = """
            SELECT signature, slot, block_time, err, memo
            FROM signatures
            WHERE address = ?
            ORDER BY block_time DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, (address,))

        results = []
        for row in cursor.fetchall():
            # Try to parse error as JSON, fallback to string
            err_value = None
            if row['err']:
                try:
                    err_value = json.loads(row['err'])
                except (json.JSONDecodeError, TypeError):
                    err_value = row['err']

            results.append({
                'signature': row['signature'],
                'slot': row['slot'],
                'block_time': row['block_time'],
                'err': err_value,
                'memo': row['memo']
            })

        return results

    def get_cached_transaction(
        self,
        signature: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached transaction details

        Args:
            signature: Transaction signature

        Returns:
            Transaction data or None if not cached
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT transaction_data
            FROM transactions
            WHERE signature = ?
        """, (signature,))

        row = cursor.fetchone()
        if row:
            return json.loads(row['transaction_data'])

        return None

    def get_cached_transactions(
        self,
        address: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all cached transactions for an address

        Args:
            address: Solana address
            limit: Maximum number of transactions to return

        Returns:
            List of transaction dictionaries
        """
        cursor = self.conn.cursor()

        query = """
            SELECT transaction_data
            FROM transactions
            WHERE address = ?
            ORDER BY block_time DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, (address,))

        results = []
        for row in cursor.fetchall():
            results.append(json.loads(row['transaction_data']))

        return results

    def update_address_metadata(
        self,
        address: str,
        total_transactions: int,
        last_signature: Optional[str] = None,
        current_balances: Optional[Dict[str, Any]] = None
    ):
        """
        Update address metadata

        Args:
            address: Solana address
            total_transactions: Total number of transactions
            last_signature: Most recent transaction signature
            current_balances: Current token balances
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO address_metadata
            (address, total_transactions, last_signature, current_balances, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            address,
            total_transactions,
            last_signature,
            json.dumps(current_balances) if current_balances else None
        ))

        self.conn.commit()

    def get_address_metadata(
        self,
        address: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get address metadata

        Args:
            address: Solana address

        Returns:
            Metadata dictionary or None if not found
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM address_metadata
            WHERE address = ?
        """, (address,))

        row = cursor.fetchone()
        if row:
            return {
                'address': row['address'],
                'total_transactions': row['total_transactions'],
                'last_signature': row['last_signature'],
                'current_balances': json.loads(row['current_balances']) if row['current_balances'] else None,
                'last_updated': row['last_updated']
            }

        return None

    def get_cache_stats(self, address: str) -> Dict[str, Any]:
        """
        Get cache statistics for an address

        Args:
            address: Solana address

        Returns:
            Statistics dictionary
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as sig_count
            FROM signatures
            WHERE address = ?
        """, (address,))
        sig_count = cursor.fetchone()['sig_count']

        cursor.execute("""
            SELECT COUNT(*) as tx_count
            FROM transactions
            WHERE address = ?
        """, (address,))
        tx_count = cursor.fetchone()['tx_count']

        metadata = self.get_address_metadata(address)

        return {
            'cached_signatures': sig_count,
            'cached_transactions': tx_count,
            'metadata': metadata
        }

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
