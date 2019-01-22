from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, FoodGroup, FoodItem
engine = create_engine('sqlite:///foodCatalog.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind = engine)
session = DBSession()

name = str(raw_input("\nWhat is the name of this food?\n:"))
difficulty = str(raw_input("""\nWhat is this food's difficulty?\n
                           beginner | intermediate | expert\n:"""))
description = str(raw_input("\nWhat is this food's description?\n:"))
recipe = str(raw_input("\nWhat is this food's recipe?\n:"))
food_group_id = int(raw_input("\nWhat is this food's food group id?\n:"))

item = FoodItem(name = name,
                difficulty = difficulty,
                description = description,
                recipe = recipe,
                food_group_id = food_group_id)
session.add(item)
session.commit()

print '{} added to food items!'.format(name)

food_items = session.query(FoodItem).all()

for food_item in food_items:
    print food_item.name
