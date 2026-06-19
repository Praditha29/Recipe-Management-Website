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


Base.metadata.create_all(bind=engine)

# ==========================================
# FASTAPI
# ==========================================

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# ==========================================
# HOME PAGE
# ==========================================

@app.get("/")
def home(request: Request,
         db: Session = Depends(get_db)):

    recipes = db.scalars(select(Recipe)).all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "recipes": recipes
        }
    )

# ==========================================
# ADD RECIPE
# ==========================================
@app.get("/recipe/add")
def add_recipe_page(request: Request):

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
    db: Session = Depends(get_db)
):
    #For image upload 
    file_location = f"static/uploads/{image.filename}"

    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    new_recipe = Recipe(
        title=title,
        description=description,
        ingredients=ingredients,
        instructions=instructions,
        image_path=file_location
    )

    db.add(new_recipe)

    db.commit()

    return RedirectResponse(
        url="/",
        status_code=303
    )

# ==========================================
# SINGLE RECIPE PAGE
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
    db: Session = Depends(get_db)
):

    recipe = db.get(Recipe, recipe_id)

    if not recipe:
        raise HTTPException(
            status_code=404,
            detail="Recipe not found"
        )

    db.delete(recipe)
    db.commit()

    return RedirectResponse(
        url="/",
        status_code=303
    )