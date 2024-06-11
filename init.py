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
        total_subjects INT
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
    weight INT DEFAULT 1,
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
    grade INT,
    details TEXT,
    weight INT,
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
    "INSERT INTO users (username, password) VALUES (%s, %s)",
    (
        name,
        hashed_password,
    ),
)
admin_id = cursor.lastrowid
print("User created")
# Insert data into grades table

for id, element in enumerate(subjects, start=1):
    cursor.execute(
        "INSERT INTO subjects (name,user_id) VALUES (%s,%s)",
        (
            element,
            admin_id,
        ),
    )
print("Subjects created")
add = 0
for id, element in enumerate(grades.values(), start=1):
    if (id + add) in nograde_index:
        add += 1

    for grade in element:
        if grade["grade"] == "":
            grade_value = None
        else:
            grade_value = grade["grade"]
        cursor.execute(
            "INSERT INTO grades (date, name, grade, details, weight, subject_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                grade["date"],
                grade["name"],
                grade_value,
                grade["details"],
                grade["weight"],
                id + add,
                admin_id,
            ),
        )
# Get the place of an item from grades.values()
gesang_id = list(subjects).index("Grundlagenfach Sologesang")
cursor.execute(
    "INSERT INTO grades (date, name, grade,details, weight, subject_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
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
print("Grades created")
# Insert data into subjects table
for id, element in enumerate(subjects, start=1):

    cursor.execute(
        "SELECT grade, weight FROM grades WHERE subject_id=%s AND user_id=%s",
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
        if grade[0] != None and grade[0] != 0:
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
            "UPDATE subjects SET average=%s, points=%s, num_exams=%s, weight=%s WHERE id=%s",
            (
                average,
                points,
                num_exams,
                weight,
                id,
            ),
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
num_subjects = sum([subject[3] for subject in subjects if subject[3] is not None])

cursor.execute(
    "UPDATE users SET total_average=%s, total_points=%s, total_subjects=%s WHERE id=%s",
    (total_average, points, num_subjects, admin_id),
)
print("User completed")
# Commit the transaction
db.commit()
print("Transaction completed")

# Close the database
