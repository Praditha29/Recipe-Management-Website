from fastapi import FastAPI, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
#to upload image files
from fastapi import UploadFile, File
from fastapi.staticfiles import StaticFiles
import shutil

from sqlalchemy import create_engine, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm import sessionmaker, Session

#for JWT Login
import jwt
from datetime import datetime, timedelta
import bcrypt
from fastapi import Cookie

# ==========================================
# DATABASE SETUP
# ==========================================

engine = create_engine(
    "sqlite:///recipes.db",
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


class Base(DeclarativeBase):
    pass


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String(50))

    description: Mapped[str] = mapped_column(String(200))

    ingredients: Mapped[str] = mapped_column(Text)

    instructions: Mapped[str] = mapped_column(Text)

    image_path: Mapped[str] = mapped_column(String(255))

    owner_id: Mapped[int] = mapped_column()
 
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(String(30), unique=True)

    email: Mapped[str] = mapped_column(String(50), unique=True)

    password: Mapped[str] = mapped_column(String(255))


Base.metadata.create_all(bind=engine)

# ==========================================
# FASTAPI
# ==========================================

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

SECRET_KEY = "mysecretkey"

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60

def get_password_hash(password):

    return bcrypt.hashpw(
        password.encode("utf-8")[:72],
        bcrypt.gensalt()
    ).decode("utf-8")
def verify_password(
        plain_password,
        hashed_password
):

    return bcrypt.checkpw(
        plain_password.encode("utf-8")[:72],
        hashed_password.encode("utf-8")
    )
from datetime import datetime, timedelta, timezone

def create_access_token(data: dict):

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update(
        {
            "exp": expire
        }
    )

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()

# ==========================================
# SIGNUP PAGE
# ==========================================
@app.get("/signup")
def signup_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="signup.html"
    )

@app.post("/signup")
def signup(
        username: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):

    hashed_password = get_password_hash(password)

    user = User(
        username=username,
        email=email,
        password=hashed_password
    )

    db.add(user)
    db.commit()

    return RedirectResponse(
        "/login",
        status_code=303
    )

# ==========================================
# LOGIN PAGE
# ==========================================
@app.get("/login")
def login_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )

@app.post("/login")
def login(
        username: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):

    stmt = select(User).where(
        User.username == username
    )

    user = db.scalars(stmt).first()

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid username"
        )

    if not verify_password(
        password,
        user.password):

        raise HTTPException(
            status_code=401,
            detail="Invalid password"
        )

    access_token = create_access_token(
        {
            "sub": user.username
        }
    )

    response = RedirectResponse(
        "/home",
        status_code=303
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True
    )

    return response 

@app.get("/logout")
def logout():

    response = RedirectResponse(
        "/login",
        status_code=303
    )

    response.delete_cookie(
        "access_token"
    )

    return response

def get_current_user(
        request: Request,
        db: Session = Depends(get_db)
):

    token = request.cookies.get(
        "access_token"
    )

    if not token:
        return None

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get(
            "sub"
        )

        if username is None:
            return None

    except jwt.InvalidTokenError:

        return None

    user = db.scalars(
        select(User).where(
            User.username == username
        )
    ).first()

    return user
# ==========================================
# HOME PAGE
# ==========================================
@app.get("/")
def root():
    return RedirectResponse(
        url="/login",
        status_code=303
    )

@app.get("/home")
def home(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # User not logged in
    if current_user is None:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    recipes = db.scalars(select(Recipe)).all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "recipes": recipes,
            "current_user": current_user
        }
    )
# ==========================================
# ADD RECIPE
# ==========================================
@app.get("/recipe/add")
def add_recipe_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    if current_user is None:
        return RedirectResponse(
            "/login",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="add_recipe.html"
    )

@app.post("/recipe/add")
def add_recipe(
    title: str = Form(...),
    description: str = Form(...),
    ingredients: str = Form(...),
    instructions: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    
    if current_user is None:
        return RedirectResponse(
            "/login",
            status_code=303
        )
    #For image upload 
    file_location = f"static/uploads/{image.filename}"

    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    new_recipe = Recipe(
    title=title,
    description=description,
    ingredients=ingredients,
    instructions=instructions,
    image_path=file_location,
    owner_id=current_user.id
)

    db.add(new_recipe)

    db.commit()

    return RedirectResponse(
        url="/home",
        status_code=303
    )

# ==========================================
# VIEW SINGLE RECIPE PAGE
# ==========================================

@app.get("/recipe/{recipe_id}")
def read_recipe(recipe_id: int,
                request: Request,
                db: Session = Depends(get_db)):

    recipe = db.get(Recipe, recipe_id)

    if not recipe:
        raise HTTPException(
            status_code=404,
            detail="Recipe not found"
        )

    return templates.TemplateResponse(
        request=request,
        name="recipe.html",
        context={
            "recipe": recipe
        }
    )

# ==========================================
# UPDATE RECIPE
# ==========================================

@app.get("/recipe/update/{recipe_id}")
def update_recipe_page(
    recipe_id: int,
    request: Request,
    db: Session = Depends(get_db)
    
):
    current_user: User = Depends(get_current_user)
    if current_user is None:
        return RedirectResponse(
            "/login",
            status_code=303
        )
    recipe = db.get(Recipe, recipe_id)

    if not recipe:
        raise HTTPException(
            status_code=404,
            detail="Recipe not found"
        )

    return templates.TemplateResponse(
        request=request,
        name="update_recipe.html",
        context={
            "recipe": recipe
        }
    )

@app.post("/recipe/update/{recipe_id}")
def update_recipe(
    recipe_id: int,
    title: str = Form(...),
    description: str = Form(...),
    ingredients: str = Form(...),
    instructions: str = Form(...),
    db: Session = Depends(get_db)
):
    current_user: User = Depends(get_current_user)
    if current_user is None:
        return RedirectResponse(
            "/login",
            status_code=303
        )
    recipe = db.get(Recipe, recipe_id)

    if not recipe:
        raise HTTPException(
            status_code=404,
            detail="Recipe not found"
        )

    recipe.title = title
    recipe.description = description
    recipe.ingredients = ingredients
    recipe.instructions = instructions

    db.commit()

    return RedirectResponse(
        url=f"/recipe/{recipe_id}",
        status_code=303
    )

# ==========================================
# DELETE RECIPE
# ==========================================
@app.get("/recipe/delete/{recipe_id}")
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user is None:
        return RedirectResponse(
            "/login",
            status_code=303
        )

    recipe = db.get(Recipe, recipe_id)

    if not recipe:
        raise HTTPException(
            status_code=404,
            detail="Recipe not found"
        )

    db.delete(recipe)
    db.commit()

    return RedirectResponse(
        url="/home",
        status_code=303
    )