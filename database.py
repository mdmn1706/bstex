import sqlite3
from typing import Optional, List, Dict, Any, Tuple

DATABASE_PATH = "factory.db"

VALID_ROLES = [
    "Администратор",
    "Директор",
    "Менеджер",
    "Бухгалтер",
    "Мастер раскроя",
    "Мастер пошива",
    "Мастер упаковки",
    "Складчик",
]

# (username, code, role)
DEFAULT_SEED_ROLES = [
    ("Директор",        "1903", "Директор"),
    ("Администратор",   "3619", "Администратор"),
    ("Бухгалтер",       "0245", "Бухгалтер"),
    ("Менеджер",        "2141", "Менеджер"),
    ("Складчик",        "5502", "Складчик"),
    ("Мастер раскроя",  "0106", "Мастер раскроя"),
    ("Мастер пошива",   "2385", "Мастер пошива"),
    ("Мастер упаковки", "0906", "Мастер упаковки"),
]

DEFAULT_STAGES = [
    ("cutting", "Раскрой", "fas fa-cut", 1),
    ("sorting", "Сортировка", "fas fa-filter", 2),
    ("sewing", "Пошив", "fas fa-tshirt", 3),
    ("cleaning", "Чистка", "fas fa-broom", 4),
    ("ironing", "Глажка", "fas fa-thermometer-half", 5),
    ("control", "Контроль", "fas fa-check-double", 6),
    ("packing", "Упаковка", "fas fa-box", 7),
    ("finished", "Готовое изделие", "fas fa-check-circle", 8),
]

# Warehouse seeds (can be edited safely)
DEFAULT_WAREHOUSE_UNITS = [
    ("m", "Метры (м)"),
    ("kg", "Килограммы (кг)"),
    ("pcs", "Штуки (шт)"),
    ("roll", "Рулоны (рул)"),
]

DEFAULT_WAREHOUSE_LOCATIONS = [
    ("MAIN", "Основной склад", 1),
    ("CUTTING", "Раскрой", 2),
    ("SEWING", "Пошив", 3),
    ("PACKING", "Упаковка", 4),
    ("SCRAP", "Брак/Списание", 99),
]

DEFAULT_WAREHOUSE_PRODUCTS = [
    "Хлопковая ткань",
    "Шерстяная ткань",
    "Нить белая",
    "Нить чёрная",
    "Пуговицы",
    "Молнии",
    "Бейка",
    "Раскроенные детали",
]


class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.init_database()

    def update_user_role(self, user_id: int, role: str) -> bool:
        """Обновляет роль пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE users
                SET role = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (role, user_id),
            )

            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    # ================= CONNECTION =================

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    # ================= SCHEMA HELPERS =================

    def _table_columns(self, cursor: sqlite3.Cursor, table: str) -> List[str]:
        cursor.execute(f"PRAGMA table_info({table})")
        return [r["name"] for r in cursor.fetchall()]

    def _add_column_if_missing(self, cursor: sqlite3.Cursor, table: str, col: str, ddl: str) -> None:
        cols = set(self._table_columns(cursor, table))
        if col not in cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    # ================= INIT DATABASE =================

    def init_database(self) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()

        # ================= USERS =================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                access_code TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                success BOOLEAN,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # ================= FINANCE =================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_type TEXT NOT NULL,
                amount REAL NOT NULL,
                payment_type TEXT NOT NULL,
                order_ref TEXT,
                comment TEXT,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                payment_type TEXT NOT NULL,
                source TEXT NOT NULL,
                comment TEXT,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cash_balance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_amount REAL DEFAULT 0,
                account_amount REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ================= ORDERS =================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_code TEXT NOT NULL UNIQUE,
                model TEXT NOT NULL,
                client TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                order_date TEXT NOT NULL,
                shipment_date TEXT NOT NULL,
                currency TEXT NOT NULL,
                exchange_rate REAL,
                price_per_unit REAL NOT NULL,
                total_amount REAL NOT NULL,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'active',   -- active|done|cancelled
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                color TEXT NOT NULL,
                size TEXT NOT NULL,
                qty INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);")

        # ================= PRODUCTION STAGES =================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS production_stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stage_key TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                icon TEXT,
                sort_order INTEGER NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS order_stage_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                stage_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'not-started',
                progress INTEGER,
                note TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER,
                UNIQUE(order_id, stage_key),
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (updated_by) REFERENCES users(id),
                FOREIGN KEY (stage_key) REFERENCES production_stages(stage_key) ON DELETE CASCADE
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stage_order ON order_stage_status(order_id);")

        # ================= SERVICES (OUTSOURCED) =================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                factory_name TEXT NOT NULL,
                stage_from TEXT,
                stage_to TEXT,
                transfer_date TEXT NOT NULL,
                comment TEXT,
                total_qty INTEGER NOT NULL DEFAULT 0,
                total_amount REAL NOT NULL DEFAULT 0,
                expense_id INTEGER,
                created_by INTEGER,
                status TEXT NOT NULL DEFAULT 'active',                 -- active|pending|completed|cancelled
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (expense_id) REFERENCES expenses(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS service_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                color TEXT NOT NULL,
                size TEXT NOT NULL,
                qty INTEGER NOT NULL DEFAULT 0,
                unit_price REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_services_order ON services(order_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_items_service ON service_items(service_id);")

        # ================= SERVICE STAGES (NEW) =================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS service_stage_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                stage_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'not-started',
                progress INTEGER,
                note TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER,
                UNIQUE(service_id, stage_key),
                FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
                FOREIGN KEY (updated_by) REFERENCES users(id),
                FOREIGN KEY (stage_key) REFERENCES production_stages(stage_key) ON DELETE CASCADE
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_stage_service ON service_stage_status(service_id);")

        # ================= FULL WAREHOUSE (NEW) =================
        # Catalog
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_units (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_locations (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 100
            )
            """
        )

        # Journal header
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_txn (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                txn_type TEXT NOT NULL,             -- income|issue|transfer|writeoff|adjust
                order_id INTEGER,                   -- NULL means common stock
                from_location TEXT,
                to_location TEXT,
                reason TEXT,
                comment TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
                FOREIGN KEY (from_location) REFERENCES warehouse_locations(code),
                FOREIGN KEY (to_location) REFERENCES warehouse_locations(code),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
            """
        )

        # Journal lines
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_txn_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                txn_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                unit TEXT NOT NULL,
                qty REAL NOT NULL,                  -- always positive
                unit_cost REAL,
                line_comment TEXT,
                FOREIGN KEY (txn_id) REFERENCES warehouse_txn(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES warehouse_products(id),
                FOREIGN KEY (unit) REFERENCES warehouse_units(code)
            )
            """
        )

        # Current stock snapshot
        # order_id == 0 means "общий склад" (без заказа)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_stock (
                order_id INTEGER NOT NULL DEFAULT 0,
                location TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                unit TEXT NOT NULL,
                qty REAL NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (order_id, location, product_id, unit),
                FOREIGN KEY (location) REFERENCES warehouse_locations(code),
                FOREIGN KEY (product_id) REFERENCES warehouse_products(id),
                FOREIGN KEY (unit) REFERENCES warehouse_units(code)
            )
            """
        )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wh_txn_order ON warehouse_txn(order_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wh_txn_type ON warehouse_txn(txn_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wh_lines_txn ON warehouse_txn_lines(txn_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wh_stock_order ON warehouse_stock(order_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wh_stock_product ON warehouse_stock(product_id);")

        # ================= PRODUCTION WIP (NEW) =================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS production_wip_txn (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                txn_type TEXT NOT NULL,              -- create|transfer|grade|scrap|adjust
                from_stage TEXT,
                to_stage TEXT,
                comment TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (from_stage) REFERENCES production_stages(stage_key),
                FOREIGN KEY (to_stage) REFERENCES production_stages(stage_key),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS production_wip_txn_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                txn_id INTEGER NOT NULL,
                color TEXT NOT NULL,
                size TEXT NOT NULL,
                grade TEXT,                          -- NULL for ungraded, else '1'|'1.5'|'2'
                qty INTEGER NOT NULL,                -- always positive
                FOREIGN KEY (txn_id) REFERENCES production_wip_txn(id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS production_wip_stock (
                order_id INTEGER NOT NULL,
                stage_key TEXT NOT NULL,
                color TEXT NOT NULL,
                size TEXT NOT NULL,
                grade TEXT NOT NULL DEFAULT '',        -- '' for ungraded, '1'|'1.5'|'2' for graded
                qty INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (order_id, stage_key, color, size, grade),
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (stage_key) REFERENCES production_stages(stage_key) ON DELETE CASCADE
            )
            """
        )

        # Migration: clean up bad data from old code (NULL grade + duplicate rows)
        # Step 1: delete zero-qty rows first (they're useless)
        cursor.execute("DELETE FROM production_wip_stock WHERE qty <= 0")
        # Step 2: for rows where grade IS NULL, deduplicate keeping max qty before we rename NULL→''
        # (if there are multiple NULL-grade rows for the same order/stage/color/size, keep only the best)
        cursor.execute(
            """
            DELETE FROM production_wip_stock
            WHERE grade IS NULL
              AND rowid NOT IN (
                SELECT MAX(rowid)
                FROM production_wip_stock
                WHERE grade IS NULL
                GROUP BY order_id, stage_key, color, size
              )
            """
        )
        # Step 3: now safe to set NULL → ''
        cursor.execute("UPDATE production_wip_stock SET grade = '' WHERE grade IS NULL")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wip_stock_order_stage ON production_wip_stock(order_id, stage_key);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wip_txn_order ON production_wip_txn(order_id);")

        # ================= SOFT MIGRATIONS =================
        self._add_column_if_missing(cursor, "services", "status", "status TEXT NOT NULL DEFAULT 'active'")
        self._add_column_if_missing(cursor, "services", "updated_at", "updated_at TIMESTAMP")  # no default

        cursor.execute(
            """
            UPDATE services
            SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
            WHERE updated_at IS NULL
            """
        )

        conn.commit()
        conn.close()

        # seed/init
        self.seed_default_users()
        self._migrate_wrong_roles()   # fix "Рабочий" → correct roles
        self.init_cash_balance()
        self.seed_production_stages()
        self.seed_warehouse_catalog()

    # ================= USERS =================

    def seed_default_users(self) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM users")
        if int(cursor.fetchone()["count"] or 0) == 0:
            for username, code, role in DEFAULT_SEED_ROLES:
                self.create_user(username, code, role)
        conn.close()

    def _migrate_wrong_roles(self) -> None:
        """Исправляет старые роли ('Рабочий', 'Управляющий') на правильные."""
        # Маппинг: имя пользователя → правильная роль
        name_to_role = {
            "Директор":        "Директор",
            "Управляющий":     "Администратор",
            "Администратор":   "Администратор",
            "Бухгалтер":       "Бухгалтер",
            "Менеджер":        "Менеджер",
            "Складчик":        "Складчик",
            "Мастер раскроя":  "Мастер раскроя",
            "Мастер пошива":   "Мастер пошива",
            "Мастер упаковки": "Мастер упаковки",
        }
        conn = self.get_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in VALID_ROLES)
        cursor.execute(
            f"SELECT id, username, role FROM users WHERE role NOT IN ({placeholders})",
            VALID_ROLES
        )
        bad = cursor.fetchall()
        for u in bad:
            correct = name_to_role.get(u["username"])
            if not correct:
                # Угадываем по ключевым словам в имени
                uname = u["username"].lower()
                if "мастер пошива" in uname or "пошив" in uname:
                    correct = "Мастер пошива"
                elif "мастер раскроя" in uname or "раскрой" in uname:
                    correct = "Мастер раскроя"
                elif "мастер упаковки" in uname or "упаковк" in uname:
                    correct = "Мастер упаковки"
                elif "склад" in uname:
                    correct = "Складчик"
                elif "бухгалт" in uname:
                    correct = "Бухгалтер"
                elif "директор" in uname:
                    correct = "Директор"
                else:
                    correct = "Мастер пошива"   # fallback
            cursor.execute(
                "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (correct, u["id"])
            )
        if bad:
            conn.commit()
        conn.close()

    def _get_role_type(self, username: str) -> str:
        """Legacy — kept for compatibility."""
        return "Администратор"

    def create_user(self, username: str, access_code: str, role: str) -> bool:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, access_code, role) VALUES (?, ?, ?)",
                (username, access_code, role),
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    def authenticate_user(self, access_code: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, role, created_at, last_login FROM users WHERE access_code = ?",
            (access_code,),
        )
        user = cursor.fetchone()
        if user:
            cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
            conn.commit()
        conn.close()
        return dict(user) if user else None

    def get_all_users(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, username, access_code, role, created_at, last_login
            FROM users
            ORDER BY username
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, username, access_code, role, created_at, last_login
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_user(self,user_id: int, username: str = None, access_code: str = None, role: str = None) -> bool:
        """Обновляет данные пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            updates = []
            params: List[Any] = []

            if username is not None:
                updates.append("username = ?")
                params.append(username)

            if access_code is not None:
                updates.append("access_code = ?")
                params.append(access_code)

            if role is not None:  # ✨ НОВОЕ
                updates.append("role = ?")
                params.append(role)

            if not updates:
                conn.close()
                return True

            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)

            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)

            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False


    def delete_user(self, user_id: int) -> bool:
        """
        Удаляет пользователя. Перед удалением обнуляет все ссылки на него
        в связанных таблицах, чтобы не нарушать FOREIGN KEY constraint.
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # Все таблицы, которые ссылаются на users(id)
            refs = [
                ("login_logs",           "user_id"),
                ("expenses",             "user_id"),
                ("income",               "user_id"),
                ("orders",               "created_by"),
                ("order_stage_status",   "updated_by"),
                ("services",             "created_by"),
                ("service_stage_status", "updated_by"),
                ("warehouse_txn",        "created_by"),
                ("production_wip_txn",   "created_by"),
            ]
            for table, col in refs:
                try:
                    cursor.execute(
                        f"UPDATE {table} SET {col} = NULL WHERE {col} = ?",
                        (user_id,)
                    )
                except Exception:
                    pass  # таблица может ещё не существовать
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            return False

    def log_login_attempt(self, user_id: Optional[int], ip_address: str, success: bool) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO login_logs (user_id, ip_address, success) VALUES (?, ?, ?)",
            (user_id, ip_address, success),
        )
        conn.commit()
        conn.close()

    def get_user_stats(self) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM users")
        total = int(cursor.fetchone()["total"] or 0)
        cursor.execute("SELECT role, COUNT(*) AS count FROM users GROUP BY role")
        roles = {row["role"]: int(row["count"]) for row in cursor.fetchall()}
        conn.close()
        return {"total": total, "roles": roles}

    # ================= FINANCE =================

    def init_cash_balance(self) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM cash_balance")
        if int(cursor.fetchone()["count"] or 0) == 0:
            cursor.execute(
                "INSERT INTO cash_balance (cash_amount, account_amount) VALUES (?, ?)",
                (50000, 350000),
            )
            conn.commit()
        conn.close()

    def _update_cash_balance(self, cursor: sqlite3.Cursor, amount: float, payment_type: str) -> None:
        if payment_type == "cash":
            cursor.execute(
                """
                UPDATE cash_balance
                SET cash_amount = cash_amount + ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (amount,),
            )
        elif payment_type == "account":
            cursor.execute(
                """
                UPDATE cash_balance
                SET account_amount = account_amount + ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (amount,),
            )
        else:
            raise ValueError("payment_type должен быть 'cash' или 'account'")

    def add_expense(
        self,
        expense_type: str,
        amount: float,
        payment_type: str,
        order_ref: str = None,
        comment: str = None,
        user_id: int = None,
    ) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO expenses (expense_type, amount, payment_type, order_ref, comment, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (expense_type, amount, payment_type, order_ref, comment, user_id),
        )
        expense_id = int(cursor.lastrowid)
        self._update_cash_balance(cursor, -float(amount), payment_type)
        conn.commit()
        conn.close()
        return expense_id

    def get_all_expenses(self, limit: int = 100) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT e.*, u.username
            FROM expenses e
            LEFT JOIN users u ON e.user_id = u.id
            ORDER BY e.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def delete_expense(self, expense_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT amount, payment_type FROM expenses WHERE id = ?", (expense_id,))
        expense = cursor.fetchone()
        if not expense:
            conn.close()
            return False
        cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        self._update_cash_balance(cursor, float(expense["amount"]), expense["payment_type"])
        conn.commit()
        conn.close()
        return True

    def add_income(
        self,
        amount: float,
        payment_type: str,
        source: str,
        comment: str = None,
        user_id: int = None,
    ) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO income (amount, payment_type, source, comment, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (amount, payment_type, source, comment, user_id),
        )
        income_id = int(cursor.lastrowid)
        self._update_cash_balance(cursor, float(amount), payment_type)
        conn.commit()
        conn.close()
        return income_id

    def get_all_income(self, limit: int = 100) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT i.*, u.username
            FROM income i
            LEFT JOIN users u ON i.user_id = u.id
            ORDER BY i.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_cash_balance(self) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cash_amount, account_amount, updated_at FROM cash_balance WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {"cash": 0, "account": 0, "total": 0, "updated_at": None}
        cash = float(row["cash_amount"] or 0)
        account = float(row["account_amount"] or 0)
        return {"cash": cash, "account": account, "total": cash + account, "updated_at": row["updated_at"]}

    def get_financial_summary(self) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) AS total FROM expenses")
        total_expenses = float(cursor.fetchone()["total"] or 0)
        cursor.execute("SELECT SUM(amount) AS total FROM income")
        total_income = float(cursor.fetchone()["total"] or 0)
        conn.close()
        balance = self.get_cash_balance()
        return {
            "total_expenses": total_expenses,
            "total_income": total_income,
            "balance": balance,
            "profit": total_income - total_expenses,
        }

    # ================= ORDERS =================

    def create_order(
        self,
        order_code: str,
        model: str,
        client: str,
        order_date: str,
        shipment_date: str,
        currency: str,
        exchange_rate: Optional[float],
        price_per_unit: float,
        notes: Optional[str],
        items: List[Dict[str, Any]],
        created_by: Optional[int] = None,
    ) -> int:
        order_code = (order_code or "").strip()
        model = (model or "").strip()
        client = (client or "").strip()
        currency = (currency or "").strip()

        if not order_code:
            raise ValueError("Артикул заказа обязателен")
        if not model:
            raise ValueError("Модель обязательна")
        if not client:
            raise ValueError("Клиент обязателен")
        if currency not in ("UZS", "USD"):
            raise ValueError("Валюта должна быть UZS или USD")
        if float(price_per_unit) <= 0:
            raise ValueError("Цена за единицу должна быть больше 0")

        if currency == "USD":
            if exchange_rate is None or float(exchange_rate) <= 0:
                raise ValueError("Для USD требуется корректный курс доллара")
        else:
            exchange_rate = None

        clean_items: List[Tuple[str, str, int]] = []
        total_qty = 0
        for it in items or []:
            color = (it.get("color") or "").strip()
            size = (it.get("size") or "").strip()
            qty = int(it.get("qty") or 0)
            if not color or not size:
                continue
            if qty < 0:
                raise ValueError("Количество не может быть отрицательным")
            if qty == 0:
                continue
            clean_items.append((color, size, qty))
            total_qty += qty

        if total_qty <= 0:
            raise ValueError("Общее количество должно быть больше 0 (заполни таблицу цветов/размеров)")

        total_amount = float(total_qty) * float(price_per_unit)

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO orders (
                    order_code, model, client, quantity,
                    order_date, shipment_date,
                    currency, exchange_rate,
                    price_per_unit, total_amount,
                    notes, status, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    order_code,
                    model,
                    client,
                    total_qty,
                    order_date,
                    shipment_date,
                    currency,
                    exchange_rate,
                    float(price_per_unit),
                    total_amount,
                    notes,
                    created_by,
                ),
            )
            order_id = int(cursor.lastrowid)

            cursor.executemany(
                "INSERT INTO order_items (order_id, color, size, qty) VALUES (?, ?, ?, ?)",
                [(order_id, c, s, q) for (c, s, q) in clean_items],
            )

            self._init_order_stages(cursor, order_id, created_by)

            conn.commit()
            return order_id
        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise ValueError("Такой артикул заказа уже существует") from e
        finally:
            conn.close()

    def update_order_status(self, order_id: int, status: str, updated_by: Optional[int] = None) -> None:
        allowed = {"active", "done", "cancelled"}
        status = (status or "").strip()
        if status not in allowed:
            raise ValueError(f"Недопустимый статус заказа: {status}. Допустимые: {allowed}")
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, order_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Заказ не найден")
            conn.commit()
        finally:
            conn.close()

    def update_service_status(self, service_id: int, status: str, updated_by: Optional[int] = None) -> None:
        allowed = {"active", "pending", "completed", "cancelled"}
        status = (status or "").strip()
        if status not in allowed:
            raise ValueError(f"Недопустимый статус услуги: {status}. Допустимые: {allowed}")
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE services SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, service_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Услуга не найдена")
            conn.commit()
        finally:
            conn.close()

    def get_orders(self, limit: int = 200, status: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute(
                """
                SELECT o.*, u.username AS created_by_username
                FROM orders o
                LEFT JOIN users u ON o.created_by = u.id
                WHERE o.status = ?
                ORDER BY o.created_at DESC
                LIMIT ?
                """,
                (status, limit),
            )
        else:
            cursor.execute(
                """
                SELECT o.*, u.username AS created_by_username
                FROM orders o
                LEFT JOIN users u ON o.created_by = u.id
                ORDER BY o.created_at DESC
                LIMIT ?
                """,
                (limit,),
            )

        rows = [dict(r) for r in cursor.fetchall()]

        if rows:
            ids = [r["id"] for r in rows]
            placeholders = ",".join("?" * len(ids))
            cursor.execute(
                f"SELECT order_id, color, size, qty FROM order_items WHERE order_id IN ({placeholders}) ORDER BY order_id, color, size",
                ids,
            )
            items_by_order: dict = {}
            for item in cursor.fetchall():
                items_by_order.setdefault(item["order_id"], []).append(dict(item))
            for r in rows:
                r["items"] = items_by_order.get(r["id"], [])
        else:
            for r in rows:
                r["items"] = []

        conn.close()
        return rows

    def get_order_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT o.*, u.username AS created_by_username
            FROM orders o
            LEFT JOIN users u ON o.created_by = u.id
            WHERE o.id = ?
            """,
            (order_id,),
        )
        order = cursor.fetchone()
        if not order:
            conn.close()
            return None

        cursor.execute(
            """
            SELECT color, size, qty
            FROM order_items
            WHERE order_id = ?
            ORDER BY color, size
            """,
            (order_id,),
        )
        items = [dict(r) for r in cursor.fetchall()]

        conn.close()
        d = dict(order)
        d["items"] = items
        return d

    def get_order_options(self, status: str = "active", limit: int = 500, wip_stage: Optional[str] = None, prev_wip_stage: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        if wip_stage and prev_wip_stage:
            # Ўзида WIP бор (transfer_next учун) ЁКИ
            # олдинги этапда WIP бор ВА олдинги этап 'completed' ёки 'cutting' (топширилди) — accept учун
            # cutting учун статус текширмаймиз (submitCutResult статусни completed қилмайди)
            cursor.execute(
                """
                SELECT DISTINCT o.id, o.order_code, o.model, o.client
                FROM orders o
                WHERE o.status = ?
                  AND (
                    EXISTS (
                      SELECT 1 FROM production_wip_stock w
                      WHERE w.order_id = o.id AND w.stage_key = ? AND w.qty > 0
                    )
                    OR EXISTS (
                      SELECT 1 FROM production_wip_stock w
                      LEFT JOIN order_stage_status oss
                        ON oss.order_id = w.order_id AND oss.stage_key = w.stage_key
                      WHERE w.order_id = o.id
                        AND w.stage_key = ?
                        AND w.qty > 0
                        AND (w.stage_key = 'cutting' OR oss.status = 'completed')
                    )
                  )
                ORDER BY o.created_at DESC
                LIMIT ?
                """,
                (status, wip_stage, prev_wip_stage, limit),
            )
        elif wip_stage:
            cursor.execute(
                """
                SELECT DISTINCT o.id, o.order_code, o.model, o.client
                FROM orders o
                JOIN production_wip_stock w ON w.order_id = o.id
                WHERE o.status = ?
                  AND w.stage_key = ?
                  AND w.qty > 0
                ORDER BY o.created_at DESC
                LIMIT ?
                """,
                (status, wip_stage, limit),
            )
        else:
            cursor.execute(
                """
                SELECT id, order_code, model, client
                FROM orders
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status, limit),
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ================= STAGES =================

    def seed_production_stages(self) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS c FROM production_stages")
        if int(cursor.fetchone()["c"] or 0) == 0:
            cursor.executemany(
                "INSERT INTO production_stages (stage_key, name, icon, sort_order) VALUES (?, ?, ?, ?)",
                DEFAULT_STAGES,
            )
            conn.commit()
        conn.close()

    def get_production_stages(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT stage_key, name, icon, sort_order
            FROM production_stages
            ORDER BY sort_order
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _init_order_stages(self, cursor: sqlite3.Cursor, order_id: int, user_id: Optional[int]) -> None:
        cursor.execute("SELECT stage_key FROM production_stages ORDER BY sort_order")
        keys = [r["stage_key"] for r in cursor.fetchall()]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO order_stage_status (order_id, stage_key, status, progress, note, updated_by)
            VALUES (?, ?, 'not-started', NULL, NULL, ?)
            """,
            [(order_id, k, user_id) for k in keys],
        )

    def get_order_stages(self, order_id: int) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ps.stage_key, ps.name, ps.icon, ps.sort_order,
                   oss.status, oss.progress, oss.note, oss.updated_at,
                   u.username AS updated_by_username
            FROM production_stages ps
            LEFT JOIN order_stage_status oss
              ON oss.stage_key = ps.stage_key AND oss.order_id = ?
            LEFT JOIN users u ON u.id = oss.updated_by
            ORDER BY ps.sort_order
            """,
            (order_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_order_stage(
        self,
        order_id: int,
        stage_key: str,
        status: str,
        progress: Optional[int],
        note: Optional[str],
        updated_by: Optional[int],
    ) -> None:
        stage_key = (stage_key or "").strip()
        status = (status or "").strip()

        allowed = {"not-started", "in-progress", "completed", "delayed"}
        if status not in allowed:
            raise ValueError("Некорректный статус этапа")

        if progress is not None:
            progress = int(progress)
            if progress < 0 or progress > 100:
                raise ValueError("progress должен быть 0..100")

        note = (note or "").strip() or None

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO order_stage_status (order_id, stage_key, status, progress, note, updated_by)
            VALUES (?, ?, 'not-started', NULL, NULL, ?)
            """,
            (order_id, stage_key, updated_by),
        )

        cursor.execute(
            """
            UPDATE order_stage_status
            SET status = ?, progress = ?, note = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ? AND stage_key = ?
            """,
            (status, progress, note, updated_by, order_id, stage_key),
        )

        conn.commit()
        conn.close()

    # ================= SERVICES =================

    def _add_expense_in_tx(
        self,
        cursor: sqlite3.Cursor,
        expense_type: str,
        amount: float,
        payment_type: str,
        order_ref: Optional[str],
        comment: Optional[str],
        user_id: Optional[int],
    ) -> int:
        cursor.execute(
            """
            INSERT INTO expenses (expense_type, amount, payment_type, order_ref, comment, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (expense_type, float(amount), payment_type, order_ref, comment, user_id),
        )
        expense_id = int(cursor.lastrowid)
        self._update_cash_balance(cursor, -float(amount), payment_type)
        return expense_id

    def _init_service_stages(self, cursor: sqlite3.Cursor, service_id: int, user_id: Optional[int]) -> None:
        cursor.execute("SELECT stage_key FROM production_stages ORDER BY sort_order")
        keys = [r["stage_key"] for r in cursor.fetchall()]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO service_stage_status (service_id, stage_key, status, progress, note, updated_by)
            VALUES (?, ?, 'not-started', NULL, NULL, ?)
            """,
            [(service_id, k, user_id) for k in keys],
        )

    def create_service(
        self,
        order_id: int,
        factory_name: str,
        stage_from: str,
        stage_to: str,
        transfer_date: str,
        comment: Optional[str],
        items: List[Dict[str, Any]],
        created_by: Optional[int],
        create_expense: bool = True,
        expense_payment_type: str = "cash",
    ) -> int:
        factory_name = (factory_name or "").strip()
        stage_from = (stage_from or "").strip() or None
        stage_to = (stage_to or "").strip() or None
        transfer_date = (transfer_date or "").strip()
        comment = (comment or "").strip() or None

        if not int(order_id):
            raise ValueError("order_id обязателен")
        if not factory_name:
            raise ValueError("Название фабрики обязательно")
        if not transfer_date:
            raise ValueError("Дата передачи обязательна")

        clean_items: List[Tuple[str, str, int, float, float]] = []
        total_qty = 0
        total_amount = 0.0

        for it in items or []:
            color = (it.get("color") or "").strip()
            size = (it.get("size") or "").strip()
            qty = int(it.get("qty") or 0)
            unit_price = float(it.get("unit_price") or 0)

            if not color or not size:
                continue
            if qty <= 0:
                continue
            if unit_price < 0:
                raise ValueError("Цена не может быть отрицательной")

            line_total = float(qty) * float(unit_price)
            clean_items.append((color, size, qty, float(unit_price), line_total))
            total_qty += qty
            total_amount += line_total

        if total_qty <= 0:
            raise ValueError("Заполни таблицу товаров (количество > 0)")

        order = self.get_order_by_id(int(order_id))
        if not order:
            raise ValueError("Заказ не найден")

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            expense_id = None
            if create_expense:
                expense_comment = f"Услуга: {factory_name}. {comment or ''}".strip()
                expense_id = self._add_expense_in_tx(
                    cursor=cursor,
                    expense_type="Услуга (внешняя фабрика)",
                    amount=total_amount,
                    payment_type=expense_payment_type,
                    order_ref=order["order_code"],
                    comment=expense_comment,
                    user_id=created_by,
                )

            cursor.execute(
                """
                INSERT INTO services (
                    order_id, factory_name, stage_from, stage_to, transfer_date,
                    comment, total_qty, total_amount, expense_id, created_by,
                    status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    int(order_id),
                    factory_name,
                    stage_from,
                    stage_to,
                    transfer_date,
                    comment,
                    int(total_qty),
                    float(total_amount),
                    expense_id,
                    created_by,
                ),
            )
            service_id = int(cursor.lastrowid)

            cursor.executemany(
                """
                INSERT INTO service_items (service_id, color, size, qty, unit_price, total)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [(service_id, c, s, q, up, t) for (c, s, q, up, t) in clean_items],
            )

            self._init_service_stages(cursor, service_id, created_by)

            conn.commit()
            return service_id

        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise ValueError("Ошибка сохранения услуги") from e
        finally:
            conn.close()

    def get_services(
        self,
        limit: int = 300,
        offset: int = 0,
        status: Optional[str] = None,
        q: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        limit = int(limit or 300)
        offset = int(offset or 0)

        where = []
        params: List[Any] = []

        if status:
            where.append("s.status = ?")
            params.append(status)

        if q:
            qq = f"%{q.strip()}%"
            where.append("(o.order_code LIKE ? OR s.factory_name LIKE ? OR CAST(s.id AS TEXT) LIKE ?)")
            params.extend([qq, qq, qq])

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT
                s.id,
                s.order_id,
                s.factory_name,
                s.stage_from,
                s.stage_to,
                s.transfer_date,
                s.comment,
                s.total_qty,
                s.total_amount,
                s.status,
                s.created_at,
                s.updated_at,
                o.order_code,
                o.currency,
                u.username AS created_by_username
            FROM services s
            JOIN orders o ON o.id = s.order_id
            LEFT JOIN users u ON u.id = s.created_by
            {where_sql}
            ORDER BY s.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        for r in rows:
            r["service_code"] = f"SERV-{int(r['id']):06d}"
        return rows

    def get_service_by_id(self, service_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                s.*,
                o.order_code,
                o.currency,
                u.username AS created_by_username
            FROM services s
            JOIN orders o ON o.id = s.order_id
            LEFT JOIN users u ON u.id = s.created_by
            WHERE s.id = ?
            """,
            (service_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        d["service_code"] = f"SERV-{int(d['id']):06d}"
        return d

    def get_service_items(self, service_id: int) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT color, size, qty, unit_price, total
            FROM service_items
            WHERE service_id = ?
            ORDER BY color, size
            """,
            (service_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_service_stages(self, service_id: int) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                ps.stage_key, ps.name, ps.icon, ps.sort_order,
                sss.status, sss.progress, sss.note, sss.updated_at,
                u.username AS updated_by_username
            FROM production_stages ps
            LEFT JOIN service_stage_status sss
              ON sss.stage_key = ps.stage_key AND sss.service_id = ?
            LEFT JOIN users u ON u.id = sss.updated_by
            ORDER BY ps.sort_order
            """,
            (service_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_service_stage(
        self,
        service_id: int,
        stage_key: str,
        status: str,
        progress: Optional[int],
        note: Optional[str],
        updated_by: Optional[int],
    ) -> None:
        stage_key = (stage_key or "").strip()
        status = (status or "").strip()

        allowed = {"not-started", "in-progress", "completed", "delayed"}
        if status not in allowed:
            raise ValueError("Некорректный статус этапа")

        if progress is not None:
            progress = int(progress)
            if progress < 0 or progress > 100:
                raise ValueError("progress должен быть 0..100")

        note = (note or "").strip() or None

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO service_stage_status (service_id, stage_key, status, progress, note, updated_by)
            VALUES (?, ?, 'not-started', NULL, NULL, ?)
            """,
            (service_id, stage_key, updated_by),
        )

        cursor.execute(
            """
            UPDATE service_stage_status
            SET status = ?, progress = ?, note = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE service_id = ? AND stage_key = ?
            """,
            (status, progress, note, updated_by, service_id, stage_key),
        )

        cursor.execute("UPDATE services SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (service_id,))

        conn.commit()
        conn.close()

    # ================= WAREHOUSE (FULL) =================

    def seed_warehouse_catalog(self) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()

        for code, name in DEFAULT_WAREHOUSE_UNITS:
            cursor.execute(
                """
                INSERT INTO warehouse_units(code, name)
                VALUES(?,?)
                ON CONFLICT(code) DO UPDATE SET name=excluded.name
                """,
                (code, name),
            )

        for code, name, sort_order in DEFAULT_WAREHOUSE_LOCATIONS:
            cursor.execute(
                """
                INSERT INTO warehouse_locations(code, name, active, sort_order)
                VALUES(?,?,1,?)
                ON CONFLICT(code) DO UPDATE SET name=excluded.name, active=1, sort_order=excluded.sort_order
                """,
                (code, name, sort_order),
            )

        for pname in DEFAULT_WAREHOUSE_PRODUCTS:
            cursor.execute("INSERT OR IGNORE INTO warehouse_products(name, active) VALUES(?,1)", (pname,))

        conn.commit()
        conn.close()

    def create_warehouse_product(self, name: str) -> Dict[str, Any]:
        """Создаёт новый товар в каталоге склада (или возвращает существующий)."""
        name = (name or "").strip()
        if not name:
            raise ValueError("Название товара не может быть пустым")
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Check existing (case-insensitive)
            cursor.execute("SELECT id, name, active FROM warehouse_products WHERE LOWER(name) = LOWER(?)", (name,))
            existing = cursor.fetchone()
            if existing:
                if not existing["active"]:
                    cursor.execute("UPDATE warehouse_products SET active=1 WHERE id=?", (existing["id"],))
                    conn.commit()
                conn.close()
                return {"id": existing["id"], "name": existing["name"], "created": False}
            cursor.execute("INSERT INTO warehouse_products(name, active) VALUES(?, 1)", (name,))
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return {"id": new_id, "name": name, "created": True}
        except Exception:
            conn.rollback()
            conn.close()
            raise

    def get_warehouse_catalog(self) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()

        # Only return products that have been actually used (have stock or transaction history)
        cursor.execute("""
            SELECT DISTINCT p.id, p.name
            FROM warehouse_products p
            WHERE p.active = 1
              AND (
                EXISTS (SELECT 1 FROM warehouse_stock s WHERE s.product_id = p.id)
                OR EXISTS (SELECT 1 FROM warehouse_txn_lines l WHERE l.product_id = p.id)
              )
            ORDER BY p.name
        """)
        products = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT code, name FROM warehouse_units ORDER BY code")
        units = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT code, name FROM warehouse_locations WHERE active=1 ORDER BY sort_order, code")
        locations = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return {"products": products, "units": units, "locations": locations}

    def _wh_stock_get(self, cursor: sqlite3.Cursor, order_id: int, location: str, product_id: int, unit: str) -> float:
        cursor.execute(
            """
            SELECT qty
            FROM warehouse_stock
            WHERE order_id=? AND location=? AND product_id=? AND unit=?
            """,
            (order_id, location, product_id, unit),
        )
        r = cursor.fetchone()
        return float(r["qty"]) if r else 0.0

    def _wh_stock_set(self, cursor: sqlite3.Cursor, order_id: int, location: str, product_id: int, unit: str, qty: float) -> None:
        cursor.execute(
            """
            INSERT INTO warehouse_stock(order_id, location, product_id, unit, qty, updated_at)
            VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(order_id, location, product_id, unit) DO UPDATE SET
              qty=excluded.qty,
              updated_at=CURRENT_TIMESTAMP
            """,
            (order_id, location, product_id, unit, float(qty)),
        )

    def warehouse_create_txn(
        self,
        txn_type: str,
        order_id: Optional[int],
        from_location: Optional[str],
        to_location: Optional[str],
        reason: Optional[str],
        comment: Optional[str],
        lines: List[Dict[str, Any]],
        created_by: Optional[int] = None,
        allow_negative: bool = False,
    ) -> int:
        """
        txn_type: income|issue|transfer|writeoff|adjust
        lines: [{product_id:int, unit:str, qty:float (>0), unit_cost?:float, line_comment?:str}]
        adjust: qty treated as ABS delta; sign controlled by 'reason':
          reason in {'decrease','minus','down','уменьшение'} => subtract, else add.
        """
        txn_type = (txn_type or "").strip()
        if txn_type not in {"income", "issue", "transfer", "writeoff", "adjust"}:
            raise ValueError("Некорректный txn_type")

        if not isinstance(lines, list) or not lines:
            raise ValueError("lines обязательны")

        ord_id = int(order_id) if order_id not in (None, "", "null") else 0

        # defaults / validation
        if txn_type == "income":
            if not to_location:
                to_location = "MAIN"
        elif txn_type == "issue":
            if not from_location:
                from_location = "MAIN"
        elif txn_type == "transfer":
            if not from_location or not to_location:
                raise ValueError("Для transfer нужны from_location и to_location")
        elif txn_type == "writeoff":
            if not from_location:
                from_location = "MAIN"
            if not to_location:
                to_location = "SCRAP"
        elif txn_type == "adjust":
            if not from_location and not to_location:
                from_location = "MAIN"

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO warehouse_txn(txn_type, order_id, from_location, to_location, reason, comment, created_by)
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    txn_type,
                    None if ord_id == 0 else ord_id,
                    from_location,
                    to_location,
                    reason,
                    comment,
                    created_by,
                ),
            )
            txn_id = int(cursor.lastrowid)

            # write lines
            for ln in lines:
                product_id = int(ln.get("product_id") or 0)
                unit = (ln.get("unit") or "").strip()
                qty = float(ln.get("qty") or 0)

                if product_id <= 0:
                    raise ValueError("product_id обязателен")
                if not unit:
                    raise ValueError("unit обязателен")
                if qty <= 0:
                    raise ValueError("qty должен быть > 0")

                unit_cost = ln.get("unit_cost", None)
                line_comment = ln.get("line_comment", None)

                cursor.execute(
                    """
                    INSERT INTO warehouse_txn_lines(txn_id, product_id, unit, qty, unit_cost, line_comment)
                    VALUES(?,?,?,?,?,?)
                    """,
                    (txn_id, product_id, unit, qty, unit_cost, line_comment),
                )

            # apply stock
            for ln in lines:
                product_id = int(ln["product_id"])
                unit = str(ln["unit"]).strip()
                qty = float(ln["qty"])

                if txn_type == "income":
                    loc = str(to_location)
                    prev = self._wh_stock_get(cursor, ord_id, loc, product_id, unit)
                    self._wh_stock_set(cursor, ord_id, loc, product_id, unit, prev + qty)

                elif txn_type == "issue":
                    loc = str(from_location)
                    prev = self._wh_stock_get(cursor, ord_id, loc, product_id, unit)
                    if prev - qty < -1e-9 and not allow_negative:
                        raise ValueError("Недостаточно остатка для расхода")
                    self._wh_stock_set(cursor, ord_id, loc, product_id, unit, prev - qty)

                elif txn_type == "transfer":
                    loc_from = str(from_location)
                    loc_to = str(to_location)
                    prev_from = self._wh_stock_get(cursor, ord_id, loc_from, product_id, unit)
                    if prev_from - qty < -1e-9 and not allow_negative:
                        raise ValueError("Недостаточно остатка для перемещения")
                    self._wh_stock_set(cursor, ord_id, loc_from, product_id, unit, prev_from - qty)

                    prev_to = self._wh_stock_get(cursor, ord_id, loc_to, product_id, unit)
                    self._wh_stock_set(cursor, ord_id, loc_to, product_id, unit, prev_to + qty)

                elif txn_type == "writeoff":
                    loc_from = str(from_location or "MAIN")
                    loc_to = str(to_location or "SCRAP")

                    prev_from = self._wh_stock_get(cursor, ord_id, loc_from, product_id, unit)
                    if prev_from - qty < -1e-9 and not allow_negative:
                        raise ValueError("Недостаточно остатка для списания")
                    self._wh_stock_set(cursor, ord_id, loc_from, product_id, unit, prev_from - qty)

                    prev_to = self._wh_stock_get(cursor, ord_id, loc_to, product_id, unit)
                    self._wh_stock_set(cursor, ord_id, loc_to, product_id, unit, prev_to + qty)

                elif txn_type == "adjust":
                    loc = str(from_location or to_location or "MAIN")
                    direction = (reason or "").lower().strip()
                    sign = -1.0 if direction in {"decrease", "minus", "down", "уменьшение"} else 1.0
                    prev = self._wh_stock_get(cursor, ord_id, loc, product_id, unit)
                    new_qty = prev + sign * qty
                    if new_qty < -1e-9 and not allow_negative:
                        raise ValueError("Корректировка приводит к отрицательному остатку")
                    self._wh_stock_set(cursor, ord_id, loc, product_id, unit, new_qty)

            conn.commit()
            return txn_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # Convenience: compatible with your warehouse.html income form
    def warehouse_income(
        self,
        order_id: int,
        product_id: int,
        qty: float,
        unit: str,
        to_location: str = "MAIN",
        comment: Optional[str] = None,
        created_by: Optional[int] = None,
    ) -> int:
        return self.warehouse_create_txn(
            txn_type="income",
            order_id=int(order_id),
            from_location=None,
            to_location=to_location,
            reason="income",
            comment=comment,
            lines=[{"product_id": int(product_id), "unit": unit, "qty": float(qty)}],
            created_by=created_by,
        )

    def get_warehouse_stock_by_order(self, order_id: int, location: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()

        if location:
            cursor.execute(
                """
                SELECT p.name AS product_name, s.unit AS unit, SUM(s.qty) AS qty
                FROM warehouse_stock s
                JOIN warehouse_products p ON p.id = s.product_id
                WHERE s.order_id = ? AND s.location = ?
                GROUP BY p.name, s.unit
                HAVING ABS(SUM(s.qty)) > 1e-9
                ORDER BY p.name, s.unit
                """,
                (int(order_id), location),
            )
        else:
            cursor.execute(
                """
                SELECT p.name AS product_name, s.unit AS unit, SUM(s.qty) AS qty
                FROM warehouse_stock s
                JOIN warehouse_products p ON p.id = s.product_id
                WHERE s.order_id = ? AND s.location <> 'SCRAP'
                GROUP BY p.name, s.unit
                HAVING ABS(SUM(s.qty)) > 1e-9
                ORDER BY p.name, s.unit
                """,
                (int(order_id),),
            )

        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        for r in rows:
            r["qty"] = float(r["qty"])
        return rows

    def get_warehouse_stock_all(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()

        # Показываем только остаток на главном складе (MAIN)
        cursor.execute(
            """
            SELECT
              s.product_id,
              p.name AS product_name,
              s.unit,
              SUM(s.qty) AS qty
            FROM warehouse_stock s
            JOIN warehouse_products p ON p.id = s.product_id
            WHERE s.location = 'MAIN'
            GROUP BY s.product_id, p.name, s.unit
            HAVING ABS(SUM(s.qty)) > 1e-9
            ORDER BY p.name, s.unit
            """
        )
        totals = [dict(r) for r in cursor.fetchall()]

        result: List[Dict[str, Any]] = []
        for t in totals:
            product_id = int(t["product_id"])
            unit = str(t["unit"])

            cursor.execute(
                """
                SELECT
                  s.order_id,
                  o.order_code,
                  SUM(s.qty) AS qty
                FROM warehouse_stock s
                LEFT JOIN orders o ON o.id = s.order_id
                WHERE s.location = 'MAIN'
                  AND s.product_id = ?
                  AND s.unit = ?
                  AND s.order_id <> 0
                GROUP BY s.order_id, o.order_code
                HAVING ABS(SUM(s.qty)) > 1e-9
                ORDER BY o.order_code
                """,
                (product_id, unit),
            )
            orders = []
            for r in cursor.fetchall():
                orders.append(
                    {
                        "order_id": int(r["order_id"]),
                        "order_code": r["order_code"] or f"#{int(r['order_id'])}",
                        "qty": float(r["qty"]),
                    }
                )

            # Брак (SCRAP) по этому товару
            cursor.execute(
                """
                SELECT COALESCE(SUM(qty), 0) AS scrap_qty
                FROM warehouse_stock
                WHERE location = 'SCRAP'
                  AND product_id = ?
                  AND unit = ?
                """,
                (product_id, unit),
            )
            scrap_row = cursor.fetchone()
            scrap_qty = float(scrap_row["scrap_qty"]) if scrap_row else 0.0

            result.append(
                {
                    "product_name": t["product_name"],
                    "unit": t["unit"],
                    "qty": float(t["qty"]),
                    "scrap_qty": scrap_qty,
                    "orders": orders,
                }
            )

        # Товары у которых есть только брак (qty=0 в MAIN, но есть в SCRAP)
        cursor.execute(
            """
            SELECT
              s.product_id,
              p.name AS product_name,
              s.unit,
              SUM(s.qty) AS scrap_qty
            FROM warehouse_stock s
            JOIN warehouse_products p ON p.id = s.product_id
            WHERE s.location = 'SCRAP'
            GROUP BY s.product_id, p.name, s.unit
            HAVING ABS(SUM(s.qty)) > 1e-9
            ORDER BY p.name, s.unit
            """
        )
        scrap_only = [dict(r) for r in cursor.fetchall()]
        existing = {(r["product_name"], r["unit"]) for r in result}
        for s in scrap_only:
            if (s["product_name"], s["unit"]) not in existing:
                result.append(
                    {
                        "product_name": s["product_name"],
                        "unit": s["unit"],
                        "qty": 0.0,
                        "scrap_qty": float(s["scrap_qty"]),
                        "orders": [],
                    }
                )

        conn.close()
        return result

    def get_production_stock(self) -> List[Dict[str, Any]]:
        """Остатки товаров в производстве (CUTTING, SEWING, PACKING) по этапам"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
              s.product_id,
              p.name AS product_name,
              s.unit,
              s.location,
              s.order_id,
              o.order_code,
              SUM(s.qty) AS qty
            FROM warehouse_stock s
            JOIN warehouse_products p ON p.id = s.product_id
            LEFT JOIN orders o ON o.id = s.order_id
            WHERE s.location IN ('CUTTING', 'SEWING', 'PACKING')
              AND s.order_id <> 0
            GROUP BY s.product_id, p.name, s.unit, s.location, s.order_id
            HAVING ABS(SUM(s.qty)) > 1e-9
            ORDER BY p.name, s.location, o.order_code
            """
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        for r in rows:
            r["qty"] = float(r["qty"])
        return rows

    def get_warehouse_txn_list(
        self,
        order_id: Optional[int] = None,
        txn_type: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()

        where = []
        params: List[Any] = []
        if order_id is not None:
            where.append("t.order_id = ?")
            params.append(int(order_id))
        if txn_type:
            where.append("t.txn_type = ?")
            params.append(txn_type)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        cursor.execute(
            f"""
            SELECT t.*
            FROM warehouse_txn t
            {where_sql}
            ORDER BY t.created_at DESC, t.id DESC
            LIMIT ?
            """,
            (*params, int(limit)),
        )
        txns = [dict(r) for r in cursor.fetchall()]

        for t in txns:
            cursor.execute(
                """
                SELECT l.*, p.name AS product_name
                FROM warehouse_txn_lines l
                JOIN warehouse_products p ON p.id = l.product_id
                WHERE l.txn_id = ?
                ORDER BY l.id
                """,
                (int(t["id"]),),
            )
            t["lines"] = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return txns

    # ================= WIP HELPERS =================

    def _wip_get(self, cursor: sqlite3.Cursor, order_id: int, stage_key: str, color: str, size: str, grade: Optional[str]) -> int:
        g = grade if grade is not None else ''
        cursor.execute(
            """
            SELECT qty FROM production_wip_stock
            WHERE order_id=? AND stage_key=? AND color=? AND size=? AND grade=?
            """,
            (order_id, stage_key, color, size, g),
        )
        r = cursor.fetchone()
        return int(r["qty"]) if r else 0

    def _wip_set(self, cursor: sqlite3.Cursor, order_id: int, stage_key: str, color: str, size: str, grade: Optional[str], qty: int) -> None:
        g = grade if grade is not None else ''
        cursor.execute(
            """
            INSERT INTO production_wip_stock(order_id, stage_key, color, size, grade, qty, updated_at)
            VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(order_id, stage_key, color, size, grade) DO UPDATE SET
              qty=excluded.qty, updated_at=CURRENT_TIMESTAMP
            """,
            (order_id, stage_key, color, size, g, int(qty)),
        )

    def wip_get_stage(self, order_id: int, stage_key: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT color, size,
                   CASE WHEN grade = '' THEN NULL ELSE grade END AS grade,
                   qty
            FROM production_wip_stock
            WHERE order_id=? AND stage_key=? AND qty > 0
            ORDER BY color, size, grade
            """,
            (int(order_id), stage_key),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        for r in rows:
            r["qty"] = int(r["qty"])
        return rows

    def wip_create_or_add(self, order_id: int, stage_key: str, lines: List[Dict[str, Any]], comment: Optional[str], created_by: Optional[int]) -> int:
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO production_wip_txn(order_id, txn_type, from_stage, to_stage, comment, created_by)
                VALUES(?, 'create', NULL, ?, ?, ?)
                """,
                (int(order_id), stage_key, comment, created_by),
            )
            txn_id = int(cur.lastrowid)

            for ln in lines:
                color = (ln.get("color") or "").strip()
                size = (ln.get("size") or "").strip()
                qty = int(ln.get("qty") or 0)
                if not color or not size or qty <= 0:
                    continue
                cur.execute(
                    """
                    INSERT INTO production_wip_txn_lines(txn_id, color, size, grade, qty)
                    VALUES(?,?,?,?,?)
                    """,
                    (txn_id, color, size, None, qty),
                )
                prev = self._wip_get(cur, int(order_id), stage_key, color, size, None)
                self._wip_set(cur, int(order_id), stage_key, color, size, None, prev + qty)

            conn.commit()
            return txn_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def wip_transfer(
        self,
        order_id: int,
        from_stage: str,
        to_stage: str,
        lines: List[Dict[str, Any]],
        comment: Optional[str],
        created_by: Optional[int],
    ) -> int:
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO production_wip_txn(order_id, txn_type, from_stage, to_stage, comment, created_by)
                VALUES(?, 'transfer', ?, ?, ?, ?)
                """,
                (int(order_id), from_stage, to_stage, (comment or "").strip() or None, created_by),
            )
            txn_id = int(cur.lastrowid)

            for ln in lines:
                color = (ln.get("color") or "").strip()
                size = (ln.get("size") or "").strip()
                grade = (ln.get("grade") or None)
                qty = int(ln.get("qty") or 0)

                if not color or not size or qty <= 0:
                    continue

                cur.execute(
                    "INSERT INTO production_wip_txn_lines(txn_id, color, size, grade, qty) VALUES(?,?,?,?,?)",
                    (txn_id, color, size, grade, qty),
                )

                prev_from = self._wip_get(cur, int(order_id), from_stage, color, size, grade)
                if prev_from - qty < 0:
                    raise ValueError(
                        f"Недостаточно WIP на этапе {from_stage}: {color}/{size} grade={grade} "
                        f"(нужно {qty}, есть {prev_from})"
                    )
                self._wip_set(cur, int(order_id), from_stage, color, size, grade, prev_from - qty)

                prev_to = self._wip_get(cur, int(order_id), to_stage, color, size, grade)
                self._wip_set(cur, int(order_id), to_stage, color, size, grade, prev_to + qty)

            conn.commit()
            return txn_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def wip_grade_to_packing(
        self,
        order_id: int,
        lines: List[Dict[str, Any]],
        comment: Optional[str],
        created_by: Optional[int],
    ) -> int:
        """
        lines: [{color,size,total,g1,g15,g2}]
        Consumes from 'control' ungraded and puts into 'packing' graded.
        """
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO production_wip_txn(order_id, txn_type, from_stage, to_stage, comment, created_by)
                VALUES(?, 'grade', 'control', 'packing', ?, ?)
                """,
                (int(order_id), (comment or "").strip() or None, created_by),
            )
            txn_id = int(cur.lastrowid)

            for ln in lines:
                color = (ln.get("color") or "").strip()
                size = (ln.get("size") or "").strip()
                total = int(ln.get("total") or 0)
                g1 = int(ln.get("g1") or 0)
                g15 = int(ln.get("g15") or 0)
                g2 = int(ln.get("g2") or 0)

                if not color or not size:
                    continue
                if total <= 0:
                    continue
                if g1 + g15 + g2 != total:
                    raise ValueError(f"Сумма сортов не равна total для {color}/{size}")

                prev_control = self._wip_get(cur, int(order_id), "control", color, size, None)
                if prev_control - total < 0:
                    raise ValueError(f"Недостаточно на контроле {color}/{size}: нужно {total}, есть {prev_control}")
                self._wip_set(cur, int(order_id), "control", color, size, None, prev_control - total)

                for grade, qty in [("1", g1), ("1.5", g15), ("2", g2)]:
                    if qty <= 0:
                        continue
                    cur.execute(
                        "INSERT INTO production_wip_txn_lines(txn_id, color, size, grade, qty) VALUES(?,?,?,?,?)",
                        (txn_id, color, size, grade, qty),
                    )
                    prev_pack = self._wip_get(cur, int(order_id), "packing", color, size, grade)
                    self._wip_set(cur, int(order_id), "packing", color, size, grade, prev_pack + qty)

            conn.commit()
            return txn_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def wip_scrap(
        self,
        order_id: int,
        stage_key: str,
        lines: List[Dict[str, Any]],
        comment: Optional[str],
        created_by: Optional[int],
    ) -> int:
        """
        списывает WIP с этапа (в брак). grade опционален.
        lines: [{color,size,grade?,qty}]
        """
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO production_wip_txn(order_id, txn_type, from_stage, to_stage, comment, created_by)
                VALUES(?, 'scrap', ?, NULL, ?, ?)
                """,
                (int(order_id), stage_key, (comment or "").strip() or None, created_by),
            )
            txn_id = int(cur.lastrowid)

            for ln in lines:
                color = (ln.get("color") or "").strip()
                size = (ln.get("size") or "").strip()
                grade = (ln.get("grade") or None)
                qty = int(ln.get("qty") or 0)
                if not color or not size or qty <= 0:
                    continue

                cur.execute(
                    "INSERT INTO production_wip_txn_lines(txn_id, color, size, grade, qty) VALUES(?,?,?,?,?)",
                    (txn_id, color, size, grade, qty),
                )

                prev = self._wip_get(cur, int(order_id), stage_key, color, size, grade)
                if prev - qty < 0:
                    raise ValueError(f"Недостаточно для списания на этапе {stage_key}: {color}/{size} нужно {qty}, есть {prev}")
                self._wip_set(cur, int(order_id), stage_key, color, size, grade, prev - qty)

            conn.commit()
            return txn_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def wip_txn_list(self, order_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.*, u.username AS created_by_username
            FROM production_wip_txn t
            LEFT JOIN users u ON u.id = t.created_by
            WHERE t.order_id=?
            ORDER BY t.created_at DESC, t.id DESC
            LIMIT ?
            """,
            (int(order_id), int(limit)),
        )
        txns = [dict(r) for r in cur.fetchall()]
        for t in txns:
            cur.execute(
                """
                SELECT color, size, grade, qty
                FROM production_wip_txn_lines
                WHERE txn_id=?
                ORDER BY color, size, grade
                """,
                (int(t["id"]),),
            )
            t["lines"] = [dict(r) for r in cur.fetchall()]
        conn.close()
        return txns


    # ================= ORDER FULL DETAIL =================

    def get_order_full_detail(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Полная информация о заказе: данные, позиции, этапы, WIP, склад, расходы, услуги"""
        conn = self.get_connection()
        cur = conn.cursor()

        # Base order
        cur.execute("""
            SELECT o.*, u.username AS created_by_username
            FROM orders o
            LEFT JOIN users u ON u.id = o.created_by
            WHERE o.id = ?
        """, (order_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        order = dict(row)

        # Items (color/size breakdown)
        cur.execute("""
            SELECT color, size, qty FROM order_items WHERE order_id = ?
            ORDER BY color, size
        """, (order_id,))
        order['items'] = [dict(r) for r in cur.fetchall()]

        # Production stages
        cur.execute("""
            SELECT ps.stage_key, ps.name, ps.icon, ps.sort_order,
                   oss.status, oss.progress, oss.note, oss.updated_at,
                   u.username AS updated_by_username
            FROM production_stages ps
            LEFT JOIN order_stage_status oss
              ON oss.stage_key = ps.stage_key AND oss.order_id = ?
            LEFT JOIN users u ON u.id = oss.updated_by
            ORDER BY ps.sort_order
        """, (order_id,))
        order['stages'] = [dict(r) for r in cur.fetchall()]

        # WIP current stock by stage
        cur.execute("""
            SELECT stage_key, color, size,
                   CASE WHEN grade='' THEN NULL ELSE grade END AS grade,
                   qty
            FROM production_wip_stock
            WHERE order_id = ? AND qty > 0
            ORDER BY stage_key, color, size, grade
        """, (order_id,))
        wip_rows = [dict(r) for r in cur.fetchall()]
        wip_by_stage: Dict[str, List] = {}
        for r in wip_rows:
            wip_by_stage.setdefault(r['stage_key'], []).append(r)
        order['wip_by_stage'] = wip_by_stage
        order['wip_total'] = sum(int(r['qty']) for r in wip_rows)

        # WIP transactions (movement history)
        cur.execute("""
            SELECT t.id, t.txn_type, t.from_stage, t.to_stage, t.comment, t.created_at,
                   u.username AS created_by_username
            FROM production_wip_txn t
            LEFT JOIN users u ON u.id = t.created_by
            WHERE t.order_id = ?
            ORDER BY t.created_at DESC LIMIT 50
        """, (order_id,))
        wip_txns = [dict(r) for r in cur.fetchall()]
        for t in wip_txns:
            cur.execute("""
                SELECT color, size, grade, qty
                FROM production_wip_txn_lines WHERE txn_id = ?
                ORDER BY color, size
            """, (t['id'],))
            t['lines'] = [dict(r) for r in cur.fetchall()]
            t['total_qty'] = sum(int(l['qty']) for l in t['lines'])
        order['wip_history'] = wip_txns

        # Warehouse stock for this order
        cur.execute("""
            SELECT wl.name AS location_name, p.name AS product_name,
                   s.unit, SUM(s.qty) AS qty
            FROM warehouse_stock s
            JOIN warehouse_products p ON p.id = s.product_id
            JOIN warehouse_locations wl ON wl.code = s.location
            WHERE s.order_id = ? AND s.location <> 'SCRAP'
            GROUP BY s.location, s.product_id, s.unit
            HAVING ABS(SUM(s.qty)) > 1e-9
            ORDER BY wl.sort_order, p.name
        """, (order_id,))
        order['warehouse_stock'] = [dict(r) for r in cur.fetchall()]

        # Warehouse income transactions for this order
        cur.execute("""
            SELECT t.id, t.txn_type, t.from_location, t.to_location,
                   t.comment, t.created_at, u.username AS created_by_username
            FROM warehouse_txn t
            LEFT JOIN users u ON u.id = t.created_by
            WHERE t.order_id = ?
            ORDER BY t.created_at DESC LIMIT 50
        """, (order_id,))
        wh_txns = [dict(r) for r in cur.fetchall()]
        for t in wh_txns:
            cur.execute("""
                SELECT l.qty, l.unit, l.unit_cost, p.name AS product_name
                FROM warehouse_txn_lines l
                JOIN warehouse_products p ON p.id = l.product_id
                WHERE l.txn_id = ?
            """, (t['id'],))
            t['lines'] = [dict(r) for r in cur.fetchall()]
        order['warehouse_history'] = wh_txns

        # Expenses linked to this order (via order_ref = order_code)
        order_code = order.get('order_code', '')
        cur.execute("""
            SELECT e.id, e.expense_type, e.amount, e.payment_type,
                   e.comment, e.created_at, u.username AS created_by_username
            FROM expenses e
            LEFT JOIN users u ON u.id = e.user_id
            WHERE e.order_ref = ?
            ORDER BY e.created_at DESC
        """, (order_code,))
        order['expenses'] = [dict(r) for r in cur.fetchall()]
        order['total_expenses'] = sum(float(e['amount']) for e in order['expenses'])

        # Income linked to this order (source contains order_code or 'Заказ')
        cur.execute("""
            SELECT i.id, i.amount, i.payment_type, i.source,
                   i.comment, i.created_at, u.username AS created_by_username
            FROM income i
            LEFT JOIN users u ON u.id = i.user_id
            WHERE i.source LIKE ? OR i.comment LIKE ?
            ORDER BY i.created_at DESC
        """, (f'%{order_code}%', f'%{order_code}%'))
        order['income'] = [dict(r) for r in cur.fetchall()]
        order['total_income'] = sum(float(i['amount']) for i in order['income'])

        # Services for this order
        cur.execute("""
            SELECT s.id, s.factory_name, s.stage_from, s.stage_to,
                   s.transfer_date, s.total_qty, s.total_amount,
                   s.status, s.comment, s.created_at,
                   u.username AS created_by_username
            FROM services s
            LEFT JOIN users u ON u.id = s.created_by
            WHERE s.order_id = ?
            ORDER BY s.created_at DESC
        """, (order_id,))
        order['services'] = [dict(r) for r in cur.fetchall()]
        order['services_total'] = sum(float(s['total_amount']) for s in order['services'])

        conn.close()
        return order

    # ================= STATISTICS =================

    def get_orders_stats(self, date_from: str = None, date_to: str = None, order_id: int = None) -> Dict[str, Any]:
        """Статистика по заказам"""
        conn = self.get_connection()
        cursor = conn.cursor()

        where = []
        params: List[Any] = []
        if date_from:
            where.append("o.created_at >= ?")
            params.append(date_from)
        if date_to:
            where.append("o.created_at <= ?")
            params.append(date_to + " 23:59:59")
        if order_id:
            where.append("o.id = ?")
            params.append(order_id)
        w = ("WHERE " + " AND ".join(where)) if where else ""

        cursor.execute(f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done,
                SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled,
                SUM(total_amount) AS total_sum,
                SUM(quantity) AS total_qty
            FROM orders o {w}
        """, params)
        row = dict(cursor.fetchone())

        cursor.execute(f"""
            SELECT COUNT(DISTINCT o.id) AS in_production
            FROM orders o
            JOIN order_stage_status oss ON oss.order_id = o.id
            WHERE oss.status = 'in-progress' {("AND " + " AND ".join(where)) if where else ""}
        """, params)
        row['in_production'] = int(cursor.fetchone()['in_production'] or 0)

        cursor.execute(f"""
            SELECT COUNT(DISTINCT o.id) AS with_finished
            FROM orders o
            JOIN order_stage_status oss ON oss.order_id = o.id AND oss.stage_key = 'finished'
            WHERE oss.status = 'completed' {("AND " + " AND ".join(where)) if where else ""}
        """, params)
        row['with_finished'] = int(cursor.fetchone()['with_finished'] or 0)

        conn.close()
        return {k: (v or 0) for k, v in row.items()}

    def get_production_stats(self, date_from: str = None, date_to: str = None, order_id: int = None) -> Dict[str, Any]:
        """Статистика по производству (WIP)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        where: List[str] = []
        params: List[Any] = []
        if order_id:
            where.append("order_id = ?")
            params.append(order_id)
        w = ("WHERE " + " AND ".join(where)) if where else ""

        cursor.execute(f"""
            SELECT stage_key, SUM(qty) AS qty
            FROM production_wip_stock
            {w}
            GROUP BY stage_key
        """, params)
        by_stage = {r['stage_key']: int(r['qty'] or 0) for r in cursor.fetchall()}

        scrap_where: List[str] = ["t.txn_type='scrap'"]
        scrap_params: List[Any] = []
        if date_from:
            scrap_where.append("t.created_at >= ?"); scrap_params.append(date_from)
        if date_to:
            scrap_where.append("t.created_at <= ?"); scrap_params.append(date_to + " 23:59:59")
        if order_id:
            scrap_where.append("t.order_id = ?"); scrap_params.append(order_id)

        cursor.execute(f"""
            SELECT COALESCE(SUM(l.qty), 0) AS scrap_qty
            FROM production_wip_txn t
            JOIN production_wip_txn_lines l ON l.txn_id = t.id
            WHERE {" AND ".join(scrap_where)}
        """, scrap_params)
        scrap_qty = int(cursor.fetchone()['scrap_qty'] or 0)

        conn.close()
        return {
            'by_stage': by_stage,
            'scrap': scrap_qty,
            'cutting': by_stage.get('cutting', 0),
            'sorting': by_stage.get('sorting', 0),
            'sewing': by_stage.get('sewing', 0),
            'cleaning': by_stage.get('cleaning', 0),
            'ironing': by_stage.get('ironing', 0),
            'control': by_stage.get('control', 0),
            'packing': by_stage.get('packing', 0),
            'finished': by_stage.get('finished', 0),
        }

    def get_services_stats(self, date_from: str = None, date_to: str = None) -> Dict[str, Any]:
        """Статистика по услугам"""
        conn = self.get_connection()
        cursor = conn.cursor()

        where: List[str] = []
        params: List[Any] = []
        if date_from:
            where.append("created_at >= ?"); params.append(date_from)
        if date_to:
            where.append("created_at <= ?"); params.append(date_to + " 23:59:59")
        w = ("WHERE " + " AND ".join(where)) if where else ""

        cursor.execute(f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled,
                SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
                SUM(total_amount) AS total_sum,
                SUM(total_qty) AS total_qty
            FROM services {w}
        """, params)
        row = dict(cursor.fetchone())
        conn.close()
        return {k: (v or 0) for k, v in row.items()}

    def get_finance_stats(self, date_from: str = None, date_to: str = None) -> Dict[str, Any]:
        """Финансовая статистика"""
        conn = self.get_connection()
        cursor = conn.cursor()

        we_conds: List[str] = []
        wi_conds: List[str] = []
        pe: List[Any] = []
        pi: List[Any] = []
        if date_from:
            we_conds.append("created_at >= ?"); pe.append(date_from)
            wi_conds.append("created_at >= ?"); pi.append(date_from)
        if date_to:
            d = date_to + " 23:59:59"
            we_conds.append("created_at <= ?"); pe.append(d)
            wi_conds.append("created_at <= ?"); pi.append(d)

        we = ("WHERE " + " AND ".join(we_conds)) if we_conds else ""
        wi = ("WHERE " + " AND ".join(wi_conds)) if wi_conds else ""

        cursor.execute(f"SELECT COALESCE(SUM(amount),0) AS total FROM expenses {we}", pe)
        total_expenses = float(cursor.fetchone()['total'] or 0)

        cursor.execute(f"SELECT COALESCE(SUM(amount),0) AS total FROM income {wi}", pi)
        total_income = float(cursor.fetchone()['total'] or 0)

        cursor.execute(f"""
            SELECT source, COALESCE(SUM(amount),0) AS s
            FROM income {wi}
            GROUP BY source
        """, pi)
        by_source = {r['source']: float(r['s']) for r in cursor.fetchall()}

        cursor.execute(f"""
            SELECT expense_type, COALESCE(SUM(amount),0) AS s
            FROM expenses {we}
            GROUP BY expense_type
            ORDER BY s DESC LIMIT 10
        """, pe)
        by_type = [{'type': r['expense_type'], 'amount': float(r['s'])} for r in cursor.fetchall()]

        cursor.execute("""
            SELECT strftime('%Y-%m', created_at) AS month, COALESCE(SUM(amount),0) AS s
            FROM income GROUP BY month ORDER BY month DESC LIMIT 6
        """)
        income_monthly = {r['month']: float(r['s']) for r in cursor.fetchall()}

        cursor.execute("""
            SELECT strftime('%Y-%m', created_at) AS month, COALESCE(SUM(amount),0) AS s
            FROM expenses GROUP BY month ORDER BY month DESC LIMIT 6
        """)
        expense_monthly = {r['month']: float(r['s']) for r in cursor.fetchall()}

        balance = self.get_cash_balance()
        conn.close()
        return {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'profit': total_income - total_expenses,
            'balance': balance,
            'by_source': by_source,
            'by_expense_type': by_type,
            'income_monthly': income_monthly,
            'expense_monthly': expense_monthly,
        }

    def get_warehouse_stats(self, order_id: int = None) -> Dict[str, Any]:
        """Статистика по складу"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) AS c FROM warehouse_products WHERE active=1")
        total_products = int(cursor.fetchone()['c'] or 0)

        cursor.execute("""
            SELECT s.location, COALESCE(SUM(s.qty),0) AS qty
            FROM warehouse_stock s
            WHERE s.location <> 'SCRAP'
            GROUP BY s.location
        """)
        by_loc_raw = {r['location']: float(r['qty']) for r in cursor.fetchall()}
        total_materials_qty = by_loc_raw.get('MAIN', 0.0)

        cursor.execute("""
            SELECT COALESCE(SUM(qty),0) AS qty FROM warehouse_stock WHERE location = 'SCRAP'
        """)
        scrap_qty = float(cursor.fetchone()['qty'] or 0)

        cursor.execute("""
            SELECT color, size, grade, SUM(qty) AS qty
            FROM production_wip_stock
            WHERE stage_key = 'finished' AND qty > 0
            GROUP BY color, size, grade
            ORDER BY color, size, grade
        """)
        finished_items = [dict(r) for r in cursor.fetchall()]
        finished_total = sum(int(r['qty']) for r in finished_items)

        cursor.execute("""
            SELECT wl.name AS loc_name, COALESCE(SUM(s.qty),0) AS qty
            FROM warehouse_stock s
            JOIN warehouse_locations wl ON wl.code = s.location
            WHERE s.location <> 'SCRAP'
            GROUP BY s.location
            ORDER BY wl.sort_order
        """)
        by_location = [{'location': r['loc_name'], 'qty': float(r['qty'])} for r in cursor.fetchall()]

        conn.close()
        return {
            'total_products': total_products,
            'total_materials_qty': total_materials_qty,
            'scrap_qty': scrap_qty,
            'finished_items': finished_items,
            'finished_total': finished_total,
            'by_location': by_location,
        }


# ===================== MODULE-LEVEL HELPERS (compat with your app.py imports) =====================

db = Database()
def update_user(user_id: int, username: str = None, access_code: str = None, role: str = None) -> bool:
    """Модульная функция для обновления пользователя"""
    return db.update_user(user_id, username, access_code, role)

def authenticate(access_code: str) -> Optional[Dict[str, Any]]:
    return db.authenticate_user(access_code)


def get_all_users() -> List[Dict[str, Any]]:
    return db.get_all_users()