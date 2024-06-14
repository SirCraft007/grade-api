import json
from werkzeug.security import generate_password_hash
from config import db, cursor

with open("Grades schulNetz.json", "r") as file:
    data = json.load(file)

grades = data["grades"]
subjects = data["subjects"]
nograde_index = [
    subjects.index("Web of Things & Robotik") + 1,
    subjects.index("Grundlagenfach Sologesang") + 1,
]

# Drop the tables if they exist
cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
cursor.execute("DROP TABLE IF EXISTS subjects;")
cursor.execute("DROP TABLE IF EXISTS grades;")
cursor.execute("DROP TABLE IF EXISTS users;")
cursor.execute("SET FOREIGN_KEY_CHECKS=1;")

print("Tables dropped")

cursor.execute(
    """CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        total_average REAL,
        total_points INT,
        total_exams INT,
        admin BOOLEAN DEFAULT FALSE
        );
        """
)

# Create the subjects table
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS subjects (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name TEXT NOT NULL,
    average REAL,
    points INT,
    num_exams INT,
    weight REAL DEFAULT 1,
    user_id INT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
"""
)

# Create the grades table
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS grades (
    id INT PRIMARY KEY AUTO_INCREMENT,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    grade FLOAT,
    details TEXT,
    weight REAL DEFAULT 1,
    user_id INT NOT NULL,
    subject_id INT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(subject_id) REFERENCES subjects(id)
);
"""
)
print("Tables created")
name = "Serafino"
password = "admin"
hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

cursor.execute(
    "INSERT INTO users (username, password,admin) VALUES (%s, %s,%s)",
    (
        name,
        hashed_password,
        True,
    ),
)
admin_id = cursor.lastrowid
print("User created")
# Insert data into grades table
values = [(element, admin_id) for element in subjects]
cursor.executemany("INSERT INTO subjects (name, user_id) VALUES (%s, %s)", values)
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
                None if grade["grade"] == "" else grade["grade"],
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
        "",
        "1",
        list(subjects).index("Grundlagenfach Sologesang") + 1,
        admin_id,
    )
)
cursor.executemany(
    "INSERT INTO grades (date, name, grade, details, weight, subject_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
    values,
)

print("Grades created")
update_queries = []

# Fetch all grades in one query
cursor.execute(
    "SELECT subject_id, grade, weight FROM grades WHERE user_id=%s",
    (admin_id,)
)
all_grades = cursor.fetchall()

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
    points = round((average - 4) * 2, 3) if average > 4 else 0
    if num_exams == 0:
        update_queries.append((None, None, None, weight, id))
    else:
        update_queries.append((average, points, num_exams, weight, id))

# Execute all updates at once
cursor.executemany(
    "UPDATE subjects SET average=%s, points=%s, num_exams=%s, weight=%s WHERE id=%s",
    update_queries,
)

print("Subjects completed")

cursor.execute(
    "SELECT average,points,name,num_exams,weight FROM subjects WHERE user_id=%s",
    (admin_id,),
)
subjects = cursor.fetchall()
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

cursor.execute(
    "UPDATE users SET total_average=%s, total_points=%s, total_exams=%s WHERE id=%s",
    (total_average, points, total_exams, admin_id),
)
print("User completed")
# Commit the transaction
db.commit()
print("Transaction completed")
db.close()

# Close the database