import json
import sys
from typing import Union
from werkzeug.security import generate_password_hash
from config import db, close_db


def to_int(value: Union[None, str, int, float, bytes]) -> int:
    """Safely convert a Value to int."""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(float(value)) if value else 0
    if isinstance(value, bytes):
        return int(value.decode()) if value else 0
    return 0


def to_float(value: Union[None, str, int, float, bytes]) -> float:
    """Safely convert a Value to float."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value) if value else 0.0
    if isinstance(value, bytes):
        return float(value.decode()) if value else 0.0
    return 0.0


with open("Grades schulNetz.json", "r") as file:
    data = json.load(file)

grades = data["grades"]
subjects = data["subjects"]
nograde_index = [
    subjects.index("Web of Things & Robotik") + 1,
    subjects.index("Grundlagenfach Sologesang") + 1,
]

# Drop the tables if they exist
db.execute("PRAGMA foreign_keys = OFF;")
db.execute("DROP TABLE IF EXISTS subjects;")
db.execute("DROP TABLE IF EXISTS grades;")
db.execute("DROP TABLE IF EXISTS users;")
db.execute("PRAGMA foreign_keys = ON;")
print("Tables dropped")

db.execute(
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        total_average REAL,
        total_points INTEGER,
        total_exams INTEGER,
        admin BOOLEAN DEFAULT FALSE
        );
        """
)

# Create the subjects table
db.execute(
    """
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    average REAL,
    points INTEGER,
    num_exams INTEGER,
    weight REAL DEFAULT 1,
    user_id INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
"""
)

# Create the grades table
db.execute(
    """
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    grade FLOAT,
    details TEXT,
    weight REAL DEFAULT 1,
    user_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(subject_id) REFERENCES subjects(id)
);
"""
)
print("Tables created")


name = "Admin"
password = "admin"
hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

result = db.execute(
    "INSERT INTO users (username, password, admin) VALUES (?, ?, ?)",
    [name, hashed_password, True],
)
admin_id = result.last_insert_rowid
print("User created")
# Insert data into grades table
subject_values = [(element, admin_id) for element in subjects]
for name, user_id in subject_values:
    db.execute("INSERT INTO subjects (name, user_id) VALUES (?, ?)", [name, user_id])
print("Subjects created")
values = []
add = 0
for id, element in enumerate(grades.values(), start=1):
    if (id + add) in nograde_index:
        add += 1
    values.extend(
        [
            (
                grade["date"],
                grade["name"],
                0 if grade["grade"] == "" else grade["grade"],
                grade["details"],
                grade["weight"],
                id + add,
                admin_id,
            )
            for grade in element
        ]
    )
values.append(
    (
        "20.01.2024",
        "Gesang",
        "5",
        0,
        "1",
        list(subjects).index("Grundlagenfach Sologesang") + 1,
        admin_id,
    )
)
for value in values:
    db.execute(
        "INSERT INTO grades (date, name, grade, details, weight, subject_id, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        list(value),
    )

print("Grades created")
update_queries = []

# Fetch all grades in one query
result = db.execute(
    "SELECT subject_id, grade, weight FROM grades WHERE user_id=?", [admin_id]
)
all_grades = result.rows

# Initialize a dictionary to hold grades for each subject
grades_dict = {i: [] for i in range(1, len(subjects) + 1)}

# Populate the dictionary with fetched grades
for grade in all_grades:
    subject_id = to_int(grade["subject_id"]) if grade["subject_id"] is not None else 0
    grade_value = to_float(grade["grade"]) if grade["grade"] is not None else 0.0
    grade_weight = to_float(grade["weight"]) if grade["weight"] is not None else 1.0
    if subject_id > 0:
        grades_dict[subject_id].append((grade_value, grade_weight))

for id, element in enumerate(subjects, start=1):
    val = 0
    sumer = 0
    weight = 1
    if element in ["Web of Things & Robotik", "Sport"]:
        weight = 0
    elif element in ["Grundlagenfach Sologesang", "Musik"]:
        weight = 0.5

    for grade in grades_dict[id]:
        if grade[0] and grade[0] != 0:
            val += grade[0] * grade[1]
            sumer += grade[1]

    average = round(val / sumer if sumer != 0 else 0, 3)
    num_exams = len(grades_dict[id]) if grades_dict[id] else 0
    points_temp = round((average - 4), 3)

    points = points_temp if average > 4 else points_temp * 2
    if num_exams == 0:
        update_queries.append((0, 0, 0, weight, id))
    else:
        update_queries.append((average, points, num_exams, weight, id))

# Execute all updates at once
for query in update_queries:
    db.execute(
        "UPDATE subjects SET average=?, points=?, num_exams=?, weight=? WHERE id=?",
        list(query),
    )

print("Subjects completed")

result = db.execute(
    "SELECT average,points,name,num_exams,weight FROM subjects WHERE user_id=?",
    [admin_id],
)
subjects = result.rows
val = 0.0
sumer = 0.0
points = 0.0
for subject in subjects:
    avg = to_float(subject["average"]) if subject["average"] is not None else 0.0
    wgt = to_float(subject["weight"]) if subject["weight"] is not None else 0.0
    pts = to_float(subject["points"]) if subject["points"] is not None else 0.0
    if avg and wgt:
        val += avg * wgt
        sumer += 1 * wgt
        points += pts * wgt
total_average = round(val / sumer if sumer != 0 else 0, 3)
total_exams = sum(
    [
        to_int(subject["num_exams"])
        for subject in subjects
        if subject["num_exams"] is not None
    ]
)

db.execute(
    "UPDATE users SET total_average=?, total_points=?, total_exams=? WHERE id=?",
    [total_average, points, total_exams, admin_id],
)
print("User completed")
# Transaction is auto-committed with libsql_client
print("Transaction completed")

# Close the database connection
print("Closing database connection...")
close_db()
print("Database seeding completed successfully!")
sys.exit(0)
