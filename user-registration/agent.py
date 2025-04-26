# -*- coding: utf-8 -*-
"""
Created on Thu Mar 27 13:57:10 2025

@author: jtste
"""

from flask import Flask, request, jsonify, render_template
import psycopg2
import asyncio
import asyncpg

from . import util
from ..config import database
#import database #for local test

class UserRegistration:
  #def __init__(self, db_config: Config, verbose=False):
    def __init__(self, db_config: database.Config, verbose=False):
        self.db_config = db_config
        self.db_init = False
        self.verbose = verbose
    def _log(self,message:any):
        print(f"[👤 User Registration]: {message}")
    async def init_database(self):
        if not self.db_init:
            server_dsn = self.db_config.dsn
            database = self.db_config.database
            self._log(f"Connecting to server to check if database '{database}' exists...")
            conn = await asyncpg.connect(server_dsn, database=database)
            try:
                async with conn.transaction():
                    db_exists = await conn.fetchval('SELECT 1 FROM pg_database WHERE datname = $1', database)
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

async def main():
    # Database configuration
    db_config = database.Config(
        #schema_dir = "../userReg/sql", #for local test
        schema_dir ="sql",
        dsn = "postgresql://@localhost:5432",
        database= "maia"
    )

app = Flask(__name__)


def get_db_connection():
    return psycopg2.connect(
        dbname="maia",
        user="postgres",
        password= "", #Is password needed?
        host="localhost",  # Change if your database is remote
        port="5432"
    )


@app.route('/')
def home():
    return render_template("index.html")

@app.route('/register', methods=['POST'])
def register():
    email = request.form.get("email")
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")

    if not email or not first_name or not last_name:
        return jsonify({"error": "All fields are required."}), 400

    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute('SELECT 1 FROM userRegist.userInfo WHERE email = %s', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({"error": "Email is already registered. Please use a different email."}), 400

        # Insert new user if email is unique
        cursor.execute('INSERT INTO userRegist.userInfo (email, first_name, last_name) VALUES (%s, %s, %s)',
                       (email, first_name, last_name))
        conn.commit()

    return jsonify({"message": "User registered successfully!"}), 201
    
@app.route('/users', methods=['GET'])
def get_users():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM maia")
        users = cursor.fetchall()
    return jsonify(users)

if __name__ == '__main__':
    asyncio.run(main())
    app.run(debug=True, use_reloader = False)