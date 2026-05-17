from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename
from datetime import timedelta

app = Flask(__name__)

# 세션 설정
app.secret_key = "분실물관리앱_비밀키_2025"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# 관리자 비밀번호
ADMIN_PASSWORD = "1234"

# 업로드 폴더 경로
UPLOAD_FOLDER = "static/uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ── DB 유틸리티 함수 ────────────────────
def save_item(name, location, lost_date, description, category, image_filename=None):
    conn = sqlite3.connect("lost_items.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO items (name, location, lost_date, description, category, image_filename)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (name, location, lost_date, description, category, image_filename))
    conn.commit()
    conn.close()

def get_db_items(category=None, search=None, show_found=True):
    """
    분실물 조회 함수
    category: 카테고리 필터
    search: 물건 이름 검색
    show_found: False면 찾은 물건 제외
    """
    conn = sqlite3.connect("lost_items.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM items WHERE 1=1"
    params = []
    
    # 카테고리 필터
    if category:
        query += " AND category = ?"
        params.append(category)
    
    # 검색 필터
    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")
    
    # 찾은 물건 제외
    if not show_found:
        query += " AND found = 0"
    
    # 최신순 정렬 (최근에 등록한 것부터)
    query += " ORDER BY id DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_statistics():
    """통계 데이터 반환"""
    conn = sqlite3.connect("lost_items.db")
    cursor = conn.cursor()
    
    # 전체 개수
    cursor.execute("SELECT COUNT(*) FROM items")
    total = cursor.fetchone()[0]
    
    # 찾은 개수
    cursor.execute("SELECT COUNT(*) FROM items WHERE found = 1")
    found_count = cursor.fetchone()[0]
    
    # 찾지 못한 개수
    not_found = total - found_count
    
    # 카테고리별 개수
    cursor.execute("""
        SELECT category, COUNT(*) as count 
        FROM items 
        WHERE found = 0
        GROUP BY category 
        ORDER BY count DESC
    """)
    by_category = cursor.fetchall()
    
    conn.close()
    
    return {
        "total": total,
        "found": found_count,
        "not_found": not_found,
        "by_category": by_category
    }

def delete_item(item_id):
    """아이템 삭제"""
    conn = sqlite3.connect("lost_items.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT image_filename FROM items WHERE id = ?", (item_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], result[0])
        if os.path.exists(image_path):
            os.remove(image_path)
    
    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def toggle_found(item_id):
    """찾음/찾지 못함 토글"""
    conn = sqlite3.connect("lost_items.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT found FROM items WHERE id = ?", (item_id,))
    result = cursor.fetchone()
    
    if result:
        new_found = 0 if result[0] == 1 else 1
        cursor.execute("UPDATE items SET found = ? WHERE id = ?", (new_found, item_id))
        conn.commit()
    
    conn.close()

def is_admin():
    """관리자 여부 확인"""
    return session.get("is_admin", False)

# ── 관리자 라우트 ────────────────────────
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password")
        
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            session.permanent = True
            return redirect("/")
        else:
            return render_template("admin_login.html", error="비밀번호가 틀렸습니다.")
    
    if is_admin():
        return redirect("/")
    
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect("/")

@app.route("/delete/<int:item_id>")
def delete(item_id):
    if not is_admin():
        return redirect("/admin")
    
    delete_item(item_id)
    return redirect("/")

@app.route("/toggle_found/<int:item_id>")
def toggle_found_route(item_id):
    if not is_admin():
        return redirect("/admin")
    
    toggle_found(item_id)
    return redirect("/")

# ── 메인 페이지 ────────────────────────
@app.route("/")
def index():
    category = request.args.get("category")
    search = request.args.get("search")
    
    items = get_db_items(category=category, search=search, show_found=False)
    stats = get_statistics()
    
    return render_template("index.html", 
                         items=items, 
                         current_category=category,
                         search_query=search,
                         stats=stats,
                         is_admin=is_admin())

# ── 대시보드 ────────────────────────
@app.route("/dashboard")
def dashboard():
    stats = get_statistics()
    
    # 최근 등록 5개
    conn = sqlite3.connect("lost_items.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE found = 0 ORDER BY id DESC LIMIT 5")
    recent = cursor.fetchall()
    conn.close()
    
    return render_template("dashboard.html", stats=stats, recent=recent, is_admin=is_admin())

# ── 분실물 등록 ────────────────────────
@app.route("/add", methods=["GET", "POST"])
def add_item():
    if request.method == "POST":
        name = request.form["item_name"]
        location = request.form["location"]
        lost_date = request.form["lost_date"]
        description = request.form["description"]
        category = request.form["category"]

        image_filename = None
        if "image" in request.files:
            file = request.files["image"]
            if file.filename != "":
                _, file_ext = os.path.splitext(file.filename)
                filename = f"{uuid.uuid4()}{file_ext}"
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                image_filename = filename

        save_item(name, location, lost_date, description, category, image_filename)
        return render_template("success.html", item_name=name)

    return render_template("add.html")

# ── 상세 페이지 ────────────────────────
@app.route("/item/<int:item_id>")
def item_detail(item_id):
    conn = sqlite3.connect("lost_items.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    
    if not item:
        return redirect("/")
    
    return render_template("item_detail.html", item=item, is_admin=is_admin())

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0")
