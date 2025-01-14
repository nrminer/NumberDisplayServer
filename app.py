from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"  # For session handling

# In-memory storage for players and logged-in users
players = {
    "alice": {"password": "pass123", "chips": 100},
    "bob": {"password": "xyz789", "chips": 50}
}

logged_in_users = set()
CHIP_TO_EURO_RATE = 0.10

# Transaction log for the last 10 actions
transaction_log = []

def log_transaction(username, action, amount, multiplier):
    """Logs chip transactions"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transaction_log.append({
        "username": username,
        "action": action,
        "amount": amount,
        "multiplier": multiplier,
        "total": amount * multiplier,
        "timestamp": timestamp
    })
    # Keep only the last 10 transactions
    if len(transaction_log) > 10:
        transaction_log.pop(0)

# --------------------------------------------------------------------------
#                             MAIN SCREEN (Fixed for Euros & Status)
# --------------------------------------------------------------------------
@app.route("/")
def index():
    try:
        user_chips_list = [
            {
                "username": username,
                "chips": data["chips"],
                "euros": data["chips"] * CHIP_TO_EURO_RATE,
                "status": "positive" if (data["chips"] * CHIP_TO_EURO_RATE) > 3 else 
                          "negative" if data["chips"] > 0 else "zero"
            }
            for username, data in players.items()
        ]
        return render_template("index.html", user_chips_list=user_chips_list, rate=CHIP_TO_EURO_RATE)
    except Exception as e:
        return jsonify({"error": f"Error rendering main screen: {str(e)}"}), 500

# --------------------------------------------------------------------------
#                             SET CONVERSION RATE
# --------------------------------------------------------------------------
@app.route("/set-rate", methods=["POST"])
def set_rate():
    global CHIP_TO_EURO_RATE
    try:
        new_rate = int(request.json.get("rate")) if request.is_json else int(request.form.get("rate"))
        if new_rate <= 0:
            raise ValueError("Rate must be positive.")
        CHIP_TO_EURO_RATE = new_rate
        return jsonify({"message": f"Conversion rate set to {new_rate}"}), 200
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid rate provided"}), 400

# --------------------------------------------------------------------------
#                             LOGIN FUNCTIONALITY
# --------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            username = request.json.get("username") if request.is_json else request.form.get("username")
            password = request.json.get("password") if request.is_json else request.form.get("password")

            if _validate_credentials(username, password):
                session["username"] = username
                logged_in_users.add(username)
                return jsonify({"message": "Login successful"}) if request.is_json else redirect(url_for("index"))
            return jsonify({"error": "Invalid credentials"}), 401
        except Exception as e:
            return jsonify({"error": f"Login failed: {str(e)}"}), 500
    return render_template("login.html")

# --------------------------------------------------------------------------
#                             LOGOUT FUNCTIONALITY
# --------------------------------------------------------------------------
@app.route("/logout", methods=["POST", "GET"])
def logout():
    username = session.pop("username", None)
    if username:
        logged_in_users.discard(username)
    return jsonify({"message": "Logout successful"}) if request.is_json else redirect(url_for("index"))

# --------------------------------------------------------------------------
#                           MANAGE PAGE (Now Restricted to Logged In Users)
# --------------------------------------------------------------------------
@app.route("/manage")
def manage_page():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("manage.html")

# --------------------------------------------------------------------------
#                           ADD PLAYER (FIXED)
# --------------------------------------------------------------------------
@app.route("/add-player", methods=["POST"])
def add_player():
    try:
        # Ensure the request is JSON, else reject it
        if not request.is_json:
            return jsonify({"error": "Invalid request format. Expected JSON."}), 400

        # Extract data from JSON request body
        data = request.get_json()
        new_username = data.get("new_username")
        new_password = data.get("new_password")
        new_chips = data.get("new_chips", 0)

        # Validation Checks
        if not new_username or not new_password:
            return jsonify({"error": "Username and password are required."}), 400

        if new_username in players:
            return jsonify({"error": f"Player '{new_username}' already exists."}), 409

        # Ensure chips is a positive integer
        try:
            new_chips = int(new_chips)
            if new_chips < 0:
                return jsonify({"error": "Initial chips cannot be negative."}), 400
        except ValueError:
            return jsonify({"error": "Invalid chip amount. Must be an integer."}), 400

        # Add the new player
        players[new_username] = {"password": new_password, "chips": new_chips}
        return jsonify({"message": f"Player '{new_username}' added successfully.", "chips": new_chips}), 201

    except Exception as e:
        return jsonify({"error": f"Error adding player: {str(e)}"}), 500


# --------------------------------------------------------------------------
#                           UPDATE CHIPS
# --------------------------------------------------------------------------
@app.route("/update-chips", methods=["POST"])
def update_chips():
    try:
        username = request.json.get("username") if request.is_json else request.form.get("username")
        action = request.json.get("action") if request.is_json else request.form.get("action")
        amount = int(request.json.get("amount", 0)) if request.is_json else int(request.form.get("amount", 0))
        multiplier = int(request.json.get("multiplier", 1)) if request.is_json else int(request.form.get("multiplier", 1))

        if username not in players:
            return jsonify({"error": "User not found."}), 404

        total_amount = amount * multiplier
        if action == "add":
            players[username]["chips"] += total_amount
        elif action == "deduct":
            if players[username]["chips"] >= total_amount:
                players[username]["chips"] -= total_amount
            else:
                return jsonify({"error": "Insufficient chips."}), 400
        else:
            return jsonify({"error": "Invalid action."}), 400

        log_transaction(username, action, amount, multiplier)
        return jsonify({"message": f"Chips updated for '{username}'."}), 200
    except Exception as e:
        return jsonify({"error": f"Error updating chips: {str(e)}"}), 500

# --------------------------------------------------------------------------
#                           GET LAST 10 TRANSACTIONS
# --------------------------------------------------------------------------
@app.route("/get-transactions", methods=["GET"])
def get_transactions():
    """Fetch the last 10 transactions as JSON"""
    return jsonify(transaction_log[-10:])

# --------------------------------------------------------------------------
#                           GET PLAYERS
# --------------------------------------------------------------------------
@app.route("/get-players", methods=["GET"])
def get_players():
    """Fetch all player usernames."""
    try:
        return jsonify({"players": list(players.keys())})  # Returns a JSON object
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# --------------------------------------------------------------------------
#                           REMOVE PLAYER
# --------------------------------------------------------------------------
@app.route("/remove-player", methods=["POST"])
def remove_player():
    try:
        username = request.json.get("username") if request.is_json else request.form.get("username")

        if username not in players:
            return jsonify({"error": f"User '{username}' not found."}), 404

        del players[username]
        logged_in_users.discard(username)
        return jsonify({"message": f"User '{username}' removed successfully."}), 200
    except Exception as e:
        return jsonify({"error": f"Error removing player: {str(e)}"}), 500

# --------------------------------------------------------------------------
#                           HELPER FUNCTIONS
# --------------------------------------------------------------------------
def _validate_credentials(username, password):
    return username in players and players[username]["password"] == password

# --------------------------------------------------------------------------
#                           SERVER RUNNER
# --------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
