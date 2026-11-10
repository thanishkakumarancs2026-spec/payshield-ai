# PayShield AI

A beginner-friendly Flask MVP for a hackathon demo: a payment monitoring dashboard, transparent fraud-risk scoring rules, transaction simulator, and PayPal Checkout. The PayPal integration uses PayPal's server-side Orders v2 API. Without credentials, the page clearly labels checkout as simulated.

> **Demo status:** This MVP uses in-memory sample transactions and hand-written rules. It is not a trained AI/ML model, a production fraud detector, or a real payment system unless configured with PayPal Sandbox credentials. The default checkout records a simulated payment and never contacts PayPal.

## Start on Windows

1. Python 3.14.5 is already installed on this computer, and this project has been prepared with a private environment. Install [Visual Studio Code](https://code.visualstudio.com/Download), then open this folder with **File → Open Folder**. If you set the project up again on this computer, use the full Python path below because the `py` launcher does not currently detect the installed Python.
2. In VS Code, open **Terminal → New Terminal** and run:

   ```powershell
   & "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

   If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, answer `Y`, then activate again. Alternatively, open a Command Prompt terminal and run `.venv\Scripts\activate.bat`.

3. Start the app:

   ```powershell
   python app.py
   ```

4. Open **http://127.0.0.1:5000** in your browser. The app runs locally and its sample data resets when restarted.

If VS Code does not pick the environment automatically, press **Ctrl+Shift+P**, choose **Python: Select Interpreter**, and select `.venv\Scripts\python.exe`.

## Enable PayPal Sandbox (optional)

1. Sign in at [PayPal Developer](https://developer.paypal.com/), open **Apps & Credentials → Sandbox**, and create an app. Copy its Sandbox **Client ID** and **Secret**. Use a Sandbox personal/buyer account to approve checkout.
2. In the VS Code terminal, set credentials for the current terminal session (replace the example text; never paste secrets into source files):

   ```powershell
   $env:PAYPAL_ENV="sandbox"
   $env:PAYPAL_CLIENT_ID="your-sandbox-client-id"
   $env:PAYPAL_CLIENT_SECRET="your-sandbox-secret"
   python app.py
   ```

3. Reload the dashboard. Choose a demo product and approve the order using the Sandbox buyer account. The server creates and captures the order; the dashboard adds the captured payment with its risk score.

The default app is Sandbox-only. Do not switch `PAYPAL_ENV` to `live` for a hackathon demo. `.env.example` documents variable names; the app does not automatically load a `.env` file.

## Demo walkthrough (about 2 minutes)

1. Start at the overview: explain the transaction count, volume, and monitoring table.
2. Submit a $420 transaction with **New device** selected. The response shows a medium risk score and names the signal.
3. Submit a $640 transaction with **New device**, **Location mismatch**, and **3 or more failed attempts**. The score caps at 100 and the transaction appears high risk.
4. Scroll to Secure Checkout. Without credentials, click the button marked **SIMULATED** and point out that the transaction appears in the table. With Sandbox configured, approve the PayPal order with the Sandbox buyer instead.
5. Finish by explaining that each score is the sum of visible rules, not a black-box model.

## Project map

- `app.py` — Flask routes, in-memory data, risk rules, and PayPal Orders API calls.
- `templates/dashboard.html` — dashboard structure and checkout UI.
- `static/style.css` — responsive visual styling.
- `static/app.js` — dashboard updates, simulator, and PayPal buttons.
- `requirements.txt` — Python dependency.

The dataset is deliberately in memory for a reliable MVP. Restarting the app restores the sample transactions. For any real deployment, replace the demo scoring/data store and add authentication, CSRF protections, audit logging, and production payment safeguards.
