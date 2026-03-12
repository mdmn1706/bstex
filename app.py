from __future__ import annotations

import os
from datetime import timedelta
from functools import wraps

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database import db, authenticate, get_all_users, update_user, VALID_ROLES
from export_finance import export_finance_excel

app = Flask(__name__)
app.register_blueprint(export_finance_excel)

# ===================== CONFIG =====================

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "your-secret-key-change-this-in-production-2024")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

# Cookies
app.config["SESSION_COOKIE_SECURE"] = bool(int(os.environ.get("SESSION_COOKIE_SECURE", "0")))  # set 1 behind HTTPS
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")


# ===================== DECORATORS =====================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Пожалуйста, войдите в систему", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Пожалуйста, войдите в систему", "error")
            return redirect(url_for("login"))
        if session.get("user_role") != "Администратор":
            flash("Доступ запрещен. Требуются права администратора.", "error")
            return redirect(url_for("menu"))
        return f(*args, **kwargs)

    return decorated


# ===================== ROUTES =====================

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("menu"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("menu"))

    if request.method == "POST":
        access_code = (request.form.get("code") or "").strip()

        if not access_code:
            flash("Введите код доступа", "error")
            return render_template("login.html")

        if len(access_code) != 4 or not access_code.isdigit():
            flash("Код должен состоять из 4 цифр", "error")
            return render_template("login.html")

        user = authenticate(access_code)
        if user:
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_role"] = user["role"]

            db.log_login_attempt(user["id"], request.remote_addr or "", True)
            flash(f'Добро пожаловать, {user["username"]}!', "success")
            return redirect(url_for("menu"))

        db.log_login_attempt(None, request.remote_addr or "", False)
        flash("Неверный код доступа. Попробуйте еще раз.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    username = session.get("username", "Пользователь")
    session.clear()
    flash(f"До свидания, {username}! Вы вышли из системы.", "info")
    return redirect(url_for("login"))


@app.route("/menu")
@login_required
def menu():
    user_stats = db.get_user_stats()
    return render_template(
        "index.html",
        username=session.get("username"),
        role=session.get("user_role"),
        stats=user_stats,
    )


@app.route("/users", methods=["GET", "POST"])
@login_required
def users():
    if request.method == "POST":
        user_id = request.form.get("user_id")
        username = (request.form.get("username") or "").strip()
        access_code = (request.form.get("access_code") or "").strip()
        role = (request.form.get("role") or "").strip()

        if not user_id or not str(user_id).isdigit():
            flash("Некорректный user_id", "error")
            return redirect(url_for("users"))

        if not username:
            flash("Имя пользователя не может быть пустым", "error")
        elif len(access_code) != 4 or not access_code.isdigit():
            flash("Код должен состоять из 4 цифр", "error")
        elif not role:
            flash("Роль не может быть пустой", "error")
        elif role not in VALID_ROLES:
            flash("Недопустимая роль. Выберите из списка.", "error")
        else:
            success = update_user(int(user_id), username=username, access_code=access_code, role=role)
            if success:
                flash("Данные пользователя успешно обновлены", "success")
            else:
                flash("Ошибка при обновлении. Возможно, такое имя уже существует.", "error")

        return redirect(url_for("users"))

    all_users = get_all_users()
    current_user_id = session.get("user_id")
    return render_template(
        "users.html",
        users=all_users,
        current_user=session.get("username"),
        current_user_id=current_user_id,
        valid_roles=VALID_ROLES,
    )


@app.route("/users/add", methods=["POST"])
@login_required
def users_add():
    username    = (request.form.get("username") or "").strip()
    access_code = (request.form.get("access_code") or "").strip()
    role        = (request.form.get("role") or "").strip()

    if not username:
        flash("Имя пользователя не может быть пустым", "error")
    elif len(access_code) != 4 or not access_code.isdigit():
        flash("Код доступа должен состоять из 4 цифр", "error")
    elif not role or role not in VALID_ROLES:
        flash("Выберите допустимую роль из списка", "error")
    else:
        ok = db.create_user(username=username, access_code=access_code, role=role)
        if ok:
            flash(f"Пользователь «{username}» успешно добавлен", "success")
        else:
            flash("Ошибка: пользователь с таким именем уже существует", "error")

    return redirect(url_for("users"))


@app.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
def users_delete(user_id: int):
    if user_id == session.get("user_id"):
        flash("Нельзя удалить свою учётную запись", "error")
        return redirect(url_for("users"))
    user = db.get_user_by_id(user_id)
    if not user:
        flash("Пользователь не найден", "error")
        return redirect(url_for("users"))
    ok = db.delete_user(user_id)
    if ok:
        flash(f"Пользователь «{user['username']}» удалён", "success")
    else:
        flash("Ошибка при удалении", "error")
    return redirect(url_for("users"))


# ===================== FINANCE =====================

@app.route("/finance")
@login_required
def finance():
    expenses = db.get_all_expenses(limit=50)
    income = db.get_all_income(limit=50)
    balance = db.get_cash_balance()
    summary = db.get_financial_summary()
    return render_template(
        "finance.html",
        expenses=expenses,
        income=income,
        balance=balance,
        summary=summary,
        username=session.get("username"),
        role=session.get("user_role"),
    )


@app.route("/api/expense/add", methods=["POST"])
@login_required
def add_expense_api():
    try:
        data = request.get_json(force=True) or {}
        expense_type = (data.get("expense_type") or "").strip()
        amount = float(data.get("amount", 0) or 0)
        payment_type = (data.get("payment_type") or "").strip()
        order_ref = (data.get("order_ref") or "").strip() or None
        comment = (data.get("comment") or "").strip() or None

        if not expense_type or amount <= 0 or payment_type not in ("cash", "account"):
            return jsonify({"success": False, "message": "Некорректные данные"}), 400

        expense_id = db.add_expense(
            expense_type=expense_type,
            amount=amount,
            payment_type=payment_type,
            order_ref=order_ref,
            comment=comment,
            user_id=session.get("user_id"),
        )

        return jsonify(
            {
                "success": True,
                "message": "Расход успешно добавлен",
                "expense_id": expense_id,
                "balance": db.get_cash_balance(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/income/add", methods=["POST"])
@login_required
def add_income_api():
    try:
        data = request.get_json(force=True) or {}
        amount = float(data.get("amount", 0) or 0)
        payment_type = (data.get("payment_type") or "").strip()
        source = (data.get("source") or "").strip()
        comment = (data.get("comment") or "").strip() or None

        if amount <= 0 or payment_type not in ("cash", "account") or not source:
            return jsonify({"success": False, "message": "Некорректные данные"}), 400

        income_id = db.add_income(
            amount=amount,
            payment_type=payment_type,
            source=source,
            comment=comment,
            user_id=session.get("user_id"),
        )

        return jsonify(
            {
                "success": True,
                "message": "Приход успешно добавлен",
                "income_id": income_id,
                "balance": db.get_cash_balance(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/balance", methods=["GET"])
@login_required
def get_balance_api():
    return jsonify({"success": True, "balance": db.get_cash_balance(), "summary": db.get_financial_summary()})


# ===================== ORDERS PAGES =====================

@app.route("/orders")
@login_required
def orders():
    orders_list = db.get_orders(limit=300, status=None)
    return render_template(
        "orders.html",
        orders=orders_list,
        username=session.get("username"),
        role=session.get("user_role"),
    )


@app.route("/active-orders")
@login_required
def active_orders_page():
    return render_template("active-orders.html")


@app.route("/add-order")
@login_required
def orders_add():
    return render_template("add-order.html")


# ===================== PRODUCTION PAGE =====================

@app.route("/production")
@login_required
def production_page():
    return render_template("production.html")


# ===================== SERVICES PAGES =====================

@app.route("/add-service")
@login_required
def services_add_page():
    return render_template("add-service.html")


@app.route("/active-services")
@login_required
def active_services_page():
    return render_template("active-services.html")


@app.route("/api/warehouse/products/add", methods=["POST"])
@login_required
def api_warehouse_product_add():
    try:
        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"success": False, "message": "Название не может быть пустым"}), 400
        result = db.create_warehouse_product(name)
        return jsonify({"success": True, "product": result})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


# ===================== WAREHOUSE PAGE =====================

@app.route("/warehouse")
@login_required
def warehouse_page():
    return render_template("warehouse.html")

@app.route("/reports")
@login_required
def warehouse_pag2e():
    return render_template("reports.html")


# ===================== STATISTICS API =====================

@app.route("/api/stats/orders")
@login_required
def api_stats_orders():
    try:
        date_from = (request.args.get("date_from") or "").strip() or None
        date_to   = (request.args.get("date_to")   or "").strip() or None
        order_id  = request.args.get("order_id", type=int)
        data = db.get_orders_stats(date_from=date_from, date_to=date_to, order_id=order_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/stats/orders/<int:order_id>/detail")
@login_required
def api_order_full_detail(order_id: int):
    try:
        data = db.get_order_full_detail(order_id)
        if not data:
            return jsonify({"success": False, "message": "Заказ не найден"}), 404
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/stats/production")
@login_required
def api_stats_production():
    try:
        date_from = (request.args.get("date_from") or "").strip() or None
        date_to   = (request.args.get("date_to")   or "").strip() or None
        order_id  = request.args.get("order_id", type=int)
        data = db.get_production_stats(date_from=date_from, date_to=date_to, order_id=order_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/stats/services")
@login_required
def api_stats_services():
    try:
        date_from = (request.args.get("date_from") or "").strip() or None
        date_to   = (request.args.get("date_to")   or "").strip() or None
        data = db.get_services_stats(date_from=date_from, date_to=date_to)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/stats/finance")
@login_required
def api_stats_finance():
    try:
        date_from = (request.args.get("date_from") or "").strip() or None
        date_to   = (request.args.get("date_to")   or "").strip() or None
        data = db.get_finance_stats(date_from=date_from, date_to=date_to)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/stats/warehouse")
@login_required
def api_stats_warehouse():
    try:
        order_id = request.args.get("order_id", type=int)
        data = db.get_warehouse_stats(order_id=order_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ===================== ORDERS API =====================

@app.route("/api/orders", methods=["GET"])
@login_required
def api_orders_list():
    """
    Query:
      status: active|done|cancelled|completed|all
      limit: int
    """
    status = (request.args.get("status") or "").strip().lower()
    limit = request.args.get("limit", 300, type=int)

    if status in ("", "all", "none"):
        db_status = None
    elif status in ("completed", "done"):
        db_status = "done"
    elif status in ("active", "new", "in-progress", "inprogress"):
        db_status = "active"
    elif status == "cancelled":
        db_status = "cancelled"
    else:
        return jsonify({"success": False, "message": "Некорректный status"}), 400

    orders_list = db.get_orders(limit=limit, status=db_status)
    return jsonify({"success": True, "orders": orders_list})


@app.route("/api/orders/options", methods=["GET"])
@login_required
def api_orders_options():
    status = (request.args.get("status") or "active").strip()
    limit = request.args.get("limit", 500, type=int)
    wip_stage = (request.args.get("wip_stage") or "").strip() or None
    prev_wip_stage = (request.args.get("prev_wip_stage") or "").strip() or None
    options = db.get_order_options(status=status, limit=limit, wip_stage=wip_stage, prev_wip_stage=prev_wip_stage)
    return jsonify({"success": True, "orders": options})


@app.route("/api/orders/<int:order_id>", methods=["GET"])
@login_required
def api_order_get(order_id: int):
    order = db.get_order_by_id(order_id)
    if not order:
        return jsonify({"success": False, "message": "Заказ не найден"}), 404
    return jsonify({"success": True, "order": order})


@app.route("/api/orders/add", methods=["POST"])
@login_required
def api_orders_add():
    try:
        data = request.get_json(force=True) or {}

        order_code = (data.get("order_code") or "").strip()
        model = (data.get("model") or "").strip()
        client = (data.get("client") or "").strip()
        order_date = (data.get("order_date") or "").strip()
        shipment_date = (data.get("shipment_date") or "").strip()
        currency = (data.get("currency") or "").strip()

        exchange_rate_raw = data.get("exchange_rate")
        exchange_rate = None
        if exchange_rate_raw not in (None, "", "null"):
            exchange_rate = float(exchange_rate_raw)

        price_per_unit = float(data.get("price_per_unit") or 0)
        notes = (data.get("notes") or "").strip() or None
        items = data.get("items") or []

        order_id = db.create_order(
            order_code=order_code,
            model=model,
            client=client,
            order_date=order_date,
            shipment_date=shipment_date,
            currency=currency,
            exchange_rate=exchange_rate,
            price_per_unit=price_per_unit,
            notes=notes,
            items=items,
            created_by=session.get("user_id"),
        )

        return jsonify({"success": True, "message": "Заказ создан", "order_id": order_id})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


# ===================== ORDER / SERVICE STATUS API =====================

@app.route("/api/orders/<int:order_id>/status", methods=["POST"])
@login_required
def api_order_status_update(order_id: int):
    try:
        if not db.get_order_by_id(order_id):
            return jsonify({"success": False, "message": "Заказ не найден"}), 404
        data = request.get_json(force=True) or {}
        status = (data.get("status") or "").strip()
        db.update_order_status(order_id, status, updated_by=session.get("user_id"))
        return jsonify({"success": True, "message": "Статус заказа обновлён", "status": status})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/services/<int:service_id>/status", methods=["POST"])
@login_required
def api_service_status_update(service_id: int):
    try:
        if not db.get_service_by_id(service_id):
            return jsonify({"success": False, "message": "Услуга не найдена"}), 404
        data = request.get_json(force=True) or {}
        status = (data.get("status") or "").strip()
        db.update_service_status(service_id, status, updated_by=session.get("user_id"))
        return jsonify({"success": True, "message": "Статус услуги обновлён", "status": status})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


# ===================== STAGES API =====================

@app.route("/api/stages", methods=["GET"])
@login_required
def api_stages_list():
    stages = db.get_production_stages()
    return jsonify({"success": True, "stages": stages})


@app.route("/api/orders/<int:order_id>/stages", methods=["GET"])
@login_required
def api_order_stages(order_id: int):
    if not db.get_order_by_id(order_id):
        return jsonify({"success": False, "message": "Заказ не найден"}), 404
    stages = db.get_order_stages(order_id)
    return jsonify({"success": True, "stages": stages})


@app.route("/api/orders/<int:order_id>/stages/<stage_key>", methods=["POST"])
@login_required
def api_order_stage_update(order_id: int, stage_key: str):
    try:
        if not db.get_order_by_id(order_id):
            return jsonify({"success": False, "message": "Заказ не найден"}), 404

        data = request.get_json(force=True) or {}
        status = data.get("status")
        progress = data.get("progress", None)
        note = data.get("note", None)

        db.update_order_stage(
            order_id=order_id,
            stage_key=stage_key,
            status=status,
            progress=progress,
            note=note,
            updated_by=session.get("user_id"),
        )
        return jsonify({"success": True, "message": "Этап обновлен"})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


# ===================== WIP API =====================

@app.route("/api/wip/<int:order_id>/<stage_key>", methods=["GET"])
@login_required
def api_wip_get_stage(order_id: int, stage_key: str):
    try:
        if not db.get_order_by_id(order_id):
            return jsonify({"success": False, "message": "Заказ не найден"}), 404
        rows = db.wip_get_stage(order_id=order_id, stage_key=stage_key)
        return jsonify({"success": True, "rows": rows})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/wip/cutting/create", methods=["POST"])
@login_required
def api_wip_cutting_create():
    """
    Body:
      { order_id, lines:[{color,size,qty}], comment? }
    """
    try:
        data = request.get_json(force=True) or {}
        order_id = int(data.get("order_id") or 0)
        comment = (data.get("comment") or "").strip() or None
        lines_in = data.get("lines") or []

        if order_id <= 0 or not isinstance(lines_in, list):
            return jsonify({"success": False, "message": "Некорректные данные"}), 400

        lines = []
        for ln in lines_in:
            color = (ln.get("color") or "").strip()
            size = (ln.get("size") or "").strip()
            qty = int(ln.get("qty") or 0)
            if color and size and qty > 0:
                lines.append({"color": color, "size": size, "qty": qty})

        if not lines:
            return jsonify({"success": False, "message": "Нет количеств для сохранения"}), 400

        txn_id = db.wip_create_or_add(
            order_id=order_id,
            stage_key="cutting",
            lines=lines,
            comment=comment,
            created_by=session.get("user_id"),
        )

        db.update_order_stage(order_id, "cutting", status="in-progress", progress=None, note=None, updated_by=session.get("user_id"))

        return jsonify({"success": True, "message": "Раскроенные изделия сохранены", "txn_id": txn_id})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/wip/transfer", methods=["POST"])
@login_required
def api_wip_transfer():
    """
    Body:
      { order_id, from_stage, to_stage, lines:[{color,size,grade?,qty}], comment? }
    """
    try:
        data = request.get_json(force=True) or {}
        order_id = int(data.get("order_id") or 0)
        from_stage = (data.get("from_stage") or "").strip()
        to_stage = (data.get("to_stage") or "").strip()
        comment = (data.get("comment") or "").strip() or None
        lines = data.get("lines") or []

        if order_id <= 0 or not from_stage or not to_stage or not isinstance(lines, list) or not lines:
            return jsonify({"success": False, "message": "Некорректные данные"}), 400

        txn_id = db.wip_transfer(
            order_id=order_id,
            from_stage=from_stage,
            to_stage=to_stage,
            lines=lines,
            comment=comment,
            created_by=session.get("user_id"),
        )

        db.update_order_stage(order_id, from_stage, status="in-progress", progress=None, note=None, updated_by=session.get("user_id"))
        db.update_order_stage(order_id, to_stage, status="in-progress", progress=None, note=None, updated_by=session.get("user_id"))

        return jsonify({"success": True, "message": "Передача выполнена", "txn_id": txn_id})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/wip/control/grade-to-packing", methods=["POST"])
@login_required
def api_wip_grade_to_packing():
    """
    Body:
      { order_id, lines:[{color,size,total,g1,g15,g2}], comment? }
    """
    try:
        data = request.get_json(force=True) or {}
        order_id = int(data.get("order_id") or 0)
        comment = (data.get("comment") or "").strip() or None
        lines = data.get("lines") or []

        if order_id <= 0 or not isinstance(lines, list) or not lines:
            return jsonify({"success": False, "message": "Некорректные данные"}), 400

        txn_id = db.wip_grade_to_packing(order_id=order_id, lines=lines, comment=comment, created_by=session.get("user_id"))

        db.update_order_stage(order_id, "control", status="in-progress", progress=None, note=None, updated_by=session.get("user_id"))
        db.update_order_stage(order_id, "packing", status="in-progress", progress=None, note=None, updated_by=session.get("user_id"))

        return jsonify({"success": True, "message": "Распределение по сортам сохранено", "txn_id": txn_id})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/wip/scrap", methods=["POST"])
@login_required
def api_wip_scrap():
    """
    Body:
      { order_id, stage_key, lines:[{color,size,grade?,qty}], comment? }
    """
    try:
        data = request.get_json(force=True) or {}
        order_id = int(data.get("order_id") or 0)
        stage_key = (data.get("stage_key") or "").strip()
        comment = (data.get("comment") or "").strip() or None
        lines = data.get("lines") or []

        if order_id <= 0 or not stage_key or not isinstance(lines, list) or not lines:
            return jsonify({"success": False, "message": "Некорректные данные"}), 400

        txn_id = db.wip_scrap(order_id=order_id, stage_key=stage_key, lines=lines, comment=comment, created_by=session.get("user_id"))
        db.update_order_stage(order_id, stage_key, status="in-progress", progress=None, note=None, updated_by=session.get("user_id"))
        return jsonify({"success": True, "message": "Брак сохранён", "txn_id": txn_id})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


# ===================== SERVICES API =====================

@app.route("/api/services/add", methods=["POST"])
@login_required
def api_services_add():
    try:
        data = request.get_json(force=True) or {}

        order_id = int(data.get("order_id") or 0)
        factory_name = (data.get("factory_name") or "").strip()
        stage_from = (data.get("stage_from") or "").strip()
        stage_to = (data.get("stage_to") or "").strip()
        transfer_date = (data.get("transfer_date") or "").strip()
        comment = (data.get("comment") or "").strip() or None
        items = data.get("items") or []

        payment_type = (data.get("payment_type") or "cash").strip()
        if payment_type not in ("cash", "account"):
            return jsonify({"success": False, "message": "payment_type должен быть cash или account"}), 400

        service_id = db.create_service(
            order_id=order_id,
            factory_name=factory_name,
            stage_from=stage_from,
            stage_to=stage_to,
            transfer_date=transfer_date,
            comment=comment,
            items=items,
            created_by=session.get("user_id"),
            create_expense=True,
            expense_payment_type=payment_type,
        )

        return jsonify({"success": True, "message": "Услуга сохранена", "service_id": service_id})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/services", methods=["GET"])
@login_required
def api_services_list():
    try:
        status = (request.args.get("status") or "").strip() or None
        q = (request.args.get("q") or "").strip() or None
        limit = request.args.get("limit", 300, type=int)
        offset = request.args.get("offset", 0, type=int)

        services = db.get_services(limit=limit, offset=offset, status=status, q=q)
        return jsonify({"success": True, "services": services})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/services/<int:service_id>", methods=["GET"])
@login_required
def api_service_get(service_id: int):
    try:
        service = db.get_service_by_id(service_id)
        if not service:
            return jsonify({"success": False, "message": "Услуга не найдена"}), 404
        return jsonify({"success": True, "service": service})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/services/<int:service_id>/items", methods=["GET"])
@login_required
def api_service_items(service_id: int):
    try:
        if not db.get_service_by_id(service_id):
            return jsonify({"success": False, "message": "Услуга не найдена"}), 404
        items = db.get_service_items(service_id)
        return jsonify({"success": True, "items": items})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/services/<int:service_id>/stages", methods=["GET"])
@login_required
def api_service_stages(service_id: int):
    try:
        if not db.get_service_by_id(service_id):
            return jsonify({"success": False, "message": "Услуга не найдена"}), 404
        stages = db.get_service_stages(service_id)
        return jsonify({"success": True, "stages": stages})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/services/<int:service_id>/stages/<stage_key>", methods=["POST"])
@login_required
def api_service_stage_update(service_id: int, stage_key: str):
    try:
        if not db.get_service_by_id(service_id):
            return jsonify({"success": False, "message": "Услуга не найдена"}), 404

        data = request.get_json(force=True) or {}
        status = (data.get("status") or "").strip()
        progress = data.get("progress", None)
        note = data.get("note", None)

        db.update_service_stage(
            service_id=service_id,
            stage_key=stage_key,
            status=status,
            progress=progress,
            note=note,
            updated_by=session.get("user_id"),
        )
        return jsonify({"success": True, "message": "Этап услуги обновлен"})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


# ===================== WAREHOUSE API =====================

@app.route("/api/warehouse/catalog", methods=["GET"])
@login_required
def api_warehouse_catalog():
    try:
        cat = db.get_warehouse_catalog()
        return jsonify({"success": True, **cat})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/warehouse/income", methods=["POST"])
@login_required
def api_warehouse_income():
    try:
        data = request.get_json(force=True) or {}
        order_id = int(data.get("order_id") or 0)
        product_id = int(data.get("product_id") or 0)
        qty = float(data.get("qty") or 0)
        unit = (data.get("unit") or "").strip()

        if order_id <= 0 or product_id <= 0 or qty <= 0 or not unit:
            return jsonify({"success": False, "message": "Некорректные данные"}), 400

        txn_id = db.warehouse_income(
            order_id=order_id,
            product_id=product_id,
            qty=qty,
            unit=unit,
            to_location="MAIN",
            comment=(data.get("comment") or "").strip() or None,
            created_by=session.get("user_id"),
        )

        return jsonify({"success": True, "message": "Приход на склад сохранён", "txn_id": txn_id})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/warehouse/txn", methods=["POST"])
@login_required
def api_warehouse_txn_create():
    try:
        data = request.get_json(force=True) or {}

        txn_type = (data.get("txn_type") or "").strip()
        order_id = data.get("order_id", None)
        from_location = (data.get("from_location") or "").strip() or None
        to_location = (data.get("to_location") or "").strip() or None
        reason = (data.get("reason") or "").strip() or None
        comment = (data.get("comment") or "").strip() or None
        allow_negative = bool(data.get("allow_negative", False))
        lines = data.get("lines") or []

        txn_id = db.warehouse_create_txn(
            txn_type=txn_type,
            order_id=order_id,
            from_location=from_location,
            to_location=to_location,
            reason=reason,
            comment=comment,
            lines=lines,
            created_by=session.get("user_id"),
            allow_negative=allow_negative,
        )

        return jsonify({"success": True, "message": "Операция склада выполнена", "txn_id": txn_id})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/warehouse/stock/by-order", methods=["GET"])
@login_required
def api_warehouse_stock_by_order():
    try:
        order_id = request.args.get("order_id", type=int)
        if not order_id:
            return jsonify({"success": False, "message": "order_id обязателен"}), 400

        location = (request.args.get("location") or "").strip() or None
        rows = db.get_warehouse_stock_by_order(order_id=order_id, location=location)
        return jsonify({"success": True, "rows": rows})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/warehouse/stock/all", methods=["GET"])
@login_required
def api_warehouse_stock_all():
    try:
        rows = db.get_warehouse_stock_all()
        return jsonify({"success": True, "rows": rows})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/warehouse/stock/production", methods=["GET"])
@login_required
def api_warehouse_stock_production():
    """Остатки материалов в производстве по этапам (CUTTING/SEWING/PACKING)"""
    try:
        rows = db.get_production_stock()
        return jsonify({"success": True, "rows": rows})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


@app.route("/api/warehouse/txn", methods=["GET"])
@login_required
def api_warehouse_txn_list():
    try:
        order_id_raw = request.args.get("order_id")
        txn_type = (request.args.get("txn_type") or "").strip() or None
        limit = request.args.get("limit", 200, type=int)

        order_id = None
        if order_id_raw not in (None, "", "null"):
            order_id = int(order_id_raw)

        rows = db.get_warehouse_txn_list(order_id=order_id, txn_type=txn_type, limit=limit)
        return jsonify({"success": True, "rows": rows})
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


# ===================== USER API =====================

@app.route("/api/user/<int:user_id>")
@login_required
def get_user_api(user_id: int):
    user = db.get_user_by_id(user_id)
    if user:
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False, "message": "Пользователь не найден"}), 404


@app.route("/api/update-user", methods=["POST"])
@login_required
def update_user_api():
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id")
    username = (data.get("username") or "").strip()
    access_code = (data.get("access_code") or "").strip()
    role = (data.get("role") or "").strip()

    if not user_id or not str(user_id).isdigit():
        return jsonify({"success": False, "message": "Некорректный user_id"}), 400
    if not username:
        return jsonify({"success": False, "message": "Имя пользователя не может быть пустым"}), 400
    if len(access_code) != 4 or not access_code.isdigit():
        return jsonify({"success": False, "message": "Код должен состоять из 4 цифр"}), 400
    if not role:
        return jsonify({"success": False, "message": "Роль не может быть пустой"}), 400
    if role not in VALID_ROLES:
        return jsonify({"success": False, "message": "Недопустимая роль"}), 400

    success = update_user(int(user_id), username=username, access_code=access_code, role=role)
    if success:
        return jsonify({"success": True, "message": "Пользователь успешно обновлен"})
    return jsonify({"success": False, "message": "Ошибка при обновлении"}), 500


@app.route("/api/users/<int:user_id>/delete", methods=["POST"])
@login_required
def api_user_delete(user_id: int):
    if user_id == session.get("user_id"):
        return jsonify({"success": False, "message": "Нельзя удалить свою учётную запись"}), 400
    user = db.get_user_by_id(user_id)
    if not user:
        return jsonify({"success": False, "message": "Пользователь не найден"}), 404
    ok = db.delete_user(user_id)
    if ok:
        return jsonify({"success": True, "message": f"Пользователь «{user['username']}» удалён"})
    return jsonify({"success": False, "message": "Ошибка при удалении"}), 500


@app.route("/api/roles", methods=["GET"])
@login_required
def api_roles():
    return jsonify({"success": True, "roles": VALID_ROLES})


# ===================== ERRORS =====================

@app.errorhandler(404)
def not_found_error(e):
    try:
        return render_template("404.html"), 404
    except Exception:
        return "<h1>404 — Страница не найдена</h1>", 404


@app.errorhandler(500)
def internal_error(e):
    try:
        return render_template("500.html"), 500
    except Exception:
        return "<h1>500 — Внутренняя ошибка сервера</h1>", 500


@app.context_processor
def inject_user():
    return {
        "current_user": {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "role": session.get("user_role"),
        }
        if "user_id" in session
        else None
    }


if __name__ == "__main__":
    print("🚀 Запуск приложения...")
    print(f"👤 Пользователей в БД: {len(get_all_users())}")
    app.run(host="0.0.0.0", port=5000, debug=True)