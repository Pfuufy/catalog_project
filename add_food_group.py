from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, FoodGroup, FoodItem
engine = create_engine('sqlite:///foodCatalog.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind = engine)
session = DBSession()

new_name = str(raw_input("\nWhat is the name of this food group?\n:"))

item = FoodGroup(name = new_name)
session.add(item)
session.commit()

print '{} added to food groups!'.format(new_name)
