# use flask to spin up a web server to serve the schedule creator page
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # set flask defaults
    app.config['DEBUG'] = True
    
    app.run(debug=True)