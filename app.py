import os
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from flask_mysqldb import MySQL
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'replace_with_a_strong_random_key'

# Single hard‑coded login
app.config['USERNAME'] = 'admin'
app.config['PASSWORD'] = 'password'

# MySQL config
app.config['MYSQL_HOST']        = 'localhost'
app.config['MYSQL_USER']        = 'root'
app.config['MYSQL_PASSWORD']    = '20sMYdec@de'
app.config['MYSQL_DB']          = 'Real_EstateManagement_System'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# File upload config
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

mysql = MySQL(app)

def allowed_file(filename):
    return (
        '.' in filename and
        filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS
    )

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            flash("Please log in first.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# -----------------------
# Home (show all properties)
# -----------------------
@app.route('/')
def index():
    q = request.args.get('q','').strip()
    cur = mysql.connection.cursor()
    if q:
        cur.execute("""
          SELECT
            P.propertyId,
            P.address,
            PT.typeName      AS propertyType,
            IL.city, IL.state,
            COALESCE(
              (SELECT imageURL
                 FROM PropertyImages
                WHERE propertyId = P.propertyId
                ORDER BY isPrimary DESC, imageId ASC
                LIMIT 1),
              '/static/images/no-image.png'
            ) AS primaryImage,
            P.price
          FROM Property P
          JOIN PropertyType PT   ON P.typeId     = PT.typeId
          JOIN IndianLocation IL ON P.locationId = IL.locationId
          WHERE P.address LIKE %s
          ORDER BY P.propertyId DESC
        """, ('%'+q+'%',))
    else:
        cur.execute("""
          SELECT
            P.propertyId,
            P.address,
            PT.typeName      AS propertyType,
            IL.city, IL.state,
            COALESCE(
              (SELECT imageURL
                 FROM PropertyImages
                WHERE propertyId = P.propertyId
                ORDER BY isPrimary DESC, imageId ASC
                LIMIT 1),
              '/static/images/no-image.png'
            ) AS primaryImage,
            P.price
          FROM Property P
          JOIN PropertyType PT   ON P.typeId     = PT.typeId
          JOIN IndianLocation IL ON P.locationId = IL.locationId
          ORDER BY P.propertyId DESC
        """)
    properties = cur.fetchall()
    cur.close()
    return render_template('index.html', properties=properties, q=q)

# -----------------------
# Login / Logout
# -----------------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u = request.form['username']
        p = request.form['password']
        if u==app.config['USERNAME'] and p==app.config['PASSWORD']:
            session['logged_in']=True
            flash("Logged in.","success")
            return redirect(url_for('properties'))
        flash("Invalid credentials.","danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash("Logged out.","info")
    return redirect(url_for('login'))

# -----------------------
# Manage Properties
# -----------------------
@app.route('/properties')
@login_required
def properties():
    q = request.args.get('q','').strip()
    cur = mysql.connection.cursor()
    if q:
        cur.execute("""
          SELECT
            P.propertyId,
            P.address,
            PT.typeName       AS propertyType,
            IL.city, IL.state,
            COALESCE(
              (SELECT imageURL
                 FROM PropertyImages
                WHERE propertyId = P.propertyId
                ORDER BY isPrimary DESC, imageId ASC
                LIMIT 1),
              '/static/images/no-image.png'
            ) AS primaryImage,
            P.price
          FROM Property P
          JOIN PropertyType PT   ON P.typeId     = PT.typeId
          JOIN IndianLocation IL ON P.locationId = IL.locationId
          WHERE P.address LIKE %s
          ORDER BY P.propertyId DESC
        """, ('%'+q+'%',))
    else:
        cur.execute("""
          SELECT
            P.propertyId,
            P.address,
            PT.typeName       AS propertyType,
            IL.city, IL.state,
            COALESCE(
              (SELECT imageURL
                 FROM PropertyImages
                WHERE propertyId = P.propertyId
                ORDER BY isPrimary DESC, imageId ASC
                LIMIT 1),
              '/static/images/no-image.png'
            ) AS primaryImage,
            P.price
          FROM Property P
          JOIN PropertyType PT   ON P.typeId     = PT.typeId
          JOIN IndianLocation IL ON P.locationId = IL.locationId
          ORDER BY P.propertyId DESC
        """)
    props = cur.fetchall()
    cur.close()
    return render_template('properties.html', properties=props, q=q)

# -----------------------
# Create Property
# -----------------------
@app.route('/properties/create', methods=['GET','POST'])
@login_required
def create_property():
    cur = mysql.connection.cursor()
    cur.execute("SELECT userId, username FROM Users")
    users = cur.fetchall()
    cur.execute("SELECT typeId, typeName FROM PropertyType")
    types = cur.fetchall()
    cur.close()

    if request.method=='POST':
        # map city to locationId
        city = request.form['city']
        lid_cur = mysql.connection.cursor()
        lid_cur.execute(
          "SELECT locationId FROM IndianLocation WHERE city=%s", (city,)
        )
        loc = lid_cur.fetchone()
        if not loc:
            flash("City not in DB","danger")
            return redirect(request.url)
        location_id = loc['locationId']

        data = (
          request.form['address'],
          request.form['ownerId'],
          request.form['price'],
          request.form['carpetArea'],
          request.form['typeId'],
          location_id,
          1 if request.form.get('reraRegistered') else 0
        )
        cur = mysql.connection.cursor()
        cur.execute("""
          INSERT INTO Property
            (address,ownerId,price,carpetArea,typeId,locationId,reraRegistered)
          VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, data)
        mysql.connection.commit()
        pid = cur.lastrowid

        # uploads
        files = request.files.getlist('images')
        folder = os.path.join(app.config['UPLOAD_FOLDER'],str(pid))
        os.makedirs(folder,exist_ok=True)
        for idx,file in enumerate(files):
            if file and allowed_file(file.filename):
                fn=secure_filename(file.filename)
                p=os.path.join(folder,fn)
                file.save(p)
                url=f'/static/uploads/{pid}/{fn}'
                cur.execute("""
                  INSERT INTO PropertyImages
                    (propertyId,imageURL,isPrimary)
                  VALUES (%s,%s,%s)
                """,(pid,url, idx==0))
        mysql.connection.commit()
        cur.close()
        flash("Created","success")
        return redirect(url_for('properties'))

    return render_template(
      'property_form.html',
      action='Create',
      users=users,
      types=types,
      property=None,
      property_images=[]
    )

# -----------------------
# Update Property
# -----------------------
@app.route('/properties/update/<int:id>', methods=['GET','POST'])
@login_required
def update_property(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Property WHERE propertyId=%s",(id,))
    prop=cur.fetchone()
    cur.execute("SELECT userId,username FROM Users")
    users=cur.fetchall()
    cur.execute("SELECT typeId,typeName FROM PropertyType")
    types=cur.fetchall()
    cur.execute("SELECT * FROM PropertyImages WHERE propertyId=%s",(id,))
    imgs=cur.fetchall()
    cur.close()

    if request.method=='POST':
        city=request.form['city']
        lid_cur=mysql.connection.cursor()
        lid_cur.execute(
          "SELECT locationId FROM IndianLocation WHERE city=%s",(city,)
        )
        loc=lid_cur.fetchone()
        if not loc:
            flash("City not in DB","danger")
            return redirect(request.url)
        location_id=loc['locationId']

        data=(
          request.form['address'],
          request.form['ownerId'],
          request.form['price'],
          request.form['carpetArea'],
          request.form['typeId'],
          location_id,
          1 if request.form.get('reraRegistered') else 0,
          id
        )
        cur=mysql.connection.cursor()
        cur.execute("""
          UPDATE Property SET
            address=%s,ownerId=%s,price=%s,carpetArea=%s,
            typeId=%s,locationId=%s,reraRegistered=%s
          WHERE propertyId=%s
        """,data)

        # deletes
        for did in request.form.getlist('delete_images'):
            cur.execute("DELETE FROM PropertyImages WHERE imageId=%s",(did,))
        # new uploads
        files=request.files.getlist('images')
        folder=os.path.join(app.config['UPLOAD_FOLDER'],str(id))
        os.makedirs(folder,exist_ok=True)
        for file in files:
            if file and allowed_file(file.filename):
                fn=secure_filename(file.filename)
                p=os.path.join(folder,fn)
                file.save(p)
                url=f'/static/uploads/{id}/{fn}'
                cur.execute("""
                  INSERT INTO PropertyImages
                    (propertyId,imageURL,isPrimary)
                  VALUES (%s,%s,FALSE)
                """,(id,url))
        mysql.connection.commit()
        cur.close()
        flash("Updated","success")
        return redirect(url_for('properties'))

    return render_template(
      'property_form.html',
      action='Update',
      users=users,
      types=types,
      property=prop,
      property_images=imgs
    )

# -----------------------
# Delete Property
# -----------------------
@app.route('/properties/delete/<int:id>',methods=['POST'])
@login_required
def delete_property(id):
    cur=mysql.connection.cursor()
    cur.execute("DELETE FROM PropertyImages WHERE propertyId=%s",(id,))
    cur.execute("DELETE FROM Property WHERE propertyId=%s",(id,))
    mysql.connection.commit()
    cur.close()
    flash("Deleted","info")
    return redirect(url_for('properties'))

# -----------------------
# Property Detail
# -----------------------
@app.route('/properties/<int:id>')
@login_required
def property_detail(id):
    cur=mysql.connection.cursor()
    cur.execute("""
        SELECT
          P.propertyId,P.address,P.price,P.carpetArea,P.reraRegistered,
          U.username   AS ownerName,
          PT.typeName  AS typeName,
          IL.city,IL.state,IL.pincode,IL.reraZone
        FROM Property P
        JOIN Users U           ON P.ownerId    = U.userId
        JOIN PropertyType PT   ON P.typeId     = PT.typeId
        JOIN IndianLocation IL ON P.locationId = IL.locationId
        WHERE P.propertyId=%s
    """,(id,))
    prop=cur.fetchone()

    cur.execute("SELECT * FROM ResidentialProperty WHERE propertyId=%s",(id,))
    residential=cur.fetchone()
    cur.execute("SELECT * FROM CommercialProperty WHERE propertyId=%s",(id,))
    commercial=cur.fetchone()
    cur.execute("SELECT * FROM Listing WHERE propertyId=%s",(id,))
    listings=cur.fetchall()
    cur.execute("SELECT * FROM PropertyImages WHERE propertyId=%s",(id,))
    images=cur.fetchall()
    cur.execute("SELECT * FROM PropertyDocuments WHERE propertyId=%s",(id,))
    documents=cur.fetchall()
    cur.execute("""
        SELECT A.*
          FROM Amenities A
          JOIN PropertyAmenities PA ON A.amenityId=PA.amenityId
         WHERE PA.propertyId=%s
    """,(id,))
    amenities=cur.fetchall()
    cur.close()
    return render_template(
      'property_detail.html',
      prop=prop,
      residential=residential,
      commercial=commercial,
      listings=listings,
      images=images,
      documents=documents,
      amenities=amenities
    )

if __name__=='__main__':
    app.run(debug=True)