# IntelliAttend — Intelligent Facial Attendance & Analytics

IntelliAttend is a web-based facial recognition attendance system that automates student attendance
 and provides attendance analytics through a simple dashboard.

The system combines computer vision, machine learning, web technologies, and a database to recognize registered students
and record their attendance automatically.



🚀 What IntelliAttend Does

IntelliAttend provides the following workflow:


Register Student
       ↓
Collect Face Images
       ↓
Create Student Dataset
       ↓
Train Recognition Model
       ↓
Recognize Student
       ↓
Mark Attendance Automatically
       ↓
Store Attendance in Database
       ↓
View Attendance & Analytics


### Key Features

* 👤 Student registration and management
* 📸 Facial image dataset collection
* 👁️ Face detection using MediaPipe
* 🖼️ Image processing using OpenCV
* 🤖 Student classification using Random Forest
* ✅ Automatic attendance marking
* 🗄️ SQLite attendance database
* 📊 Attendance analytics
* 📅 Daily, weekly and monthly attendance records
* 📥 CSV attendance export
* 🌐 Flask-based web application
* ⚙️ Background model training with training-status tracking

---

## 🧠 How IntelliAttend Works

IntelliAttend has two major processes:

### 1. Model Training

Student images are collected and stored according to their student ID.

```text
Student Images
      ↓
MediaPipe Face Detection
      ↓
Face Cropping
      ↓
Grayscale Conversion
      ↓
Resize to 32 × 32
      ↓
Normalized Feature Vector
      ↓
Random Forest Classifier
      ↓
Trained Model
```

The trained model is saved as:

```text
model.pkl
```

### 2. Attendance Recognition

When a student needs to mark attendance:

```text
New Face
   ↓
MediaPipe Face Detection
   ↓
Feature Extraction
   ↓
Random Forest Prediction
   ↓
Student ID + Confidence
   ↓
Student Database
   ↓
Attendance Record
```

If the recognition confidence reaches the configured threshold, the student's attendance is recorded with a timestamp.

---

## 🛠️ Technology Stack

| Technology          | Purpose                         |
| ------------------- | ------------------------------- |
| Python 3.10         | Core programming language       |
| Flask               | Web backend and APIs            |
| OpenCV 4.10.0.84    | Image processing                |
| MediaPipe 0.10.21   | Face detection                  |
| NumPy 1.26.4        | Numerical processing            |
| Scikit-learn        | Machine learning                |
| Random Forest       | Student classification          |
| SQLite3             | Student and attendance database |
| Pandas              | Attendance analytics            |
| HTML/CSS/JavaScript | Frontend                        |

---

## 📂 Project Structure

```text
IntelliAttend/
│
├── app.py
├── model.py
├── model.pkl
├── train_status.json
├── attendance.db
│
├── dataset/
│   ├── 1/
│   │   ├── image1.jpg
│   │   ├── image2.jpg
│   │   └── ...
│   │
│   ├── 2/
│   │   ├── image1.jpg
│   │   └── ...
│   │
│   └── ...
│
├── templates/
│   └── HTML pages
│
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
├── .gitignore
└── README.md
```

---

## 🔍 Facial Recognition Pipeline

The current implementation converts a detected face into a numerical feature vector.

```text
Image
 ↓
Face Detection
 ↓
Face Crop
 ↓
Grayscale
 ↓
32 × 32 Resize
 ↓
Flatten
 ↓
Normalize Pixel Values
 ↓
1024-Value Feature Vector
```

This feature vector is given to the Random Forest classifier.

> **Technical note:** IntelliAttend currently uses a normalized grayscale pixel feature vector. It does not use a deep neural-network facial embedding.

---

## 🤖 Machine Learning

IntelliAttend uses a **Random Forest Classifier** to identify registered students.

The model learns:

```text
Facial Feature Vector
        ↓
   Student ID
```

The classifier is configured with:

```python
RandomForestClassifier(
    n_estimators=150,
    n_jobs=-1,
    random_state=42
)
```

The trained model is stored in:

```text
model.pkl
```

---

## 🗄️ Database

IntelliAttend uses **SQLite3** to store application data.

### Students

Stores student information such as:

* Student ID
* Name
* Roll number
* Class
* Section
* Registration number
* Creation timestamp

### Attendance

Stores:

* Attendance ID
* Student ID
* Student name
* Attendance timestamp

---

## 📊 Attendance Analytics

IntelliAttend processes attendance records to provide useful statistics through the dashboard.

The backend uses **Pandas** to process attendance data.

Analytics can include:

* Attendance counts
* Daily attendance
* Recent attendance trends
* Student attendance records

---

## 📥 Attendance Export

Attendance records can be exported as a CSV file for further analysis or administrative use.

---

## ⚙️ Installation


### 1. Create a Python 3.10 virtual environment

```powershell
py -3.10 -m venv venv
```

### 2. Activate the environment

```powershell
.\venv\Scripts\activate
```

### 3. Install dependencies

```powershell
python -m pip install flask pandas numpy==1.26.4 opencv-python==4.10.0.84 mediapipe==0.10.21 scikit-learn
```

### 4. Verify MediaPipe

```powershell
python -c "import mediapipe as mp; print(mp.__version__); print(hasattr(mp,'solutions'))"
```

Expected:

```text
0.10.21
True
```

### 5. Run IntelliAttend

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

## 🔄 Model Training

Start training from:

```text
http://127.0.0.1:5000/train_model
```

Check training status:

```text
http://127.0.0.1:5000/train_status
```

Example:

```json
{
    "running": true,
    "progress": 50,
    "message": "Processed 5/10 students"
}
```

---

## 🔌 Main API Endpoints

| Endpoint             | Purpose                        |
| -------------------- | ------------------------------ |
| `/`                  | IntelliAttend dashboard        |
| `/students`          | Retrieve students              |
| `/add_student`       | Register student               |
| `/upload_face`       | Upload facial images           |
| `/train_model`       | Start model training           |
| `/train_status`      | Check training status          |
| `/recognize_face`    | Recognize a student            |
| `/attendance_record` | Retrieve attendance records    |
| `/attendance_stats`  | Retrieve attendance statistics |
| `/download_csv`      | Export attendance data         |
| `/students/<id>`     | Delete a student               |

---

## 🎯 Core Architecture

```text
                    IntelliAttend
                         │
          ┌──────────────┴──────────────┐
          │                             │
       Frontend                       Flask
          │                             │
          │                  ┌──────────┴──────────┐
          │                  │                     │
          │               model.py             SQLite
          │                  │                     │
          │           ┌──────┴──────┐              │
          │           │             │              │
          │       MediaPipe    Random Forest       │
          │           │             │              │
          │           └──────┬──────┘              │
          │                  │                     │
          └──────────────────┴─────────────────────┘
                         │
                  Attendance Analytics
```

---

## 🌟 Project Objective

**IntelliAttend** aims to simplify attendance management by combining:

```text
Computer Vision
       +
Machine Learning
       +
Web Application
       +
Database
       +
Attendance Analytics
```

into one automated attendance platform.

---

## 🔮 Future Enhancements

Planned possibilities include:

* AI-generated attendance summaries
* More robust facial embeddings
* Liveness / anti-spoofing detection
* Improved analytics dashboard
* PDF attendance reports
* Role-based teacher/admin access
* Cloud deployment
* Improved model training and error handling

---

### 🛡️ Security & OWASP Implementation

IntelliAttend includes a lightweight security layer designed to protect sensitive student biometric data, attendance records, and administrative actions:

* **Authentication & Access Control:** The admin dashboard, database modifications, and machine learning training endpoints are protected by Flask session-based authentication, preventing unauthorized access.
* **Secure Password Hashing:** Passwords are never stored or evaluated in plaintext. They are dynamically hashed and verified using Werkzeug's cryptographic utilities.
* **Input Validation:** Form submissions (such as student names and emails) are strictly validated using Regular Expressions to prevent injection and format-based errors.
* **Secure File Uploads:** Uploaded facial images are validated against a strict list of allowed file extensions (`.jpg`, `.jpeg`, `.png`) and sanitized using `secure_filename()` to prevent malicious file execution and path traversal attacks.
* **Credential Protection:** Sensitive API keys, email credentials, and the Flask secret key are isolated from the source code using a local `.env` configuration file.

---

### 📝 Updates to Add to Your Existing README Sections

**Add to the "Technology Stack" Table:**

| Technology | Purpose |
| --- | --- |
| `python-dotenv` | Environment variable & secret management |
| `Werkzeug Security` | Cryptographic password hashing & file sanitization |

**Add to the "Main API Endpoints" Table:**

| Endpoint | Purpose |
| --- | --- |
| `/login` | Admin authentication portal |
| `/logout` | Terminate secure session |

**Update the "Installation" Step 3:**

```powershell
python -m pip install flask pandas numpy==1.26.4 opencv-python==4.10.0.84 mediapipe==0.10.21 scikit-learn python-dotenv

```

## 👩‍💻 Author

**Adiba Naushad**

B.Tech Computer Science & Engineering

---

## 📄 License

This project is intended for educational and development purposes.



# Branding


**Name:** `IntelliAttend`  
**Full name:** `IntelliAttend — Intelligent Facial Attendance & Analytics`  
**Short description:** `AI-powered facial attendance with intelligent analytics.`


