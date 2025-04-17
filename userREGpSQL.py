# -*- coding: utf-8 -*-
"""
Created on Thu Mar 27 13:57:10 2025

@author: jtste
"""

from flask import Flask, request, jsonify, render_template
import psycopg2

app = Flask(__name__)

def get_db_connection():
    return psycopg2.connect(
        dbname="userregistinfo",
        user="postgres",
        password="G0@gg!e$26",
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
        cursor.execute('SELECT 1 FROM immigration_agent.users WHERE email = %s', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({"error": "Email is already registered. Please use a different email."}), 400

        # Insert new user if email is unique
        cursor.execute('INSERT INTO immigration_agent.users (email, first_name, last_name) VALUES (%s, %s, %s)',
                       (email, first_name, last_name))
        conn.commit()

    return jsonify({"message": "User registered successfully!"}), 201
    
@app.route('/users', methods=['GET'])
def get_users():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM userregistinfo")
        users = cursor.fetchall()
    return jsonify(users)

if __name__ == '__main__':
    get_db_connection()
    app.run(debug=True, use_reloader = False)