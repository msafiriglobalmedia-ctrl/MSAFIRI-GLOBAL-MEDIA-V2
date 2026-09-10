import os
import uuid
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# =========================================================
# MSAFIRI GLOBAL MEDIA V2
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(exist_ok=True)

DB_FILE = BASE_DIR / "msafiri_global_media.db"

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")

MAX_FILE_SIZE = 50 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "webp",
    "mp4", "webm", "mov",
    "mp3", "wav", "ogg", "m4a",
    "pdf", "doc", "docx", "txt",
    "zip"
}


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            caption TEXT DEFAULT '',
            media TEXT DEFAULT '',
            media_type TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER,
            message TEXT DEFAULT '',
            file TEXT DEFAULT '',
            message_type TEXT DEFAULT 'text',
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            task TEXT NOT NULL,
            done INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# HELPERS
# =========================================================

def now():
    return datetime.utcnow().isoformat()


def allowed_file(filename):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def file_type(filename):
    ext = filename.rsplit(".", 1)[1].lower()

    if ext in {"png", "jpg", "jpeg", "gif", "webp"}:
        return "image"

    if ext in {"mp4", "webm", "mov"}:
        return "video"

    if ext in {"mp3", "wav", "ogg", "m4a"}:
        return "audio"

    if ext in {"pdf", "doc", "docx", "txt"}:
        return "document"

    return "file"


def get_user(user_id):
    conn = db()
    user = conn.execute(
        "SELECT id, username, name, created_at FROM users WHERE id=?",
        (user_id,)
    ).fetchone()
    conn.close()

    return dict(user) if user else None


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    index_file = BASE_DIR / "index.html"

    if not index_file.exists():
        return """
        <h1>MSAFIRI GLOBAL MEDIA</h1>
        <p>index.html haijapatikana.</p>
        <p>Weka index.html pamoja na main.py.</p>
        """, 404

    return send_from_directory(BASE_DIR, "index.html")


# =========================================================
# HEALTH
# =========================================================

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "app": "Msafiri Global Media",
        "version": "V2",
        "time": now()
    })


# =========================================================
# REGISTER
# =========================================================

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    name = str(data.get("name", "")).strip()

    if not username or not password or not name:
        return jsonify({
            "success": False,
            "message": "Jaza jina, username na password."
        }), 400

    conn = db()

    try:
        cur = conn.execute("""
            INSERT INTO users(username,password,name,created_at)
            VALUES(?,?,?,?)
        """, (username, password, name, now()))

        conn.commit()

        user_id = cur.lastrowid

    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Username tayari ipo."
        }), 409

    conn.close()

    return jsonify({
        "success": True,
        "user": get_user(user_id)
    })


# =========================================================
# LOGIN
# =========================================================

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()

    conn = db()

    user = conn.execute("""
        SELECT id, username, name, created_at
        FROM users
        WHERE username=? AND password=?
    """, (username, password)).fetchone()

    conn.close()

    if not user:
        return jsonify({
            "success": False,
            "message": "Username au password si sahihi."
        }), 401

    return jsonify({
        "success": True,
        "user": dict(user)
    })


# =========================================================
# USERS
# =========================================================

@app.route("/api/users")
def users():
    conn = db()

    rows = conn.execute("""
        SELECT id, username, name, created_at
        FROM users
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return jsonify({
        "success": True,
        "users": [dict(x) for x in rows]
    })


# =========================================================
# POSTS
# =========================================================

@app.route("/api/posts")
def posts():
    conn = db()

    rows = conn.execute("""
        SELECT
            posts.id,
            posts.user_id,
            posts.caption,
            posts.media,
            posts.media_type,
            posts.created_at,
            users.username,
            users.name
        FROM posts
        JOIN users ON users.id = posts.user_id
        ORDER BY posts.id DESC
    """).fetchall()

    conn.close()

    result = []

    for row in rows:
        item = dict(row)

        if item["media"]:
            item["media_url"] = "/media/" + item["media"]
        else:
            item["media_url"] = ""

        result.append(item)

    return jsonify({
        "success": True,
        "posts": result
    })


# =========================================================
# CREATE POST
# =========================================================

@app.route("/api/posts", methods=["POST"])
def create_post():

    user_id = request.form.get("user_id")
    caption = request.form.get("caption", "").strip()

    if not user_id:
        return jsonify({
            "success": False,
            "message": "user_id inahitajika."
        }), 400

    uploaded = request.files.get("media")

    filename = ""
    media_type = ""

    if uploaded and uploaded.filename:

        if not allowed_file(uploaded.filename):
            return jsonify({
                "success": False,
                "message": "Aina ya file hairuhusiwi."
            }), 400

        original = secure_filename(uploaded.filename)

        filename = f"{uuid.uuid4().hex}_{original}"

        uploaded.save(MEDIA_DIR / filename)

        media_type = file_type(filename)

    if not caption and not filename:
        return jsonify({
            "success": False,
            "message": "Weka caption au media."
        }), 400

    conn = db()

    cur = conn.execute("""
        INSERT INTO posts(
            user_id,
            caption,
            media,
            media_type,
            created_at
        )
        VALUES(?,?,?,?,?)
    """, (
        int(user_id),
        caption,
        filename,
        media_type,
        now()
    ))

    conn.commit()
    post_id = cur.lastrowid
    conn.close()

    return jsonify({
        "success": True,
        "post_id": post_id
    })


# =========================================================
# DELETE POST
# =========================================================

@app.route("/api/posts/<int:post_id>", methods=["DELETE"])
def delete_post(post_id):

    user_id = request.args.get("user_id")

    conn = db()

    post = conn.execute(
        "SELECT * FROM posts WHERE id=?",
        (post_id,)
    ).fetchone()

    if not post:
        conn.close()

        return jsonify({
            "success": False,
            "message": "Post haipo."
        }), 404

    if user_id and int(post["user_id"]) != int(user_id):
        conn.close()

        return jsonify({
            "success": False,
            "message": "Huruhusiwi kufuta post hii."
        }), 403

    conn.execute(
        "DELETE FROM posts WHERE id=?",
        (post_id,)
    )

    conn.commit()
    conn.close()

    if post["media"]:
        path = MEDIA_DIR / post["media"]

        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass

    return jsonify({
        "success": True,
        "message": "Post imefutwa."
    })


# =========================================================
# MEDIA
# =========================================================

@app.route("/media/<path:filename>")
def media(filename):
    return send_from_directory(MEDIA_DIR, filename)


# =========================================================
# GENERAL UPLOAD
# =========================================================

@app.route("/api/upload", methods=["POST"])
def upload():

    uploaded = request.files.get("file")

    if not uploaded or not uploaded.filename:
        return jsonify({
            "success": False,
            "message": "Hakuna file."
        }), 400

    if not allowed_file(uploaded.filename):
        return jsonify({
            "success": False,
            "message": "File hii hairuhusiwi."
        }), 400

    original = secure_filename(uploaded.filename)

    filename = f"{uuid.uuid4().hex}_{original}"

    uploaded.save(MEDIA_DIR / filename)

    return jsonify({
        "success": True,
        "filename": filename,
        "url": "/media/" + filename,
        "type": file_type(filename)
    })


# =========================================================
# CHAT
# =========================================================

@app.route("/api/messages")
def messages():

    user_id = request.args.get("user_id")
    other_id = request.args.get("other_id")

    if not user_id:
        return jsonify({
            "success": False,
            "messages": []
        })

    conn = db()

    if other_id:
        rows = conn.execute("""
            SELECT *
            FROM messages
            WHERE
                (sender_id=? AND receiver_id=?)
                OR
                (sender_id=? AND receiver_id=?)
            ORDER BY id ASC
        """, (
            user_id,
            other_id,
            other_id,
            user_id
        )).fetchall()
    else:
        rows = conn.execute("""
            SELECT *
            FROM messages
            WHERE sender_id=? OR receiver_id=?
            ORDER BY id ASC
        """, (user_id, user_id)).fetchall()

    conn.close()

    return jsonify({
        "success": True,
        "messages": [dict(x) for x in rows]
    })


@app.route("/api/messages", methods=["POST"])
def send_message():

    data = request.get_json(silent=True) or {}

    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")
    message = str(data.get("message", "")).strip()
    message_type = data.get("message_type", "text")
    file = data.get("file", "")

    if not sender_id:
        return jsonify({
            "success": False,
            "message": "sender_id inahitajika."
        }), 400

    if not message and not file:
        return jsonify({
            "success": False,
            "message": "Message haina content."
        }), 400

    conn = db()

    cur = conn.execute("""
        INSERT INTO messages(
            sender_id,
            receiver_id,
            message,
            file,
            message_type,
            created_at
        )
        VALUES(?,?,?,?,?,?)
    """, (
        sender_id,
        receiver_id,
        message,
        file,
        message_type,
        now()
    ))

    conn.commit()

    message_id = cur.lastrowid

    conn.close()

    return jsonify({
        "success": True,
        "message_id": message_id
    })


# =========================================================
# DOCUMENTS / KNOWLEDGE VAULT
# =========================================================

@app.route("/api/documents")
def documents():

    user_id = request.args.get("user_id")

    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM documents
        WHERE user_id=?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    conn.close()

    return jsonify({
        "success": True,
        "documents": [dict(x) for x in rows]
    })


@app.route("/api/documents", methods=["POST"])
def upload_document():

    user_id = request.form.get("user_id")
    uploaded = request.files.get("file")

    if not user_id or not uploaded:
        return jsonify({
            "success": False,
            "message": "User na file vinahitajika."
        }), 400

    if not allowed_file(uploaded.filename):
        return jsonify({
            "success": False,
            "message": "Document hairuhusiwi."
        }), 400

    original = secure_filename(uploaded.filename)

    filename = f"{uuid.uuid4().hex}_{original}"

    uploaded.save(MEDIA_DIR / filename)

    conn = db()

    cur = conn.execute("""
        INSERT INTO documents(
            user_id,
            filename,
            path,
            created_at
        )
        VALUES(?,?,?,?)
    """, (
        user_id,
        original,
        filename,
        now()
    ))

    conn.commit()

    document_id = cur.lastrowid

    conn.close()

    return jsonify({
        "success": True,
        "document_id": document_id,
        "filename": original,
        "url": "/media/" + filename
    })


# =========================================================
# AI COUNCILS
# =========================================================

AI_COUNCILS = {
    "education": {
        "name": "Edu AI",
        "description": "Msaidizi wa elimu, syllabus, notes, revision na assessment."
    },
    "health": {
        "name": "Health AI",
        "description": "Msaidizi wa maarifa ya afya na elimu ya afya."
    },
    "business": {
        "name": "Business AI",
        "description": "Msaidizi wa biashara, strategy, finance na entrepreneurship."
    },
    "agriculture": {
        "name": "Agriculture AI",
        "description": "Msaidizi wa kilimo, mazao, udongo, mifugo na irrigation."
    },
    "research": {
        "name": "Research AI",
        "description": "Msaidizi wa research questions, methodology na analysis."
    },
    "science": {
        "name": "Science & Technology AI",
        "description": "Msaidizi wa science, engineering na technology."
    },
    "vision": {
        "name": "Vision AI",
        "description": "Msaidizi wa kuchambua picha na visual information."
    }
}


@app.route("/api/ai/councils")
def councils():

    return jsonify({
        "success": True,
        "councils": AI_COUNCILS
    })


@app.route("/api/ai/ask", methods=["POST"])
def ai_ask():

    data = request.get_json(silent=True) or {}

    council = str(data.get("council", "education")).lower()
    question = str(data.get("question", "")).strip()

    if not question:
        return jsonify({
            "success": False,
            "message": "Andika swali kwanza."
        }), 400

    council_data = AI_COUNCILS.get(
        council,
        AI_COUNCILS["education"]
    )

    response = (
        f"{council_data['name']} imepokea swali lako. "
        f"Kwa sasa hii ni AI Council prototype ya MSAFIRI GLOBAL MEDIA. "
        f"Swali lako ni: {question}"
    )

    return jsonify({
        "success": True,
        "council": council_data["name"],
        "answer": response
    })


# =========================================================
# REALITY LAB
# =========================================================

@app.route("/api/reality")
def reality():

    return jsonify({
        "success": True,
        "tools": [
            {
                "id": "measure",
                "name": "Measure Length",
                "status": "available"
            },
            {
                "id": "counter",
                "name": "Object Counter",
                "status": "available"
            },
            {
                "id": "plant",
                "name": "Plant Identifier",
                "status": "available"
            }
        ]
    })


# =========================================================
# CHANNELS
# =========================================================

@app.route("/api/channels")
def channels():

    channels_data = [
        {
            "name": "BBC",
            "category": "News"
        },
        {
            "name": "CNN",
            "category": "News"
        },
        {
            "name": "National Geographic",
            "category": "Science & Documentary"
        },
        {
            "name": "Entertainment",
            "category": "Entertainment"
        },
        {
            "name": "Live Now",
            "category": "Live"
        }
    ]

    return jsonify({
        "success": True,
        "channels": channels_data
    })


# =========================================================
# MARKET
# =========================================================

@app.route("/api/market")
def market():

    products = [
        {
            "id": 1,
            "name": "Smart Phone",
            "category": "Electronics",
            "price": "TZS 450,000"
        },
        {
            "id": 2,
            "name": "Laptop",
            "category": "Technology",
            "price": "TZS 1,200,000"
        },
        {
            "id": 3,
            "name": "Solar System",
            "category": "Energy",
            "price": "TZS 850,000"
        }
    ]

    return jsonify({
        "success": True,
        "products": products
    })


# =========================================================
# PROJECT COLLABORATION
# =========================================================

@app.route("/api/projects", methods=["GET"])
def get_projects():

    user_id = request.args.get("user_id")

    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM projects
        WHERE user_id=?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    conn.close()

    return jsonify({
        "success": True,
        "projects": [dict(x) for x in rows]
    })


@app.route("/api/projects", methods=["POST"])
def create_project():

    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()

    if not user_id or not title:
        return jsonify({
            "success": False,
            "message": "Project title inahitajika."
        }), 400

    conn = db()

    cur = conn.execute("""
        INSERT INTO projects(
            user_id,
            title,
            description,
            created_at
        )
        VALUES(?,?,?,?)
    """, (
        user_id,
        title,
        description,
        now()
    ))

    project_id = cur.lastrowid

    conn.execute("""
        INSERT INTO project_tasks(project_id,task)
        VALUES(?,?)
    """, (
        project_id,
        "Project planning"
    ))

    conn.execute("""
        INSERT INTO project_tasks(project_id,task)
        VALUES(?,?)
    """, (
        project_id,
        "Build prototype"
    ))

    conn.execute("""
        INSERT INTO project_tasks(project_id,task)
        VALUES(?,?)
    """, (
        project_id,
        "Testing"
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "project_id": project_id
    })


# =========================================================
# SEARCH
# =========================================================

@app.route("/api/search")
def search():

    q = request.args.get("q", "").strip()

    if not q:
        return jsonify({
            "success": True,
            "results": []
        })

    conn = db()

    users_result = conn.execute("""
        SELECT id, username, name
        FROM users
        WHERE username LIKE ? OR name LIKE ?
        LIMIT 20
    """, (
        f"%{q}%",
        f"%{q}%"
    )).fetchall()

    posts_result = conn.execute("""
        SELECT id, user_id, caption, created_at
        FROM posts
        WHERE caption LIKE ?
        ORDER BY id DESC
        LIMIT 20
    """, (
        f"%{q}%",
    )).fetchall()

    conn.close()

    return jsonify({
        "success": True,
        "users": [dict(x) for x in users_result],
        "posts": [dict(x) for x in posts_result]
    })


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/api/dashboard")
def dashboard():

    user_id = request.args.get("user_id")

    conn = db()

    posts_count = conn.execute(
        "SELECT COUNT(*) AS c FROM posts WHERE user_id=?",
        (user_id,)
    ).fetchone()["c"]

    docs_count = conn.execute(
        "SELECT COUNT(*) AS c FROM documents WHERE user_id=?",
        (user_id,)
    ).fetchone()["c"]

    projects_count = conn.execute(
        "SELECT COUNT(*) AS c FROM projects WHERE user_id=?",
        (user_id,)
    ).fetchone()["c"]

    conn.close()

    return jsonify({
        "success": True,
        "dashboard": {
            "posts": posts_count,
            "documents": docs_count,
            "projects": projects_count
        }
    })


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(413)
def too_large(error):
    return jsonify({
        "success": False,
        "message": "File ni kubwa sana. Maximum ni 50MB."
    }), 413


@app.errorhandler(404)
def not_found(error):

    if request.path.startswith("/api/"):
        return jsonify({
            "success": False,
            "message": "API endpoint haijapatikana."
        }), 404

    return """
    <h1>MSAFIRI GLOBAL MEDIA V2</h1>
    <p>Page not found.</p>
    """, 404


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    print("=" * 55)
    print("       MSAFIRI GLOBAL MEDIA V2")
    print("=" * 55)
    print("STATUS : RUNNING")
    print("HOME   : /")
    print("API    : /api")
    print("HEALTH : /api/health")
    print("=" * 55)

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
