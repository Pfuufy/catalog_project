from sqlalchemy import (Column,
                        ForeignKey,
                        Integer,
                        String)
from sqlalchemy import create_engine
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = 'User'

    username = Column(String(100))
    id = Column(Integer, primary_key=True)
    gplus_id = Column(Integer, nullable=False)
    email = Column(String(300), nullable=False)


class FoodGroup(Base):
    __tablename__ = 'FoodGroup'

    name = Column(String(30), nullable=False)
    id = Column(Integer, primary_key=True)

    @property
    def serialize(self):
        return {
            'name': self.name,
            'id': self.id
        }


class FoodItem(Base):
    __tablename__ = 'FoodItem'

    name = Column(String(50), nullable=False)
    id = Column(Integer, primary_key=True)
    difficulty = Column(String(6), nullable=False)
    description = Column(String(150), nullable=False)
    recipe = Column(String(1000), nullable=False)
    creator = relationship(User)
    creator_gplus_id = Column(String(100), ForeignKey('User.gplus_id'))
    food_group = relationship(FoodGroup)
    food_group_id = Column(Integer, ForeignKey('FoodGroup.id'))

    @property
    def serialize(self):
        return {
            'name': self.name,
            'id': self.id,
            'difficulty': self.difficulty,
            'description': self.description,
            'recipe': self.recipe,
            'creator_gplus_id': self.creator_gplus_id
        }


engine = create_engine('sqlite:///foodCatalog.db')
Base.metadata.create_all(engine)
