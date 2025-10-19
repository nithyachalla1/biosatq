import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib, os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "bio_ml.pkl")

def generate_synthetic_dataset(n=2000, seed=0):
    np.random.seed(seed)
    hrs = np.random.normal(75, 8, n)
    spo2 = np.clip(np.random.normal(98, 1, n), 85, 100)
    temp = np.random.normal(36.6, 0.4, n)
    radiation = np.random.rand(n)
    y = ((spo2 < 95) | (hrs > 95) | ((radiation > 0.8) & (temp > 37))).astype(int)
    X = np.vstack([hrs, spo2, temp, radiation]).T
    return X, y

def train_and_save_model():
    X, y = generate_synthetic_dataset()
    clf = RandomForestClassifier(n_estimators=80, random_state=0)
    clf.fit(X, y)
    joblib.dump(clf, MODEL_PATH)
    return clf

def load_model():
    if os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    else:
        return train_and_save_model()

def predict_risk(hr, spo2, temp, radiation):
    model = load_model()
    X = np.array([[hr, spo2, temp, radiation]])
    prob = float(model.predict_proba(X)[0,1])
    label = int(prob > 0.5)
    return {"risk_prob": prob, "risk_label": label}
