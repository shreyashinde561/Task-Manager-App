from flask import Flask, render_template, request, redirect, session
import mysql.connector
import os
from werkzeug.security import generate_password_hash, check_password_hash
from flask import jsonify

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_secret")


# ---------------- DB CONNECTION ----------------
#def get_db():
    ##return mysql.connector.connect(
      #  host="localhost",
       # user="root",
        #password="root",
        #database="task_manager",
        #port=3306
    #)
def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQLHOST"),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
        port=int(os.getenv("MYSQLPORT", 3306))
    )


# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("login.html")


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            return "Email already exists"

        cursor.execute("""
            INSERT INTO users(username,email,password,role)
            VALUES(%s,%s,%s,'member')
        """, (username, email, password))

        db.commit()
        return redirect("/")

    return render_template("reg.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    email = request.form["email"]
    password = request.form["password"]

    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if user and check_password_hash(user["password"], password):
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        return redirect("/dashboard")

    return "Invalid login"


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            projects.name,
            tasks.title,
            tasks.status,
            tasks.due_date AS deadline
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        ORDER BY tasks.id DESC
    """)

    tasks = cursor.fetchall()

    return render_template("dashboard.html", tasks=tasks)


# ---------------- CREATE PROJECT ----------------
@app.route("/create_project", methods=["POST"])
def create_project():
    if session.get("role") != "admin":
        return "Unauthorized"

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO projects(name,description,created_by)
        VALUES(%s,%s,%s)
    """, (
        request.form["name"],
        request.form["description"],
        session["user_id"]
    ))

    db.commit()
    return redirect("/dashboard")


# ---------------- CREATE TASK ----------------
@app.route("/create_task", methods=["POST"])
def create_task():
    if session.get("role") != "admin":
        return "Unauthorized"

    db = get_db()
    cursor = db.cursor()

    d = request.form

    cursor.execute("""
        INSERT INTO tasks(project_id,title,description,assigned_to,status,due_date)
        VALUES(%s,%s,%s,%s,'pending',%s)
    """, (d["project_id"], d["title"], d["description"], d["assigned_to"], d["due_date"]))

    db.commit()
    return redirect("/dashboard")
@app.route("/complete_task/<int:id>")
def complete_task(id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("UPDATE tasks SET status='completed' WHERE id=%s", (id,))
    db.commit()

    return redirect("/my_tasks")

@app.route("/api/tasks")
def api_tasks():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM tasks")
    return jsonify(cursor.fetchall())

@app.route("/api/tasks", methods=["POST"])
def api_create_task():
    db = get_db()
    cursor = db.cursor()

    d = request.json

    cursor.execute("""
        INSERT INTO tasks(project_id,title,description,assigned_to,status,due_date)
        VALUES(%s,%s,%s,%s,'pending',%s)
    """, (d["project_id"], d["title"], d["description"], d["assigned_to"], d["due_date"]))

    db.commit()

    return {"message": "Task created"}

# ---------------- MY TASKS ----------------
@app.route("/my_tasks")
def my_tasks():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
    SELECT 
        tasks.id,
        tasks.title AS task_title,
        tasks.description AS task_description,
        tasks.status,
        tasks.due_date AS deadline,
        projects.name AS project
    FROM tasks
    JOIN projects ON tasks.project_id = projects.id
    WHERE tasks.assigned_to = %s
""", (session["user_id"],))

    tasks = cursor.fetchall()

    return render_template("user_tasks.html", tasks=tasks)


# ---------------- VIEW ALL TASKS (ADMIN) ----------------
@app.route("/view_tasks")
def view_tasks():
    if session.get("role") != "admin":
        return "Unauthorized"

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            tasks.id,
            tasks.title AS task_title,
            tasks.status,
            tasks.due_date AS deadline,
            users.username AS assigned_to
        FROM tasks
        JOIN users ON tasks.assigned_to = users.id
    """)

    tasks = cursor.fetchall()

    return render_template("view_tasks.html", tasks=tasks)


@app.route("/toggle_theme")
def toggle_theme():
    if session.get("theme") == "dark":
        session["theme"] = "light"
    else:
        session["theme"] = "dark"

    return redirect(request.referrer or "/dashboard")

# ---------------- TASK DETAILS ----------------
@app.route("/task/<int:id>")
def view_task(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            title AS task_title,
            description AS task_description,
            status,
            due_date AS deadline
        FROM tasks
        WHERE id=%s
    """, (id,))

    task = cursor.fetchone()

    return render_template("task_details.html", task=task)





# ---------------- CHAT ----------------
@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        msg = request.form["message"]

        cursor.execute(
            "INSERT INTO messages(user, message) VALUES(%s,%s)",
            (session["username"], msg)
        )
        db.commit()

    cursor.execute(
        "SELECT id, user, message, created_at FROM messages ORDER BY id ASC"
    )
    messages = cursor.fetchall()

    return render_template("chat.html", messages=messages)


# ---------------- PROFILE ----------------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()

    return render_template("profile.html", user=user)


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

    
