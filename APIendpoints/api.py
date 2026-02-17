from flask import Blueprint, jsonify, request, abort, current_app
import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from config import conn, cur
import os

api_routes = Blueprint("api_routes", __name__)


def generate_jwt(user, password):
    try:
        cur.execute(
            "SELECT username, password, id FROM users WHERE username = %s", (user,)
        )
        user_data = cur.fetchone()
        if user_data and check_password_hash(user_data[1], password):
            token = jwt.encode(
                {
                    "username": user_data[0],
                    "exp": datetime.datetime.now(datetime.timezone.utc)
                    + datetime.timedelta(hours=12),
                    "id": user_data[2],
                },
                current_app.config["SECRET_KEY"],
            )
            return token
        else:
            # Raise an exception for invalid username or password
            raise ValueError("Invalid username or password")
    except (ExpiredSignatureError, InvalidTokenError) as e:
        # Handle JWT errors here
        print(e)
        abort(401, "Token error")


# Function to get the name of a subject based on its ID
def get_subject_name(subject_id, current_user):
    cur.execute(
        "SELECT name FROM subjects WHERE id=%s AND user_id=%s",
        (subject_id, current_user["id"]),
    )
    subject = cur.fetchone()
    if subject:
        return subject[0]
    else:
        return "Unknown"


def delete_user_data(user_id):
    try:
        cur.execute(
            "SELECT COUNT(*) FROM subjects WHERE user_id=%s",
            (user_id,),
        )
        subject_count = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM grades WHERE user_id=%s",
            (user_id,),
        )
        grade_count = cur.fetchone()[0]
        cur.execute(
            "DELETE FROM grades WHERE user_id=%s",
            (user_id,),
        )
        cur.execute(
            "DELETE FROM subjects WHERE user_id=%s",
            (user_id,),
        )
        cur.execute(
            "DELETE FROM users WHERE id=%s",
            (user_id,),
        )
        return f"User deleted successfully with {subject_count} subjects, {grade_count} grades"
    except Exception as e:
        raise ValueError(f"Error deleting user: {e}")


def get_subject_id(subject_name, current_user):
    cur.execute(
        "SELECT id FROM subjects WHERE name=%s AND user_id=%s",
        (subject_name, current_user["id"]),
    )
    new_grade = False
    subject = cur.fetchone()
    if subject:
        subject_id = subject[0]
    else:
        try:
            cur.execute(
                "INSERT INTO subjects (name, user_id) VALUES (%s, %s)",
                (subject_name, current_user["id"]),
            )
            subject_id = cur.lastrowid
            new_grade = True

        except Exception as e:
            raise ValueError(f"Error inserting subject: {e}")
    return {"id": subject_id, "new_grade": new_grade}


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("x-access-token")
        if not token:
            return jsonify({"success": False, "message": "Token is missing"}), 403

        try:
            data = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            current_user = {"username": data["username"], "id": data["id"]}
        except (ExpiredSignatureError, InvalidTokenError):
            return (
                jsonify({"success": False, "message": "Token is invalid or expired"}),
                403,
            )

        return f(current_user, *args, **kwargs)

    return decorated


def admin_token_required(f):
    @wraps(f)
    def admin_decorated(*args, **kwargs):
        token = request.headers.get("x-access-token")
        if not token:
            return jsonify({"success": False, "message": "Token is missing"}), 403

        try:
            data = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            current_user = {"username": data["username"], "id": data["id"]}
            cur.execute(
                "SELECT username, id, admin FROM users WHERE username = %s",
                (data["username"],),
            )
            user_data = cur.fetchone()
            if user_data is None:
                return (
                    jsonify({"success": False, "message": "User does not exist"}),
                    403,
                )
            if not user_data[0] == data["username"]:
                return (
                    jsonify({"success": False, "message": "Username is not correct"}),
                    403,
                )
            if not user_data[1] == data["id"]:
                return (
                    jsonify({"success": False, "message": "ID is not correct"}),
                    403,
                )
            if not user_data[2]:
                return (
                    jsonify({"success": False, "message": "User is not admin"}),
                    403,
                )

        except (ExpiredSignatureError, InvalidTokenError):
            return (
                jsonify({"success": False, "message": "Token is invalid or expired"}),
                403,
            )

        return f(current_user, *args, **kwargs)

    return admin_decorated


# Function to update the average, points, and number of exams for each subject
def update_subjects(current_user):
    update_queries = []
    cur.execute("SELECT id, name FROM subjects WHERE user_id=%s", (current_user["id"],))
    subjects = cur.fetchall()
    for id, element in enumerate(subjects, start=1):
        cur.execute(
            "SELECT grade, weight FROM grades WHERE subject_id=%s AND user_id=%s",
            (id, current_user["id"]),
        )
        grades = cur.fetchall()
        val = 0
        sumer = 0
        weight = 1
        if element in ["Web of Things & Robotik", "Sport"]:
            weight = 0
        elif element in ["Grundlagenfach Sologesang", "Musik"]:
            weight = 0.5

        for grade in grades:
            if grade[0] and grade[0] != 0:
                val += grade[0] * grade[1]
                sumer += grade[1]

        average = round(val / sumer if sumer != 0 else 0, 3)
        num_exams = len(grades) if grades else 0
        points = round((average - 4) * 2, 3) if average > 4 else 0

        if num_exams == 0:
            update_queries.append((None, None, None, weight, id))
        else:
            update_queries.append((average, points, num_exams, weight, id))

    # Execute all updates at once
    cur.executemany(
        "UPDATE subjects SET average=%s, points=%s, num_exams=%s, weight=%s WHERE id=%s",
        update_queries,
    )
    update_main(current_user)


# Function to update the total average, total points, and total number of exams in the main table
def update_main(current_user):
    cur.execute(
        "SELECT name,average,points,num_exams,weight FROM subjects WHERE user_id=%s",
        (current_user["id"],),
    )
    subjects = cur.fetchall()

    val = 0
    sumer = 0
    points = 0
    for subject in subjects:
        if subject[3] is None or subject[3] == "":
            continue
        else:
            val += subject[1] * subject[4]
            sumer += 1 * subject[4]
            points += subject[2] * subject[4]
    total_average = round(val / sumer if sumer != 0 else 0, 3)
    num_exams = sum(
        [subject[3] if subject[3] is not None else 0 for subject in subjects]
    )

    cur.execute(
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
        cur.execute(
            "SELECT id, name, average, points, num_exams FROM subjects WHERE id=%s AND user_id=%s",
            (subject_id, current_user["id"]),
        )
        subject = cur.fetchone()
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
        cur.execute(
            "SELECT id FROM grades WHERE subject_id=%s AND user_id=%s",
            (subject_id, current_user["id"]),
        )
        grade_ids = cur.fetchall()
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
        except KeyError:
            weight = 1

        cur.execute(
            "INSERT INTO subjects (name, weight, user_id) VALUES (%s,%s,%s)",
            (
                name,
                weight,
                current_user["id"],
            ),
        )
        subject_id = cur.lastrowid
        update_subjects(current_user)
        conn.commit()
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
            cur.execute(
                "UPDATE subjects SET name=%s, weight=%s WHERE id=%s AND user_id=%s",
                (name, weight, subject_id, current_user["id"]),
            )
        else:
            cur.execute(
                "UPDATE subjects SET name=%s WHERE id=%s AND user_id=%s",
                (name, subject_id, current_user["id"]),
            )
            update_subjects(current_user)

        conn.commit()
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
        cur.execute(
            "DELETE FROM subjects WHERE id=%s AND user_id=%s",
            (subject_id, current_user["id"]),
        )
        update_subjects(current_user)
        conn.commit()
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
        cur.execute(
            "SELECT id,name, grade, weight,date, details, subject_id FROM grades WHERE id=%s AND user_id=%s",
            (grade_id, current_user["id"]),
        )
        grade = cur.fetchone()
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
        cur.execute(
            "SELECT id, grade, weight,date, details FROM grades WHERE subject_id=%s AND user_id=%s",
            (subject_id, current_user["id"]),
        )
        grades = cur.fetchall()
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
        if data.get("subject_id") is None:
            response = get_subject_id(data.get("subject_name"), current_user)
            subject_id = response["id"]

            message = {
                "success": True,
                "message": (
                    "New grade added successfully"
                    if not response["new_grade"]
                    else "New grade and new subject added successfully"
                ),
                "subjekt_id": response["id"] if response["new_grade"] else None,
            }
        else:
            subject_id = data.get("subject_id")
            message = {
                "success": True,
                "message": ("New grade added successfully"),
            }

        cur.execute(
            "INSERT INTO grades (date, name, grade, weight, details, subject_id, user_id) VALUES (%s,%s, %s, %s, %s, %s, %s)",
            (date, name, grade, weight, details, subject_id, current_user["id"]),
        )
        grade_id = cur.lastrowid
        message["id"] = grade_id
        update_subjects(current_user)
        conn.commit()
        return (
            jsonify(message),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/grades", methods=["GET"])
@token_required
def get_grades(current_user):
    try:
        cur.execute(
            "SELECT id,name, grade, weight,date, details, subject_id FROM grades WHERE user_id=%s",
            (current_user["id"],),
        )
        grades = cur.fetchall()
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
        valid_keys = ["date", "name", "grade", "weight", "details"]

        # Validate keys in the incoming data
        for key in data.keys():
            if key not in valid_keys and key not in ["subject_id", "subject_name"]:
                return (
                    jsonify({"success": False, "message": f"Invalid key: {key}"}),
                    400,
                )
        data.pop("subject_id", None)
        data.pop("subject_name", None)
        if data.get("subject_id") is None:
            if data.get("subject_name") is not None:
                response = get_subject_id(data.get("subject_name"), current_user)
                subject_id = response["id"]
            else:
                print("test")
                subject_id = None
                response = None
        else:
            subject_id = data.get("subject_id")
            response = None
        # add the subject_id to the data
        if subject_id:
            data["subject_id"] = subject_id

        update_columns = ", ".join(f"{key} = %s" for key in data.keys())
        update_values = tuple(data.values())
        update_values += (grade_id, current_user["id"])
        sql = f"UPDATE grades SET {update_columns} WHERE id = %s and user_id=%s"
        cur.execute(sql, update_values)
        if (
            data.get("grade") is not None
            or data.get("weight") is not None
            or subject_id is not None
        ):
            update_subjects(current_user)
        conn.commit()
        if response:
            if response["new_grade"]:
                return (
                    jsonify(
                        {
                            "success": True,
                            "message": "Grade updated and new subject added successfully",
                            "subjekt_id": (
                                response["id"] if response["new_grade"] else None
                            ),
                        }
                    ),
                    200,
                )
            else:
                return (
                    jsonify({"success": True, "message": "Grade updated successfully"}),
                    200,
                )

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
        cur.execute(
            "DELETE FROM grades WHERE id=%s AND user_id=%s",
            (grade_id, current_user["id"]),
        )
        update_subjects(current_user)
        conn.commit()
        return jsonify({"success": True, "message": "Grade deleted successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to get information about all subjects
@api_routes.route("/subjects", methods=["GET"])
@token_required
def get_subjects(current_user):
    try:
        cur.execute(
            "SELECT id, name, average, points, num_exams FROM subjects WHERE user_id=%s",
            (current_user["id"],),
        )
        subjects = cur.fetchall()
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
        cur.execute(
            "SELECT id, username, total_average, total_points, total_exams FROM users WHERE id=%s",
            (current_user["id"],),
        )
        user = cur.fetchone()
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


# what method should this be?
@api_routes.route("/user/update_password", methods=["PUT"])
@token_required
def update_password(current_user):
    data = request.get_json()
    try:
        old_password = data.get("old_password")
        new_password = data.get("new_password")
        cur.execute("SELECT password FROM users WHERE id = %s", (current_user["id"],))
        user = cur.fetchone()

        if user and check_password_hash(user[0], old_password):
            hashed_password = generate_password_hash(
                new_password, method="pbkdf2:sha256"
            )
            cur.execute(
                "UPDATE users SET password=%s WHERE id=%s",
                (hashed_password, current_user["id"]),
            )
            cur.execute(
                "SELECT username, password, id FROM users WHERE username = %s",
                (current_user["username"],),
            )
            user = cur.fetchone()
            token = generate_jwt(current_user["username"], new_password)
            conn.commit()
            return jsonify({"success": True, "token": token, "id": user[2]}), 200
        else:
            return jsonify({"success": False, "message": "Invalid password"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/user/update_username", methods=["PUT"])
@token_required
def update_username(current_user):
    data = request.get_json()
    try:
        username = data.get("username")
        password = data.get("password")

        cur.execute(
            "UPDATE users SET username=%s WHERE id=%s",
            (username, current_user["id"]),
        )

        token = generate_jwt(username, password)
        conn.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Username updated successfully",
                    "token": token,
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/register", methods=["PUT"])
def register():
    data = request.get_json()
    try:
        username = data.get("username")
        password = data.get("password")

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hashed_password),
        )

        token = generate_jwt(username, password)
        conn.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "message": "User registered successfully",
                    "token": token,
                }
            ),
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

        token = generate_jwt(username, password)

        return jsonify({"success": True, "token": token}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/user", methods=["DELETE"])
@token_required
def delete_user(current_user):
    try:
        message = delete_user_data(current_user["id"])

        return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/user/<int:user_id>", methods=["DELETE"])
@admin_token_required
def admin_delete_user(current_user, user_id):
    if not user_id:
        return jsonify({"success": False, "message": "No User given"}), 500
    try:
        message = delete_user_data(user_id)

        return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    os.system("python3 app.py")
