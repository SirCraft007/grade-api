import sqlite3
import json
from werkzeug.security import generate_password_hash, check_password_hash
from config import VALID_API_KEYS, ADMIN_API_KEYS

with open("Grades schulNetz.json", "r") as file:
    data = json.load(file)

grades = data["grades"]
subjects = data["subjects"]
nograde_index = [
    subjects.index("Web of Things & Robotik") + 1,
    subjects.index("Grundlagenfach Sologesang") + 1,
]
db = sqlite3.connect("Grades.db")
cursor = db.cursor()

# Drop the tables if they exist
cursor.execute("DROP TABLE IF EXISTS subjects;")
cursor.execute("DROP TABLE IF EXISTS grades;")
cursor.execute("DROP TABLE IF EXISTS users;")

cursor.execute(
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        total_average REAL,
        total_points INTEGER,
        total_exams INTEGER,
        schulnetz BOOLEAN DEFAULT FALSE
        );
        """
)

# Create the subjects table
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    average REAL,
    points INTEGER,
    num_exams INTEGER,
    weight INTEGER DEFAULT 1,
    user_id INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
"""
)

# Create the grades table
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    grade INTEGER,
    details TEXT,
    weight INTEGER,
    user_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(subject_id) REFERENCES subjects(id)
);
"""
)
password = "admin"
hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

cursor.execute(
    "INSERT INTO users (username, password) VALUES ('admin', ?)",
    (hashed_password,),
)
add = 0
admin_id = cursor.lastrowid
# Insert data into grades table
for id, element in enumerate(grades.values(), start=1):
    if (id + add) in nograde_index:
        add += 1

    for grade in element:
        cursor.execute(
            "INSERT INTO grades (date, name, grade, details, weight, subject_id, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                grade["date"],
                grade["name"],
                grade["grade"],
                grade["details"],
                grade["weight"],
                id + add,
                admin_id,
            ),
        )


# Get the place of an item from grades.values()
gesang_id = list(subjects).index("Grundlagenfach Sologesang")
cursor.execute(
    "INSERT INTO grades (date, name, grade,details, weight, subject_id, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
    (
        "20.01.2024",
        "Gesang",
        "5",
        "",
        "1",
        gesang_id,
        admin_id,
    ),
)
# Insert data into subjects table
for id, element in enumerate(subjects, start=1):

    cursor.execute(
        "SELECT grade, weight FROM grades WHERE subject_id=? AND user_id=?",
        (id, admin_id),
    )
    grades = cursor.fetchall()
    val = 0
    sumer = 0
    weight = 1
    if element == "Web of Things & Robotik":
        weight = 0
    elif element == "Grundlagenfach Sologesang":
        weight = 0.5
    elif element == "Sport":
        weight = 0
    elif element == "Musik":
        weight = 0.5

    for grade in grades:
        if grade[0] != "":
            val += grade[0] * grade[1]
            sumer += grade[1]
        else:
            continue
    average = round(val / sumer if sumer != 0 else 0, 3)
    num_exams = len(grades) if len(grades) != 0 else 0
    if average > 4:
        points = round(average - 4, 3)
    elif average == 0:
        points = 0
    else:
        points = round((average - 4) * 2, 3)

    cursor.execute(
        "INSERT INTO subjects (name, average, points, num_exams,weight, user_id) VALUES (?, ?, ?, ?,?,?)",
        (
            element,
            average,
            points,
            num_exams,
            weight,
            admin_id,
        ),
    )

cursor.execute(
    "SELECT average,points,name,num_exams,weight FROM subjects WHERE user_id=?",
    (admin_id,),
)
subjects = cursor.fetchall()
val = 0
sumer = 0
points = 0
for subject in subjects:
    val += subject[0] * subject[4]
    sumer += 1 * subject[4]
    points += subject[1] * subject[4]
total_average = round(val / sumer if sumer != 0 else 0, 3)
num_exams = sum([subject[3] for subject in subjects])

cursor.execute(
    "UPDATE users SET total_average=?, total_points=?, total_exams=?, schulnetz=TRUE WHERE id=?",
    (total_average, points, num_exams, admin_id),
)

# Commit the transaction
db.commit()

# Close the database connection
db.close()
