# Running EchoLearn on another Windows PC

One command installs everything, creates the database and starts the app.

## What the friend's PC needs

- Windows 10 or 11, 64-bit, with internet.
- About 6 GB of free disk space and 8 GB of RAM.
- `winget`, which is built into Windows 10/11. If it's missing, install **App Installer** from the Microsoft Store.

Nothing else needs to be installed by hand. The setup installs **Python 3.11**, **Node.js LTS** and **PostgreSQL 16** if they are missing.

## Step 1 (you): give your friend the project

**Option A: GitHub**, if your friend has access to the repository:

```
git clone https://github.com/MrSiraj27/Echolearn.git
```

**Option B: a zip of the project folder.** Leave these folders out. They are large, and the setup rebuilds them:

- `backend\venv`, `frontend\node_modules`, `frontend\.next`
- `backend\chroma_data*`, `backend\storage`, `backend\.hf_cache`, `backend\voices`
- `backend\.env`, which holds your passwords and keys

## Step 2 (you): send the API keys privately

Send your Groq key (`gsk_...`) and/or Gemini key (`AIza...`) in a private message. Don't put them in the zip or on GitHub. The setup asks for them.

Both PCs then share the same free daily limit: Groq allows 200,000 tokens a day for each key. If you use the app a lot, your friend can create a free key at console.groq.com and aistudio.google.com.

## Step 3 (your friend): the one command

Open the project folder and **double-click `setup.bat`**, or run this in a terminal in that folder:

```
setup.bat
```

It runs these steps:

1. Installs Python 3.11, Node.js, PostgreSQL 16 and the VC++ runtime if they are missing. Windows may ask for permission once.
2. Installs all frontend and backend packages. The first run takes 5–15 minutes.
3. Creates the PostgreSQL database `echolearn` with its own random password, and writes `backend\.env`.
4. Asks for the **Groq** and **Gemini** API keys.
5. Creates the database tables and downloads the reading voice (about 110 MB).
6. Asks for an **email, name and password** for your friend's login. This account is created already verified, with admin rights.
7. Starts the app and opens **http://localhost:3000**.

Your friend then signs in with the email and password from step 6.

**If PostgreSQL was already installed on that PC,** the setup asks once for the password of its `postgres` user, which was chosen when PostgreSQL was installed.

## Every time after that

Double-click **`start.bat`**. It opens two windows, *EchoLearn backend* and *EchoLearn frontend*, and then the browser. Keep both windows open while using the app; close them to stop it.

The first question in a new document can take a minute, because the search model (about 100 MB) downloads once.

## If something goes wrong

- **The setup stopped with a red message:** fix what it says and run `setup.bat` again. Steps that are already done are skipped.
- **Need to change an API key:** run `setup.bat` again and type the new key. Pressing Enter keeps the current one.
- **Need another login:** in the `backend` folder, run:

  ```
  venv\Scripts\python scripts\create_admin.py other@example.com --role superadmin --name "Name" --password "Their-Password"
  ```

- **New users can't sign up from the website:** that needs an email service. Without one, create accounts with the command above.
- **"Port 8000/3000 already in use":** another program is using that port. Close it, or restart the PC.
