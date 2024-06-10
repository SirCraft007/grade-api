from flask import Blueprint, jsonify, request, abort, current_app
import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import mysql.connector

api_routes = Blueprint("api_routes", __name__)

# Connect to the database
db = mysql.connector.connect(
    host="jungwac1.mysql.db.hostpoint.ch",
    user="jungwac1_DataB",
    password="3!%;+dEe1j",
    database="jungwac1_data",
)
cursor = db.cursor()


# Function to get the name of a subject based on its ID
def get_subject_name(subject_id, current_user):
    cursor.execute(
        "SELECT name FROM subjects WHERE id=%s AND user_id=%s",
        (subject_id, current_user["id"]),
    )
    subject = cursor.fetchone()
    if subject:
        return subject[0]
    else:
        return "Unknown"


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("x-access-token")
        if not token:
            return jsonify({"message": "Token is missing"}), 403

        try:
            data = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            current_user = {"username": data["username"], "id": data["id"]}
        except:
            return jsonify({"message": "Token is invalid or expired"}), 403

        return f(current_user, *args, **kwargs)

    return decorated


# Function to update the average, points, and number of exams for each subject
def update_subjects(current_user):
    cursor.execute(
        "SELECT id, name FROM subjects WHERE user_id=%s", (current_user["id"],)
    )
    subjects = cursor.fetchall()
    for subject in subjects:
        subject_id = subject[0]
        cursor.execute(
            "SELECT grade, weight FROM grades WHERE subject_id=%s AND user_id=%s",
            (subject_id, current_user["id"]),
        )
        grades = cursor.fetchall()
        val = 0
        sumer = 0
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
            "UPDATE subjects SET average=%s , points=%s, num_exams=%s WHERE id=%s",
            (
                average,
                points,
                num_exams,
                subject_id,
            ),
        )
    update_main(current_user)


# Function to update the total average, total points, and total number of exams in the main table
def update_main(current_user):
    cursor.execute(
        "SELECT average,points,name,num_exams,weight FROM subjects WHERE user_id=%s",
        (current_user["id"],),
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
        "UPDATE users SET total_average=%s, total_points=%s, total_exams=%s WHERE id=%s",
        (
            total_average,
            points,
            num_exams,
            current_user["id"],
        ),
    )


# Route to get information about a specific subject
@api_routes.route("/subjects/<int:subject_id>", methods=["GET"])
@token_required
def get_subject(current_user, subject_id):
    if not subject_id:
        return jsonify({"success": False, "message": "Subject ID is required"}), 400
    try:
        cursor.execute(
            "SELECT id, name, average, points, num_exams FROM subjects WHERE id=%s AND user_id=%s",
            (subject_id, current_user["id"]),
        )
        subject = cursor.fetchone()
        if not subject:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "No subject found with id:" + subject_id,
                    }
                ),
                404,
            )
        cursor.execute(
            "SELECT id FROM grades WHERE subject_id=%s AND user_id=%s",
            (subject_id, current_user["id"]),
        )
        grade_ids = cursor.fetchall()
        grade_ids_list = [grade_id[0] for grade_id in grade_ids]
        subject_list = {
            "id": subject[0],
            "name": subject[1],
            "average": subject[2],
            "points": subject[3],
            "num_exams": subject[4],
            "grade_ids": grade_ids_list,
        }
        return jsonify({"success": True, "subject": subject_list}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to add a new subject
@api_routes.route("/subjects", methods=["POST"])
@token_required
def add_subject(current_user):
    try:
        data = request.get_json()
        name = data.get("name")
        try:
            weight = data.get("weight")
        except:
            weight = 1

        cursor.execute(
            "INSERT INTO subjects (name, weight, user_id) VALUES (%s,%s,%s)",
            (
                name,
                weight,
                current_user["id"],
            ),
        )
        cursor.execute(
            "SELECT id FROM subjects WHERE name=%s AND user_id=%s",
            (name, current_user["id"]),
        )
        subject_id = cursor.fetchone()[0]
        update_subjects(current_user)
        db.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Subject added successfully",
                    "id": subject_id,
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to update an existing subject
@api_routes.route("/subjects/<int:subject_id>", methods=["PUT"])
@token_required
def update_subject(current_user, subject_id):
    try:
        data = request.get_json()
        name = data.get("name")
        weight = data.get("weight")
        if weight is not None:
            cursor.execute(
                "UPDATE subjects SET name=%s, weight=%s WHERE id=%s AND user_id=%s",
                (name, weight, subject_id, current_user["id"]),
            )
        else:
            cursor.execute(
                "UPDATE subjects SET name=%s WHERE id=%s AND user_id=%s",
                (name, subject_id, current_user["id"]),
            )
        update_subjects(current_user)
        db.commit()
        return (
            jsonify({"success": True, "message": "Subject updated successfully"}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to delete a subject
@api_routes.route("/subjects/<int:subject_id>", methods=["DELETE"])
@token_required
def delete_subject(current_user, subject_id):
    try:
        cursor.execute(
            "DELETE FROM subjects WHERE id=%s AND user_id=%s",
            (subject_id, current_user["id"]),
        )
        update_subjects(current_user)
        db.commit()
        return (
            jsonify({"success": True, "message": "Subject deleted successfully"}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to get information about a specific grade
@api_routes.route("/grades/<int:grade_id>", methods=["GET"])
@token_required
def get_grade(current_user, grade_id):
    try:
        cursor.execute(
            "SELECT id,name, grade, weight,date, details, subject_id FROM grades WHERE id=%s AND user_id=%s",
            (grade_id, current_user["id"]),
        )
        grade = cursor.fetchone()
        grade_list = {
            "id": grade[0],
            "name": grade[1],
            "grade": grade[2],
            "weight": grade[3],
            "date": grade[4],
            "details": grade[5],
            "subject": get_subject_name(grade[6], current_user),
        }
        return jsonify({"success": True, "grade": grade_list}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to get grades for a specific subject
@api_routes.route("/subjects/<int:subject_id>/grades", methods=["GET"])
@token_required
def subject_grade(current_user, subject_id):
    try:
        cursor.execute(
            "SELECT id, grade, weight,date, details FROM grades WHERE subject_id=%s AND user_id=%s",
            (subject_id, current_user["id"]),
        )
        grades = cursor.fetchall()
        grades_list = [
            {
                "id": grade[0],
                "grade": grade[1],
                "weight": grade[2],
                "date": grade[3],
                "details": grade[4],
            }
            for grade in grades
        ]
        return jsonify({"success": True, "grades": grades_list}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to add a new grade
@api_routes.route("/grades", methods=["POST"])
@token_required
def add_grade(current_user):
    try:
        data = request.get_json()
        date = data.get("date")
        name = data.get("name")
        grade = data.get("grade")
        weight = data.get("weight")
        details = data.get("details")
        subject_id = data.get("subject_id")

        cursor.execute(
            "INSERT INTO grades (date, name, grade, weight, details, subject_id, user_id) VALUES (%s,%s, %s, %s, %s, %s, %s)",
            (date, name, grade, weight, details, subject_id, current_user["id"]),
        )

        cursor.execute("SELECT id FROM grades WHERE name=%s", (name,))
        grade_id = cursor.fetchone()[0]
        update_subjects(current_user)
        db.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Grade added successfully",
                    "id": grade_id,
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/grades", methods=["GET"])
@token_required
def get_grades(current_user):
    try:
        cursor.execute(
            "SELECT id,name, grade, weight,date, details, subject_id FROM grades WHERE user_id=%s",
            (current_user["id"],),
        )
        grades = cursor.fetchall()
        grades_list = [
            {
                "id": grade[0],
                "name": grade[1],
                "grade": grade[2],
                "weight": grade[3],
                "date": grade[4],
                "details": grade[5],
                "subject": get_subject_name(grade[6], current_user),
            }
            for grade in grades
        ]
        return jsonify({"success": True, "grades": grades_list}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to update an existing grade
@api_routes.route("/grades/<int:grade_id>", methods=["PUT"])
@token_required
def update_grade(current_user, grade_id):
    try:
        data = request.get_json()

        # Define a list of valid keys
        valid_keys = ["date", "name", "grade", "weight", "details", "subject_id"]

        # Validate keys in the incoming data
        for key in data.keys():
            if key not in valid_keys:
                return (
                    jsonify({"success": False, "message": f"Invalid key: {key}"}),
                    400,
                )

        update_columns = ", ".join(f"{key} = %s" for key in data.keys())
        update_values = tuple(data.values())
        update_values += (grade_id, current_user["id"])
        sql = f"UPDATE grades SET {update_columns} WHERE id = %s and user_id=%s"
        cursor.execute(sql, update_values)

        update_subjects(current_user)
        db.commit()
        return (
            jsonify({"success": True, "message": "Grade updated successfully"}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to delete a grade
@api_routes.route("/grades/<int:grade_id>", methods=["DELETE"])
@token_required
def delete_grade(current_user, grade_id):
    try:
        cursor.execute(
            "DELETE FROM grades WHERE id=%s AND user_id=%s",
            (grade_id, current_user["id"]),
        )
        update_subjects(current_user)
        db.commit()
        return jsonify({"success": True, "message": "Grade deleted successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to get information about all subjects
@api_routes.route("/subjects", methods=["GET"])
@token_required
def get_subjects(current_user):
    try:
        cursor.execute(
            "SELECT id, name, average, points, num_exams FROM subjects WHERE user_id=%s",
            (current_user["id"],),
        )
        subjects = cursor.fetchall()
        subjects_list = [
            {
                "id": subject[0],
                "name": subject[1],
                "average": subject[2],
                "points": subject[3],
                "num_exams": subject[4],
                # Assuming you want to include grade IDs here
            }
            for subject in subjects  # Combine subjects with their grade IDs
        ]
        return jsonify({"success": True, "subjects": subjects_list}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/user", methods=["GET"])
@token_required
def get_user(current_user):
    try:
        cursor.execute(
            "SELECT id, username, total_average, total_points, total_exams FROM users WHERE id=%s",
            (current_user["id"],),
        )
        user = cursor.fetchone()
        user_list = {
            "id": user[0],
            "username": user[1],
            "total_average": user[2],
            "total_points": user[3],
            "total_exams": user[4],
        }
        return jsonify({"success": True, "user": user_list}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/user/update_password", methods=["POST"])
@token_required
def update_password(current_user):
    data = request.get_json()
    try:
        old_password = data.get("old_password")
        new_password = data.get("new_password")
        cursor.execute("SELECT password FROM users WHERE id = %s", (current_user["id"],))
        user = cursor.fetchone()

        if user and check_password_hash(user[0], old_password):
            hashed_password = generate_password_hash(
                new_password, method="pbkdf2:sha256"
            )
            cursor.execute(
                "UPDATE users SET password=%s WHERE id=%s",
                (hashed_password, current_user["id"]),
            )
            cursor.commit()
            return (
                jsonify({"success": False, "message": "Password updated successfully"}),
                200,
            )
        else:
            return jsonify({"success": False, "message": "Invalid password"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/user/update_username", methods=["POST"])
@token_required
def update_username(current_user):
    data = request.get_json()
    try:
        username = data.get("username")

        cursor.execute(
            "UPDATE users SET username=%s WHERE id=%s",
            (username, current_user["id"]),
        )
        cursor.commit()
        return (
            jsonify({"success": False, "message": "Username updated successfully"}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    try:
        username = data.get("username")
        password = data.get("password")

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hashed_password),
        )
        cursor.commit()
        return (
            jsonify({"success": True, "message": "User registered successfully"}),
            201,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    try:
        username = data.get("username")
        password = data.get("password")

        cursor.execute(
            "SELECT username, password, id FROM users WHERE username = %s", (username,)
        )
        user = cursor.fetchone()

        if user and check_password_hash(user[1], password):
            token = jwt.encode(
                {
                    "username": username,
                    "exp": datetime.datetime.now(datetime.timezone.utc)
                    + datetime.timedelta(hours=24),
                    "id": user[2],
                },
                current_app.config["SECRET_KEY"],
            )

            return jsonify({"success": True, "token": token, "id": user[2]}), 200
        else:
            return jsonify({"success": False, "message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
