import os
import joblib
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    ConfusionMatrixDisplay,
    classification_report
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler


class ModelEvaluation:

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.dataset_path = os.path.join(
            self.base_dir,
            "dataset",
            "placement_predict_50k_Dataset.xlsx"
        )

        self.model_path = os.path.join(
            self.base_dir,
            "saved_models",
            "placement_model.pkl"
        )

        self.report_dir = os.path.join(
            self.base_dir,
            "reports"
        )

        os.makedirs(self.report_dir, exist_ok=True)

    def prepare_data(self):
        df = pd.read_excel(self.dataset_path, engine="openpyxl")

        if "StudentID" in df.columns:
            df.drop(columns=["StudentID"], inplace=True)

        num_cols = df.select_dtypes(include=["number"]).columns
        cat_cols = df.select_dtypes(include=["object", "string"]).columns

        for col in num_cols:
            df[col] = df[col].fillna(df[col].median())

        for col in cat_cols:
            df[col] = df[col].fillna(df[col].mode()[0])
            df[col] = LabelEncoder().fit_transform(df[col])

        X = df.drop(columns=["PlacementStatus"])
        y = df["PlacementStatus"]

        X = MinMaxScaler().fit_transform(X)

        return train_test_split(
            X,
            y,
            test_size=0.20,
            random_state=42,
            stratify=y
        )

    def evaluate(self):
        X_train, X_test, y_train, y_test = self.prepare_data()

        model = joblib.load(self.model_path)

        y_pred = model.predict(X_test)

        print("\n========== MODEL EVALUATION ==========")
        print("Accuracy :", round(accuracy_score(y_test, y_pred) * 100, 2), "%")
        print("Precision:", round(precision_score(y_test, y_pred), 4))
        print("Recall   :", round(recall_score(y_test, y_pred), 4))
        print("F1 Score :", round(f1_score(y_test, y_pred), 4))

        print("\nClassification Report")
        print(classification_report(y_test, y_pred))

        cm = confusion_matrix(y_test, y_pred)

        disp = ConfusionMatrixDisplay(confusion_matrix=cm)
        disp.plot()

        plt.title("Confusion Matrix")
        plt.savefig(os.path.join(self.report_dir, "confusion_matrix.png"))
        plt.close()

        print("\nConfusion matrix saved in reports/confusion_matrix.png")


def main():
    evaluator = ModelEvaluation()
    evaluator.evaluate()


if __name__ == "__main__":
    main()
