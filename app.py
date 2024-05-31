from flask import Flask, jsonify, request, abort, render_template
import sqlite3
from functools import wraps

from config import ADMIN_API_KEYS, VALID_API_KEYS

app = Flask(__name__)

db = sqlite3.connect("Grades.db", check_same_thread=False)
cursor = db.cursor()


def update_subjects():
    cursor.execute("SELECT id, name FROM subjects")
    subjects = cursor.fetchall()
    for subject in subjects:
        subject_id = subject[0]
        cursor.execute(
            "SELECT grade, weight FROM grades WHERE subject_id=?", (subject_id,)
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
            "UPDATE subjects SET average=? , points=?, num_exams=? WHERE id=?",
            (
                average,
                points,
                num_exams,
                subject_id,
            ),
        )
    update_main()


def update_main():
    cursor.execute("SELECT average,points,name,num_exams,weight FROM subjects")
    subjects = cursor.fetchall()
    val = 0
    sumer = 0
    points = 0
    for subject in subjects:
        if subject[2] == "Grundlagenfach Sologesang":
            val += 5 * subject[4]
        else:
            val += subject[0] * subject[4]
        sumer += 1 * subject[4]
        points += subject[1] * subject[4]
    total_average = round(val / sumer if sumer != 0 else 0, 3)
    num_exams = sum([subject[3] for subject in subjects])
    cursor.execute(
        "UPDATE main SET total_average=?, total_points=?, total_exams=? WHERE id=1",
        (
            total_average,
            points,
            num_exams,
        ),
    )


def get_subject_name(subject_id):
    cursor.execute("SELECT name FROM subjects WHERE id=?", (subject_id,))
    subject = cursor.fetchone()
    if subject:
        return subject[0]
    else:
        return None


def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if 'x-api-key' is in the request headers
        if "x-api-key" not in request.headers:
            abort(401)  # Unauthorized access

        # Check if the provided API key is valid
        api_key = request.headers.get("x-api-key")
        if api_key not in VALID_API_KEYS and api_key not in ADMIN_API_KEYS:
            abort(403)  # Forbidden access

        return f(*args, **kwargs)

    return decorated_function


def require_admin_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if 'x-api-key' is in the request headers
        if "x-api-key" not in request.headers:
            abort(401)  # Unauthorized access

        # Check if the provided API key is valid
        api_key = request.headers.get("x-api-key")
        if api_key not in ADMIN_API_KEYS:
            abort(403)  # Forbidden access

        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def home():
    return render_template("index.html")

@app.route("/subjects/<int:subject_id>", methods=["GET"])
@require_api_key
def get_subject(subject_id):
    if not subject_id:
        return jsonify({"success": False, "message": "Subject ID is required"}), 400
    try:
        cursor.execute(
            "SELECT id, name, average, points, num_exams FROM subjects WHERE id=?",
            (subject_id,),
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
        cursor.execute("SELECT id FROM grades WHERE subject_id=?", (subject_id,))
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


@app.route("/subjects", methods=["POST"])
@require_admin_key
def add_subject():
    try:
        data = request.get_json()
        name = data.get("name")
        try:
            weight = data.get("weight")
        except:
            weight = 1

        cursor.execute(
            "INSERT INTO subjects (name, weight) VALUES (?,?)",
            (
                name,
                weight,
            ),
        )
        cursor.execute("SELECT id FROM subjects WHERE name=?", (name,))
        subject_id = cursor.fetchone()[0]
        update_subjects()
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


@app.route("/subjects/<int:subject_id>", methods=["PUT"])
@require_admin_key
def update_subject(subject_id):
    try:
        data = request.get_json()
        name = data.get("name")
        weight = data.get("weight")
        if weight is not None:
            cursor.execute(
                "UPDATE subjects SET name=?, weight=? WHERE id=?",
                (name, weight, subject_id),
            )
        else:
            cursor.execute("UPDATE subjects SET name=? WHERE id=?", (name, subject_id))
        update_subjects()
        db.commit()
        return (
            jsonify({"success": True, "message": "Subject updated successfully"}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/subjects/<int:subject_id>", methods=["DELETE"])
@require_admin_key
def delete_subject(subject_id):
    try:
        cursor.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
        update_subjects()
        db.commit()
        return (
            jsonify({"success": True, "message": "Subject deleted successfully"}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/grades/<int:grade_id>", methods=["GET"])
@require_api_key
def get_grade(grade_id):
    try:
        cursor.execute(
            "SELECT id,name, grade, weight,details, subject_id FROM grades WHERE id=?",
            (grade_id,),
        )
        grade = cursor.fetchone()
        grade_list = {
            "id": grade[0],
            "name": grade[1],
            "grade": grade[2],
            "weight": grade[3],
            "details": grade[4],
            "subject": get_subject_name(grade[5]),
        }
        return jsonify({"success": True, "grade": grade_list}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/subjects/<int:subject_id>/grades", methods=["GET"])
@require_api_key
def subject_grade(subject_id):
    try:
        cursor.execute(
            "SELECT id, grade, weight,details FROM grades WHERE subject_id=?",
            (subject_id,),
        )
        grades = cursor.fetchall()
        grades_list = [
            {"id": grade[0], "grade": grade[1], "weight": grade[2], "details": grade[3]}
            for grade in grades
        ]
        return jsonify({"success": True, "grades": grades_list}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/grades", methods=["POST"])
@require_admin_key
def add_grade():
    try:
        data = request.get_json()
        date = data.get("date")
        name = data.get("name")
        grade = data.get("grade")
        weight = data.get("weight")
        details = data.get("details")
        subject_id = data.get("subject_id")

        cursor.execute(
            "INSERT INTO grades (date, name, grade, weight, details, subject_id) VALUES (?,?, ?, ?, ?, ?)",
            (date, name, grade, weight, details, subject_id),
        )

        cursor.execute("SELECT id FROM grades WHERE name=?", (name,))
        grade_id = cursor.fetchone()[0]
        update_subjects()
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


@app.route("/grades/<int:grade_id>", methods=["PUT"])
@require_admin_key
def update_grade(grade_id):
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

        update_columns = ", ".join(f"{key} = ?" for key in data.keys())
        update_values = tuple(data.values())
        update_values += (grade_id,)

        sql = f"UPDATE grades SET {update_columns} WHERE id = ?"
        cursor.execute(sql, update_values)

        update_subjects()
        db.commit()
        return (
            jsonify({"success": True, "message": "Grade updated successfully"}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/grades/<int:grade_id>", methods=["DELETE"])
@require_admin_key
def delete_grade(grade_id):
    try:
        cursor.execute("DELETE FROM grades WHERE id=?", (grade_id,))
        update_subjects()
        db.commit()
        return jsonify({"success": True, "message": "Grade deleted successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/subjects", methods=["GET"])
@require_api_key
def get_subjects():
    try:
        cursor.execute("SELECT id, name, average, points, num_exams FROM subjects")
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
    
if __name__ == '__main__':
    app.run(debug=True)