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
        print "Token's client ID does not match app's."
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

    login_session['username'] = data['name']
    login_session['email'] = data['email']
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
        response = make_response(
            json.dumps('Current user not connected.'),
            401)
        response.headers['Content-Type'] = 'application/json'
        return response

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
    if request.method == 'POST':

        # Gather info to display food group
        if 'inputDifficulty' in request.form:
            food_group_id = request.form.get('inputFoodGroup')
            difficulty = request.form.get('inputDifficulty')
            return (redirect(url_for('show_food_group',
                    food_group_id=food_group_id,
                    difficulty=difficulty)))

        # Add a new food group
        if 'newFoodGroup' in request.form:
            food_group_name = request.form.get('newFoodGroup')
            new_food_group = FoodGroup(name=food_group_name)
            session.add(new_food_group)
            session.commit()
            return redirect(url_for('show_home_page'))

    else:
        if 'username' not in login_session:
            state = get_csrf_token()
            login_session['state'] = state
            food_groups = session.query(FoodGroup).all()
            return render_template('public_home.html',
                                   food_groups=food_groups,
                                   state=state)
        else:
            # Get and store csrf state token for later verification
            food_groups = session.query(FoodGroup).all()
            return render_template('home.html', food_groups=food_groups)

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
        state = get_csrf_token()
        login_session['state'] = state
        return render_template('public_show_food_group.html',
                               food_group=food_group,
                               food_items=food_items,
                               difficulty=difficulty,
                               state=state)
    else:
        return render_template('show_food_group.html',
                               food_group=food_group,
                               food_items=food_items,
                               difficulty=difficulty)

# Individual item pages #


@app.route("/food-groups/<int:food_group_id>/difficulty/" +
           "<difficulty>/item-id/<int:food_item_id>")
def show_food_item(food_group_id, difficulty, food_item_id):
    """Displays individual food item"""

    session = DBSession()
    food_item = session.query(FoodItem).filter_by(id=food_item_id).one()

    if 'username' not in login_session:
        state = get_csrf_token()
        login_session['state'] = state
        return render_template('public_show_food_item.html',
                               food_group_id=food_group_id,
                               difficulty=difficulty,
                               food_item=food_item,
                               state=state)
    else:
        return render_template('show_food_item.html',
                               food_group_id=food_group_id,
                               difficulty=difficulty,
                               food_item=food_item)


@app.route("/food-groups/<int:food_group_id>/difficulty/" +
           "<difficulty>/add-new-item", methods=['GET', 'POST'])
def add_new_food_item(food_group_id, difficulty):
    """Adds new food item to food group at given difficulty"""

    session = DBSession()

    # Gather info to add new food item
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        recipe = request.form['recipe']
        new_item = FoodItem(name=name,
                            difficulty=difficulty,
                            description=description,
                            recipe=recipe,
                            food_group_id=food_group_id)
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

    # Gather item details to edit item if new information is present
    if request.method == 'POST':
        food_item = (session.query(FoodItem)
                     .filter_by(id=food_item_id).one())
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
        food_item = session.query(FoodItem).filter_by(id=food_item_id).one()
        return render_template('edit_food_item.html',
                               food_group_id=food_group_id,
                               difficulty=difficulty,
                               food_item=food_item)


@app.route("/food-groups/<int:food_group_id>/difficulty/" +
           "<difficulty>/<int:food_item_id>/delete", methods=['GET', 'POST'])
def delete_food_item(food_group_id, difficulty, food_item_id):
    """Allows user to delete food item"""

    session = DBSession()

    # Delete food item
    if request.method == 'POST':
        food_item = session.query(FoodItem).filter_by(id=food_item_id).one()
        session.delete(food_item)
        session.commit()
        return redirect(url_for('show_food_group',
                        food_group_id=food_group_id,
                        difficulty=difficulty))

    # Display delete screen for food item
    else:
        food_item = (session.query(FoodItem)
                     .filter_by(id=food_item_id).one())
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
