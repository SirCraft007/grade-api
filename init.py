import json
from werkzeug.security import generate_password_hash
from config import conn, cur

with open("Grades schulNetz.json", "r") as file:
    data = json.load(file)

grades = data["grades"]
subjects = data["subjects"]
nograde_index = [
    subjects.index("Web of Things & Robotik") + 1,
    subjects.index("Grundlagenfach Sologesang") + 1,
]

# Drop the tables if they exist
cur.execute("PRAGMA foreign_keys = OFF;")
cur.execute("DROP TABLE IF EXISTS subjects;")
cur.execute("DROP TABLE IF EXISTS grades;")
cur.execute("DROP TABLE IF EXISTS users;")
cur.execute("PRAGMA foreign_keys = ON;")
print("Tables dropped")

cur.execute(
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
cur.execute(
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
cur.execute(
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


name = "Serafino"
password = "admin"
hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

cursor = conn.cursor()
cursor.execute(
    "INSERT INTO users (username, password, admin) VALUES (?, ?, ?)",
    (name, hashed_password, True),
)
admin_id = cursor.lastrowid
print("User created")
# Insert data into grades table
subject_values = [(element, admin_id) for element in subjects]
cur.executemany("INSERT INTO subjects (name, user_id) VALUES (?, ?)", subject_values)
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
cur.executemany(
    "INSERT INTO grades (date, name, grade, details, weight, subject_id, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
    values,
)

print("Grades created")
update_queries = []

# Fetch all grades in one query
cur.execute("SELECT subject_id, grade, weight FROM grades WHERE user_id=?", (admin_id,))
all_grades = cur.fetchall()

# Initialize a dictionary to hold grades for each subject
grades_dict = {i: [] for i in range(1, len(subjects) + 1)}

# Populate the dictionary with fetched grades
for grade in all_grades:
    subject_id, grade_value, grade_weight = grade
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
cur.executemany(
    "UPDATE subjects SET average=?, points=?, num_exams=?, weight=? WHERE id=?",
    update_queries,
)

print("Subjects completed")

cur.execute(
    "SELECT average,points,name,num_exams,weight FROM subjects WHERE user_id=?",
    (admin_id,),
)
subjects = cur.fetchall()
val = 0
sumer = 0
points = 0
for subject in subjects:
    if subject[0] is not None and subject[4] is not None:
        val += subject[0] * subject[4]
        sumer += 1 * subject[4]
        points += subject[1] * subject[4]
total_average = round(val / sumer if sumer != 0 else 0, 3)
total_exams = sum([subject[3] for subject in subjects if subject[3] is not None])

cur.execute(
    "UPDATE users SET total_average=?, total_points=?, total_exams=? WHERE id=?",
    (total_average, points, total_exams, admin_id),
)
print("User completed")
# Commit the transaction
conn.commit()
print("Transaction completed")

# Close the database
