import os
from flask import Flask, render_template, request, redirect, session
import mysql.connector
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ================= SAFE SECRET =================
app.secret_key = os.getenv("SECRET_KEY", "dev_secret")


# ================= DB CONNECTION =================
def get_db():
    try:
        return mysql.connector.connect(
            host=os.getenv("MYSQLHOST"),
            user=os.getenv("MYSQLUSER"),
            password=os.getenv("MYSQLPASSWORD"),
            database=os.getenv("MYSQLDATABASE"),
            port=int(os.getenv("MYSQLPORT", "3306"))
        )
    except Exception as e:
        print("DB CONNECTION ERROR:", e)
        return None


# ================= HOME =================
@app.route("/")
def home():
    return render_template("login.html")


# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():
    try:
        if request.method == "POST":
            db = get_db()
            if not db:
                return "Database not connected"

            cursor = db.cursor()

            username = request.form["username"]
            email = request.form["email"]
            password = generate_password_hash(request.form["password"])

            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                return "Email already exists ❌"

            cursor.execute("""
                INSERT INTO users(username,email,password,role)
                VALUES(%s,%s,%s,'member')
            """, (username, email, password))

            db.commit()
            return redirect("/")

        return render_template("reg.html")

    except Exception as e:
        return f"Error: {e}"


# ================= LOGIN =================
@app.route("/login", methods=["POST"])
def login():
    try:
        db = get_db()
        if not db:
            return "DB not connected"

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

    except Exception as e:
        return f"Error: {e}"


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    try:
        if "user_id" not in session:
            return redirect("/")

        db = get_db()
        if not db:
            return "DB not connected"

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT projects.name, tasks.title, tasks.status, tasks.due_date
            FROM tasks
            JOIN projects ON tasks.project_id = projects.id
            ORDER BY tasks.id DESC
        """)

        return render_template("dashboard.html", tasks=cursor.fetchall())

    except Exception as e:
        return f"Error: {e}"


# ================= CREATE PROJECT =================
@app.route("/create_project", methods=["POST"])
def create_project():
    try:
        if session.get("role") != "admin":
            return "Unauthorized"

        db = get_db()
        if not db:
            return "DB not connected"

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

    except Exception as e:
        return f"Error: {e}"


# ================= CREATE TASK =================
@app.route("/create_task", methods=["POST"])
def create_task():
    try:
        if session.get("role") != "admin":
            return "Unauthorized"

        db = get_db()
        if not db:
            return "DB not connected"

        cursor = db.cursor()
        d = request.form

        cursor.execute("""
            INSERT INTO tasks(project_id,title,description,assigned_to,status,due_date)
            VALUES(%s,%s,%s,%s,'pending',%s)
        """, (d["project_id"], d["title"], d["description"], d["assigned_to"], d["due_date"]))

        db.commit()
        return redirect("/dashboard")

    except Exception as e:
        return f"Error: {e}"


# ================= STATIC PAGES =================
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")


# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
