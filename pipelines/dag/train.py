import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

df = pd.read_csv("/inputs/preprocessed.csv")
X = df.drop("target", axis=1)
y = df["target"]

model = RandomForestClassifier()
model.fit(X, y)

joblib.dump(model, "/outputs/model.pkl")
print("Training done.")
