from pathlib import Path

import joblib
import pandas as pd


class Predictor:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.model_dir = self.base_dir / "saved_models"
        self.legacy = False
        bundle_path = self.model_dir / "model_bundle.pkl"
        if bundle_path.exists():
            bundle = joblib.load(bundle_path)
            self.pipeline = bundle["pipeline"]
            self.feature_columns = list(bundle.get("feature_columns", []))
            self.feature_schema = bundle.get("feature_schema", {})
            self.best_model = bundle.get("best_model", "Model")
            return

        model_path = self.model_dir / "placement_model.pkl"
        scaler_path = self.model_dir / "scaler.pkl"
        encoders_path = self.model_dir / "label_encoders.pkl"
        columns_path = self.model_dir / "feature_columns.pkl"
        required = [model_path, scaler_path, encoders_path, columns_path]
        if not all(path.exists() for path in required):
            raise FileNotFoundError("No trained model artifacts were found. Train models from the Model Leaderboard page first.")

        self.legacy = True
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
        self.encoders = joblib.load(encoders_path)
        self.feature_columns = list(joblib.load(columns_path))
        self.feature_schema = {}
        for column in self.feature_columns:
            if column in self.encoders:
                self.feature_schema[column] = {"type": "categorical", "choices": [str(v) for v in self.encoders[column].classes_]}
            else:
                self.feature_schema[column] = {"type": "numeric"}
        self.best_model = "Legacy trained model"

    def get_feature_columns(self):
        return self.feature_columns

    def get_feature_schema(self):
        return self.feature_schema

    def preprocess_input(self, form_data):
        processed = {}
        for column in self.feature_columns:
            raw = form_data.get(column)
            if raw is None or str(raw).strip() == "":
                raise ValueError(f"'{column}' is required.")
            schema = self.feature_schema.get(column, {})
            if schema.get("type") == "numeric":
                try:
                    processed[column] = float(raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"'{column}' must be numeric.") from exc
            elif self.legacy and column in self.encoders:
                encoder = self.encoders[column]
                try:
                    processed[column] = encoder.transform([str(raw)])[0]
                except ValueError as exc:
                    raise ValueError(f"Invalid value for '{column}'.") from exc
            else:
                processed[column] = str(raw)
        return pd.DataFrame([processed], columns=self.feature_columns)

    def predict(self, form_data):
        input_df = self.preprocess_input(form_data)
        confidence = None
        if self.legacy:
            transformed = self.scaler.transform(input_df)
            prediction = int(self.model.predict(transformed)[0])
            if hasattr(self.model, "predict_proba"):
                confidence = round(float(max(self.model.predict_proba(transformed)[0])) * 100, 2)
        else:
            prediction = int(self.pipeline.predict(input_df)[0])
            if hasattr(self.pipeline, "predict_proba"):
                confidence = round(float(max(self.pipeline.predict_proba(input_df)[0])) * 100, 2)
        return {"prediction": "Placed" if prediction == 1 else "Not Placed", "confidence": confidence, "model": self.best_model}


def main():
    predictor = Predictor()
    print("Loaded model:", predictor.best_model)
    print("Features:", predictor.get_feature_columns())


if __name__ == "__main__":
    main()
