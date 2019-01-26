#!/usr/bin/env python2

from flask import (Flask,
                   render_template,
                   url_for,
                   request,
                   redirect,
                   flash,
                   jsonify,
                   session as login_session,
                   make_response)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from oauth2client.client import (flow_from_clientsecrets,
                                 OAuth2WebServerFlow,
                                 FlowExchangeError)
from database_setup import (Base,
                            User,
                            FoodGroup,
                            FoodItem)
import httplib2
import requests
import json
import random
import string

app = Flask(__name__, static_url_path='/static')

engine = create_engine('sqlite:///foodCatalog.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

with open('client_secrets.json') as file:
    data = json.load(file)

CLIENT_ID = data['web']['client_id']
CLIENT_SECRET = data['web']['client_secret']

# HELPER FUNCTIONS


def get_csrf_token():
    """Returns CSRF (cross site reference forgery) token"""
    state = (''.join(random.choice(string.ascii_uppercase
             + string.ascii_lowercase + string.digits) for _ in range(32)))
    return state

# LOGIN/LOGOUT ROUTES


@app.route('/gconnect', methods=['POST'])
def gconnect():
    """Login function for Google login"""

    session = DBSession()

    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])

    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check if user already logged in
    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['credentials'] = credentials
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    # A real name is not guaranteed
    try:
        login_session['username'] = data['name']
    except KeyError:
        login_session['username'] = 'username'
    login_session['email'] = data['email']

    # Check if user already exists in database. If not create new user
    if (session.query(User).filter_by(email=login_session['email'])
        .first() == None):
        new_user = User(username=login_session['username'],
                        email=login_session['email'])
        session.add(new_user)
        session.commit()

    flash('You are now logged in as %s' % login_session['username'])

    # This function must return something, doesn't matter what.
    # Returning 'success' is arbitrary.
    return 'success'


@app.route('/gdisconnect')
def gdisconnect():
    """Logout function for Google login"""

    # Can't log out if you're not logged in ;)
    access_token = login_session.get('access_token')
    if access_token is None:
        flash('Current user not logged in')
        return redirect(url_for('/'))

    # Revoke access token for user
    requests.post('https://accounts.google.com/o/oauth2/revoke',
                  params={'token': access_token},
                  headers={'content-type': 'application/json'})
    del login_session['access_token']
    del login_session['gplus_id']
    del login_session['username']
    del login_session['email']
    flash('User successfully logged out')
    return redirect(url_for('show_home_page'))

# NORMAL USE ROUTES

# Root pages


@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def show_home_page():
    """Displays the home page"""

    session = DBSession()
    food_groups = session.query(FoodGroup).all()
    no_food_groups = False

    if len(food_groups) == 0:
        no_food_groups = True

    if request.method == 'POST':


        # There are two different if statements here because there are
        # two different forms on this page. These distinguish between
        # which form to use and gather info from.

        # Gather info to display food group
        if 'inputDifficulty' in request.form:

            food_group_id = request.form.get('inputFoodGroup')

            if food_group_id == "-1":
                response = """<script>
                                window.location.replace('/');
                                alert('There are no food groups, please add one');
                              </script>"""
                return response

            difficulty = request.form.get('inputDifficulty')
            return (redirect(url_for('show_food_group',
                    food_group_id=food_group_id,
                    difficulty=difficulty)))

        # Add a new food group
        if ('newFoodGroup' in request.form) and (login_session['username']
                                                 is not None):
            food_group_name = request.form.get('newFoodGroup')
            new_food_group = FoodGroup(name=food_group_name)
            session.add(new_food_group)
            session.commit()
            flash('New food group created!')
            return redirect(url_for('show_home_page'))

    else:
        if 'username' not in login_session:
            username = None

            # Get and store csrf state token for later verification
            state = get_csrf_token()
            login_session['state'] = state
        else:
            username = login_session['username']

            # State is defined as None just so the state token isnt
            # needlessly floating around, potentially causing
            # security issues.
            state = None
        food_groups = session.query(FoodGroup).all()
        return render_template('home.html',
                               no_food_groups=no_food_groups,
                               food_groups=food_groups,
                               state=state,
                               username=username)

# Food Group Page #


@app.route("/food-groups/<int:food_group_id>/difficulty/<difficulty>")
def show_food_group(food_group_id, difficulty):
    """Displays food group at given difficulty"""

    # Gather info to display food items
    session = DBSession()
    food_group = session.query(FoodGroup).filter_by(id=food_group_id).one()
    food_items = (session.query(FoodItem)
                  .filter_by(food_group_id=food_group_id,
                             difficulty=difficulty).all())

    if 'username' not in login_session:
        username = None
        state = get_csrf_token()
        login_session['state'] = state
    else:
        username = login_session['username']
        state = None

    return render_template('show_food_group.html',
                           food_group=food_group,
                           food_items=food_items,
                           difficulty=difficulty,
                           state=state,
                           username=username)

# Individual item pages #


@app.route("/food-groups/<int:food_group_id>/difficulty/" +
           "<difficulty>/item-id/<int:food_item_id>")
def show_food_item(food_group_id, difficulty, food_item_id):
    """Displays individual food item"""

    session = DBSession()
    food_item = session.query(FoodItem).filter_by(id=food_item_id).one()

    # Using login_session['email'] and login_session['username']
    # because this page already reiles on the email for linking
    # the new item to its creator and the 'main.html' file needs
    # the username information to determine whether to display
    # the sigin or signout button.
    if 'email' not in login_session:
        current_user_email = None
        username = None
        state = get_csrf_token()
        login_session['state'] = state
    else:
        current_user_email = login_session['email']
        username = login_session['username']
        state = None

    return render_template('show_food_item.html',
                           food_group_id=food_group_id,
                           difficulty=difficulty,
                           food_item=food_item,
                           state=state,
                           current_user_email=current_user_email,
                           creator_email=food_item.creator_email,
                           username=username)


@app.route("/food-groups/<int:food_group_id>/difficulty/" +
           "<difficulty>/add-new-item", methods=['GET', 'POST'])
def add_new_food_item(food_group_id, difficulty):
    """Adds new food item to food group at given difficulty"""

    session = DBSession()

    if request.method == 'POST' and login_session['username'] is not None:
        name = request.form['name']
        description = request.form['description']
        recipe = request.form['recipe']
        new_item = FoodItem(name=name,
                            difficulty=difficulty,
                            description=description,
                            recipe=recipe,
                            food_group_id=food_group_id,
                            creator_email=login_session['email'])
        session.add(new_item)
        session.commit()
        flash('Item added')
        return redirect(url_for('show_food_group',
                        food_group_id=food_group_id,
                        difficulty=difficulty))

    # Display input form for new item
    else:
        food_group = (session.query(FoodGroup)
                      .filter_by(id=food_group_id).one())
        return render_template('add_new_food_item.html',
                               food_group=food_group,
                               difficulty=difficulty)


@app.route("/food-groups/<int:food_group_id>/difficulty/" +
           "<difficulty>/<int:food_item_id>/edit", methods=['GET', 'POST'])
def edit_food_item(food_group_id, difficulty, food_item_id):
    """Allows user to edit food item"""

    session = DBSession()
    food_item = session.query(FoodItem).filter_by(id=food_item_id).one()
    creator = session.query(User).filter_by(email=food_item.creator_email).one()

    # Check if the current user is the one who created the item
    if (request.method == 'POST') and (login_session['email'] ==
                                       creator.email):

        # Gather item details to edit item if new information is present
        if request.form['name']:
            food_item.name = request.form['name']
        if request.form['description']:
            food_item.description = request.form['description']
        if request.form['recipe']:
            food_item.recipe = request.form['recipe']
        session.add(food_item)
        session.commit()
        flash('Item Edited')
        return redirect(url_for('show_food_group',
                        food_group_id=food_group_id,
                        difficulty=difficulty))

    # Display the edit food item page
    else:
        return render_template('edit_food_item.html',
                               food_group_id=food_group_id,
                               difficulty=difficulty,
                               food_item=food_item)


# Long Routes have to be formatted with concatenation because using multi-line
# string techniques result in really weird url paths.
@app.route("/food-groups/<int:food_group_id>/difficulty/" +
           "<difficulty>/<int:food_item_id>/delete", methods=['GET', 'POST'])
def delete_food_item(food_group_id, difficulty, food_item_id):
    """Allows user to delete food item"""

    session = DBSession()
    food_item = session.query(FoodItem).filter_by(id=food_item_id).one()
    creator = session.query(User).filter_by(email=food_item.creator_email).one()

    # Check if the current user is the one who created the item
    if (request.method == 'POST') and (login_session['email'] ==
                                       creator.email):
        session.delete(food_item)
        session.commit()
        return redirect(url_for('show_food_group',
                        food_group_id=food_group_id,
                        difficulty=difficulty))

    # Display delete screen for food item
    else:
        return render_template('delete_food_item.html',
                               food_group_id=food_group_id,
                               difficulty=difficulty,
                               food_item=food_item)

# JSON ROUTES


@app.route("/food-groups/json")
def get_food_groups_json():
    """JSON for all food groups"""

    session = DBSession()
    food_groups = session.query(FoodGroup).all()
    return jsonify({'foodGroups':
                   [food_group.serialize for food_group in food_groups]})


@app.route("/food-groups/<int:food_group_id>/difficulty/<difficulty>/json")
def get_food_group_difficulty_json(food_group_id, difficulty):
    """JSON for all food items of a given food group at a given difficulty"""

    session = DBSession()
    food_items = (session.query(FoodItem)
                  .filter_by(food_group_id=food_group_id,
                             difficulty=difficulty).all())
    food_group = session.query(FoodGroup).filter_by(id=food_group_id).one()
    return jsonify({'foodGroupID': food_group_id,
                    'foodGroupName': food_group.name,
                    'difficulty': difficulty,
                    'items':
                    [food_item.serialize for food_item in food_items]})


@app.route("/food-groups/<int:food_group_id>/difficulty/" +
           "<difficulty>/item-id/<int:food_item_id>/json")
def get_food_item_json(food_group_id, difficulty, food_item_id):
    """JSON for particular food item"""

    session = DBSession()
    food_item = session.query(FoodItem).filter_by(id=food_item_id).one()
    return jsonify({'foodItem': [food_item.serialize]})


if __name__ == '__main__':
    app.secret_key = 'super secret key'
    app.debug = True
    app.run(host='0.0.0.0', port=2000)
