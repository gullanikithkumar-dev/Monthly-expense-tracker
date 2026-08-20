from flask import Flask, render_template, request, redirect, session, flash, send_file
import mysql.connector
from flask_bcrypt import Bcrypt
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "secretkey"

bcrypt = Bcrypt(app)

# Database Connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Nikki@18",
    database="expense_tracker"
)

cursor = db.cursor(dictionary=True, buffered=True)

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')

        try:
            cursor.execute(
                "INSERT INTO users (username,email,password) VALUES (%s,%s,%s)",
                (username,email,hashed)
            )
            db.commit()
            flash("Account created successfully")
            return redirect('/login')
        except:
            flash("Username already exists")

    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']

        cursor.execute(
            "SELECT * FROM users WHERE LOWER(username)=%s OR LOWER(email)=%s",
            (username, username)
        )
        user = cursor.fetchone()

        if not user:
            flash("User not found")
            return redirect('/login')

        if not bcrypt.check_password_hash(user['password'], password):
            flash("Invalid password")
            return redirect('/login')

        session['user_id'] = user['id']
        session['username'] = user['username']

        return redirect('/dashboard')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    month = request.args.get('month', '').strip()

    cursor.execute(
        "SELECT income FROM users WHERE id=%s",
        (session['user_id'],)
    )
    user_data = cursor.fetchone()
    monthly_income = float(user_data['income'] or 0)

    if month:
        cursor.execute(
            "SELECT * FROM expenses WHERE user_id=%s AND DATE_FORMAT(date,'%Y-%m')=%s ORDER BY date DESC",
            (session['user_id'], month)
        )
    else:
        cursor.execute(
            "SELECT * FROM expenses WHERE user_id=%s ORDER BY date DESC",
            (session['user_id'],)
        )

    expenses = cursor.fetchall()

    if month:
        cursor.execute(
            "SELECT IFNULL(SUM(amount),0) AS total FROM expenses WHERE user_id=%s AND DATE_FORMAT(date,'%Y-%m')=%s",
            (session['user_id'], month)
        )
    else:
        cursor.execute(
            "SELECT IFNULL(SUM(amount),0) AS total FROM expenses WHERE user_id=%s",
            (session['user_id'],)
        )

    total_expense = float(cursor.fetchone()['total'])

    balance = monthly_income - total_expense

    return render_template(
        'dashboard.html',
        expenses=expenses,
        total_expense=total_expense,
        monthly_income=monthly_income,
        balance=balance,
        selected_month=month if month else None
    )

@app.route('/add_expense', methods=['POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect('/login')

    action = request.form.get('action')

    if action == "income":
        income = request.form.get('monthly_income')

        cursor.execute(
            "UPDATE users SET income=%s WHERE id=%s",
            (income, session['user_id'])
        )
        db.commit()

        flash("Income updated")
        return redirect('/dashboard')

    if action == "add":
        title = request.form.get('title')
        amount = request.form.get('amount')
        category = request.form.get('category')
        date = request.form.get('date')

        cursor.execute(
            "INSERT INTO expenses (user_id,title,amount,category,date) VALUES (%s,%s,%s,%s,%s)",
            (session['user_id'], title, amount, category, date)
        )
        db.commit()

        flash("Expense added")
        return redirect('/dashboard')

@app.route('/delete/<int:id>')
def delete_expense(id):
    cursor.execute(
        "DELETE FROM expenses WHERE id=%s AND user_id=%s",
        (id, session['user_id'])
    )
    db.commit()
    return redirect('/dashboard')

@app.route('/edit/<int:id>', methods=['GET','POST'])
def edit_expense(id):
    if request.method == 'POST':
        title = request.form['title']
        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']

        cursor.execute(
            "UPDATE expenses SET title=%s, amount=%s, category=%s, date=%s WHERE id=%s AND user_id=%s",
            (title, amount, category, date, id, session['user_id'])
        )
        db.commit()

        return redirect('/dashboard')

    cursor.execute(
        "SELECT * FROM expenses WHERE id=%s AND user_id=%s",
        (id, session['user_id'])
    )
    expense = cursor.fetchone()

    return render_template('edit.html', expense=expense)

@app.route('/download_pdf')
def download_pdf():
    if 'user_id' not in session:
        return redirect('/login')

    month = request.args.get('month', '').strip()

    if month:
        cursor.execute(
            "SELECT * FROM expenses WHERE user_id=%s AND DATE_FORMAT(date,'%Y-%m')=%s ORDER BY date DESC",
            (session['user_id'], month)
        )
        title = f"Expense Report - {month}"
    else:
        cursor.execute(
            "SELECT * FROM expenses WHERE user_id=%s ORDER BY date DESC",
            (session['user_id'],)
        )
        title = "Expense Report - All Expenses"

    expenses = cursor.fetchall()

    file_path = "report.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=letter)

    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(title, styles['Title']))
    elements.append(Spacer(1, 10))

    if expenses:
        data = [["Title", "Amount", "Category", "Date"]]

        total = 0
        for e in expenses:
            data.append([
                e['title'],
                f"- ₹{int(e['amount'])}",
                e['category'],
                str(e['date'])
            ])
            total += e['amount']

        table = Table(data)

        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))

        elements.append(table)
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(f"<b>Total Amount: ₹{int(total)}</b>", styles['Normal']))
    else:
        elements.append(Paragraph("No expenses found for this period.", styles['Normal']))

    doc.build(elements)

    return send_file(file_path, as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# Explicitly defining development host configuration
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)