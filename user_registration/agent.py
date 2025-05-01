from flask import request, redirect, url_for, flash
import asyncpg
from ..config import database

class UserRegistration:
    def __init__(self, db_config: database.Config, verbose=False):
        self.db_config = db_config
        self.db_init = False
        self.verbose = verbose

    def _log(self, message: any):
        print(f"[👤 User Registration]: {message}")

    async def init_database(self):
        if not self.db_init:
            server_dsn = self.db_config.dsn
            database = self.db_config.database
            self._log(f"Connecting to server to check if database '{database}' exists...")
            conn = await asyncpg.connect(server_dsn, database=database)
            try:
                async with conn.transaction():
                    db_exists = await conn.fetchval(
                        'SELECT 1 FROM pg_database WHERE datname = $1', database
                    )
                    if not db_exists:
                        self._log(f"Creating database '{database}'...")
                        await conn.execute(f'CREATE DATABASE {database}')
                        self._log(f"Database '{database}' created successfully.")
                    else:
                        self._log(f"Database '{database}' already exists.")

                    self._log("Setting up database schema...")
                    for schema_file in self.db_config.schema_dir.rglob("*.sql"):
                        self._log(f"Executing schema file: {schema_file}")
                        await conn.execute(schema_file.read_text())
                    self.db_init = True
            except Exception as e:
                self._log(f"❌ Error initializing database: {e}")
                raise e
            finally:
                await conn.close()

    async def login(self):
        email = request.form.get('email')
        password = request.form.get('password')

        self._log(f"User is attempting to login: {email}")

        if not email or not password:
            return "Email and password are required", None

        conn = await asyncpg.connect(self.db_config.dsn, database=self.db_config.database)

        try:
            user = await conn.fetchrow("""
                SELECT first_name, last_name, email
                FROM users.userInfo
                WHERE email = $1
            """, email)

            if not user:
                return "Invalid email or password", None

            self._log(f"User authenticated: {email}")
            return "success", {
                "first_name": user['first_name'],
                "last_name": user['last_name'],
                "email": user['email']
            }
        finally:
            await conn.close()

    async def register(self):
        email = request.form.get("email")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not email or not password:
            flash('Email and password are required')
            return redirect(url_for('login'))

        if password != confirm_password:
            flash('Passwords do not match')
            flash('Passwords do not match')
            return redirect(url_for('login'))


        conn = await asyncpg.connect(self.db_config.dsn, database=self.db_config.database)

        try:
            existing_user = await conn.fetchval("""
                SELECT 1 FROM users.userInfo WHERE email = $1
            """, email)

            if existing_user:
                flash('User already exists, please enter unique email')
                return redirect(url_for('login'))

            await conn.execute("""
                INSERT INTO users.userInfo (email, first_name, last_name)
                VALUES ($1, $2, $3)
            """, email, first_name, last_name)

            self._log(f"User successfully registered in database: {email}")
            return redirect(url_for('chat'))
        finally:
            await conn.close()
