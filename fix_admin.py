from werkzeug.security import generate_password_hash
import mysql.connector

import os
print("DB UTILISÉE PAR SCRIPT:", os.path.abspath("database.db"))

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="sirh"
)

cursor = db.cursor()

username = "admin"
password = "admin123"
role = "admin"

# ⚠️ PAS de method → laisse scrypt par défaut
hash_password = generate_password_hash(password)

print("HASH:", hash_password)

# 🔥 nettoyage total
cursor.execute("DELETE FROM users")

# 🔥 insertion propre
cursor.execute(
    "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
    (username, hash_password, role)
)

db.commit()

print("✅ Admin recréé")