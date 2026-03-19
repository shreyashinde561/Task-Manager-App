from flask import Flask, render_template, request, redirect, session, url_for, Response, send_from_directory
import mysql.connector
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from datetime import datetime
import mysql.connector

ALLOWED_EXTENSIONS = {"zip"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

REGISTRATION_SECRET = os.environ.get("REG_SECRET", "Sparklabians")

app = Flask(__name__)
app.secret_key = "Secret_key"
@app.route("/")
def home():
    return render_template("login.html")

UPLOAD_FOLDER = "uploads"
PROFILE_FOLDER = "static/profile_pics"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PROFILE_FOLDER"] = PROFILE_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_FOLDER, exist_ok=True)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="collab_app",
    port=3306
)

cursor = db.cursor(buffered=True)

cursor.execute("UPDATE users SET is_logged_in=0")
db.commit()

def send_otp_email(to_email, otp):
    msg = EmailMessage()
    msg.set_content(f"Your OTP is {otp}")
    msg["Subject"] = "Collab App Login OTP"
    msg["From"] = "your_email@gmail.com"
    msg["To"] = to_email

    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login("yourmail@gmail.com", "elumzvbiycncabtx")
    server.send_message(msg)
    server.quit()
#Download zip file
@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)
#download code
@app.route("/download_code/<int:code_id>")
def download_code(code_id):
    if "user_id" not in session:
        return redirect("/")

    cursor.execute("SELECT code FROM codes WHERE id=%s", (code_id,))
    result = cursor.fetchone()

    if not result:
        return "Code not found"

    return Response(
        result[0],
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment;filename=code_{code_id}.txt"}
    )
#Login
# Login
@app.route('/login', methods=['GET','POST'])
def login():


 if request.method == 'POST':

    email = request.form['email']
    password = request.form['password']
    login_type = request.form['login_type']

    if not email or not password:
        return "Email or Password missing"

    cursor = db.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()
    cursor.close()

    # Check user and password
    if user and check_password_hash(user['password'], password):

        # ROLE SECURITY CHECK
        if login_type == "admin" and user["role"] != "admin":
            return "You are not an admin!"

        if login_type == "user" and user["role"] == "admin":
            return "Admin must login using 'Login as Admin'"

        # Refresh login status
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT is_logged_in FROM users WHERE id=%s",
            (user['id'],)
        )
        login_status = cursor.fetchone()
        cursor.close()

        # Restrict multiple device login (except admin)
        if login_status['is_logged_in'] == 1 and user["role"] != "admin":
            return "You are already logged in on another device!"

        # Generate OTP
        otp = random.randint(100000, 999999)

        cursor = db.cursor()
        cursor.execute(
            "UPDATE users SET otp=%s WHERE id=%s",
            (otp, user['id'])
        )
        db.commit()
        cursor.close()

        # Send OTP email
        send_otp_email(user['email'], otp)

        # Temporary session until OTP verification
        session.clear()
        session["temp_user_id"] = user["id"]
        session["temp_email"] = user["email"]
        session["temp_username"] = user["username"]
        session["temp_profile_pic"] = user["profile_pic"]

        return redirect('/verify_otp')

    return "Invalid credentials"

 return render_template('login.html')


    
#upload code
@app.route("/upload_code", methods=["POST"])
def upload_code():
    if "user_id" not in session:
        return redirect("/")

    code = request.form["code"]

    cursor.execute(
        "INSERT INTO codes (username, code) VALUES (%s, %s)",
        (session["username"], code)
    )
    db.commit()

    return redirect("/dashboard")
#Admin new
# USER -> ADMIN CHAT
@app.route("/user_admin_chat", methods=["GET", "POST"])
def user_admin_chat():
    if "user_id" not in session:
        return redirect("/")

    # get admin id
    cursor.execute("SELECT id FROM users WHERE role='admin' LIMIT 1")
    admin_id = cursor.fetchone()[0]

    if request.method == "POST":
        msg = request.form["message"]
        cursor.execute("""
            INSERT INTO admin_chats (user_id, admin_id, message, sender)
            VALUES (%s,%s,%s,%s)
        """, (session["user_id"], admin_id, msg, "user"))
        db.commit()
        return redirect("/user_admin_chat")

    cursor.execute("""
        SELECT admin_chats.id, admin_chats.message, admin_chats.sender, admin_chats.time
        FROM admin_chats
        WHERE user_id=%s AND admin_id=%s
        ORDER BY time
    """, (session["user_id"], admin_id))

    chats = cursor.fetchall()
    return render_template("user_admin_chat.html", chats=chats)

# ADMIN USER LIST
@app.route("/admin_private_chat")
def admin_private_chat():
    if "user_id" not in session:
        return redirect("/")

    cursor.execute("SELECT role FROM users WHERE id=%s", (session["user_id"],))
    role = cursor.fetchone()[0]
    if role != "admin":
        return "Access Denied"

    cursor.execute("SELECT id, username FROM users WHERE role!='admin'")
    users = cursor.fetchall()

    return render_template("admin_private_chat.html", users=users, chats=[], selected_user=None)


# ADMIN CHAT WITH SELECTED USER
@app.route("/admin_private_chat/<int:user_id>", methods=["GET", "POST"])
def admin_chat_user(user_id):
    if "user_id" not in session:
        return redirect("/")

    cursor.execute("SELECT role FROM users WHERE id=%s", (session["user_id"],))
    role = cursor.fetchone()[0]
    if role != "admin":
        return "Access Denied"

    if request.method == "POST":
        msg = request.form["message"]
        cursor.execute("""
            INSERT INTO admin_chats (user_id, admin_id, message, sender)
            VALUES (%s,%s,%s,%s)
        """, (user_id, session["user_id"], msg, "admin"))
        db.commit()
        return redirect(f"/admin_private_chat/{user_id}")

    cursor.execute("SELECT id, username FROM users WHERE role!='admin'")
    users = cursor.fetchall()

    cursor.execute("""
        SELECT admin_chats.id, admin_chats.message, admin_chats.sender, 
               admin_chats.time, users.username
        FROM admin_chats
        JOIN users ON admin_chats.user_id = users.id
        WHERE admin_chats.user_id=%s
        ORDER BY time
    """, (user_id,))
    
    chats = cursor.fetchall()

    return render_template(
        "admin_private_chat.html",
        users=users,
        chats=chats,
        selected_user=user_id
    )
#Admin chat

# Admin Allow Logout
@app.route("/allow_logout/<int:user_id>")
def allow_logout(user_id):
    if "user_id" not in session:
        return redirect("/")

    cursor.execute("SELECT role FROM users WHERE id=%s", (session["user_id"],))
    role = cursor.fetchone()

    if role and role[0] == "admin":
        cursor.execute("UPDATE users SET can_logout=1 WHERE id=%s", (user_id,))
        db.commit()
        return "Logout permission granted!"
    else:
        return "Access Denied"
#contact and about
@app.route("/about")
def about():
    return render_template("about.html")

#@app.route("/contact")
#def contact():
 #   return render_template("contact.html")
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        msg = request.form["msg"]

        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO contact_messages (username, email, msg) VALUES (%s, %s, %s)",
            (username, email, msg)
        )
        db.commit()
        cursor.close()

        return "Message sent successfully!"

    return render_template("contact.html")


# Chat
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'user_id' not in session:
        return redirect('/')

    if request.method == 'POST':
        message = request.form['message']
        user_id = session['user_id']

        cursor.execute(
            "INSERT INTO message (user_id, message) VALUES (%s, %s)",
            (user_id, message)
        )
        db.commit()

        return redirect('/chat')
    
    cursor.execute("""
        SELECT message.id, users.username, message.message, message.created_at
        FROM message
        JOIN users ON message.user_id = users.id
        WHERE message.id NOT IN (
        SELECT message_id 
        FROM deleted_messages 
        WHERE user_id=%s
        )
        ORDER BY message.created_at
        """, (session["user_id"],))
    
    messages = cursor.fetchall()

    



    return render_template('chat.html', messages=messages)

# Delete for everyone
@app.route("/delete_for_everyone/<int:msg_id>")
def delete_for_everyone(msg_id):
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]
    cursor = db.cursor()

    # check message owner
    cursor.execute("SELECT user_id FROM message WHERE id=%s", (msg_id,))
    msg = cursor.fetchone()

    if msg and msg[0] == user_id:
        # Insert into deleted_messages before deleting (optional)
        cursor.execute("""
            INSERT INTO deleted_messages (user_id, message_id, deleted_at)
            VALUES (%s, %s, NOW())
        """, (user_id, msg_id))

        # Delete the message
        cursor.execute("DELETE FROM message WHERE id=%s", (msg_id,))
        db.commit()

    cursor.close()
    return redirect("/chat")


# Delete for me
@app.route("/delete_for_me/<int:msg_id>")
def delete_for_me(msg_id):
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]
    cursor = db.cursor()

    # check if already deleted
    cursor.execute("""
        SELECT id FROM deleted_messages
        WHERE user_id=%s AND message_id=%s
    """, (user_id, msg_id))
    exists = cursor.fetchone()

    if not exists:
        # Insert deletion record with timestamp
        cursor.execute("""
            INSERT INTO deleted_messages (user_id, message_id, deleted_at)
            VALUES (%s, %s, NOW())
        """, (user_id, msg_id))
        db.commit()

    cursor.close()
    return redirect("/chat")
#Register
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        secret_key = request.form["secret_key"]

        if secret_key != REGISTRATION_SECRET:
            return "Invalid Secret Key! You cannot register."

        hashed_password = generate_password_hash(password)

        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
            (username, email, hashed_password)
        )
        db.commit()
        return redirect("/")

    return render_template("reg.html")
#Dashboard
from datetime import datetime, timedelta

@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    if "user_id" not in session:
        return redirect("/")



    # ✅ get last login time from DB
    cursor.execute("""
        SELECT login_time 
        FROM login_logs 
        WHERE user_id=%s 
        ORDER BY id DESC 
        LIMIT 1
    """, (session["user_id"],))
    row = cursor.fetchone()

    if not row:
        return "Login time not found"

    login_time = row[0]

    SESSION_LIMIT = 7200  # 5 minutes (change to 7200 for 2 hours)
    elapsed = (datetime.now() - login_time).total_seconds()
    remaining_time = int(SESSION_LIMIT - elapsed)

    if remaining_time <= 0:
        return redirect("/logout")

    # ================= FILE UPLOAD PART (UNCHANGED) =================
    if request.method == "POST" and "file" in request.files:
        file = request.files["file"]

        if file.filename == "":
            return "No file selected"

        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

            size = os.path.getsize(os.path.join(app.config["UPLOAD_FOLDER"], filename))

            cursor.execute(
                "INSERT INTO shared_files (filename, size, uploaded_by) VALUES (%s, %s, %s)",
                (filename, size, session["username"])
            )
            db.commit()
        else:
            return "Only ZIP files allowed"

    cursor.execute("SELECT id, filename, size, uploaded_by FROM shared_files ORDER BY id DESC")
    rows = cursor.fetchall()

    shared_files = [
        {"id": r[0], "name": r[1], "size": round(r[2]/1024, 2), "uploaded_by": r[3]}
        for r in rows
    ]

    cursor.execute("""
        SELECT c.id, c.username, c.code
        FROM codes c
        WHERE c.id NOT IN (
          SELECT item_id FROM deleted_items
          WHERE user_id=%s AND item_type='code'
        )
        ORDER BY c.id DESC
    """, (session["user_id"],))

    codes = cursor.fetchall()

    return render_template(
        "dashboard.html",
        shared_files=shared_files,
        codes=codes,
        remaining_time=remaining_time
    )
#delete route
#Delete for me
@app.route("/delete_code_me/<int:code_id>")
def delete_code_me(code_id):
    if "user_id" not in session:
        return redirect("/")

    cursor.execute(
        "INSERT INTO deleted_items (item_type, item_id, user_id) VALUES (%s,%s,%s)",
        ("code", code_id, session["user_id"])
    )
    db.commit()

    return redirect("/dashboard")

#delete for everyone
@app.route("/delete_code_all/<int:code_id>")
def delete_code_all(code_id):
    if "user_id" not in session:
        return redirect("/")

    cursor.execute(
        "DELETE FROM codes WHERE id=%s AND username=%s",
        (code_id, session["username"])
    )
    db.commit()

    return redirect("/dashboard")
    
# Profile
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/")

    cursor.execute(
    "SELECT username, email, profile_pic, can_logout FROM users WHERE id=%s",
    (session["user_id"],)
)
    
    user = cursor.fetchone()

    return render_template("profile.html", user=user,can_logout=user[3])

#editProfile
@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":
        new_username = request.form["username"]
        file = request.files["profile_pic"]

        if file and file.filename != "":
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["PROFILE_FOLDER"], filename))

            cursor.execute(
                "UPDATE users SET username=%s, profile_pic=%s WHERE id=%s",
                (new_username, filename, session["user_id"])
            )
            session["profile_pic"] = filename
        else:
            cursor.execute(
                "UPDATE users SET username=%s WHERE id=%s",
                (new_username, session["user_id"])
            )

        db.commit()
        session["username"] = new_username
        return redirect("/profile")

    cursor.execute(
        "SELECT username, email, profile_pic FROM users WHERE id=%s",
        (session["user_id"],)
    )
    user = cursor.fetchone()

    return render_template("edit_profile.html", user=user)

#Admin Dashboard
@app.route("/admin_dashboard")
def admin_dashboard():
    if "user_id" not in session:
        return redirect("/")

    cursor.execute("SELECT role FROM users WHERE id=%s", (session["user_id"],))
    role = cursor.fetchone()[0]

    if role != "admin":
        return "Access Denied" , 403

    # USERS
    cursor.execute("SELECT id, username, email, role, can_logout FROM users")
    users = cursor.fetchall()

    # 🔥 LOGIN LOGS (JOIN users)
    cursor.execute("""
    SELECT 
        users.id,
        users.username,
        login_logs.login_time,
        login_logs.logout_time
        FROM login_logs
        JOIN users ON login_logs.user_id = users.id
        ORDER BY login_logs.id DESC
    """)
    logs = cursor.fetchall()
    

    return render_template(
        "admin.html",
        users=users,
        logs=logs
    )
#Delete file
@app.route("/delete_shared/<int:file_id>")
def delete_shared(file_id):
    cursor.execute("SELECT filename, uploaded_by FROM shared_files WHERE id=%s", (file_id,))
    file = cursor.fetchone()

    if not file:
        return "File not found"

    filename, uploaded_by = file

    if uploaded_by != session["username"]:
        return "You are not allowed to delete this file"

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    cursor.execute("DELETE FROM shared_files WHERE id=%s", (file_id,))
    db.commit()

    return redirect("/dashboard")

@app.route("/download_shared/<filename>")
def download_shared(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

#DeleteProfile

@app.route("/delete_profile_pic")
def delete_profile_pic():
    if "user_id" not in session:
        return redirect("/")

    cursor.execute(
        "UPDATE users SET profile_pic=NULL WHERE id=%s",
        (session["user_id"],)
    )
    db.commit()
    session["profile_pic"] = None

    return redirect("/profile")

#Delete account
@app.route("/delete_account")
def delete_account():
    if "user_id" not in session:
        return redirect("/")

    cursor.execute("DELETE FROM users WHERE id=%s", (session["user_id"],))
    db.commit()
    session.clear()

    return redirect("/")
#theme route
@app.route("/toggle_theme")
def toggle_theme():
    if session.get("theme") == "dark":
        session["theme"] = "light"
    else:
        session["theme"] = "dark"
    return redirect(request.referrer or "/dashboard")
#VerifyOTP
# OTP verify
@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():

    if "temp_user_id" not in session:
        return redirect("/")

    if request.method == "POST":

        entered_otp = request.form["otp"]

        cursor = db.cursor(buffered=True)

        cursor.execute(
            "SELECT otp, role FROM users WHERE id=%s",
            (session["temp_user_id"],)
        )

        result = cursor.fetchone()

        # DEBUG
        print("Entered OTP:", entered_otp)
        print("Database OTP:", result[0] if result else None)

        if result and str(entered_otp).strip() == str(result[0]).strip():

            user_id = session["temp_user_id"]
            username = session["temp_username"]
            profile_pic = session["temp_profile_pic"]
            role = result[1]

            session.clear()

            session["user_id"] = user_id
            session["username"] = username
            session["profile_pic"] = profile_pic
            session["role"] = role

            # Save login log
            cursor.execute(
                "INSERT INTO login_logs (user_id, login_time) VALUES (%s, NOW())",
                (user_id,)
            )

            # Disable logout initially
            cursor.execute(
                "UPDATE users SET can_logout=0, is_logged_in=1 WHERE id=%s",
                (user_id,)
            )

            db.commit()
            cursor.close()

            if role == "admin":
                return redirect("/admin_dashboard")
            else:
                return redirect("/dashboard")

        else:
            cursor.close()
            return "Invalid OTP"

    return render_template("verify_otp.html")
#Admin task
# Admin Task Manager
# Admin task manager
@app.route('/admin_tasks')
def admin_tasks():

    if session.get("role") != "admin":
        return "Unauthorized"

    cursor = db.cursor()
    cursor.execute("SELECT username FROM users")
    users = cursor.fetchall()
    cursor.close()

    return render_template("admin_tasks.html", users=users)

#Create tasks
# Create task
@app.route('/create_task', methods=['POST'])
def create_task():

    if session.get("role") != "admin":
        return "Unauthorized"

    title = request.form['title']
    description = request.form['description']
    assigned_to = request.form['assigned_to']
    deadline = request.form['deadline']

    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO tasks
        (task_title, task_description, assigned_to, deadline, created_by)
        VALUES (%s,%s,%s,%s,%s)
    """,(title, description, assigned_to, deadline, session["username"]))

    db.commit()
    cursor.close()
    return redirect('/admin_tasks?success=1')
    #return redirect('/admin_tasks')
# User Tasks
# User tickets list
@app.route('/my_tasks')
def my_tasks():

    if "user_id" not in session:
        return redirect('/')

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, task_title, task_description,
               assigned_to, deadline, created_by,
               created_at, status
        FROM tasks
        WHERE assigned_to=%s
        ORDER BY created_at DESC
    """,(session["username"],))

    tasks = cursor.fetchall()

    cursor.close()

    return render_template("user_tasks.html", tasks=tasks)

#Task complete
# Complete task
@app.route('/complete_task/<int:id>')
def complete_task(id):

    if "user_id" not in session:
        return redirect('/')

    cursor = db.cursor()

    cursor.execute("""
        UPDATE tasks
        SET status='Completed'
        WHERE id=%s AND assigned_to=%s
    """,(id, session["username"]))

    db.commit()
    cursor.close()

    return redirect('/my_tasks')
##new tasks details 
# View all tasks (ticket list)
@app.route('/view_tasks')
def view_tasks():

    if "user_id" not in session:
        return redirect('/')

    if session.get("role") != "admin":
        return "Unauthorized"

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, task_title, task_description,
               assigned_to, deadline, created_by,
               created_at, status
        FROM tasks
        ORDER BY created_at DESC
    """)

    tasks = cursor.fetchall()
    cursor.close()

    return render_template("view_tasks.html", tasks=tasks)


# Open ticket
@app.route('/task/<int:id>')
def task_details(id):

    if "user_id" not in session:
        return redirect('/')

    cursor = db.cursor(dictionary=True)

    # Admin can open any task
    if session.get("role") == "admin":

        cursor.execute("""
            SELECT id, task_title, task_description,
                   assigned_to, deadline, created_by,
                   created_at, status
            FROM tasks
            WHERE id=%s
        """,(id,))

    # User can open only their own tasks
    else:

        cursor.execute("""
            SELECT id, task_title, task_description,
                   assigned_to, deadline, created_by,
                   created_at, status
            FROM tasks
            WHERE id=%s AND assigned_to=%s
        """,(id, session["username"]))

    task = cursor.fetchone()
    cursor.close()

    if not task:
        return "Task not found or access denied"

    return render_template("task_details.html", task=task)

#Delete task (This allows admin to remove tasks.)
@app.route('/delete_task/<int:id>')
def delete_task(id):

    if session.get("role") != "admin":
        return "Unauthorized"

    cursor = db.cursor()

    cursor.execute("""
        DELETE FROM tasks
        WHERE id=%s
    """,(id,))

    db.commit()
    cursor.close()

    return redirect('/admin_tasks')

#Update task (Admin)
@app.route('/update_task_status/<int:id>', methods=['POST'])
def update_task_status(id):

    if session.get("role") != "admin":
        return "Unauthorized"

    status = request.form['status']

    cursor = db.cursor()

    cursor.execute("""
        UPDATE tasks
        SET status=%s
        WHERE id=%s
    """,(status, id))

    db.commit()
    cursor.close()

    return redirect('/admin_tasks')
#Admin View Single Task Ticket
@app.route('/admin_task/<int:id>')
def admin_task_view(id):

    if session.get("role") != "admin":
        return "Unauthorized"

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, task_title, task_description,
               assigned_to, deadline, created_by,
               created_at, status
        FROM tasks
        WHERE id=%s
    """,(id,))

    task = cursor.fetchone()

    cursor.close()

    if not task:
        return "Task not found"

    return render_template("task_details.html", task=task)


#Logout 
# Logout
@app.route("/logout", methods=["GET", "POST"])
def logout():

    if "user_id" not in session:
        return redirect("/")

    auto_logout = request.args.get("auto")

    cursor = db.cursor(buffered=True)

    cursor.execute(
        "SELECT role, can_logout FROM users WHERE id=%s",
        (session["user_id"],)
    )

    user_row = cursor.fetchone()

    if not user_row:
        session.clear()
        cursor.close()
        return redirect("/")

    role, can_logout = user_row

    cursor.execute("""
        SELECT login_time
        FROM login_logs
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],))

    log_row = cursor.fetchone()

    if not log_row:
        session.clear()
        cursor.close()
        return redirect("/")

    login_time = log_row[0]
    now = datetime.now()
    diff = now - login_time

    # ✅ Admin can logout anytime
    if role == "admin":

        cursor.execute("""
            UPDATE login_logs
            SET logout_time=NOW()
            WHERE user_id=%s
            ORDER BY id DESC
            LIMIT 1
        """, (session["user_id"],))

        # ⭐ important for single device system
        cursor.execute(
            "UPDATE users SET is_logged_in=0 WHERE id=%s",
            (session["user_id"],)
        )

        db.commit()
        cursor.close()
        session.clear()

        return redirect("/")

    # ❌ Block logout before 2 hours
    if diff < timedelta(hours=2) and can_logout == 0 and auto_logout is None:
        cursor.close()
        return render_template("logout_blocked.html")

    cursor.execute("""
        UPDATE login_logs
        SET logout_time=NOW()
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],))

    # ⭐ important for single device system
    cursor.execute(
        "UPDATE users SET is_logged_in=0 WHERE id=%s",
        (session["user_id"],)
    )

    db.commit()
    cursor.close()

    session.clear()

    return redirect("/")
if __name__ == "__main__":
    app.run(debug=True)