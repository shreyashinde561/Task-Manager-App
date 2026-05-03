import os
from flask import Flask

app = Flask(__name__)

# Aapka baaki saara code (routes etc.) yahan hona chahiye

if __name__ == "__main__":
    # Railway environment variable PORT use karta hai, default 8080 rakhte hain
    port = int(os.environ.get("PORT", 8080))
    # host='0.0.0.0' hona zaroori hai taaki Railway bahar se connect kar sake
    app.run(host='0.0.0.0', port=port)
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Railway variables ko fetch karna
database_url = os.environ.get('MYSQL_URL')
# Agar MYSQL_URL nahi hai toh individual variables se connection string banana
if not database_url:
    user = os.environ.get('MYSQLUSER')
    password = os.environ.get('MYSQLPASSWORD')
    host = os.environ.get('MYSQLHOST')
    port = os.environ.get('MYSQLPORT')
    db_name = os.environ.get('MYSQLDATABASE')
    database_url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db_name}"

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
