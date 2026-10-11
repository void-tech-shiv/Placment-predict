import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier


class ModelTrainer:
    def __init__(self, dataset_path=None):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.dataset_path = Path(dataset_path) if dataset_path else self.base_dir / "dataset" / "placement_predict_50k_Dataset.xlsx"
        self.model_dir = self.base_dir / "saved_models"
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def load_data(self):
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")
        df = pd.read_csv(self.dataset_path) if self.dataset_path.suffix.lower() == ".csv" else pd.read_excel(self.dataset_path, engine="openpyxl")
        drop_cols = [c for c in ["StudentID", "Salary Package", "IsAnomaly"] if c in df.columns]
        if drop_cols: df = df.drop(columns=drop_cols)
        target = next((c for c in ["PlacementStatus", "Placed"] if c in df.columns), None)
        if not target: raise ValueError("Dataset must contain PlacementStatus or Placed target column.")
        df = df.dropna(subset=[target]).copy(); y = df[target]
        if y.dtype == object:
            mapped = y.astype(str).str.strip().str.lower().map({"placed":1,"yes":1,"true":1,"1":1,"not placed":0,"not_placed":0,"no":0,"false":0,"0":0})
            if mapped.isna().any(): raise ValueError("Target contains unsupported placement labels.")
            y = mapped.astype(int)
        else: y = pd.to_numeric(y, errors="raise").astype(int)
        X = df.drop(columns=[target]); feature_columns = list(X.columns); numeric_columns = list(X.select_dtypes(include=["number"]).columns); categorical_columns = [c for c in feature_columns if c not in numeric_columns]
        schema = {}
        for column in feature_columns:
            if column in categorical_columns:
                schema[column] = {"type":"categorical","choices":sorted({str(v) for v in X[column].dropna().astype(str).tolist()})[:250]}
            else:
                series = pd.to_numeric(X[column], errors="coerce"); schema[column] = {"type":"numeric","min":None if not series.notna().any() else float(series.min()),"max":None if not series.notna().any() else float(series.max())}
        numeric_pipeline = Pipeline([("imputer",SimpleImputer(strategy="median")),("scaler",MinMaxScaler())])
        categorical_pipeline = Pipeline([("imputer",SimpleImputer(strategy="most_frequent")),("onehot",OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
        preprocessor = ColumnTransformer([("numeric",numeric_pipeline,numeric_columns),("categorical",categorical_pipeline,categorical_columns)], remainder="drop")
        return X, y, feature_columns, schema, preprocessor, target

    def train(self):
        X, y, feature_columns, schema, preprocessor, target = self.load_data()
        if y.nunique() < 2: raise ValueError("Target must contain at least two classes.")
        X_train, X_test, y_train, y_test = train_test_split(X,y,test_size=.20,random_state=42,stratify=y)
        models = {
            "Logistic Regression":LogisticRegression(max_iter=1500,random_state=42),
            "Decision Tree":DecisionTreeClassifier(random_state=42),
            "Random Forest":RandomForestClassifier(n_estimators=200,random_state=42,n_jobs=-1),
            "KNN":KNeighborsClassifier(),
            "Naive Bayes":GaussianNB(),
            "SVM":SVC(probability=True,random_state=42),
        }
        cv = StratifiedKFold(n_splits=5,shuffle=True,random_state=42); cv_scores = {}
        for name, estimator in models.items():
            pipeline = Pipeline([("preprocessor",preprocessor),("model",estimator)])
            cv_scores[name] = float(np.mean(cross_val_score(pipeline,X_train,y_train,cv=cv,scoring="accuracy",n_jobs=1)))
            print(f"{name}: CV accuracy {cv_scores[name]*100:.2f}%")
        best_name = max(cv_scores,key=cv_scores.get); best_pipeline = Pipeline([("preprocessor",preprocessor),("model",models[best_name])]); best_pipeline.fit(X_train,y_train)
        test_accuracy = float(accuracy_score(y_test,best_pipeline.predict(X_test)))
        accuracy = {name:round(score*100,2) for name,score in cv_scores.items()}
        bundle = {"pipeline":best_pipeline,"feature_columns":feature_columns,"feature_schema":schema,"target_column":target,"best_model":best_name,"test_accuracy":round(test_accuracy*100,2),"dataset_path":str(self.dataset_path.resolve())}
        joblib.dump(bundle,self.model_dir/"model_bundle.pkl")
        with (self.model_dir/"accuracy.json").open("w",encoding="utf-8") as handle: json.dump(accuracy,handle,indent=2)
        with (self.model_dir/"model_metadata.json").open("w",encoding="utf-8") as handle: json.dump({"best_model":best_name,"cv_accuracy":accuracy[best_name],"test_accuracy":round(test_accuracy*100,2),"target_column":target,"dataset_path":str(self.dataset_path.resolve())},handle,indent=2)
        print(f"Best model: {best_name}"); print(f"Final test accuracy: {test_accuracy*100:.2f}%")
        return accuracy


def main():
    parser = argparse.ArgumentParser(description="Train placement prediction models"); parser.add_argument("--dataset",help="Path to active CSV/XLSX dataset"); args = parser.parse_args(); ModelTrainer(args.dataset).train()


if __name__ == "__main__": main()
