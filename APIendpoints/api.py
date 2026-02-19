from flask import Blueprint, jsonify, request, abort, current_app
import datetime
from functools import wraps
from typing import Union
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from config import db
import os


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


def to_str(value: Union[None, str, int, float, bytes]) -> str:
    """Safely convert a Value to str."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


api_routes = Blueprint("api_routes", __name__)


def generate_jwt(user, password):
    try:
        result = db.execute("SELECT username, password, id FROM users WHERE username = ?", [user])
        
        if result.rows and result.rows[0]:
            user_data = result.rows[0]
            username = user_data["username"]
            password_hash = to_str(user_data["password"])
            user_id = user_data["id"]
            
            if check_password_hash(password_hash, password):
                token = jwt.encode(
                    {
                        "username": username,
                        "exp": datetime.datetime.now(datetime.timezone.utc)
                        + datetime.timedelta(hours=12),
                        "id": user_id,
                    },
                    current_app.config["SECRET_KEY"],
                )
                return token
            else:
                raise ValueError("Invalid username or password")
        else:
            raise ValueError("Invalid username or password")
    except (ExpiredSignatureError, InvalidTokenError) as e:
        print(e)
        abort(401, "Token error")


# Function to get the name of a subject based on its ID
def get_subject_name(subject_id, current_user):
    result = db.execute(
        "SELECT name FROM subjects WHERE id=? AND user_id=?",
        [subject_id, current_user["id"]],
    )
    if result.rows and result.rows[0]:
        return result.rows[0]["name"]
    else:
        return "Unknown"


def delete_user_data(user_id):
    try:
        subject_result = db.execute("SELECT COUNT(*) as count FROM subjects WHERE user_id=?", [user_id])
        subject_count = subject_result.rows[0]["count"]
        
        grade_result = db.execute("SELECT COUNT(*) as count FROM grades WHERE user_id=?", [user_id])
        grade_count = grade_result.rows[0]["count"]
        
        db.execute("DELETE FROM grades WHERE user_id=?", [user_id])
        db.execute("DELETE FROM subjects WHERE user_id=?", [user_id])
        db.execute("DELETE FROM users WHERE id=?", [user_id])
        
        return f"User deleted successfully with {subject_count} subjects, {grade_count} grades"
    except Exception as e:
        raise ValueError(f"Error deleting user: {e}")


def get_subject_id(subject_name, current_user):
    result = db.execute(
        "SELECT id FROM subjects WHERE name=? AND user_id=?",
        [subject_name, current_user["id"]],
    )
    
    if result.rows and result.rows[0]:
        return {"id": result.rows[0]["id"], "new_grade": False}
    else:
        try:
            insert_result = db.execute(
                "INSERT INTO subjects (name, user_id) VALUES (?, ?)",
                [subject_name, current_user["id"]],
            )
            return {"id": insert_result.last_insert_rowid, "new_grade": True}
        except Exception as e:
            raise ValueError(f"Error inserting subject: {e}")


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
            
            result = db.execute(
                "SELECT username, id, admin FROM users WHERE username = ?",
                [data["username"]],
            )
            
            if not result.rows or not result.rows[0]:
                return (
                    jsonify({"success": False, "message": "User does not exist"}),
                    403,
                )
            
            user_data = result.rows[0]
            if not user_data["username"] == data["username"]:
                return (
                    jsonify({"success": False, "message": "Username is not correct"}),
                    403,
                )
            if not user_data["id"] == data["id"]:
                return (
                    jsonify({"success": False, "message": "ID is not correct"}),
                    403,
                )
            if not user_data["admin"]:
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
    subjects_result = db.execute("SELECT id, name FROM subjects WHERE user_id=?", [current_user["id"]])
    subjects = subjects_result.rows
    
    for subject in subjects:
        subject_id = subject["id"]
        subject_name = subject["name"]
        
        grades_result = db.execute(
            "SELECT grade, weight FROM grades WHERE subject_id=? AND user_id=?",
            [subject_id, current_user["id"]],
        )
        grades = grades_result.rows
        
        val = 0
        sumer = 0
        weight = 1
        if subject_name in ["Web of Things & Robotik", "Sport"]:
            weight = 0
        elif subject_name in ["Grundlagenfach Sologesang", "Musik"]:
            weight = 0.5

        for grade in grades:
            if grade["grade"] and grade["grade"] != 0:
                val += to_float(grade["grade"]) * to_float(grade["weight"])
                sumer += to_float(grade["weight"])

        average = round(val / sumer if sumer != 0 else 0, 3)
        num_exams = len(grades) if grades else 0
        points = round((average - 4) * 2, 3) if average > 4 else 0

        if num_exams == 0:
            db.execute(
                "UPDATE subjects SET average=?, points=?, num_exams=?, weight=? WHERE id=?",
                [None, None, None, weight, subject_id],
            )
        else:
            db.execute(
                "UPDATE subjects SET average=?, points=?, num_exams=?, weight=? WHERE id=?",
                [average, points, num_exams, weight, subject_id],
            )
    
    update_main(current_user)


# Function to update the total average, total points, and total number of exams in the main table
def update_main(current_user):
    subjects_result = db.execute(
        "SELECT name, average, points, num_exams, weight FROM subjects WHERE user_id=?",
        [current_user["id"]],
    )
    subjects = subjects_result.rows

    val = 0.0
    sumer = 0.0
    points = 0.0
    for subject in subjects:
        if subject["num_exams"] is None or subject["num_exams"] == "":
            continue
        else:
            val += to_float(subject["average"]) * to_float(subject["weight"])
            sumer += 1 * to_float(subject["weight"])
            points += to_float(subject["points"]) * to_float(subject["weight"])
    
    total_average = round(val / sumer if sumer != 0 else 0, 3)
    num_exams = sum([to_int(subject["num_exams"]) if subject["num_exams"] is not None else 0 for subject in subjects])

    db.execute(
        "UPDATE users SET total_average=?, total_points=?, total_exams=? WHERE id=?",
        [total_average, points, num_exams, current_user["id"]],
    )



# Route to get information about a specific subject
@api_routes.route("/subjects/<int:subject_id>", methods=["GET"])
@token_required
def get_subject(current_user, subject_id):
    if not subject_id:
        return jsonify({"success": False, "message": "Subject ID is required"}), 400
    try:
        result = db.execute(
            "SELECT id, name, average, points, num_exams FROM subjects WHERE id=? AND user_id=?",
            [subject_id, current_user["id"]],
        )
        
        if not result.rows or not result.rows[0]:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "No subject found with id:" + str(subject_id),
                    }
                ),
                404,
            )
        
        subject = result.rows[0]
        grades_result = db.execute(
            "SELECT id FROM grades WHERE subject_id=? AND user_id=?",
            [subject_id, current_user["id"]],
        )
        grade_ids_list = [grade["id"] for grade in grades_result.rows]
        
        subject_list = {
            "id": subject["id"],
            "name": subject["name"],
            "average": subject["average"],
            "points": subject["points"],
            "num_exams": subject["num_exams"],
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

        result = db.execute(
            "INSERT INTO subjects (name, weight, user_id) VALUES (?,?,?)",
            [name, weight, current_user["id"]],
        )
        subject_id = result.last_insert_rowid
        update_subjects(current_user)
        
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
            db.execute(
                "UPDATE subjects SET name=?, weight=? WHERE id=? AND user_id=?",
                [name, weight, subject_id, current_user["id"]],
            )
        else:
            db.execute(
                "UPDATE subjects SET name=? WHERE id=? AND user_id=?",
                [name, subject_id, current_user["id"]],
            )
        
        update_subjects(current_user)
        
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
        db.execute(
            "DELETE FROM subjects WHERE id=? AND user_id=?",
            [subject_id, current_user["id"]],
        )
        update_subjects(current_user)
        
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
        result = db.execute(
            "SELECT id, name, grade, weight, date, details, subject_id FROM grades WHERE id=? AND user_id=?",
            [grade_id, current_user["id"]],
        )
        
        if not result.rows or not result.rows[0]:
            return jsonify({"success": False, "message": "Grade not found"}), 404
        
        grade = result.rows[0]
        grade_list = {
            "id": grade["id"],
            "name": grade["name"],
            "grade": grade["grade"],
            "weight": grade["weight"],
            "date": grade["date"],
            "details": grade["details"],
            "subject": get_subject_name(grade["subject_id"], current_user),
        }
        return jsonify({"success": True, "grade": grade_list}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to get grades for a specific subject
@api_routes.route("/subjects/<int:subject_id>/grades", methods=["GET"])
@token_required
def subject_grade(current_user, subject_id):
    try:
        result = db.execute(
            "SELECT id, grade, weight, date, details FROM grades WHERE subject_id=? AND user_id=?",
            [subject_id, current_user["id"]],
        )
        
        grades_list = [
            {
                "id": grade["id"],
                "grade": grade["grade"],
                "weight": grade["weight"],
                "date": grade["date"],
                "details": grade["details"],
            }
            for grade in result.rows
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

        result = db.execute(
            "INSERT INTO grades (date, name, grade, weight, details, subject_id, user_id) VALUES (?,?,?,?,?,?,?)",
            [date, name, grade, weight, details, subject_id, current_user["id"]],
        )
        grade_id = result.last_insert_rowid
        message["id"] = grade_id
        update_subjects(current_user)
        
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
        result = db.execute(
            "SELECT id, name, grade, weight, date, details, subject_id FROM grades WHERE user_id=?",
            [current_user["id"]],
        )
        
        grades_list = [
            {
                "id": grade["id"],
                "name": grade["name"],
                "grade": grade["grade"],
                "weight": grade["weight"],
                "date": grade["date"],
                "details": grade["details"],
                "subject": get_subject_name(grade["subject_id"], current_user),
            }
            for grade in result.rows
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

        update_columns = ", ".join(f"{key} = ?" for key in data.keys())
        update_values = list(data.values())
        update_values += [grade_id, current_user["id"]]
        sql = f"UPDATE grades SET {update_columns} WHERE id = ? and user_id=?"
        db.execute(sql, update_values)
        if (
            data.get("grade") is not None
            or data.get("weight") is not None
            or subject_id is not None
        ):
            update_subjects(current_user)
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
        db.execute(
            "DELETE FROM grades WHERE id=? AND user_id=?",
            [grade_id, current_user["id"]],
        )
        update_subjects(current_user)
        return jsonify({"success": True, "message": "Grade deleted successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Route to get information about all subjects
@api_routes.route("/subjects", methods=["GET"])
@token_required
def get_subjects(current_user):
    try:
        result = db.execute(
            "SELECT id, name, average, points, num_exams FROM subjects WHERE user_id=?",
            [current_user["id"]],
        )
        subjects_list = [
            {
                "id": subject["id"],
                "name": subject["name"],
                "average": subject["average"],
                "points": subject["points"],
                "num_exams": subject["num_exams"],
                # Assuming you want to include grade IDs here
            }
            for subject in result.rows  # Combine subjects with their grade IDs
        ]
        return jsonify({"success": True, "subjects": subjects_list}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_routes.route("/user", methods=["GET"])
@token_required
def get_user(current_user):
    try:
        result = db.execute(
            "SELECT id, username, total_average, total_points, total_exams FROM users WHERE id=?",
            [current_user["id"]],
        )
        user = result.rows[0]
        user_list = {
            "id": user["id"],
            "username": user["username"],
            "total_average": user["total_average"],
            "total_points": user["total_points"],
            "total_exams": user["total_exams"],
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
        result = db.execute("SELECT password FROM users WHERE id = ?", [current_user["id"]])
        user = result.rows[0]

        if user and check_password_hash(to_str(user["password"]), old_password):
            hashed_password = generate_password_hash(
                new_password, method="pbkdf2:sha256"
            )
            db.execute(
                "UPDATE users SET password=? WHERE id=?",
                [hashed_password, current_user["id"]],
            )
            result = db.execute(
                "SELECT username, password, id FROM users WHERE username = ?",
                [current_user["username"]],
            )
            user = result.rows[0]
            token = generate_jwt(current_user["username"], new_password)
            return jsonify({"success": True, "token": token, "id": user["id"]}), 200
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

        db.execute(
            "UPDATE users SET username=? WHERE id=?",
            [username, current_user["id"]],
        )

        token = generate_jwt(username, password)
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
        db.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            [username, hashed_password],
        )

        token = generate_jwt(username, password)
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
